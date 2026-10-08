"""
eval.py — Evaluation Entry Point

STRICT RULES:
  - All metrics computed from REAL forward passes on REAL data
  - NO hardcoded numbers — all values come from actual computation
  - Results saved to results/metrics/<run_id>.json
  - FPS measured with proper warm-up and multiple timing runs

Usage:
    python src/eval.py --config configs/baseline_unet.yaml --checkpoint checkpoints/best.pt
    python src/eval.py --config configs/baseline_unet.yaml --checkpoint checkpoints/best.pt --dataset etis
"""

import argparse
import json
import time
import logging
import sys
from pathlib import Path

import torch
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Standard test datasets (as used by PraNet, SANet, Polyp-PVT)
STANDARD_TEST_DATASETS = [
    "kvasir_test",
    "clinicdb_test",
    "colondb",
    "etis",
    "cvc300",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Polyp Segmentation Evaluation")
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument(
        "--dataset", type=str, default="all",
        choices=["all"] + STANDARD_TEST_DATASETS,
        help="Which test dataset(s) to evaluate on"
    )
    parser.add_argument(
        "--save_predictions", action="store_true",
        help="Save predicted masks to results/sample_predictions/"
    )
    return parser.parse_args()


def validate_checkpoint(checkpoint_path: str) -> None:
    """STRICT: Checkpoint must exist. Never fabricate results."""
    path = Path(checkpoint_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {path}\n"
            f"Train a model first with: python src/train.py --config <config>"
        )
    logger.info(f"✓ Checkpoint found: {path}")


def compute_dice(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    """
    Compute Dice coefficient from actual binary predictions and ground truth.
    
    STRICT: This must be called on REAL predictions from a REAL model.
    Never call this with fabricated values.
    """
    assert pred.shape == gt.shape, f"Shape mismatch: pred={pred.shape}, gt={gt.shape}"
    pred = pred.astype(bool)
    gt = gt.astype(bool)
    
    intersection = (pred & gt).sum()
    dice = (2.0 * intersection + eps) / (pred.sum() + gt.sum() + eps)
    return float(dice)


def compute_iou(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    """
    Compute Intersection over Union from actual binary predictions and ground truth.
    """
    pred = pred.astype(bool)
    gt = gt.astype(bool)
    
    intersection = (pred & gt).sum()
    union = (pred | gt).sum()
    return float((intersection + eps) / (union + eps))


def measure_fps(model: torch.nn.Module, device: torch.device,
                input_size: tuple = (1, 3, 352, 352),
                warmup_runs: int = 10, timing_runs: int = 100) -> float:
    """
    Measure inference speed in frames per second.
    
    Uses proper GPU warm-up to get stable measurements.
    Timing runs with CUDA synchronization for accurate GPU timing.
    
    Returns: FPS (float)
    """
    model.eval()
    dummy_input = torch.randn(*input_size).to(device)
    
    # Warm up GPU
    logger.info(f"Warming up GPU ({warmup_runs} runs)...")
    with torch.no_grad():
        for _ in range(warmup_runs):
            _ = model(dummy_input)
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # Timed runs
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
    """Save evaluation results to JSON file in results/metrics/."""
    output_dir = Path("results/metrics")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{run_id}.json"
    
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to: {output_file}")


def main():
    args = parse_args()
    validate_checkpoint(args.checkpoint)
    
    # TODO (Phase 1): Load config, model, data loaders, run evaluation
    raise NotImplementedError(
        "Phase 1 not yet implemented.\n"
        "This is a Phase 0 stub. Implement src/models/ and src/data_loaders/ first."
    )


if __name__ == "__main__":
    main()
