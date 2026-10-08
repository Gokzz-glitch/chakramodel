import os
import sys
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from torch.amp import autocast

sys.path.append(r'm:\chakramodel\notebooks')

with open(r'm:\chakramodel\notebooks\Combo6_ChakraTransformer.ipynb', 'r', encoding='utf-8') as f:
    import json
    nb = json.load(f)

# Extract code from the patched notebook cells
code = ""
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        # Strip training loop execution
        if "# Training Execution Configuration" in source:
            import re
            source = re.sub(r'(?s)# Training Execution Configuration.*?🏆 Training Complete![^\n]*\n', '', source)
        if "# 1. Compute Full Segmentation Performance Metrics on Test Set" in source:
            continue # skip evaluation loop since we only want to run ConformalCalibrator
        if "# ==============================================================================\n# CELL 8" in source:
            break
            
        # Strip the calibration call so it doesn't fail on missing 'model'
        if "calibrator.calibrate(model, CAL_LOADER, device=device)" in source:
            source = source.replace("calibrator.calibrate(model, CAL_LOADER, device=device)", "")
            
        code += source + "\n"

# Fix multiprocessing on Windows for dynamically executed code
code = code.replace("num_workers=4", "num_workers=0")

namespace = {}
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
exec(code, namespace)

device = namespace['device']
TEST_LOADER = namespace['TEST_LOADER']
CAL_LOADER = namespace['CAL_LOADER']
ConformalCalibrator = namespace['ConformalCalibrator']
ChakraTransformerSegmenter = namespace['ChakraTransformerSegmenter']

model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=False).to(device)

weights_path = r'm:\chakramodel\weights\chakra_transformer_vit_large_best (1).pth'
if not os.path.exists(weights_path):
    weights_path = r'm:\chakramodel\weights\chakra_transformer_best.pth'
    
model.load_state_dict(torch.load(weights_path, map_location=device))
model.eval()

print("\n--- Testing Option B Calibration ---")
calibrator = ConformalCalibrator(alpha_levels=[0.10, 0.05], failure_iou_threshold=0.1)
calibrator.calibrate(model, CAL_LOADER, device=device)

print("\n--- Verifying Test Set Coverage & Failure Rates ---")
summary = calibrator.evaluate_test_coverage(model, TEST_LOADER, device=device)

print("\nResults:")
for alpha, stat in summary.items():
    print(f"Alpha = {alpha:0.2f}")
    print(f"  Target Coverage:      {stat['target_coverage']}%")
    print(f"  Empirical Coverage:   {stat['empirical_coverage']:.2f}% (on successful detections)")
    print(f"  Detection Failures:   {stat['failure_rate']:.1f}%")
    print(f"  Mean Safety Band:     {stat['mean_band_pct']:.1f}% of frame (Tightened!)")
