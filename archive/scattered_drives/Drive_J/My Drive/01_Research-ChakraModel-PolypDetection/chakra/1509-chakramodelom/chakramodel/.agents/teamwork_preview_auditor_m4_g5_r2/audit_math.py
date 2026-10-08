import json
import numpy as np

json_path = 'results/corrected_eval_kvasir_seg.json'
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

per_image = data.get('per_image_results', [])
n = len(per_image)
print(f"Total per_image items: {n}")
print(f"Header n_images: {data.get('n_images')}")

dices = [x['dice'] for x in per_image]
ious = [x['iou'] for x in per_image]

mean_dsc = float(np.mean(dices))
mean_iou = float(np.mean(ious))
std_dsc = float(np.std(dices))
std_iou = float(np.std(ious))
min_dsc = float(np.min(dices))
max_dsc = float(np.max(dices))
min_iou = float(np.min(ious))
max_iou = float(np.max(ious))

print(f"Reported mean_dsc: {data.get('mean_dsc')}")
print(f"Calculated mean_dsc: {mean_dsc:.6f} (diff: {abs(data.get('mean_dsc') - mean_dsc):.6e})")

print(f"Reported mean_iou: {data.get('mean_iou')}")
print(f"Calculated mean_iou: {mean_iou:.6f} (diff: {abs(data.get('mean_iou') - mean_iou):.6e})")

if 'metrics_summary' in data:
    ms = data['metrics_summary']
    print("\nMetrics summary verification:")
    for k, calc in [
        ('mean_dsc', mean_dsc),
        ('std_dsc', std_dsc),
        ('min_dsc', min_dsc),
        ('max_dsc', max_dsc),
        ('mean_iou', mean_iou),
        ('std_iou', std_iou),
        ('min_iou', min_iou),
        ('max_iou', max_iou)
    ]:
        rep = ms.get(k)
        diff = abs(rep - calc)
        status = "MATCH" if diff < 1e-4 else "MISMATCH"
        print(f"  {k:10s} reported={rep:<10} calc={calc:<10.6f} diff={diff:.6e} [{status}]")

# Check pixel calculations
print("\nPixel-level formula verification across all items:")
mismatches = 0
for idx, item in enumerate(per_image):
    if 'pred_pixels' in item and 'gt_pixels' in item and 'intersection_pixels' in item:
        p = item['pred_pixels']
        g = item['gt_pixels']
        inter = item['intersection_pixels']
        calc_dsc = (2.0 * inter + 1e-6) / (p + g + 1e-6)
        calc_iou = (inter + 1e-6) / (p + g - inter + 1e-6)
        diff_d = abs(item['dice'] - calc_dsc)
        diff_i = abs(item['iou'] - calc_iou)
        if diff_d > 1e-4 or diff_i > 1e-4:
            print(f"  Mismatch item {idx} ({item['image']}): dice={item['dice']} vs calc={calc_dsc}, iou={item['iou']} vs calc={calc_iou}")
            mismatches += 1

print(f"Pixel calculation check completed. Mismatches: {mismatches} / {len(per_image)}")
