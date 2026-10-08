import os
import sys
import torch
import numpy as np
from pathlib import Path

# Add src to path
sys.path.append(r"m:\chakramodel\src")

weights_path = Path(r"m:\chakramodel\weights\chakra_transformer_best.pth")
assert weights_path.exists(), f"Weights path does not exist: {weights_path}"

sd_raw = torch.load(str(weights_path), map_location="cpu", weights_only=True)
print(f"Raw checkpoint keys count: {len(sd_raw)}")

# Check key prefix distribution
module_keys = [k for k in sd_raw.keys() if k.startswith("module.")]
backbone_keys = [k for k in sd_raw.keys() if "backbone" in k]
decode_head_keys = [k for k in sd_raw.keys() if "decode_head" in k]
print(f"Keys starting with 'module.': {len(module_keys)}/{len(sd_raw)}")
print(f"Backbone keys count: {len(backbone_keys)}")
print(f"Decode head keys count: {len(decode_head_keys)}")

# Check module.decode_head.6.bias
bias_val = None
if "module.decode_head.6.bias" in sd_raw:
    bias_tensor = sd_raw["module.decode_head.6.bias"]
    bias_val = bias_tensor.item() if bias_tensor.numel() == 1 else bias_tensor[0].item()
    print(f"module.decode_head.6.bias: {bias_val:.6f}")

# Check num_batches_tracked
batches_tracked = [v.item() for k, v in sd_raw.items() if "num_batches_tracked" in k]
if batches_tracked:
    print(f"Sample num_batches_tracked: {batches_tracked[0]}")

# Strip prefixes
sd_stripped = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd_raw.items()}
print(f"Stripped keys count: {len(sd_stripped)}")

# Import ChakraNetMicroRefiner
from chakranet_segmenter import ChakraNetMicroRefiner
model = ChakraNetMicroRefiner(channels=24)
missing, unexpected = model.load_state_dict(sd_stripped, strict=False)
print(f"Missing keys: {len(missing)}, Unexpected keys: {len(unexpected)}")

# Model forward pass output spread
model.eval()
torch.manual_seed(42)
outputs = []
with torch.no_grad():
    for _ in range(5):
        x = torch.randn(1, 3, 224, 224)
        outputs.append(torch.sigmoid(model(x)).mean().item())

output_std = float(np.std(outputs))
output_spread = max(outputs) - min(outputs) if outputs else 0.0
is_collapsed = all(0.49 <= o <= 0.51 for o in outputs)
print(f"Output std: {output_std:.6f}, spread: {output_spread:.6f}, outputs: {outputs}")
print(f"Is collapsed (all in [0.49, 0.51]): {is_collapsed}")
