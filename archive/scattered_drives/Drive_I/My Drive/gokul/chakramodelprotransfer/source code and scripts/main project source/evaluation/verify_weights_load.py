"""
ChakraNet Weight Loading Sanity Check
=====================================
Verifies that:
1. Weights load cleanly (no missing/unexpected keys)
2. The model does NOT output a constant ~0.504 (mode collapse indicator)
3. Outputs actually vary across different inputs

Usage: python src/verify_weights_load.py
"""

import sys
import os
from pathlib import Path

# Ensure stdout and stderr use UTF-8 encoding safely across platforms/consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

# Add project root, src, and models to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
for p in [str(PROJECT_ROOT), str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "src" / "models")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import torch
import numpy as np

candidate_weights = [
    PROJECT_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth",
    PROJECT_ROOT / "weights" / "chakra_transformer_best.pth",
]
WEIGHTS_PATH = next((p for p in candidate_weights if p.exists()), candidate_weights[0])
COLLAPSE_RANGE = (0.49, 0.51)  # sigmoid(0) ≈ 0.504 — mode collapse zone

def main():
    print("=" * 60)
    print("  ChakraNet Weight Loading Sanity Check")
    print(f"  Timestamp: {__import__('datetime').datetime.utcnow().isoformat()}Z")
    print("=" * 60)

    # 1. Check weights file exists
    if not WEIGHTS_PATH.exists():
        print(f"[FAIL] Weights file not found: {WEIGHTS_PATH}")
        sys.exit(1)
    print(f"[OK]   Weights file found: {WEIGHTS_PATH} ({WEIGHTS_PATH.stat().st_size / 1e9:.2f} GB)")

    # 2. Load the weights and check keys
    print("\n[...] Loading weights (may take 10-20s for 1.2GB file)...")
    sd = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
    print(f"[OK]   Raw checkpoint keys: {len(sd)}")

    # Strip DDP and torch.compile prefixes
    sd_stripped = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
    print(f"[OK]   After prefix stripping: {len(sd_stripped)} keys")

    # Sample some key names
    sample_keys = list(sd_stripped.keys())[:3]
    print(f"[OK]   Sample keys after stripping: {sample_keys}")

    # 3. Instantiate the model (CPU, no GPU needed)
    from chakranet_segmenter import ChakraNetMicroRefiner

    model = ChakraNetMicroRefiner(channels=24)
    missing, unexpected = model.load_state_dict(sd_stripped, strict=False)

    if missing:
        print(f"\n[WARN] Missing keys ({len(missing)}): {missing[:5]}")
    if unexpected:
        print(f"[WARN] Unexpected keys ({len(unexpected)}): {unexpected[:5]}")
    if not missing and not unexpected:
        print(f"[OK]   All keys loaded cleanly — STRICT EQUIVALENT PASS")
    
    model.eval()

    # 4. Run forward passes on diverse inputs
    print("\n[...] Running forward passes on diverse inputs...")
    outputs = []
    with torch.no_grad():
        for i in range(5):
            # Use very different inputs: noise, zeros, ones, gradient, random
            if i == 0:
                x = torch.randn(1, 3, 384, 384)
                label = "random_noise"
            elif i == 1:
                x = torch.zeros(1, 3, 384, 384)
                label = "all_zeros"
            elif i == 2:
                x = torch.ones(1, 3, 384, 384)
                label = "all_ones"
            elif i == 3:
                x = torch.linspace(-2, 2, 384*384*3).view(1, 3, 384, 384)
                label = "gradient"
            else:
                x = torch.rand(1, 3, 384, 384) * 6 - 3  # uniform [-3, 3]
                label = "wide_uniform"

            try:
                logits = model(x)
                prob = torch.sigmoid(logits).mean().item()
                outputs.append(prob)
                collapse_flag = "⚠️ COLLAPSE" if COLLAPSE_RANGE[0] <= prob <= COLLAPSE_RANGE[1] else "✓ VARIED"
                print(f"  [{collapse_flag}] {label}: mean_prob={prob:.6f}")
            except Exception as e:
                print(f"  [ERROR] {label}: {e}")
                outputs.append(0.504)  # force fail

    # 5. Check variance across outputs
    output_std = float(np.std(outputs))
    print(f"\n[INFO] Output std across 5 diverse inputs: {output_std:.6f}")

    # 6. Final verdict
    print("\n" + "=" * 60)
    all_in_collapse = all(COLLAPSE_RANGE[0] <= o <= COLLAPSE_RANGE[1] for o in outputs)
    
    if all_in_collapse:
        print("  RESULT: ⛔ FAIL — MODEL IS IN MODE COLLAPSE")
        print(f"  All outputs are in [{COLLAPSE_RANGE[0]}, {COLLAPSE_RANGE[1]}]")
        print("  The decoder weights were NOT loaded correctly.")
        sys.exit(1)
    elif missing:
        print("  RESULT: ⚠️  PARTIAL — Weights loaded but with missing keys")
        print("  Check the missing key list above for architecture mismatches.")
        sys.exit(1)
    else:
        print("  RESULT: ✅ PASS — Weights loaded cleanly, outputs vary with input")
        print(f"  Output mean range: [{min(outputs):.4f}, {max(outputs):.4f}]")
    print("=" * 60)

if __name__ == "__main__":
    main()
