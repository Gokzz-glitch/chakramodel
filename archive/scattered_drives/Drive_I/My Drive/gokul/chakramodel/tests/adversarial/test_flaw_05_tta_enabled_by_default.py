#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 05:
Test-Time Augmentation (TTA) enabled by default in inference methods.

Exit Codes:
  1: Flaw detected (TTA defaults to True, silently running 3-pass ensembling).
  0: Flaw resolved (TTA defaults to False, enforcing honest single-pass baseline).
  2: Configuration or target file error.
"""

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET = REPO_ROOT / "src" / "models" / "chakranet_segmenter.py"


def check_flaw_05(target_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 05 - Test-Time Augmentation (TTA) Default State")
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

    tta_defaults = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "getattr":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == "use_tta":
                default_val = node.args[2].value if len(node.args) >= 3 and isinstance(node.args[2], ast.Constant) else None
                tta_defaults.append((node.lineno, default_val))

    has_true_default = any(val is True for _, val in tta_defaults)

    # Check ChakraNet.__init__ for explicit use_tta parameter
    init_has_use_tta_false = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ChakraNet":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    arg_defaults = {}
                    # Check positional arguments with defaults (zip from right)
                    pos_args = item.args.args
                    defaults = item.args.defaults
                    if defaults:
                        for a, d in zip(pos_args[-len(defaults):], defaults):
                            arg_defaults[a.arg] = d

                    # Check keyword-only arguments with defaults
                    kwonlyargs = getattr(item.args, "kwonlyargs", [])
                    kw_defaults = getattr(item.args, "kw_defaults", [])
                    for kw_arg, kw_def in zip(kwonlyargs, kw_defaults):
                        if kw_def is not None:
                            arg_defaults[kw_arg.arg] = kw_def

                    if "use_tta" in arg_defaults:
                        def_node = arg_defaults["use_tta"]
                        if isinstance(def_node, ast.Constant) and def_node.value is False:
                            init_has_use_tta_false = True

    print(f"  - Scanned getattr(self, 'use_tta', ...) calls: {tta_defaults}")
    print(f"  - ChakraNet.__init__ has use_tta=False default:   {init_has_use_tta_false}")

    if has_true_default or not init_has_use_tta_false:
        print("\n[FAIL] FLAW 05 DETECTED: TTA is enabled by default in inference methods.")
        print("       getattr(self, 'use_tta', True) triggers 3 forward passes per ROI,")
        print("       tripling latency (3x compute penalty) and conflating multi-pass ensemble metrics")
        print("       with single-pass baseline model scores.")
        return 1
    else:
        print("\n[PASS] Flaw 05 Resolved: TTA defaults to False. Baseline single-pass evaluation is enforced.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 05 (TTA enabled by default).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Path to chakranet_segmenter.py (default: {DEFAULT_TARGET})"
    )
    args = parser.parse_args()
    sys.exit(check_flaw_05(args.target_file))


if __name__ == "__main__":
    main()
