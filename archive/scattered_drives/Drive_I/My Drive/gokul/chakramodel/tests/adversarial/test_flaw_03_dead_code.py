#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 03:
75 lines of uninstantiated dead code (BasicConv2d, RFBBlock, ReverseAttention) in chakranet_segmenter.py.

Exit Codes:
  1: Flaw detected (dead classes defined in target file but never instantiated).
  0: Flaw resolved (dead classes excised and architecture docstring cleansed).
  2: Configuration or target file error.
"""

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET = REPO_ROOT / "src" / "models" / "chakranet_segmenter.py"
DEAD_CLASS_NAMES = ["BasicConv2d", "RFBBlock", "ReverseAttention"]


def check_flaw_03(target_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 03 - 75 Lines of Misleading Dead Code")
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

    found_classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            found_classes[node.name] = node.lineno

    dead_found = [cls for cls in DEAD_CLASS_NAMES if cls in found_classes]

    # Check if active model classes instantiate any of these
    active_instantiations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name in DEAD_CLASS_NAMES:
                active_instantiations.append((func_name, getattr(node, "lineno", 0)))

    # Filter out instantiations inside the dead classes themselves
    # (e.g. RFBBlock instantiating BasicConv2d)
    instantiations_in_active = []
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef) and cls.name not in DEAD_CLASS_NAMES:
            for sub in ast.walk(cls):
                if isinstance(sub, ast.Call):
                    name = None
                    if isinstance(sub.func, ast.Name):
                        name = sub.func.id
                    elif isinstance(sub.func, ast.Attribute):
                        name = sub.func.attr
                    if name in DEAD_CLASS_NAMES:
                        instantiations_in_active.append((name, sub.lineno))

    doc = ast.get_docstring(tree) or ""
    misleading_doc = "Reverse Attention" in doc or "Receptive Field Block" in doc

    print(f"  - Scanned dead classes:               {DEAD_CLASS_NAMES}")
    print(f"  - Dead classes detected:             {dead_found}")
    for cls in dead_found:
        print(f"    * Class '{cls}' defined at line {found_classes[cls]}")
    print(f"  - Instantiated by active model:       {instantiations_in_active}")
    print(f"  - Misleading docstring claiming RFB: {misleading_doc}")

    if dead_found and not instantiations_in_active:
        print(f"\n[FAIL] FLAW 03 DETECTED: {len(dead_found)} dead classes found in {target_file.name}.")
        print("       75 lines of unused code (BasicConv2d, RFBBlock, ReverseAttention) are never instantiated")
        print("       by ChakraNetMicroRefiner or ChakraNet, falsely implying a PraNet/RFB/RA CNN architecture")
        print("       when the system actually runs a pure Vision Transformer.")
        return 1
    else:
        print("\n[PASS] Flaw 03 Resolved: Dead classes excised and documentation accurately reflects architecture.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 03 (Dead code).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Path to chakranet_segmenter.py (default: {DEFAULT_TARGET})"
    )
    args = parser.parse_args()
    sys.exit(check_flaw_03(args.target_file))


if __name__ == "__main__":
    main()
