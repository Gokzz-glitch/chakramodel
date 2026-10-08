import sys
from pathlib import Path
import torch
import torch.nn as nn

# Let's inspect src/models/chakranet_segmenter.py
# If we pass state_dict with 'module.' prefix to a model that does not strip it,
# or if someone passes weights where strict=False silently ignores all keys:

class SimpleModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv2d(3, 16, 3, padding=1)
        self.head = nn.Linear(16, 1)

model = SimpleModel()
original_sd = model.state_dict()

# Simulate DDP wrapped state dict
ddp_sd = {f"module.{k}": v for k, v in original_sd.items()}

# Test what happens with strict=False and no assertions
missing, unexpected = model.load_state_dict(ddp_sd, strict=False)

print(f"Total model keys: {len(original_sd)}")
print(f"Loaded keys matching: {len(original_sd) - len(missing)}")
print(f"Missing keys: {len(missing)}")
print(f"Unexpected keys: {len(unexpected)}")
print(f"Did PyTorch raise error? No! Silent failure!")
