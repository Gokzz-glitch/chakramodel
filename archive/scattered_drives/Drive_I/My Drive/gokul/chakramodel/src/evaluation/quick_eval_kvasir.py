#!/usr/bin/env python3
"""
Quick DSC and IoU Evaluation on Kvasir-SEG
Evaluates the fixed ChakraNet / ChakraTransformer model with cleanly loaded weights
(module. and _orig_mod. stripped) on local Kvasir-SEG data.
All metrics are computed genuinely from real model predictions against ground truth masks.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import json
import cv2
import numpy as np
import torch

# Ensure safe UTF-8 output across Windows consoles and logs
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

# Add project root, src, and models to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in [str(PROJECT_ROOT), str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "src" / "models")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from chakranet_segmenter import ChakraNetMicroRefiner
from utils.transforms import letterbox_pad, unletterbox


def compute_dsc_iou(pred_bin: np.ndarray, gt_bin: np.ndarray, smooth: float = 1e-6):
    """
    Computes genuine pixel-level Dice Similarity Coefficient (DSC) and
    Intersection over Union (IoU / Jaccard index) between two binary arrays.
    """
    p = (pred_bin > 0).astype(np.float32).flatten()
    g = (gt_bin > 0).astype(np.float32).flatten()

    intersection = float(np.dot(p, g))
    total_p = float(p.sum())
    total_g = float(g.sum())
    union = float(total_p + total_g - intersection)

    dsc = (2.0 * intersection + smooth) / (total_p + total_g + smooth)
    iou = (intersection + smooth) / (union + smooth)
    return dsc, iou, int(total_p), int(total_g), int(intersection)


def main():
    print("=" * 70)
    print("  ChakraModel Quick DSC / IoU Evaluation on Kvasir-SEG")
    print(f"  Start Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    candidate_weights = [
        PROJECT_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth",
        PROJECT_ROOT / "weights" / "chakra_transformer_best.pth",
    ]
    weights_path = next((p for p in candidate_weights if p.exists()), candidate_weights[0])
    images_dir = PROJECT_ROOT / "data" / "kvasir-seg" / "images"
    masks_dir = PROJECT_ROOT / "data" / "kvasir-seg" / "masks"
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_json = results_dir / "corrected_eval_kvasir_seg.json"

    # 1. Check paths
    assert weights_path.exists(), f"Weights not found: {weights_path}"
    assert images_dir.exists(), f"Images directory not found: {images_dir}"
    assert masks_dir.exists(), f"Masks directory not found: {masks_dir}"

    # 2. Select Device
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    print(f"[INFO] Device: {device} (CUDA available: {use_cuda})")

    # 3. Instantiate model and load stripped weights
    print(f"[INFO] Instantiating ChakraNetMicroRefiner(channels=24)...")
    if use_cuda:
        # Load in half precision (FP16) on GPU to prevent 2.8GB VRAM cap OOM
        model = ChakraNetMicroRefiner(channels=24).to(device).half()
        raw_sd = torch.load(weights_path, map_location="cpu", weights_only=True)
        sd_stripped = {
            k.replace("module.", "").replace("_orig_mod.", ""): v.half()
            for k, v in raw_sd.items()
        }
    else:
        model = ChakraNetMicroRefiner(channels=24).to(device)
        raw_sd = torch.load(weights_path, map_location="cpu", weights_only=True)
        sd_stripped = {
            k.replace("module.", "").replace("_orig_mod.", ""): v
            for k, v in raw_sd.items()
        }

    missing, unexpected = model.load_state_dict(sd_stripped, strict=False)
    print(f"[INFO] Checkpoint keys: raw={len(raw_sd)}, stripped={len(sd_stripped)}")
    print(f"[INFO] Missing keys: {len(missing)}, Unexpected keys: {len(unexpected)}")

    if len(missing) == 0 and len(unexpected) == 0:
        weight_status = "STRICT_EQUIVALENT_PASS (0 missing, 0 unexpected keys)"
    else:
        weight_status = f"PARTIAL (missing={len(missing)}, unexpected={len(unexpected)})"
    print(f"[INFO] Weight loading status: {weight_status}")

    model.eval()

    # 4. Gather image and mask pairs (at least 50 images, evaluating 60 pairs)
    all_img_files = sorted([f for f in images_dir.iterdir() if f.suffix.lower() in {'.jpg', '.png'}])
    paired_samples = []
    for img_p in all_img_files:
        mask_p = masks_dir / img_p.name
        if mask_p.exists():
            paired_samples.append((img_p, mask_p))

    n_eval = min(60, len(paired_samples))
    eval_samples = paired_samples[:n_eval]
    print(f"[INFO] Total available paired images: {len(paired_samples)}")
    print(f"[INFO] Evaluating first {len(eval_samples)} images...")

    # Preprocessing constants (ImageNet mean/std)
    if use_cuda:
        mean_t = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float16, device=device).view(1, 3, 1, 1)
        std_t = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float16, device=device).view(1, 3, 1, 1)
    else:
        mean_t = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32, device=device).view(1, 3, 1, 1)
        std_t = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32, device=device).view(1, 3, 1, 1)

    image_results = []
    dices = []
    ious = []

    print("-" * 70)
    print(f"{'Idx':<4} {'Filename':<32} {'Dice':<10} {'IoU':<10} {'Pred Px':<10} {'GT Px':<10}")
    print("-" * 70)

    for idx, (img_path, mask_path) in enumerate(eval_samples, 1):
        img_bgr = cv2.imread(str(img_path))
        gt_gray = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

        if img_bgr is None or gt_gray is None:
            print(f"[WARN] Failed to read {img_path.name}, skipping.")
            continue

        orig_h, orig_w = img_bgr.shape[:2]
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # Pad to square and resize to (384, 384)
        padded_img, pad_meta = letterbox_pad(img_rgb, target_size=(384, 384))

        if use_cuda:
            tensor = torch.from_numpy(padded_img).permute(2, 0, 1).unsqueeze(0).half().to(device) / 255.0
        else:
            tensor = torch.from_numpy(padded_img).permute(2, 0, 1).unsqueeze(0).float().to(device) / 255.0

        tensor = (tensor - mean_t) / std_t

        with torch.no_grad():
            logits = model(tensor)
            prob_map = torch.sigmoid(logits)[0, 0].float().detach().cpu().numpy()

        # Unletterbox prediction back to original image resolution
        prob_orig = unletterbox(prob_map, pad_meta)
        pred_bin = (prob_orig >= 0.5).astype(np.uint8)
        gt_bin = (gt_gray > 127).astype(np.uint8)

        # Match dimensions if slight discrepancy
        if pred_bin.shape != gt_bin.shape:
            pred_bin = cv2.resize(pred_bin, (gt_bin.shape[1], gt_bin.shape[0]), interpolation=cv2.INTER_NEAREST)

        dsc, iou, pred_px, gt_px, inter_px = compute_dsc_iou(pred_bin, gt_bin)
        dices.append(dsc)
        ious.append(iou)

        image_results.append({
            "image": img_path.name,
            "dice": round(dsc, 6),
            "iou": round(iou, 6),
            "pred_pixels": pred_px,
            "gt_pixels": gt_px,
            "intersection_pixels": inter_px,
            "prob_min": round(float(prob_orig.min()), 6),
            "prob_max": round(float(prob_orig.max()), 6),
            "prob_mean": round(float(prob_orig.mean()), 6)
        })

        if idx <= 10 or idx % 10 == 0 or idx == len(eval_samples):
            print(f"{idx:<4} {img_path.name:<32} {dsc:<10.4f} {iou:<10.4f} {pred_px:<10} {gt_px:<10}")

    mean_dsc = float(np.mean(dices))
    mean_iou = float(np.mean(ious))
    std_dsc = float(np.std(dices))
    std_iou = float(np.std(ious))

    print("-" * 70)
    print(f"Summary on {len(dices)} images:")
    print(f"  Mean DSC: {mean_dsc:.4f} (± {std_dsc:.4f})")
    print(f"  Mean IoU: {mean_iou:.4f} (± {std_iou:.4f})")
    print(f"  Min DSC : {min(dices):.4f} | Max DSC: {max(dices):.4f}")
    print("=" * 70)

    # Save to required json
    payload = {
        "mean_dsc": round(mean_dsc, 6),
        "mean_iou": round(mean_iou, 6),
        "n_images": len(dices),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_path": str(weights_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "weight_loading_status": weight_status,
        "metrics_summary": {
            "mean_dsc": round(mean_dsc, 6),
            "std_dsc": round(std_dsc, 6),
            "min_dsc": round(float(min(dices)), 6),
            "max_dsc": round(float(max(dices)), 6),
            "mean_iou": round(mean_iou, 6),
            "std_iou": round(std_iou, 6),
            "min_iou": round(float(min(ious)), 6),
            "max_iou": round(float(max(ious)), 6)
        },
        "per_image_results": image_results
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"[OK] Results genuinely saved to: {out_json}")


if __name__ == "__main__":
    main()
