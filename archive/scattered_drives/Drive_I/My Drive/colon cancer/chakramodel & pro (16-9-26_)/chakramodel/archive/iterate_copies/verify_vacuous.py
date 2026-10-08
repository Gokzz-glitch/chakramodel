import os
import sys
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from torch.amp import autocast
import matplotlib.pyplot as plt

sys.path.append(r'm:\chakramodel\notebooks')

with open(r'm:\chakramodel\notebooks\Combo6_ChakraTransformer.py', 'r', encoding='utf-8') as f:
    code = f.read()

import re
code = re.sub(r'(?s)# Training Execution Configuration.*?🏆 Training Complete![^\n]*\n', '', code)
code = re.sub(r'(?s)# Execute Split-Conformal Calibration.*', '', code)

namespace = {}
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
exec(code, namespace)

device = namespace['device']
TEST_LOADER = namespace['TEST_LOADER']
CAL_LOADER = namespace['CAL_LOADER']
ConformalCalibrator = namespace['ConformalCalibrator']
ChakraTransformerSegmenter = namespace['ChakraTransformerSegmenter']

# Re-instantiate model that was stripped
model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=False).to(device)

weights_path = r'm:\chakramodel\weights\chakra_transformer_vit_large_best (1).pth'
if not os.path.exists(weights_path):
    weights_path = r'm:\chakramodel\weights\chakra_transformer_best.pth'
    
model.load_state_dict(torch.load(weights_path, map_location=device))
model.eval()

print("--- STEP 1: Vacuous Mask Confirmation ---")
calibrator = ConformalCalibrator(alpha_levels=[0.10, 0.05])
calibrator.calibrate(model, CAL_LOADER, device=device)

outer_fracs = {alpha: [] for alpha in calibrator.alpha_levels}
with torch.no_grad():
    for imgs, masks in TEST_LOADER:
        imgs = imgs.to(device, non_blocking=True)
        with autocast(device_type='cuda', dtype=torch.float16):
            logits = model(imgs)
        probs = torch.sigmoid(logits).cpu().numpy()
        for b in range(probs.shape[0]):
            for alpha in calibrator.alpha_levels:
                _, outer, _ = calibrator.predict_conformal_bands(probs[b,0], alpha=alpha)
                outer_fracs[alpha].append(outer.mean())

for alpha, fracs in outer_fracs.items():
    print(f"Alpha={alpha}: mean outer-band area = {np.mean(fracs)*100:.1f}% of frame")


print("\n--- STEP 2: Worst Image Analysis ---")
taus = np.linspace(0.0, 1.0, 1000)
risk_matrix = []
cal_files = CAL_LOADER.dataset.file_paths

with torch.no_grad():
    for imgs, masks in CAL_LOADER:
        imgs = imgs.to(device, non_blocking=True)
        with autocast(device_type='cuda', dtype=torch.float16):
            logits = model(imgs)
        probs = torch.sigmoid(logits).cpu().numpy()
        masks_np = masks.numpy()

        for b in range(probs.shape[0]):
            p_map = probs[b, 0]
            gt_map = (masks_np[b, 0] > 0.5)

            if gt_map.sum() > 0:
                true_p = p_map[gt_map]
                sorted_p = np.sort(true_p)
                counts = np.searchsorted(sorted_p, taus)
                r_i = counts / len(true_p)
                risk_matrix.append(r_i)
            else:
                risk_matrix.append(np.zeros_like(taus))

risk_matrix = np.array(risk_matrix)
mean_risk_per_image = risk_matrix.mean(axis=1)
worst_idx = np.argsort(-mean_risk_per_image)[:15]

print("Worst calibration image indices:", worst_idx)
print("Files dragging tau down:")
for i in worst_idx:
    print(f"Index {i}: {cal_files[i].name} (Mean Risk: {mean_risk_per_image[i]:.4f})")
