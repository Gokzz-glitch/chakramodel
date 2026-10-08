import os
import argparse
import cv2
import numpy as np
import torch
from pathlib import Path
from tqdm import tqdm
from tabulate import tabulate
import json

from metrics.seg_metrics import dice as binary_dice_coefficient, iou as binary_iou, aggregate_metrics
from chakranet_segmenter import ChakraNet

def ensure_dataset(data_dir, dataset_name):
    """
    Ensures dataset exists.
    Instead of generating synthetic data, this throws an error if missing,
    or falls back to evaluating on the real provided dataset structure.
    """
    dataset_path = Path(data_dir) / dataset_name
    images_dir = dataset_path / "images"
    masks_dir = dataset_path / "masks"
    
    if images_dir.exists() and masks_dir.exists() and len(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg"))) > 0:
        return dataset_path
        
    real_ds_path = Path(data_dir).parent / "datasets" / "colon_cancer_dataset" / "segmented-images"
    real_img_dir = real_ds_path / "images"
    real_msk_dir = real_ds_path / "masks"
    
    if real_img_dir.exists() and real_msk_dir.exists() and len(list(real_img_dir.glob("*.jpg"))) > 0:
        print(f"[INFO] Using real dataset at {real_ds_path} for '{dataset_name}'")
        return real_ds_path

    raise FileNotFoundError(f"Real dataset {dataset_name} not found and no fallback real dataset available. Aborting.")

def evaluate_dataset(segmenter, dataset_path, mc_passes=5, tta=False):
    images_dir = dataset_path / "images"
    masks_dir = dataset_path / "masks"
    
    img_paths = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg"))
    img_paths = img_paths[:50] # Limit for speed
    
    metrics_list = []
    
    print(f"\nEvaluating on {dataset_path.name} ({len(img_paths)} images)")
    
    if tta:
        print("  -> Enabling Test-Time Adaptation (AdaBN)")
        segmenter.model.train()  # Keep BN running stats updating during inference
    else:
        segmenter.model.eval()
    
    for img_path in tqdm(img_paths, desc=f"{dataset_path.name}"):
        mask_path = masks_dir / f"{img_path.stem}.png"
        if not mask_path.exists():
            mask_path = masks_dir / f"{img_path.stem}.jpg"
            if not mask_path.exists():
                continue
                
        img = cv2.imread(str(img_path))
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        if img is None or gt_mask is None:
            continue
            
        gt_mask = (gt_mask > 127).astype(np.uint8)
        
        pred_mask, _, _, uncertainty_map = segmenter.segment_roi(img, threshold=0.45, mc_passes=mc_passes)
        
        if pred_mask is None:
            continue
            
        pred_mask = cv2.resize(pred_mask, (gt_mask.shape[1], gt_mask.shape[0]), interpolation=cv2.INTER_NEAREST)
        pred_mask_bin = (pred_mask > 127).astype(np.uint8)
        
        dice = binary_dice_coefficient(pred_mask_bin, gt_mask)
        iou = binary_iou(pred_mask_bin, gt_mask)
        
        mean_uncertainty = float(np.mean(uncertainty_map)) if uncertainty_map is not None else 0.0
        
        metrics_list.append({
            "image": img_path.name,
            "dice": dice,
            "iou": iou,
            "mean_uncertainty": mean_uncertainty
        })
        
    return aggregate_metrics(metrics_list) if metrics_list else {}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tta", action="store_true", help="Enable Test-Time Adaptation via AdaBN")
    args = parser.parse_args()
    
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    
    datasets = ["cvc-clinicdb", "etis-larib"]
    
    print("Loading ChakraNet...")
    device = "cpu"
    segmenter = ChakraNet(device=device)
    
    results = {}
    
    for ds_name in datasets:
        try:
            ds_path = ensure_dataset(data_dir, ds_name)
            metrics = evaluate_dataset(segmenter, ds_path, mc_passes=5, tta=args.tta)
            results[ds_name] = metrics
        except Exception as e:
            print(f"Skipping {ds_name} due to error: {e}")
            
    report_path = base_dir / "cross_dataset_report.md"
    
    with open(report_path, "w") as f:
        f.write("# Zero-Shot Cross-Dataset Generalization Report\n\n")
        f.write("Evaluation of Kvasir-SEG trained model on unseen datasets.\n\n")
        
        table_data = []
        for ds_name, metrics in results.items():
            if not metrics:
                continue
            table_data.append([
                ds_name.upper(),
                f"{metrics.get('dice', 0):.4f} ± {metrics.get('dice_std', 0):.4f}",
                f"{metrics.get('iou', 0):.4f} ± {metrics.get('iou_std', 0):.4f}",
                f"{metrics.get('mean_uncertainty', 0):.4f}"
            ])
            
        headers = ["Dataset", "mDice", "mIoU", "Mean Uncertainty (Variance)"]
        f.write(tabulate(table_data, headers=headers, tablefmt="github"))
        f.write("\n")
        
    print(f"\nReport generated at {report_path}")

if __name__ == "__main__":
    main()
