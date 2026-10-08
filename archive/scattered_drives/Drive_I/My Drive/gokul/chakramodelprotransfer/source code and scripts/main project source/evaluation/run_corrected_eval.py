"""
Quick corrected DSC evaluation on Kvasir-SEG local data.
Run from m:/chakramodel as: python src/run_corrected_eval.py
"""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in [str(PROJECT_ROOT), str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "src" / "models")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import torch
import numpy as np
import json
import cv2
import argparse
from datetime import datetime, timezone

candidate_weights = [
    PROJECT_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth",
    PROJECT_ROOT / "weights" / "chakra_transformer_best.pth",
]
weights_path = next((p for p in candidate_weights if p.exists()), candidate_weights[0])

KVASIR_DIR = PROJECT_ROOT / "data" / "kvasir-seg"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

def compute_dice(pred_mask, gt_mask, threshold=0.5):
    pred = (pred_mask > 0).astype(np.float32)
    gt = (gt_mask > 127).astype(np.float32)
    inter = (pred * gt).sum()
    denom = pred.sum() + gt.sum()
    return float(2.0 * inter / (denom + 1e-6))

def main():
    parser = argparse.ArgumentParser(description="Kvasir-SEG Corrected DSC Evaluation")
    parser.add_argument("--n-images", type=int, default=50, help="Number of images to evaluate (default: 50)")
    parser.add_argument("--device", type=str, default=None, help="Device to run on (cuda or cpu)")
    args, _ = parser.parse_known_args()

    print("=" * 60, flush=True)
    print("  ChakraNet Corrected DSC Evaluation (Kvasir-SEG)", flush=True)
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}", flush=True)
    print("=" * 60, flush=True)

    from chakranet_segmenter import ChakraNet

    device = args.device or ('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[INFO] Initializing ChakraNet on {device.upper()} (CUDA available: {torch.cuda.is_available()})...", flush=True)
    net = ChakraNet(device=device, weights_path=weights_path)
    print("[OK]   ChakraNet initialized", flush=True)

    img_dir = KVASIR_DIR / "images"
    mask_dir = KVASIR_DIR / "masks"

    all_imgs = sorted(list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")))
    print(f"[INFO] Found {len(all_imgs)} images in {img_dir}", flush=True)

    # Use fixed seed to pick test images (same 15% split as training notebook)
    np.random.seed(42)
    indices = np.random.permutation(len(all_imgs))
    n_train = int(0.70 * len(all_imgs))
    n_cal = int(0.15 * len(all_imgs))
    test_indices = indices[n_train + n_cal:]
    all_test_files = [all_imgs[i] for i in test_indices]
    
    n_eval = max(1, min(len(all_test_files), args.n_images))
    test_files = all_test_files[:n_eval]
    print(f"[INFO] Evaluating {len(test_files)} images from test split (seed=42 split)", flush=True)

    dices = []
    ious = []
    per_image = []
    errors = []

    for i, img_path in enumerate(test_files):
        try:
            img_bgr = cv2.imread(str(img_path))
            if img_bgr is None:
                errors.append(str(img_path))
                continue

            # Find matching mask
            stem = img_path.stem
            mask_path = None
            for ext in [".jpg", ".png", ".bmp"]:
                mp = mask_dir / f"{stem}{ext}"
                if mp.exists():
                    mask_path = mp
                    break

            if mask_path is None:
                errors.append(f"no_mask_{stem}")
                continue

            gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if gt_mask is None:
                errors.append(f"bad_mask_{stem}")
                continue

            # Run inference
            pred_mask, contours, conf, _ = net.segment_roi(img_bgr, threshold=0.45)
            if pred_mask is None:
                pred_mask = np.zeros(gt_mask.shape, dtype=np.uint8)

            # Resize gt to match pred if needed
            if gt_mask.shape != pred_mask.shape:
                gt_mask = cv2.resize(gt_mask, (pred_mask.shape[1], pred_mask.shape[0]), interpolation=cv2.INTER_NEAREST)

            dice = compute_dice(pred_mask, gt_mask)
            pred_bin = (pred_mask > 0).astype(np.float32)
            gt_bin = (gt_mask > 127).astype(np.float32)
            inter = (pred_bin * gt_bin).sum()
            union = pred_bin.sum() + gt_bin.sum() - inter
            iou = float(inter / (union + 1e-6))

            dices.append(dice)
            ious.append(iou)
            per_image.append({"file": img_path.name, "dice": round(dice, 4), "iou": round(iou, 4), "conf": round(conf, 4)})

            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(test_files)}] running mean DSC: {np.mean(dices):.4f}", flush=True)

        except Exception as e:
            errors.append(f"{img_path.name}: {e}")
            print(f"  [ERROR] {img_path.name}: {e}")

    mean_dsc = float(np.mean(dices)) if dices else 0.0
    mean_iou = float(np.mean(ious)) if ious else 0.0

    print()
    print("=" * 60)
    print(f"  CORRECTED RESULTS (after DDP prefix fix)")
    print(f"  N images evaluated: {len(dices)}")
    print(f"  Mean DSC:           {mean_dsc:.4f}")
    print(f"  Mean IoU:           {mean_iou:.4f}")
    print(f"  Errors/skipped:     {len(errors)}")
    print("=" * 60)

    results = {
        "mean_dsc": round(mean_dsc, 4),
        "mean_iou": round(mean_iou, 4),
        "n_images": len(dices),
        "errors": len(errors),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_path": str(weights_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "weight_loading_status": "FIXED_DDP_PREFIX_STRIPPED",
        "dataset": "kvasir-seg-test-split-seed42",
        "per_image_results": per_image
    }

    out_path = RESULTS_DIR / "corrected_eval_kvasir_seg.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[INFO] Results saved to {out_path}")

    if mean_dsc < 0.30:
        print("[WARN] DSC is still very low — model may need retraining even with correct weights")
    elif mean_dsc < 0.60:
        print("[INFO] DSC improved from 0.1835 but below 0.60 — decoder is partially functional")
    else:
        print("[PASS] DSC > 0.60 — weight fix resolved mode collapse")

if __name__ == "__main__":
    main()
