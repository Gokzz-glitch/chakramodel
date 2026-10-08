import os
import cv2
import numpy as np
from pathlib import Path
import torch
import sys

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent))

from chakranet_segmenter import ChakraNet
from metrics.seg_metrics import dice

def run_diagnostic():
    base_dir = Path(__file__).parent.parent
    img_dir = base_dir / "data" / "etis-larib" / "images"
    mask_dir = base_dir / "data" / "etis-larib" / "masks"
    out_dir = base_dir / "diagnostic_output"
    out_dir.mkdir(exist_ok=True)
    
    if not img_dir.exists():
        print(f"Directory not found: {img_dir}")
        return
        
    img_paths = sorted(list(img_dir.glob("*.tif")) + list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")))[:10]
    print(f"Found {len(img_paths)} images for diagnostic.")
    
    weights = base_dir / "weights" / "chakra_transformer_best.pth"
    model = ChakraNet(device='cpu', weights_path=weights)
    
    overall_dice = []
    
    for p in img_paths:
        img = cv2.imread(str(p))
        # ETIS masks are typically .tif or .png
        mask_path = mask_dir / (p.stem + ".tif")
        if not mask_path.exists():
            mask_path = mask_dir / (p.stem + ".png")
            
        if not mask_path.exists():
            print(f"Mask not found for {p.name}")
            continue
            
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        if img is None or mask is None:
            print(f"Failed to read {p.name}")
            continue
            
        pred_mask, _, _, _ = model.segment_roi(img, threshold=0.5)
        
        # calculate dice
        pred_bin = (pred_mask > 127).astype(np.uint8) * 255
        gt_bin = (mask > 127).astype(np.uint8) * 255
        
        if pred_bin.shape != gt_bin.shape:
            pred_bin = cv2.resize(pred_bin, (gt_bin.shape[1], gt_bin.shape[0]), interpolation=cv2.INTER_NEAREST)
            
        d = dice(pred_bin, gt_bin)
        overall_dice.append(d)
        
        # Overlay
        overlay = img.copy()
        
        # Green for GT
        gt_colored = np.zeros_like(overlay)
        gt_colored[gt_bin > 127] = [0, 255, 0]
        
        # Red for Pred
        pred_colored = np.zeros_like(overlay)
        pred_colored[pred_bin > 127] = [0, 0, 255]
        
        # Alpha blending
        overlay = cv2.addWeighted(overlay, 0.7, gt_colored, 0.3, 0)
        overlay = cv2.addWeighted(overlay, 1.0, pred_colored, 0.5, 0)
        
        # Concat side by side: Original, GT, Pred, Overlay
        gt_c = cv2.cvtColor(gt_bin, cv2.COLOR_GRAY2BGR)
        pred_c = cv2.cvtColor(pred_bin, cv2.COLOR_GRAY2BGR)
        
        h = 352
        w = int(img.shape[1] * (352 / img.shape[0]))
        
        img_r = cv2.resize(img, (w, h))
        gt_r = cv2.resize(gt_c, (w, h))
        pred_r = cv2.resize(pred_c, (w, h))
        ov_r = cv2.resize(overlay, (w, h))
        
        grid = np.hstack([img_r, gt_r, pred_r, ov_r])
        
        out_p = out_dir / f"{p.stem}_dice_{d:.4f}.jpg"
        cv2.imwrite(str(out_p), grid)
        print(f"Saved {out_p.name} (Dice: {d:.4f})")
        
    print(f"\nMean Dice on {len(img_paths)} samples: {np.mean(overall_dice):.4f}")

if __name__ == '__main__':
    run_diagnostic()
