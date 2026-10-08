import os
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import timm

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print("Testing Combo 6 isolated on device:", device)

from forensic_verifier_suite import extract_defs_from_notebook, build_base_scope

classes, funcs = extract_defs_from_notebook("Combo6_ChakraTransformer.ipynb")
scope = build_base_scope(device)
scope['timm'] = timm

for cname in ['ProgressiveDecoderBlock', 'ChakraTransformerSegmenter', 'DiceFocalLoss', 'ConformalCalibrator']:
    exec(classes[cname], scope)
    
ChakraTransformerSegmenter = scope['ChakraTransformerSegmenter']
ConformalCalibrator = scope['ConformalCalibrator']

print("Instantiating ChakraTransformerSegmenter...")
model = ChakraTransformerSegmenter(backbone_name='vit_base_patch16_384', pretrained=False).to(device)
print("ChakraTransformerSegmenter instantiated.")

x = torch.randn(2, 3, 384, 384, device=device)
print("Running forward pass...")
logits = model(x)
print("Forward pass complete:", logits.shape)

calibrator = ConformalCalibrator(alpha_levels=[0.10, 0.05])
class MockCalDataset:
    def __len__(self): return 4
    def __getitem__(self, idx):
        return torch.randn(3, 384, 384), torch.zeros(1, 384, 384)
        
cal_loader = torch.utils.data.DataLoader(MockCalDataset(), batch_size=2)
print("Running calibration...")
# Make sure dataset has a polyp
class MockCalDatasetWithPolyp:
    def __len__(self): return 4
    def __getitem__(self, idx):
        img = torch.randn(3, 384, 384)
        msk = torch.zeros(1, 384, 384)
        msk[0, 50:150, 50:150] = 1.0
        return img, msk

cal_loader = torch.utils.data.DataLoader(MockCalDatasetWithPolyp(), batch_size=2)
calibrator.calibrate(model, cal_loader, device=device)
print("Calibration complete!")
print("q_hats:", calibrator.q_hats)
