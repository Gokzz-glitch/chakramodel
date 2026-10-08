import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path for imports
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
import cv2
import yaml
import numpy as np

import torch
from torch.utils.data import DataLoader

from src.data_loaders.dataset import PolypDataset
from src.models import build_model
from src.utils.metrics import SegmentationMetrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Polyp Segmentation Evaluation")
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument(
        "--dataset", type=str, default="all",
        help="Which test dataset(s) to evaluate on"
    )
    parser.add_argument(
        "--save_predictions", action="store_true",
        help="Save predicted masks to results/sample_predictions/"
    )
    return parser.parse_args()

def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def measure_fps(model: torch.nn.Module, device: torch.device,
                input_size: tuple = (1, 3, 352, 352),
                warmup_runs: int = 10, timing_runs: int = 100) -> float:
    model.eval()
    dummy_input = torch.randn(*input_size).to(device)
    logger.info(f"Warming up GPU ({warmup_runs} runs)...")
    with torch.no_grad():
        for _ in range(warmup_runs):
            _ = model(dummy_input)
    if device.type == "cuda":
        torch.cuda.synchronize()
    logger.info(f"Timing inference ({timing_runs} runs)...")
    start = time.perf_counter()
    with torch.no_grad():
        for _ in range(timing_runs):
            _ = model(dummy_input)
    if device.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    fps = timing_runs / elapsed
    logger.info(f"Measured FPS: {fps:.2f} (input size: {input_size})")
    return fps

def save_results(results: dict, run_id: str) -> None:
    output_dir = Path("results/metrics")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{run_id}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to: {output_file}")

def main():
    args = parse_args()
    config = load_config(args.config)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    model = build_model(config["model"])
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint.get('model_state_dict', checkpoint))
    model.to(device)
    model.eval()
    
    if config.get("evaluation", {}).get("compute_fps", False):
        measure_fps(model, device)
        
    data_root = config["data"]["data_root"]
    test_manifests = config["data"]["test_manifests"]
    
    if args.dataset != "all":
        test_manifests = {args.dataset: test_manifests[args.dataset]}
        
    all_results = {}
    
    pred_dir = Path("results/sample_predictions")
    if args.save_predictions:
        pred_dir.mkdir(parents=True, exist_ok=True)
        
    metrics_calc = SegmentationMetrics()
    
    for dataset_name, manifest_path in test_manifests.items():
        logger.info(f"Evaluating on {dataset_name}...")
        dataset = PolypDataset(data_root=data_root, manifest_path=manifest_path, is_train=False)
        loader = DataLoader(dataset, batch_size=1, shuffle=False)
        metrics_calc.reset()
        
        with torch.no_grad():
            for i, (images, masks) in enumerate(loader):
                images, masks = images.to(device), masks.to(device)
                outputs = model(images)
                logits = outputs['pred']
                preds = torch.sigmoid(logits).cpu().numpy()[0, 0]
                gt = masks.cpu().numpy()[0, 0]
                
                metrics_calc.update(preds, gt)
                
                if args.save_predictions:
                    pred_mask = (preds >= 0.5).astype(np.uint8) * 255
                    cv2.imwrite(str(pred_dir / f"{dataset_name}_{i:04d}.png"), pred_mask)
                    
        results = metrics_calc.compute()
        all_results[dataset_name] = results
        logger.info(f"{dataset_name} results: {metrics_calc}")
        
    run_id = Path(args.checkpoint).stem
    save_results(all_results, run_id)

if __name__ == "__main__":
    main()
