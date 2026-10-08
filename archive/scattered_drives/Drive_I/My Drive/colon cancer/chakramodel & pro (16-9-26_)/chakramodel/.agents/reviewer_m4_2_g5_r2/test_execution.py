import os
import sys
from pathlib import Path
import torch
import numpy as np

# Add src to sys.path
sys.path.insert(0, str(Path("src").resolve()))

from chakranet_segmenter import ChakraNetMicroRefiner, ChakraNet

print("Checking weights file...")
weights_path = Path("weights/chakra_transformer_best.pth")
print(f"Weights path exists: {weights_path.exists()} (size: {weights_path.stat().st_size if weights_path.exists() else 0} bytes)")

if weights_path.exists():
    sd_raw = torch.load(str(weights_path), map_location="cpu")
    print(f"Total keys in raw checkpoint: {len(sd_raw)}")
    module_keys = [k for k in sd_raw.keys() if k.startswith("module.")]
    print(f"Keys starting with 'module.': {len(module_keys)} / {len(sd_raw)}")
    
    # Check old loading logic:
    sd_old = {k.replace("_orig_mod.", ""): v for k, v in sd_raw.items()}
    model_old = ChakraNetMicroRefiner(channels=24)
    missing_old, unexp_old = model_old.load_state_dict(sd_old, strict=False)
    print(f"OLD LOGIC - missing keys: {len(missing_old)}, unexpected: {len(unexp_old)}")
    
    # Check new loading logic:
    sd_new = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd_raw.items()}
    model_new = ChakraNetMicroRefiner(channels=24)
    missing_new, unexp_new = model_new.load_state_dict(sd_new, strict=False)
    print(f"NEW LOGIC - missing keys: {len(missing_new)}, unexpected: {len(unexp_new)}")
    
    # Check forward pass variation:
    torch.manual_seed(42)
    model_new.eval()
    outputs = []
    with torch.no_grad():
        for i in range(5):
            x = torch.randn(1, 3, 224, 224)
            out_mean = torch.sigmoid(model_new(x)).mean().item()
            outputs.append(out_mean)
    
    output_std = float(np.std(outputs))
    output_spread = max(outputs) - min(outputs)
    is_collapsed = all(0.49 <= o <= 0.51 for o in outputs)
    print(f"Forward outputs: {[round(o, 5) for o in outputs]}")
    print(f"Output std: {output_std:.6f}, spread: {output_spread:.6f}, is_collapsed: {is_collapsed}")
    
    # Also test ChakraNet class itself:
    print("\nTesting ChakraNet class initialization...")
    chakra_net = ChakraNet(weights_path=str(weights_path), device="cpu")
    print("ChakraNet initialized successfully.")
