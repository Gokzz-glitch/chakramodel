import json
import numpy as np
from pathlib import Path

json_path = Path("m:/chakramodel/results/corrected_eval_kvasir_seg.json")
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("--- Top Level Keys ---")
print(list(data.keys()))

required_top_keys = {"mean_dsc", "mean_iou", "n_images", "timestamp", "model_path", "weight_loading_status"}
assert required_top_keys.issubset(set(data.keys())), f"Missing top keys: {required_top_keys - set(data.keys())}"

n_images = data["n_images"]
per_image = data["per_image_results"]
print(f"n_images: {n_images}, len(per_image_results): {len(per_image)}")
assert n_images == 60, f"Expected 60 images, got {n_images}"
assert len(per_image) == 60, f"Expected 60 per-image entries, got {len(per_image)}"

dices = [entry["dice"] for entry in per_image]
ious = [entry["iou"] for entry in per_image]

mean_dsc_calc = float(np.mean(dices))
mean_iou_calc = float(np.mean(ious))
std_dsc_calc = float(np.std(dices))
std_iou_calc = float(np.std(ious))
min_dsc_calc = float(np.min(dices))
max_dsc_calc = float(np.max(dices))
min_iou_calc = float(np.min(ious))
max_iou_calc = float(np.max(ious))

print(f"Reported mean_dsc: {data['mean_dsc']}, Calculated: {mean_dsc_calc:.6f}")
print(f"Reported mean_iou: {data['mean_iou']}, Calculated: {mean_iou_calc:.6f}")
assert abs(data["mean_dsc"] - mean_dsc_calc) < 1e-4, "mean_dsc mismatch"
assert abs(data["mean_iou"] - mean_iou_calc) < 1e-4, "mean_iou mismatch"
assert data["mean_dsc"] > 0.50, f"mean_dsc {data['mean_dsc']} is not > 0.50"

# Check math on each per-image entry
filenames = set()
math_errors = 0
for idx, entry in enumerate(per_image):
    fname = entry["image"]
    assert fname not in filenames, f"Duplicate filename found: {fname}"
    filenames.add(fname)
    
    pred_p = entry["pred_pixels"]
    gt_p = entry["gt_pixels"]
    inter_p = entry["intersection_pixels"]
    
    # Calculate expected dice & iou
    if pred_p + gt_p > 0:
        expected_dice = (2.0 * inter_p) / (pred_p + gt_p)
        expected_iou = inter_p / (pred_p + gt_p - inter_p) if (pred_p + gt_p - inter_p) > 0 else 0.0
    else:
        expected_dice = 1.0 if inter_p == 0 else 0.0
        expected_iou = 1.0 if inter_p == 0 else 0.0
        
    diff_dice = abs(entry["dice"] - expected_dice)
    diff_iou = abs(entry["iou"] - expected_iou)
    
    if diff_dice > 1e-4 or diff_iou > 1e-4:
        print(f"Math discrepancy in entry {idx} ({fname}): dice {entry['dice']} vs {expected_dice}, iou {entry['iou']} vs {expected_iou}")
        math_errors += 1

print(f"Math errors count: {math_errors}")
assert math_errors == 0, f"Encountered {math_errors} math discrepancies!"

print("ALL EVAL CHECKS PASSED PERFECTLY!")
