"""
Independent Empirical Audit of results/corrected_eval_kvasir_seg.json
Challenger 2 - Milestone 4 (Gen 6)
"""

import json
import math
import os
import sys
from pathlib import Path
import numpy as np


def run_audit(json_path: str = "results/corrected_eval_kvasir_seg.json"):
    print(f"=== Running Audit on {json_path} ===")
    assert os.path.exists(json_path), f"File {json_path} does not exist!"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Top-level keys
    print("Top-level keys:", list(data.keys()))
    top_mean_dsc = data.get("mean_dsc")
    top_mean_iou = data.get("mean_iou")
    n_images = data.get("n_images")
    per_image = data.get("per_image_results", [])
    metrics_summary = data.get("metrics_summary", {})

    print(f"Reported n_images: {n_images}")
    print(f"Actual entries in per_image_results: {len(per_image)}")
    assert len(per_image) == n_images, f"Mismatch in n_images ({n_images}) and per_image length ({len(per_image)})"
    assert n_images >= 50, f"n_images ({n_images}) < 50"

    # Lists for metrics
    dices = []
    ious = []
    image_names = []
    pred_pixel_list = []
    gt_pixel_list = []
    inter_pixel_list = []

    # Pixel count math checks
    math_failures_dice = []
    math_failures_iou = []
    math_failures_set_relation = []
    pixel_bounds_failures = []
    prob_bounds_failures = []

    for idx, item in enumerate(per_image):
        img = item["image"]
        image_names.append(img)
        d = float(item["dice"])
        iou = float(item["iou"])
        pred_p = int(item["pred_pixels"])
        gt_p = int(item["gt_pixels"])
        inter_p = int(item["intersection_pixels"])

        dices.append(d)
        ious.append(iou)
        pred_pixel_list.append(pred_p)
        gt_pixel_list.append(gt_p)
        inter_pixel_list.append(inter_p)

        # 1. Pixel bounds checks
        if not (0 <= inter_p <= min(pred_p, gt_p)):
            pixel_bounds_failures.append((idx, img, pred_p, gt_p, inter_p))

        # Prob bounds check if present
        if "prob_min" in item and "prob_max" in item and "prob_mean" in item:
            p_min = float(item["prob_min"])
            p_max = float(item["prob_max"])
            p_mean = float(item["prob_mean"])
            if not (0.0 <= p_min <= p_mean <= p_max <= 1.0 + 1e-6):
                prob_bounds_failures.append((idx, img, p_min, p_mean, p_max))

        # 2. Exact Dice calculation check
        denom_dice = pred_p + gt_p
        if denom_dice == 0:
            expected_dice = 1.0 if inter_p == 0 else 0.0
        else:
            expected_dice = (2.0 * inter_p) / denom_dice

        # Given 6 decimal places rounding in JSON
        if abs(d - expected_dice) > 1e-4:
            math_failures_dice.append({
                "idx": idx, "img": img, "reported_dice": d,
                "expected_dice": expected_dice, "diff": abs(d - expected_dice)
            })

        # 3. Exact IoU calculation check
        denom_iou = pred_p + gt_p - inter_p
        if denom_iou == 0:
            expected_iou = 1.0 if inter_p == 0 else 0.0
        else:
            expected_iou = float(inter_p) / float(denom_iou)

        if abs(iou - expected_iou) > 1e-4:
            math_failures_iou.append({
                "idx": idx, "img": img, "reported_iou": iou,
                "expected_iou": expected_iou, "diff": abs(iou - expected_iou)
            })

        # 4. Algebraic relation IoU = DSC / (2 - DSC)
        if denom_dice > 0 and denom_iou > 0:
            # Theoretical relation: iou_from_dsc = d / (2 - d)
            iou_from_dsc = d / (2.0 - d)
            if abs(iou - iou_from_dsc) > 1e-3:  # allowing small precision rounding
                math_failures_set_relation.append({
                    "idx": idx, "img": img, "reported_iou": iou,
                    "iou_from_dsc": iou_from_dsc, "diff": abs(iou - iou_from_dsc)
                })

    dices = np.array(dices, dtype=np.float64)
    ious = np.array(ious, dtype=np.float64)

    # Statistical properties
    mean_dsc_calc = float(np.mean(dices))
    std_dsc_sample = float(np.std(dices, ddof=1))
    std_dsc_pop = float(np.std(dices, ddof=0))
    min_dsc_calc = float(np.min(dices))
    max_dsc_calc = float(np.max(dices))

    mean_iou_calc = float(np.mean(ious))
    std_iou_sample = float(np.std(ious, ddof=1))
    std_iou_pop = float(np.std(ious, ddof=0))
    min_iou_calc = float(np.min(ious))
    max_iou_calc = float(np.max(ious))

    median_dsc = float(np.median(dices))
    median_iou = float(np.median(ious))
    q25_dsc, q75_dsc = float(np.percentile(dices, 25)), float(np.percentile(dices, 75))
    q25_iou, q75_iou = float(np.percentile(ious, 25)), float(np.percentile(ious, 75))

    # Variability and uniqueness checks
    unique_images = len(set(image_names))
    unique_dices = len(set(dices.round(6).tolist()))
    unique_ious = len(set(ious.round(6).tolist()))
    unique_preds = len(set(pred_pixel_list))
    unique_gts = len(set(gt_pixel_list))
    unique_inters = len(set(inter_pixel_list))

    print("\n--- RESULTS & RE-COMPUTATION ---")
    print(f"DSC Metrics:")
    print(f"  Calculated Mean:   {mean_dsc_calc:.6f} (Top-level reported: {top_mean_dsc})")
    print(f"  Calculated Min:    {min_dsc_calc:.6f} (Summary reported: {metrics_summary.get('min_dsc')})")
    print(f"  Calculated Max:    {max_dsc_calc:.6f} (Summary reported: {metrics_summary.get('max_dsc')})")
    print(f"  Sample Std (N-1):  {std_dsc_sample:.6f} (Summary reported: {metrics_summary.get('std_dsc')})")
    print(f"  Pop Std (N):       {std_dsc_pop:.6f}")
    print(f"  Median:            {median_dsc:.6f}, IQR: [{q25_dsc:.6f}, {q75_dsc:.6f}]")

    print(f"\nIoU Metrics:")
    print(f"  Calculated Mean:   {mean_iou_calc:.6f} (Top-level reported: {top_mean_iou})")
    print(f"  Calculated Min:    {min_iou_calc:.6f} (Summary reported: {metrics_summary.get('min_iou')})")
    print(f"  Calculated Max:    {max_iou_calc:.6f} (Summary reported: {metrics_summary.get('max_iou')})")
    print(f"  Sample Std (N-1):  {std_iou_sample:.6f} (Summary reported: {metrics_summary.get('std_iou')})")
    print(f"  Pop Std (N):       {std_iou_pop:.6f}")
    print(f"  Median:            {median_iou:.6f}, IQR: [{q25_iou:.6f}, {q75_iou:.6f}]")

    print("\n--- PERCENTILES BREAKDOWN ---")
    for p in [0, 5, 10, 25, 50, 75, 90, 95, 100]:
        print(f"  {p:3d}th percentile: DSC = {float(np.percentile(dices, p)):.6f} | IoU = {float(np.percentile(ious, p)):.6f}")

    sorted_entries = sorted(per_image, key=lambda x: x["dice"])
    print("\n--- BOTTOM 5 PERFORMING SAMPLES ---")
    for x in sorted_entries[:5]:
        print(f"  {x['image']}: DSC={x['dice']:.6f}, IoU={x['iou']:.6f}, Pred={x['pred_pixels']}, GT={x['gt_pixels']}, Inter={x['intersection_pixels']}")

    print("\n--- TOP 5 PERFORMING SAMPLES ---")
    for x in sorted_entries[-5:]:
        print(f"  {x['image']}: DSC={x['dice']:.6f}, IoU={x['iou']:.6f}, Pred={x['pred_pixels']}, GT={x['gt_pixels']}, Inter={x['intersection_pixels']}")

    print("\n--- VARIABILITY & INTEGRITY ---")
    print(f"Unique images: {unique_images} / {n_images}")
    print(f"Unique DSC values: {unique_dices} / {n_images}")
    print(f"Unique IoU values: {unique_ious} / {n_images}")
    print(f"Unique pred pixel counts: {unique_preds} / {n_images}")
    print(f"Unique GT pixel counts: {unique_gts} / {n_images}")
    print(f"Unique intersection pixel counts: {unique_inters} / {n_images}")

    print("\n--- MATHEMATICAL CONSISTENCY FAILURES ---")
    print(f"Pixel bounds failures: {len(pixel_bounds_failures)}")
    print(f"Probability bounds failures: {len(prob_bounds_failures)}")
    print(f"Dice math failures (tol=1e-4): {len(math_failures_dice)}")
    print(f"IoU math failures (tol=1e-4): {len(math_failures_iou)}")
    print(f"Set relation failures (tol=1e-3): {len(math_failures_set_relation)}")

    # Assertions for pass/fail
    assert unique_images == n_images == 60, "Image names are not all unique!"
    assert unique_dices >= 58, "Too many identical DSC values!"
    assert len(pixel_bounds_failures) == 0, f"Pixel bounds violated: {pixel_bounds_failures}"
    assert len(prob_bounds_failures) == 0, f"Prob bounds violated: {prob_bounds_failures}"
    assert len(math_failures_dice) == 0, f"Dice formula mismatches: {math_failures_dice}"
    assert len(math_failures_iou) == 0, f"IoU formula mismatches: {math_failures_iou}"
    assert len(math_failures_set_relation) == 0, f"Set relation mismatches: {math_failures_set_relation}"
    assert mean_dsc_calc > 0.50, f"Mean DSC {mean_dsc_calc} <= 0.50"
    assert abs(mean_dsc_calc - 0.80225) < 0.001, f"Mean DSC {mean_dsc_calc} deviated significantly from expected ~0.80225"

    return {
        "n_images": n_images,
        "mean_dsc": mean_dsc_calc,
        "std_dsc_sample": std_dsc_sample,
        "std_dsc_pop": std_dsc_pop,
        "min_dsc": min_dsc_calc,
        "max_dsc": max_dsc_calc,
        "median_dsc": median_dsc,
        "iqr_dsc": (q25_dsc, q75_dsc),
        "mean_iou": mean_iou_calc,
        "std_iou_sample": std_iou_sample,
        "std_iou_pop": std_iou_pop,
        "min_iou": min_iou_calc,
        "max_iou": max_iou_calc,
        "median_iou": median_iou,
        "iqr_iou": (q25_iou, q75_iou),
        "unique_images": unique_images,
        "unique_dices": unique_dices,
        "unique_ious": unique_ious,
        "unique_preds": unique_preds,
        "unique_gts": unique_gts,
        "unique_inters": unique_inters,
    }


def test_eval_kvasir_seg_metrics_audit():
    res = run_audit("results/corrected_eval_kvasir_seg.json")
    assert res["n_images"] == 60
    assert res["mean_dsc"] > 0.50
    assert abs(res["mean_dsc"] - 0.80225) < 1e-4


if __name__ == "__main__":
    run_audit()
