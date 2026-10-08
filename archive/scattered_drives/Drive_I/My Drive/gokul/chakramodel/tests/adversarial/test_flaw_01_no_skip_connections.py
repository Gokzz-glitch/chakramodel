#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 01:
No skip connections in the decoder — finest detail is restricted to 16x16 pixels.

Exit Codes:
  1: Flaw detected (decoder lacks multi-scale skip connections, bottleneck tokens only).
  0: Flaw resolved (multi-scale skip connections present in decoder).
  2: Configuration or target file error.
"""

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET = REPO_ROOT / "src" / "models" / "chakranet_segmenter.py"


def check_flaw_01(target_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 01 - Decoder Skip Connections")
    print(f"Target File: {target_file}")
    print("=" * 75)

    if not target_file.exists():
        print(f"[ERROR] Target file not found: {target_file}", file=sys.stderr)
        return 2

    source = target_file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(target_file))
    except Exception as err:
        print(f"[ERROR] Failed to parse target file AST: {err}", file=sys.stderr)
        return 2

    micro_refiner = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ChakraNetMicroRefiner":
            micro_refiner = node
            break

    if micro_refiner is None:
        print("[ERROR] Class ChakraNetMicroRefiner not found in AST.", file=sys.stderr)
        return 2

    has_skip_modules = False
    has_intermediate_hooks = False

    for sub in ast.walk(micro_refiner):
        if isinstance(sub, ast.Assign):
            for target in sub.targets:
                if isinstance(target, ast.Attribute) and target.attr in (
                    "skip_convs", "lateral_convs", "skips", "up1", "up2", "skip_layers"
                ):
                    has_skip_modules = True
        if isinstance(sub, ast.FunctionDef) and sub.name == "forward":
            forward_source = ast.unparse(sub)
            if any(term in forward_source for term in [
                "skip", "intermediate", "lateral", "blocks[", "extract_features", "skip_convs"
            ]):
                has_intermediate_hooks = True

    is_naive_sequential = False
    for sub in ast.walk(micro_refiner):
        if isinstance(sub, ast.Assign):
            for target in sub.targets:
                if isinstance(target, ast.Attribute) and target.attr == "decode_head":
                    if isinstance(sub.value, ast.Call) and getattr(sub.value.func, "attr", "") == "Sequential":
                        first_arg = sub.value.args[0] if sub.value.args else None
                        if first_arg and getattr(first_arg.func, "attr", "") == "ConvTranspose2d":
                            is_naive_sequential = True

    print(f"  - Naive single-stream Sequential decode_head: {is_naive_sequential}")
    print(f"  - Dedicated skip connection modules:        {has_skip_modules}")
    print(f"  - Intermediate backbone feature extraction:  {has_intermediate_hooks}")

    if (is_naive_sequential or not has_skip_modules) and not has_intermediate_hooks:
        print("\n[FAIL] FLAW 01 DETECTED: ChakraNetMicroRefiner decoder has NO skip connections.")
        print("       Finest spatial detail is restricted to 16x16 pixel patch tokens (24x24 bottleneck).")
        print("       High-frequency mucosal boundaries and small polyps (<16px) vanish or are hallucinated.")
        return 1
    else:
        print("\n[PASS] Flaw 01 Resolved: Multi-scale skip connections are present in the decoder.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 01 (No skip connections).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Path to chakranet_segmenter.py (default: {DEFAULT_TARGET})"
    )
    args = parser.parse_args()
    sys.exit(check_flaw_01(args.target_file))


if __name__ == "__main__":
    main()
