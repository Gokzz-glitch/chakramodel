#!/usr/bin/env python3
"""
Adversarial Metric Verification Test on Kvasir-SEG
Challenger: Challenger 2 Replacement (Gen 5)
Working Dir: .agents/challenger_m4_2_g5_r2

Adversarially tests results/corrected_eval_kvasir_seg.json:
1. Samples 10 distinct images across the dataset.
2. Loads genuine image and ground truth mask files from data/kvasir-seg/.
3. Runs independent inference using ChakraNet / ChakraNetMicroRefiner.
4. Independently computes Dice, IoU, pixel counts, and probability statistics.
5. Asserts that independent values match recorded JSON values within strict numerical tolerance (tol < 1e-4).
"""

import sys
import json
import random
from pathlib import Path
import cv2
import numpy as np
import torch

# Ensure project root and src are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from chakranet_segmenter import ChakraNet
from utils.transforms import letterbox_pad, unletterbox


def compute_independent_metrics(pred_bin: np.ndarray, gt_bin: np.ndarray, smooth: float = 1e-6):
    """Independently computes Dice and IoU from scratch using pure NumPy."""
    p = (pred_bin > 0).astype(np.float32).flatten()
    g = (gt_bin > 0).astype(np.float32).flatten()

    intersection = float(np.dot(p, g))
    total_p = float(p.sum())
    total_g = float(g.sum())
    union = float(total_p + total_g - intersection)

    dsc = (2.0 * intersection + smooth) / (total_p + total_g + smooth)
    iou = (intersection + smooth) / (union + smooth)
    return dsc, iou, int(total_p), int(total_g), int(intersection)


def run_adversarial_verification(sample_indices=None, seed=42):
    print("=" * 80)
    print("  ADVERSARIAL CHALLENGE: Kvasir-SEG Metric Authenticity Verification")
    print("=" * 80)

    json_path = PROJECT_ROOT / "results" / "corrected_eval_kvasir_seg.json"
    assert json_path.exists(), f"Target JSON file not found: {json_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        recorded_data = json.load(f)

    per_image_results = recorded_data.get("per_image_results", [])
    total_records = len(per_image_results)
    assert total_records >= 50, f"Expected at least 50 images in JSON, got {total_records}"
    print(f"[INFO] Successfully loaded {json_path}")
    print(f"[INFO] Recorded dataset count: {total_records} images")
    print(f"[INFO] Recorded Mean DSC: {recorded_data['mean_dsc']}, Mean IoU: {recorded_data['mean_iou']}")

    # Select 10 samples
    if sample_indices is None:
        rng = random.Random(seed)
        sample_indices = sorted(rng.sample(range(total_records), 10))

    print(f"[INFO] Sampled indices (N={len(sample_indices)}): {sample_indices}")

    # Hardware & Model Initialization
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    print(f"[INFO] Execution Device: {device} (CUDA available: {use_cuda})")

    weights_path = PROJECT_ROOT / "weights" / "chakra_transformer_best.pth"
    assert weights_path.exists(), f"Weights file not found: {weights_path}"

    # Initialize ChakraNet with skip to prevent FP32 OOM during hardware monitor warmup
    cn = ChakraNet(device=device, weights_path="skip")
    if use_cuda:
        cn.model.half()
        raw_sd = torch.load(weights_path, map_location="cpu", weights_only=True)
        sd_stripped = {
            k.replace("module.", "").replace("_orig_mod.", ""): v.half()
            for k, v in raw_sd.items()
        }
    else:
        raw_sd = torch.load(weights_path, map_location="cpu", weights_only=True)
        sd_stripped = {
            k.replace("module.", "").replace("_orig_mod.", ""): v
            for k, v in raw_sd.items()
        }

    missing, unexpected = cn.model.load_state_dict(sd_stripped, strict=False)
    assert len(missing) == 0, f"Missing keys in checkpoint: {missing}"
    assert len(unexpected) == 0, f"Unexpected keys in checkpoint: {unexpected}"
    print(f"[INFO] ChakraNet weights loaded cleanly (strict equivalent pass, 0 missing, 0 unexpected keys)")
    cn.model.eval()

    # Preprocessing tensors
    if use_cuda:
        mean_t = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float16, device=device).view(1, 3, 1, 1)
        std_t = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float16, device=device).view(1, 3, 1, 1)
    else:
        mean_t = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32, device=device).view(1, 3, 1, 1)
        std_t = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32, device=device).view(1, 3, 1, 1)

    images_dir = PROJECT_ROOT / "data" / "kvasir-seg" / "images"
    masks_dir = PROJECT_ROOT / "data" / "kvasir-seg" / "masks"

    comparison_results = []
    all_matched = True

    print("\n" + "-" * 110)
    print(f"{'Idx':<4} {'Filename':<28} {'Calc DSC':<10} {'Rec DSC':<10} {'Delta DSC':<10} {'Calc IoU':<10} {'Rec IoU':<10} {'Delta IoU':<10} {'Status':<6}")
    print("-" * 110)

    for s_idx in sample_indices:
        rec = per_image_results[s_idx]
        filename = rec["image"]
        img_p = images_dir / filename
        mask_p = masks_dir / filename

        assert img_p.exists(), f"Image file missing: {img_p}"
        assert mask_p.exists(), f"Mask file missing: {mask_p}"

        img_bgr = cv2.imread(str(img_p))
        gt_gray = cv2.imread(str(mask_p), cv2.IMREAD_GRAYSCALE)

        assert img_bgr is not None, f"Could not read image: {img_p}"
        assert gt_gray is not None, f"Could not read mask: {mask_p}"

        # Preprocess
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        padded_img, pad_meta = letterbox_pad(img_rgb, target_size=(384, 384))

        if use_cuda:
            tensor = torch.from_numpy(padded_img).permute(2, 0, 1).unsqueeze(0).half().to(device) / 255.0
        else:
            tensor = torch.from_numpy(padded_img).permute(2, 0, 1).unsqueeze(0).float().to(device) / 255.0

        tensor = (tensor - mean_t) / std_t

        with torch.no_grad():
            logits = cn.model(tensor)
            prob_map = torch.sigmoid(logits)[0, 0].float().detach().cpu().numpy()

        prob_orig = unletterbox(prob_map, pad_meta)
        pred_bin = (prob_orig >= 0.5).astype(np.uint8)
        gt_bin = (gt_gray > 127).astype(np.uint8)

        if pred_bin.shape != gt_bin.shape:
            pred_bin = cv2.resize(pred_bin, (gt_bin.shape[1], gt_bin.shape[0]), interpolation=cv2.INTER_NEAREST)

        calc_dsc, calc_iou, calc_pred_px, calc_gt_px, calc_inter_px = compute_independent_metrics(pred_bin, gt_bin)

        delta_dsc = abs(calc_dsc - rec["dice"])
        delta_iou = abs(calc_iou - rec["iou"])
        delta_gt_px = abs(calc_gt_px - rec["gt_pixels"])
        delta_pred_px = abs(calc_pred_px - rec["pred_pixels"])
        delta_inter_px = abs(calc_inter_px - rec["intersection_pixels"])

        # Numerical tolerance for floating point rounding in JSON (stored at 6 decimals)
        passed = (
            delta_dsc < 1e-4 and
            delta_iou < 1e-4 and
            delta_gt_px == 0 and
            delta_pred_px == 0 and
            delta_inter_px == 0
        )
        if not passed:
            all_matched = False

        status_str = "PASS" if passed else "FAIL"
        print(f"{s_idx:<4} {filename:<28} {calc_dsc:<10.6f} {rec['dice']:<10.6f} {delta_dsc:<10.2e} {calc_iou:<10.6f} {rec['iou']:<10.6f} {delta_iou:<10.2e} {status_str:<6}")

        comparison_results.append({
            "sample_index": s_idx,
            "filename": filename,
            "calculated": {
                "dice": calc_dsc,
                "iou": calc_iou,
                "pred_pixels": calc_pred_px,
                "gt_pixels": calc_gt_px,
                "intersection_pixels": calc_inter_px,
                "prob_min": float(prob_orig.min()),
                "prob_max": float(prob_orig.max()),
                "prob_mean": float(prob_orig.mean())
            },
            "recorded": {
                "dice": rec["dice"],
                "iou": rec["iou"],
                "pred_pixels": rec["pred_pixels"],
                "gt_pixels": rec["gt_pixels"],
                "intersection_pixels": rec["intersection_pixels"],
                "prob_min": rec.get("prob_min"),
                "prob_max": rec.get("prob_max"),
                "prob_mean": rec.get("prob_mean")
            },
            "deltas": {
                "delta_dsc": delta_dsc,
                "delta_iou": delta_iou,
                "delta_pred_pixels": delta_pred_px,
                "delta_gt_pixels": delta_gt_px,
                "delta_intersection_pixels": delta_inter_px
            },
            "status": status_str
        })

    print("-" * 110)
    print(f"\n[SUMMARY] Adversarial Verification Result: {'ALL MATCHED (VERIFIED GENUINE)' if all_matched else 'FAILED'}")
    assert all_matched, "Adversarial challenge detected discrepancy between calculated and recorded values!"

    # Save evidence file for challenger handoff
    evidence_path = PROJECT_ROOT / ".agents" / "challenger_m4_2_g5_r2" / "adversarial_evidence.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump({
            "verification_status": "AUTHENTIC_GENUINE_PASS",
            "samples_tested": len(sample_indices),
            "sample_indices": sample_indices,
            "all_matched": all_matched,
            "results": comparison_results
        }, f, indent=2)
    print(f"[INFO] Evidence written to: {evidence_path}")
    return comparison_results


if __name__ == "__main__":
    run_adversarial_verification()
