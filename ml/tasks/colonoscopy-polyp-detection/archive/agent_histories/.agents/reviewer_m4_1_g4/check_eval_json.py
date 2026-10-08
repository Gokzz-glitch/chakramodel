import json
import math

with open('results/corrected_eval_kvasir_seg.json', 'r') as f:
    data = json.load(f)

required_keys = ['mean_dsc', 'mean_iou', 'n_images', 'timestamp', 'model_path', 'weight_loading_status']
for k in required_keys:
    assert k in data, f"Missing required key {k}"
    print(f"Key present: {k} = {data[k]}")

per_img = data['per_image_results']
assert len(per_img) == data['n_images'], f"Expected {data['n_images']} items, got {len(per_img)}"
print(f"Total per-image results: {len(per_img)}")

dices = []
ious = []
mismatches = []
for i, item in enumerate(per_img):
    pred = item['pred_pixels']
    gt = item['gt_pixels']
    inter = item['intersection_pixels']
    calc_dice = (2.0 * inter) / (pred + gt) if (pred + gt) > 0 else 1.0
    calc_iou = inter / (pred + gt - inter) if (pred + gt - inter) > 0 else 1.0
    
    if abs(calc_dice - item['dice']) > 1e-4:
        mismatches.append(f"Img {i} Dice mismatch: {item['dice']} vs {calc_dice}")
    if abs(calc_iou - item['iou']) > 1e-4:
        mismatches.append(f"Img {i} IoU mismatch: {item['iou']} vs {calc_iou}")
    dices.append(item['dice'])
    ious.append(item['iou'])

calc_mean_dsc = sum(dices) / len(dices)
calc_mean_iou = sum(ious) / len(ious)
print(f"Calculated mean_dsc: {calc_mean_dsc:.6f} vs JSON {data['mean_dsc']}")
print(f"Calculated mean_iou: {calc_mean_iou:.6f} vs JSON {data['mean_iou']}")
assert abs(calc_mean_dsc - data['mean_dsc']) < 1e-4
assert abs(calc_mean_iou - data['mean_iou']) < 1e-4
print("Pixel counts and metrics verification: " + ("PASS" if not mismatches else f"FAIL: {len(mismatches)} mismatches"))
