#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 02:
Dead ImageNet classifier head (~1.025M parameters) instantiated in ViT-Large backbone.

Exit Codes:
  1: Flaw detected (num_classes != 0, creating a dead 1000-class Linear head).
  0: Flaw resolved (num_classes=0 specified, dead head excised).
  2: Configuration or target file error.
"""

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET = REPO_ROOT / "src" / "models" / "chakranet_segmenter.py"


def check_flaw_02(target_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 02 - Dead ImageNet Classifier Head")
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

    create_model_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "create_model":
            keywords = {}
            for kw in node.keywords:
                val = kw.value
                if isinstance(val, ast.Constant):
                    keywords[kw.arg] = val.value
                elif isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub) and isinstance(val.operand, ast.Constant):
                    keywords[kw.arg] = -val.operand.value
                else:
                    keywords[kw.arg] = None
            create_model_calls.append((node.lineno, keywords))

    if not create_model_calls:
        print("[ERROR] No timm.create_model call found in target file.", file=sys.stderr)
        return 2

    lineno, kw_dict = create_model_calls[0]
    num_classes = kw_dict.get("num_classes", None)

    print(f"  - timm.create_model call found at line: {lineno}")
    print(f"  - num_classes argument:                 {num_classes}")

    if num_classes != 0:
        print("\n[FAIL] FLAW 02 DETECTED: num_classes is not 0 (found: " + str(num_classes) + ").")
        print("       timm instantiates a 1000-class Linear(1024, 1000) ImageNet classification head.")
        print("       This wastes 1,025,000 dead parameters (~4.1 MB VRAM/disk) in every checkpoint,")
        print("       inflates the parameter count to 309M, and causes strict state_dict load mismatches.")
        return 1
    else:
        print("\n[PASS] Flaw 02 Resolved: num_classes=0 specified. Dead ImageNet head is excised.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 02 (Dead ImageNet head).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Path to chakranet_segmenter.py (default: {DEFAULT_TARGET})"
    )
    args = parser.parse_args()
    sys.exit(check_flaw_02(args.target_file))


if __name__ == "__main__":
    main()
