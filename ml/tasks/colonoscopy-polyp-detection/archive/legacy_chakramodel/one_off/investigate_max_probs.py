import os
import sys
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from torch.amp import autocast

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
ChakraTransformerSegmenter = namespace['ChakraTransformerSegmenter']

model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=False).to(device)

weights_path = r'm:\chakramodel\weights\chakra_transformer_vit_large_best (1).pth'
if not os.path.exists(weights_path):
    weights_path = r'm:\chakramodel\weights\chakra_transformer_best.pth'
    
model.load_state_dict(torch.load(weights_path, map_location=device))
model.eval()

print("\n--- Investigating Max Probabilities ---")
cal_files = CAL_LOADER.dataset.file_paths

max_probs = []
with torch.no_grad():
    for imgs, masks in CAL_LOADER:
        imgs = imgs.to(device, non_blocking=True)
        with autocast(device_type='cuda', dtype=torch.float16):
            logits = model(imgs)
        probs = torch.sigmoid(logits).cpu().numpy()

        for b in range(probs.shape[0]):
            max_probs.append(probs[b, 0].max())

max_probs = np.array(max_probs)
# We know the worst indices from the previous run:
worst_idx = [35, 99, 26, 94, 56, 90, 95, 47, 32, 44, 59, 27, 33, 79, 72]

for i in worst_idx:
    print(f"Index {i}: {cal_files[i].name} (Max Prob: {max_probs[i]:.4f})")
    
# Let's see the overall distribution of max probabilities
print("\nMax Prob Percentiles across Calibration Set:")
for p in [0, 1, 5, 10, 25, 50, 75, 100]:
    print(f"{p}th percentile: {np.percentile(max_probs, p):.4f}")
