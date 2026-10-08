"""
Minimal DDP key-strip verification.
Does NOT instantiate a full model (no timm/HuggingFace download needed).
Tests:
  1. Key stripping correctness on the real 1.24 GB checkpoint
  2. That stripped keys MATCH the expected ChakraNetMicroRefiner key names
  3. A synthetic forward pass on just the decode_head to confirm non-collapse
"""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import torch
import torch.nn as nn
import numpy as np
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
candidate_weights = [
    REPO_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth",
    REPO_ROOT / "weights" / "chakra_transformer_best.pth",
]
WEIGHTS_PATH = next((p for p in candidate_weights if p.exists()), candidate_weights[0])


def main():
    print("=" * 60)
    print("  ChakraNet DDP Fix Minimal Verification")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("  (No timm/HuggingFace download needed)")
    print("=" * 60)

    # --- 1. Load and strip keys ---
    print(f"\n[1/4] Loading checkpoint ({WEIGHTS_PATH.stat().st_size / 1e9:.2f} GB)...")
    sd = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
    print(f"      Raw keys: {len(sd)}")

    sample_raw = list(sd.keys())[:2]
    has_module_prefix = all(k.startswith("module.") for k in sd.keys())
    print(f"      Sample raw: {sample_raw}")
    print(f"      Has DDP 'module.' prefix: {has_module_prefix}")

    # Bug simulation: old code (only strips _orig_mod.)
    sd_buggy = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
    # Fix: strip both prefixes
    sd_fixed = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}

    sample_fixed = list(sd_fixed.keys())[:3]
    print(f"      After fix strip: {sample_fixed}")

    # --- 2. Check expected key names vs actual ---
    print(f"\n[2/4] Key matching check...")
    # ChakraNetMicroRefiner expected top-level key groups
    expected_prefixes = ["backbone.", "decode_head."]
    matched = {p: sum(1 for k in sd_fixed if k.startswith(p)) for p in expected_prefixes}
    for p, count in matched.items():
        status = "OK" if count > 0 else "MISSING"
        print(f"      [{status}] '{p}' keys: {count}")

    buggy_matched = {p: sum(1 for k in sd_buggy if k.startswith(p)) for p in expected_prefixes}
    print(f"      [OLD BUG] backbone. keys matched: {buggy_matched['backbone.']} (should be 0)")
    print(f"      [FIX]     backbone. keys matched: {matched['backbone.']} (should be >200)")

    # --- 3. Test the decode_head weights directly (no backbone needed) ---
    print(f"\n[3/4] Testing decode_head weights for mode collapse signature...")
    # Extract just the decode_head weights
    dh_keys = {k: v for k, v in sd_fixed.items() if k.startswith("decode_head.")}
    print(f"      decode_head keys: {len(dh_keys)}")

    # Build just the decode_head from ChakraNetMicroRefiner (inline, no timm needed)
    # ChakraNetMicroRefiner.decode_head = nn.Sequential(
    #   [0] ConvTranspose2d(1024, 256, 4, stride=4)
    #   [1] BatchNorm2d(256)
    #   [2] ReLU
    #   [3] ConvTranspose2d(256, 64, 4, stride=4)
    #   [4] BatchNorm2d(64)
    #   [5] ReLU
    #   [6] Conv2d(64, 1, 3, padding=1)
    # )
    decode_head = nn.Sequential(
        nn.ConvTranspose2d(1024, 256, kernel_size=4, stride=4),
        nn.BatchNorm2d(256),
        nn.ReLU(inplace=True),
        nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4),
        nn.BatchNorm2d(64),
        nn.ReLU(inplace=True),
        nn.Conv2d(64, 1, kernel_size=3, padding=1),
    )

    # Load only the decode_head weights (strip the "decode_head." prefix for Sequential indexing)
    dh_sd = {k.replace("decode_head.", ""): v for k, v in dh_keys.items()}
    missing, unexpected = decode_head.load_state_dict(dh_sd, strict=False)
    print(f"      Missing keys:    {len(missing)}")
    print(f"      Unexpected keys: {len(unexpected)}")

    # Inspect final conv bias (the mode collapse indicator)
    final_bias = sd_fixed.get("decode_head.6.bias")
    if final_bias is not None:
        bias_val = final_bias.item()
        print(f"      decode_head.6.bias = {bias_val:.6f}")
        print(f"      sigmoid(bias)      = {torch.sigmoid(torch.tensor(bias_val)).item():.6f}")
        in_collapse_zone = 0.49 <= torch.sigmoid(torch.tensor(bias_val)).item() <= 0.51
        print(f"      In collapse zone [0.49,0.51]: {in_collapse_zone}")

    # --- 4. Forward pass through just the decode_head ---
    print(f"\n[4/4] Forward pass through loaded decode_head (no backbone needed)...")
    decode_head.eval()
    outputs = []
    with torch.no_grad():
        for i in range(5):
            # Simulate backbone output: (B, 1024, 24, 24) — what ViT-Large produces
            if i == 0:
                x = torch.randn(1, 1024, 24, 24)
                label = "random_noise"
            elif i == 1:
                x = torch.zeros(1, 1024, 24, 24)
                label = "all_zeros"
            elif i == 2:
                x = torch.ones(1, 1024, 24, 24)
                label = "all_ones"
            elif i == 3:
                x = torch.randn(1, 1024, 24, 24) * 0.1
                label = "small_noise"
            else:
                x = torch.rand(1, 1024, 24, 24) * 4 - 2
                label = "uniform_wide"

            logit = decode_head(x)
            prob = torch.sigmoid(logit).mean().item()
            outputs.append(prob)
            in_zone = "COLLAPSE" if 0.49 <= prob <= 0.51 else "VARIED"
            print(f"      [{in_zone}] {label}: mean_prob={prob:.6f}, logit_range=[{logit.min():.3f}, {logit.max():.3f}]")

    output_std = float(np.std(outputs))
    all_collapsed = all(0.49 <= o <= 0.51 for o in outputs)

    print(f"\n      Output std:     {output_std:.6f}")
    print(f"      All collapsed:  {all_collapsed}")

    # --- Final verdict ---
    print("\n" + "=" * 60)
    if buggy_matched["backbone."] == 0 and matched["backbone."] > 200:
        print("  [OK] KEY STRIPPING FIX CONFIRMED")
        print(f"       Old code loaded: {sum(buggy_matched.values())} matching keys (of {len(sd)})")
        print(f"       New code loads:  {sum(matched.values())} matching keys (of {len(sd_fixed)})")

    if not all_collapsed and len(missing) == 0:
        print("  [PASS] Decode head loaded correctly, no mode collapse")
    elif all_collapsed:
        print("  [FAIL] Decode head still in mode collapse zone")
    else:
        print(f"  [WARN] {len(missing)} missing keys in decode_head — architecture mismatch?")
        print(f"         Missing: {missing}")
    print("=" * 60)


if __name__ == "__main__":
    main()
