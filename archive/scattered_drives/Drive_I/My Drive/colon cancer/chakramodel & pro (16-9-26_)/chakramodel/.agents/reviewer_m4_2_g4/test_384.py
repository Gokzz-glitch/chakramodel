import os
import sys
import torch
import numpy as np
from pathlib import Path

# Add src to path
sys.path.append(r"m:\chakramodel\src")

weights_path = Path(r"m:\chakramodel\weights\chakra_transformer_best.pth")
sd_raw = torch.load(str(weights_path), map_location="cpu", weights_only=True)

sd_stripped = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd_raw.items()}

from chakranet_segmenter import ChakraNetMicroRefiner
model = ChakraNetMicroRefiner(channels=24)
missing, unexpected = model.load_state_dict(sd_stripped, strict=False)
print(f"Loaded with missing: {len(missing)}, unexpected: {len(unexpected)}")

model.eval()
torch.manual_seed(42)
outputs = []
with torch.no_grad():
    for _ in range(3):
        x = torch.randn(1, 3, 384, 384)
        outputs.append(torch.sigmoid(model(x)).mean().item())

output_std = float(np.std(outputs))
output_spread = max(outputs) - min(outputs) if outputs else 0.0
is_collapsed = all(0.49 <= o <= 0.51 for o in outputs)
print(f"Output std: {output_std:.6f}, spread: {output_spread:.6f}, outputs: {outputs}")
print(f"Is collapsed: {is_collapsed}")
if not is_collapsed and len(missing) == 0 and output_spread > 0.001:
    print("STATUS: PASS")
else:
    print("STATUS: FAIL")
