import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"m:\chakramodel\src")))

import torch
import numpy as np
from chakranet_segmenter import ChakraNetMicroRefiner

weights_path = Path(r"m:\chakramodel\weights\chakra_transformer_best.pth")
sd = torch.load(weights_path, map_location="cpu", weights_only=True)
sd_stripped = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}

model = ChakraNetMicroRefiner(channels=24)
missing, unexpected = model.load_state_dict(sd_stripped, strict=False)
print(f"Missing: {len(missing)}, Unexpected: {len(unexpected)}")

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Running test on: {device}")
model = model.to(device)
model.eval()

inputs = [
    ("random_noise", torch.randn(1, 3, 384, 384, device=device)),
    ("all_zeros", torch.zeros(1, 3, 384, 384, device=device)),
    ("all_ones", torch.ones(1, 3, 384, 384, device=device)),
    ("gradient", torch.linspace(-2, 2, 384*384*3, device=device).view(1, 3, 384, 384)),
    ("wide_uniform", torch.rand(1, 3, 384, 384, device=device) * 6 - 3),
]

outputs = []
with torch.no_grad():
    for label, x in inputs:
        logits = model(x)
        prob = torch.sigmoid(logits).mean().item()
        outputs.append(prob)
        min_p = torch.sigmoid(logits).min().item()
        max_p = torch.sigmoid(logits).max().item()
        std_p = torch.sigmoid(logits).std().item()
        print(f"{label}: mean={prob:.6f}, min={min_p:.6f}, max={max_p:.6f}, std={std_p:.6f}")

print("\nSummary across the 5 inputs:")
print(f"Means: {[round(p, 6) for p in outputs]}")
print(f"Mean of means: {np.mean(outputs):.6f}")
print(f"Span of means (max - min): {max(outputs) - min(outputs):.6f}")
print(f"Std of means: {np.std(outputs):.6f}")
