import sys
from pathlib import Path
import torch
import numpy as np

sys.path.append(str(Path("src").resolve()))
from chakranet_segmenter import ChakraNetMicroRefiner

model = ChakraNetMicroRefiner(channels=24)
sd_raw = torch.load("weights/chakra_transformer_best.pth", map_location="cpu")
sd_stripped = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd_raw.items()}
missing, unexpected = model.load_state_dict(sd_stripped, strict=False)

print("Load successful. Now testing x = torch.randn(1, 3, 224, 224)...")
try:
    x = torch.randn(1, 3, 224, 224)
    out = model(x)
    print("Success with 224x224:", out.shape)
except Exception as e:
    print(f"FAILED with 224x224: {type(e).__name__}: {e}")

print("Now testing x = torch.randn(1, 3, 384, 384)...")
try:
    x = torch.randn(1, 3, 384, 384)
    out = model(x)
    print("Success with 384x384:", out.shape)
    outputs = []
    with torch.no_grad():
        for _ in range(3):
            x = torch.randn(1, 3, 384, 384)
            outputs.append(torch.sigmoid(model(x)).mean().item())
    print("Outputs with 384x384:", outputs)
    output_spread = max(outputs) - min(outputs)
    print("Spread:", output_spread)
except Exception as e:
    print(f"FAILED with 384x384: {type(e).__name__}: {e}")
