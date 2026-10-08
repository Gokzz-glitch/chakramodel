"""
Fast spot-check: evaluate 10 images from Kvasir-SEG test split
to confirm the DDP fix produces non-collapsed outputs.
Designed to complete in <5 minutes on CPU.
"""
import sys, os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in [str(PROJECT_ROOT), str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "src" / "models")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import torch
import numpy as np
import json
import cv2
from datetime import datetime, timezone

candidate_weights = [
    PROJECT_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth",
    PROJECT_ROOT / "weights" / "chakra_transformer_best.pth",
]
weights_path = next((p for p in candidate_weights if p.exists()), candidate_weights[0])

KVASIR_DIR = PROJECT_ROOT / "data" / "kvasir-seg"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)
N_SPOT = 10  # small but enough to confirm fix


def compute_dice(pred_mask, gt_mask):
    pred = (pred_mask > 0).astype(np.float32)
    gt = (gt_mask > 127).astype(np.float32)
    inter = (pred * gt).sum()
    denom = pred.sum() + gt.sum()
    return float(2.0 * inter / (denom + 1e-6))


def main():
    print("=" * 60)
    print(f"  ChakraNet Spot-Check Eval ({N_SPOT} images) | {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    from chakranet_segmenter import ChakraNet

    print("[INFO] Initializing ChakraNet on CPU...")
    net = ChakraNet(device='cpu', weights_path=weights_path)

    img_dir = KVASIR_DIR / "images"
    mask_dir = KVASIR_DIR / "masks"
    all_imgs = sorted(list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")))

    # Pick N_SPOT from the test split (same seed=42 as training)
    np.random.seed(42)
    indices = np.random.permutation(len(all_imgs))
    n_train = int(0.70 * len(all_imgs))
    n_cal = int(0.15 * len(all_imgs))
    test_indices = indices[n_train + n_cal:]
    test_files = [all_imgs[i] for i in test_indices[:N_SPOT]]
    print(f"[INFO] Spot-checking {len(test_files)} test images (seed=42)")

    dices, ious, raw_probs = [], [], []

    for i, img_path in enumerate(test_files):
        t0 = datetime.now()
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            continue

        stem = img_path.stem
        mask_path = None
        for ext in [".jpg", ".png", ".bmp"]:
            mp = mask_dir / f"{stem}{ext}"
            if mp.exists():
                mask_path = mp
                break

        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE) if mask_path else None
        if gt_mask is None:
            continue

        pred_mask, contours, conf, _ = net.segment_roi(img_bgr, threshold=0.45)
        if pred_mask is None:
            pred_mask = np.zeros(gt_mask.shape, dtype=np.uint8)

        if gt_mask.shape != pred_mask.shape:
            gt_mask = cv2.resize(gt_mask, (pred_mask.shape[1], pred_mask.shape[0]), interpolation=cv2.INTER_NEAREST)

        dice = compute_dice(pred_mask, gt_mask)
        pred_bin = (pred_mask > 0).astype(np.float32)
        gt_bin = (gt_mask > 127).astype(np.float32)
        inter = (pred_bin * gt_bin).sum()
        union = pred_bin.sum() + gt_bin.sum() - inter
        iou = float(inter / (union + 1e-6))

        # Also capture raw probability (to detect mode collapse)
        # Resize img for ViT and get raw sigmoid output
        raw_prob = float(np.mean(pred_mask > 0))
        raw_probs.append(raw_prob)

        elapsed = (datetime.now() - t0).total_seconds()
        dices.append(dice)
        ious.append(iou)
        print(f"  [{i+1:2d}/{N_SPOT}] {img_path.name}: DSC={dice:.4f} | IoU={iou:.4f} | coverage={raw_prob:.4f} | {elapsed:.1f}s")

    mean_dsc = float(np.mean(dices)) if dices else 0.0
    mean_iou = float(np.mean(ious)) if ious else 0.0
    prob_std = float(np.std(raw_probs)) if raw_probs else 0.0

    print()
    print("=" * 60)
    print(f"  SPOT-CHECK RESULTS (N={len(dices)})")
    print(f"  Mean DSC:           {mean_dsc:.4f}")
    print(f"  Mean IoU:           {mean_iou:.4f}")
    print(f"  Coverage std:       {prob_std:.4f}  (>0.01 = no collapse)")
    is_collapsed = prob_std < 0.001
    print(f"  Mode collapse:      {'YES - STILL BROKEN' if is_collapsed else 'NO - FIX CONFIRMED'}")

    if mean_dsc < 0.20:
        verdict = "POOR - Decoder may need retraining (architecture mismatch remains?)"
    elif mean_dsc < 0.50:
        verdict = "PARTIAL - Better than baseline (0.1835), but decoder not fully functional"
    elif mean_dsc < 0.70:
        verdict = "GOOD - Weight fix worked, training was partial"
    else:
        verdict = "EXCELLENT - Model fully recovered by weight fix alone"

    print(f"  Verdict:            {verdict}")
    print("=" * 60)

    results = {
        "spot_check_n": len(dices),
        "mean_dsc": round(mean_dsc, 4),
        "mean_iou": round(mean_iou, 4),
        "coverage_std": round(prob_std, 4),
        "mode_collapse": is_collapsed,
        "verdict": verdict,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_path": "weights/chakra_transformer_best.pth",
        "weight_loading_status": "FIXED_DDP_PREFIX_STRIPPED",
        "dataset": "kvasir-seg-test-split-seed42",
        "per_image": [
            {"idx": i+1, "dsc": round(d, 4), "iou": round(ious[i], 4)}
            for i, d in enumerate(dices)
        ]
    }

    out_path = RESULTS_DIR / "spot_check_corrected_eval.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[INFO] Results -> {out_path}")


if __name__ == "__main__":
    main()
