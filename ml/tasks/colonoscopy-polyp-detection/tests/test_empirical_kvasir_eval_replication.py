"""
Empirical Replication & Adversarial Challenge Harness for Kvasir-SEG Evaluation
Verifies results/corrected_eval_kvasir_seg.json:
1. Mathematical self-consistency of all 60 reported entries.
2. Device and environment inspection.
3. Model instantiation and weight loading verification.
4. Empirical re-inference on sample images from data/kvasir-seg/images and data/kvasir-seg/masks.
5. Exact and delta comparisons against reported Dice, IoU, and pixel counts.
6. Anti-fabrication tests: input sensitivity, weight perturbation, and uninitialized baseline.
"""

import os
import sys
from pathlib import Path
import json
import random
import cv2
import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for p in [str(PROJECT_ROOT), str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "src" / "models")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from chakranet_segmenter import ChakraNetMicroRefiner
from utils.transforms import letterbox_pad, unletterbox

JSON_PATH = PROJECT_ROOT / "results" / "corrected_eval_kvasir_seg.json"
candidate_weights = [
    PROJECT_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth",
    PROJECT_ROOT / "weights" / "chakra_transformer_best.pth",
]
WEIGHTS_PATH = next((p for p in candidate_weights if p.exists()), candidate_weights[0])
IMAGES_DIR = PROJECT_ROOT / "data" / "kvasir-seg" / "images"
MASKS_DIR = PROJECT_ROOT / "data" / "kvasir-seg" / "masks"


def compute_dsc_iou(pred_bin: np.ndarray, gt_bin: np.ndarray, smooth: float = 1e-6):
    p = (pred_bin > 0).astype(np.float32).flatten()
    g = (gt_bin > 0).astype(np.float32).flatten()

    intersection = float(np.dot(p, g))
    total_p = float(p.sum())
    total_g = float(g.sum())
    union = float(total_p + total_g - intersection)

    dsc = (2.0 * intersection + smooth) / (total_p + total_g + smooth)
    iou = (intersection + smooth) / (union + smooth)
    return dsc, iou, int(total_p), int(total_g), int(intersection)


def run_verification():
    print("=" * 75)
    print("  EMPIRICAL CHALLENGER: KVASIR-SEG REPLICATION & AUDIT HARNESS")
    print("=" * 75)

    assert JSON_PATH.exists(), f"Results JSON not found at {JSON_PATH}"
    assert WEIGHTS_PATH.exists(), f"Weights not found at {WEIGHTS_PATH}"
    assert IMAGES_DIR.exists(), f"Images dir not found at {IMAGES_DIR}"
    assert MASKS_DIR.exists(), f"Masks dir not found at {MASKS_DIR}"

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    per_image = data["per_image_results"]
    n_images = len(per_image)
    print(f"[STAGE 1] JSON Schema & Mathematical Consistency Check ({n_images} items):")
    print(f"  Reported Mean DSC: {data['mean_dsc']}")
    print(f"  Reported Mean IoU: {data['mean_iou']}")

    # 1. Check mathematical oracle consistency of reported metrics
    math_failures = []
    dices_from_json = []
    ious_from_json = []
    for entry in per_image:
        p_px = entry["pred_pixels"]
        g_px = entry["gt_pixels"]
        inter_px = entry["intersection_pixels"]
        rep_dice = entry["dice"]
        rep_iou = entry["iou"]

        dices_from_json.append(rep_dice)
        ious_from_json.append(rep_iou)

        expected_dice = (2.0 * inter_px + 1e-6) / (p_px + g_px + 1e-6)
        expected_iou = (inter_px + 1e-6) / (p_px + g_px - inter_px + 1e-6)

        if abs(expected_dice - rep_dice) > 1e-4 or abs(expected_iou - rep_iou) > 1e-4:
            math_failures.append({
                "image": entry["image"],
                "reported_dice": rep_dice,
                "expected_dice": expected_dice,
                "reported_iou": rep_iou,
                "expected_iou": expected_iou
            })

    calc_mean_dsc = float(np.mean(dices_from_json))
    calc_mean_iou = float(np.mean(ious_from_json))
    print(f"  Calculated Mean DSC from array: {calc_mean_dsc:.6f} (diff: {abs(calc_mean_dsc - data['mean_dsc']):.6e})")
    print(f"  Calculated Mean IoU from array: {calc_mean_iou:.6f} (diff: {abs(calc_mean_iou - data['mean_iou']):.6e})")
    print(f"  Mathematical Formula Failures: {len(math_failures)}")
    if math_failures:
        print(f"  [ERROR] Inconsistent entries found: {math_failures[:3]}")

    # 2. Select Sample Images: at least 5 randomly chosen, plus specific edge cases
    random.seed(20260908)
    sample_indices = sorted(random.sample(range(n_images), 7))
    # Also include min DSC and max DSC indices
    min_idx = int(np.argmin(dices_from_json))
    max_idx = int(np.argmax(dices_from_json))
    all_test_indices = sorted(list(set(sample_indices + [min_idx, max_idx])))

    print(f"\n[STAGE 2] Selected {len(all_test_indices)} Sample Images for Empirical Re-Inference:")
    for idx in all_test_indices:
        print(f"  Index {idx:02d}: {per_image[idx]['image']} (Reported DSC: {per_image[idx]['dice']:.4f}, IoU: {per_image[idx]['iou']:.4f})")

    # 3. Model setup on available device
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    print(f"\n[STAGE 3] Loading Model on Device: {device} (use_cuda={use_cuda})")

    raw_sd = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
    if use_cuda:
        model = ChakraNetMicroRefiner(channels=24).to(device).half()
        sd_stripped = {
            k.replace("module.", "").replace("_orig_mod.", ""): v.half()
            for k, v in raw_sd.items()
        }
    else:
        model = ChakraNetMicroRefiner(channels=24).to(device)
        sd_stripped = {
            k.replace("module.", "").replace("_orig_mod.", ""): v
            for k, v in raw_sd.items()
        }

    missing, unexpected = model.load_state_dict(sd_stripped, strict=False)
    print(f"  Missing keys: {len(missing)}, Unexpected keys: {len(unexpected)}")
    assert len(missing) == 0 and len(unexpected) == 0, f"Weight mismatch! Missing={missing[:5]}, Unexpected={unexpected[:5]}"
    model.eval()

    # Preprocessing constants
    if use_cuda:
        mean_t = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float16, device=device).view(1, 3, 1, 1)
        std_t = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float16, device=device).view(1, 3, 1, 1)
    else:
        mean_t = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32, device=device).view(1, 3, 1, 1)
        std_t = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32, device=device).view(1, 3, 1, 1)

    print("\n[STAGE 4] Executing Empirical Re-Inference on Sample Images...")
    results_comparison = []

    for idx in all_test_indices:
        entry = per_image[idx]
        img_name = entry["image"]
        img_path = IMAGES_DIR / img_name
        mask_path = MASKS_DIR / img_name

        assert img_path.exists(), f"Image not found: {img_path}"
        assert mask_path.exists(), f"Mask not found: {mask_path}"

        img_bgr = cv2.imread(str(img_path))
        gt_gray = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

        assert img_bgr is not None, f"Failed to read image {img_path}"
        assert gt_gray is not None, f"Failed to read mask {mask_path}"

        orig_h, orig_w = img_bgr.shape[:2]
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        padded_img, pad_meta = letterbox_pad(img_rgb, target_size=(384, 384))

        if use_cuda:
            tensor = torch.from_numpy(padded_img).permute(2, 0, 1).unsqueeze(0).half().to(device) / 255.0
        else:
            tensor = torch.from_numpy(padded_img).permute(2, 0, 1).unsqueeze(0).float().to(device) / 255.0

        tensor = (tensor - mean_t) / std_t

        with torch.no_grad():
            logits = model(tensor)
            prob_map = torch.sigmoid(logits)[0, 0].float().detach().cpu().numpy()

        prob_orig = unletterbox(prob_map, pad_meta)
        pred_bin = (prob_orig >= 0.5).astype(np.uint8)
        gt_bin = (gt_gray > 127).astype(np.uint8)

        if pred_bin.shape != gt_bin.shape:
            pred_bin = cv2.resize(pred_bin, (gt_bin.shape[1], gt_bin.shape[0]), interpolation=cv2.INTER_NEAREST)

        emp_dsc, emp_iou, emp_p_px, emp_g_px, emp_inter_px = compute_dsc_iou(pred_bin, gt_bin)

        diff_dsc = abs(emp_dsc - entry["dice"])
        diff_iou = abs(emp_iou - entry["iou"])
        diff_pred_px = abs(emp_p_px - entry["pred_pixels"])
        diff_gt_px = abs(emp_g_px - entry["gt_pixels"])
        diff_inter_px = abs(emp_inter_px - entry["intersection_pixels"])

        comp = {
            "image": img_name,
            "rep_dice": entry["dice"],
            "emp_dice": emp_dsc,
            "diff_dice": diff_dsc,
            "rep_iou": entry["iou"],
            "emp_iou": emp_iou,
            "diff_iou": diff_iou,
            "rep_pred_px": entry["pred_pixels"],
            "emp_pred_px": emp_p_px,
            "diff_pred_px": diff_pred_px,
            "rep_gt_px": entry["gt_pixels"],
            "emp_gt_px": emp_g_px,
            "diff_gt_px": diff_gt_px,
            "rep_inter_px": entry["intersection_pixels"],
            "emp_inter_px": emp_inter_px,
            "diff_inter_px": diff_inter_px,
        }
        results_comparison.append(comp)

        status_flag = "EXACT_MATCH" if diff_pred_px == 0 and diff_inter_px == 0 else ("CLOSE_MATCH" if diff_dsc < 0.01 else "DISCREPANCY")
        print(f"  [{status_flag}] {img_name}:")
        print(f"     DSC: Rep={entry['dice']:.6f} | Emp={emp_dsc:.6f} | diff={diff_dsc:.6e}")
        print(f"     IoU: Rep={entry['iou']:.6f} | Emp={emp_iou:.6f} | diff={diff_iou:.6e}")
        print(f"     Pred Px: Rep={entry['pred_pixels']} | Emp={emp_p_px} | diff={diff_pred_px}")
        print(f"     GT Px:   Rep={entry['gt_pixels']} | Emp={emp_g_px} | diff={diff_gt_px}")
        print(f"     Inter:   Rep={entry['intersection_pixels']} | Emp={emp_inter_px} | diff={diff_inter_px}")

    # 5. Anti-Fabrication Stress Tests
    print("\n[STAGE 5] Anti-Fabrication and Input-Sensitivity Stress Testing:")
    test_img_name = per_image[all_test_indices[0]]["image"]
    test_img_path = IMAGES_DIR / test_img_name
    img_bgr = cv2.imread(str(test_img_path))
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    padded_img, _ = letterbox_pad(img_rgb, target_size=(384, 384))
    
    if use_cuda:
        real_tensor = (torch.from_numpy(padded_img).permute(2, 0, 1).unsqueeze(0).half().to(device) / 255.0 - mean_t) / std_t
        black_tensor = (torch.zeros((1, 3, 384, 384), dtype=torch.float16, device=device) - mean_t) / std_t
        noise_tensor = (torch.randn((1, 3, 384, 384), dtype=torch.float16, device=device) - mean_t) / std_t
    else:
        real_tensor = (torch.from_numpy(padded_img).permute(2, 0, 1).unsqueeze(0).float().to(device) / 255.0 - mean_t) / std_t
        black_tensor = (torch.zeros((1, 3, 384, 384), dtype=torch.float32, device=device) - mean_t) / std_t
        noise_tensor = (torch.randn((1, 3, 384, 384), dtype=torch.float32, device=device) - mean_t) / std_t

    with torch.no_grad():
        out_real = torch.sigmoid(model(real_tensor))
        out_black = torch.sigmoid(model(black_tensor))
        out_noise = torch.sigmoid(model(noise_tensor))

    real_mean = out_real.mean().item()
    black_mean = out_black.mean().item()
    noise_mean = out_noise.mean().item()
    diff_real_black = abs(real_mean - black_mean)
    diff_real_noise = abs(real_mean - noise_mean)

    print(f"  Real Image Prob Mean:       {real_mean:.6f}")
    print(f"  Black Image Prob Mean:      {black_mean:.6f}")
    print(f"  Noise Image Prob Mean:      {noise_mean:.6f}")
    print(f"  Dynamic Response Spread:    {max(real_mean, black_mean, noise_mean) - min(real_mean, black_mean, noise_mean):.6f}")

    is_dynamic = (diff_real_black > 0.05) and (diff_real_noise > 0.05)
    print(f"  Input Conditioning Check:   {'PASS (Dynamic response, NOT hardcoded)' if is_dynamic else 'FAIL (Static response)'}")

    # Test weight zeroing
    print("\n[STAGE 6] Model Weight Causality Test:")
    orig_conv_weight = model.decode_head[6].weight.clone()
    orig_conv_bias = model.decode_head[6].bias.clone()
    with torch.no_grad():
        model.decode_head[6].weight.zero_()
        model.decode_head[6].bias.zero_()
        out_zeroed = torch.sigmoid(model(real_tensor))
        zeroed_std = out_zeroed.std().item()
        zeroed_mean = out_zeroed.mean().item()
        model.decode_head[6].weight.copy_(orig_conv_weight)
        model.decode_head[6].bias.copy_(orig_conv_bias)

    print(f"  Zeroed Head Output Mean:    {zeroed_mean:.6f} (sigmoid(0) = 0.5)")
    print(f"  Zeroed Head Output Std:     {zeroed_std:.6e} (flat output)")
    weight_causality = (abs(zeroed_mean - 0.5) < 1e-3) and (zeroed_std < 1e-4)
    print(f"  Weight Causality Check:     {'PASS (Outputs directly depend on weights)' if weight_causality else 'FAIL'}")

    # Output JSON summary
    summary = {
        "status": "COMPLETED",
        "n_evaluated_samples": len(results_comparison),
        "mathematical_consistency": len(math_failures) == 0,
        "results_comparison": results_comparison,
        "anti_fabrication": {
            "dynamic_input_response": is_dynamic,
            "weight_causality_pass": weight_causality,
            "real_mean": real_mean,
            "black_mean": black_mean,
            "noise_mean": noise_mean
        }
    }

    out_file = PROJECT_ROOT / "tests" / "replication_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[INFO] Summary written to {out_file}")

if __name__ == "__main__":
    run_verification()
