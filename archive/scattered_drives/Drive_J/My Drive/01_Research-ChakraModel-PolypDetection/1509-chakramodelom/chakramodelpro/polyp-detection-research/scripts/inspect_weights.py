"""
inspect_weights.py — Step 1: Figure out what architecture is inside your .pth files.

Run this FIRST before anything else. It prints the layer names and shapes
so you know what model class to instantiate for evaluation.

Usage:
    python scripts/inspect_weights.py --checkpoint path/to/chakra_transformer_best.pth
    python scripts/inspect_weights.py --checkpoint path/to/combo1_best.pth

No GPU required. No dataset required.
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

import torch


def classify_architecture(keys: list[str]) -> dict:
    """
    Guess the architecture family from state dict keys.
    Returns a dict with 'family', 'components', 'notes'.
    """
    all_keys = " ".join(keys)
    key_set = set(keys)

    components = []
    family = "Unknown"
    notes = []

    # --- Backbone detection ---
    if any("patch_embed" in k for k in keys):
        components.append("ViT-style patch embedding")
        family = "Vision Transformer (ViT)"
    if any("pvt" in k.lower() or "pyramid_vision" in k.lower() for k in keys):
        components.append("PVT backbone")
        family = "PVT (Pyramid Vision Transformer)"
    if any(k.startswith("layer1") or k.startswith("layer2") for k in keys):
        components.append("ResNet-style conv layers")
        if "ViT" not in family:
            family = "CNN (ResNet-style)"
    if any("hardnet" in k.lower() or "HarD" in k for k in keys):
        components.append("HarDNet block")
        family = "HarDNet"
    if any("efficientnet" in k.lower() or "_blocks." in k for k in keys):
        components.append("EfficientNet blocks")
    if any("swin" in k.lower() for k in keys):
        components.append("Swin Transformer")
        family = "Swin Transformer"

    # --- Detection head (YOLO-style) ---
    if any("detect" in k.lower() or "yolo" in k.lower() or "anchor" in k.lower() for k in keys):
        components.append("Detection head (YOLO-style)")
        notes.append("Has detection head — model outputs bounding boxes, not just masks")
    if any("bbox" in k.lower() or "cls_pred" in k.lower() or "reg_pred" in k.lower() for k in keys):
        components.append("Classification/regression prediction heads")

    # --- Segmentation decoder ---
    if any("decoder" in k for k in keys):
        components.append("Decoder module")
    if any("reverse_attention" in k or "ra" in k.lower() for k in keys):
        components.append("Reverse Attention module (PraNet-style)")
    if any("cpd" in k.lower() or "cascaded" in k.lower() for k in keys):
        components.append("Cascaded Partial Decoder")
    if any("unet" in k.lower() or ("up" in k and "conv" in k) for k in keys):
        components.append("U-Net style decoder")
    if any("transformer" in k.lower() or "attention" in k.lower() for k in keys):
        components.append("Attention / Transformer blocks")

    # --- Hybrid? ---
    has_cnn = any(k.startswith("layer") or "conv" in k for k in keys)
    has_transformer = any("attention" in k or "patch" in k or "mlp" in k for k in keys)
    if has_cnn and has_transformer:
        family = "CNN + Transformer Hybrid"

    return {"family": family, "components": components, "notes": notes}


def print_layer_summary(state_dict: dict, max_rows: int = 60) -> None:
    """Print a grouped summary of layers by prefix."""
    # Group by top-level prefix
    groups = defaultdict(list)
    for key in state_dict.keys():
        prefix = key.split(".")[0]
        groups[prefix].append(key)

    print("\n" + "=" * 70)
    print("LAYER GROUPS (top-level module names)")
    print("=" * 70)
    for prefix, keys in sorted(groups.items()):
        total_params = sum(
            state_dict[k].numel() for k in keys
            if isinstance(state_dict[k], torch.Tensor)
        )
        print(f"  {prefix:40s}  {len(keys):5d} tensors  {total_params/1e6:7.2f}M params")

    print("\n" + "=" * 70)
    print(f"FIRST {min(max_rows, len(state_dict))} LAYER NAMES + SHAPES")
    print("=" * 70)
    for i, (k, v) in enumerate(state_dict.items()):
        if i >= max_rows:
            print(f"  ... ({len(state_dict) - max_rows} more layers not shown)")
            break
        shape_str = str(list(v.shape)) if isinstance(v, torch.Tensor) else str(type(v))
        dtype_str = str(v.dtype) if isinstance(v, torch.Tensor) else ""
        print(f"  {k:55s}  {shape_str}  {dtype_str}")


def main():
    parser = argparse.ArgumentParser(description="Inspect .pth checkpoint architecture")
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="Path to .pth or .pt checkpoint file")
    parser.add_argument("--full", action="store_true",
                        help="Print ALL layer names (can be very long)")
    args = parser.parse_args()

    ckpt_path = Path(args.checkpoint)
    if not ckpt_path.exists():
        print(f"ERROR: File not found: {ckpt_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\nLoading checkpoint: {ckpt_path}")
    print(f"File size: {ckpt_path.stat().st_size / 1e6:.1f} MB")

    # Load on CPU — no GPU needed for inspection
    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=False)

    # Handle different checkpoint formats
    if isinstance(checkpoint, dict):
        # Common keys in saved checkpoints
        if "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
            print("\n[INFO] Found 'state_dict' key — standard Lightning/torchvision format")
            # Print any metadata
            for meta_key in ["epoch", "val_dice", "val_loss", "config", "arch", "model_name"]:
                if meta_key in checkpoint:
                    print(f"[META] {meta_key}: {checkpoint[meta_key]}")
        elif "model" in checkpoint:
            state_dict = checkpoint["model"]
            print("\n[INFO] Found 'model' key")
            for meta_key in ["epoch", "best_score", "optimizer", "scheduler"]:
                if meta_key in checkpoint:
                    val = checkpoint[meta_key]
                    if not isinstance(val, dict):  # skip large dicts
                        print(f"[META] {meta_key}: {val}")
        elif "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
            print("\n[INFO] Found 'model_state_dict' key")
        else:
            # Assume it's a raw state dict
            state_dict = checkpoint
            print("\n[INFO] Raw state dict (no wrapper keys)")
            print(f"[INFO] Top-level keys: {list(checkpoint.keys())[:10]}")
    elif hasattr(checkpoint, "state_dict"):
        # Full model object saved
        state_dict = checkpoint.state_dict()
        print("\n[INFO] Full model object saved (unusual) — extracted state_dict")
    else:
        print(f"\n[ERROR] Unexpected checkpoint format: {type(checkpoint)}")
        sys.exit(1)

    # Count total parameters
    total_params = sum(
        v.numel() for v in state_dict.values()
        if isinstance(v, torch.Tensor)
    )
    trainable_layers = [k for k, v in state_dict.items()
                        if isinstance(v, torch.Tensor) and v.requires_grad]

    print(f"\n{'='*70}")
    print("CHECKPOINT SUMMARY")
    print(f"{'='*70}")
    print(f"  Total layers in state dict : {len(state_dict)}")
    print(f"  Total parameters           : {total_params/1e6:.2f}M  ({total_params:,})")
    print(f"  File size                  : {ckpt_path.stat().st_size / 1e6:.1f} MB")

    # Architecture classification
    keys = list(state_dict.keys())
    arch_info = classify_architecture(keys)

    print(f"\n{'='*70}")
    print("ARCHITECTURE DETECTION")
    print(f"{'='*70}")
    print(f"  Detected family   : {arch_info['family']}")
    print(f"  Components found  :")
    for c in arch_info["components"]:
        print(f"    - {c}")
    if arch_info["notes"]:
        print(f"  Notes:")
        for n in arch_info["notes"]:
            print(f"    ⚠ {n}")

    max_rows = 999 if args.full else 60
    print_layer_summary(state_dict, max_rows=max_rows)

    print(f"\n{'='*70}")
    print("NEXT STEPS")
    print(f"{'='*70}")
    print("  1. Look at the layer names above to identify the model class.")
    print("  2. If you see 'patch_embed' + 'blocks' → it's a ViT-family model.")
    print("  3. If you see 'layer1/2/3/4' → it's ResNet-style.")
    print("  4. If you see both → it's a hybrid.")
    print("  5. Match to your model definition in src/models/ and run benchmark_eval.py.")
    print()


if __name__ == "__main__":
    main()
