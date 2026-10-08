#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 04:
Dangerous OOM fallback in forward() that calls self.to('cpu').

Exit Codes:
  1: Flaw detected (in-place self.to('cpu') mutation in forward() OOM handler).
  0: Flaw resolved (no in-place device mutation; OOM handled cleanly or re-raised).
  2: Configuration or target file error.
"""

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET = REPO_ROOT / "src" / "models" / "chakranet_segmenter.py"


def check_flaw_04(target_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 04 - In-Place Device Mutation in forward() OOM Handler")
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

    dangerous_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "forward":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "to":
                    # Check if caller is 'self'
                    is_self_call = isinstance(sub.func.value, ast.Name) and sub.func.value.id == "self"
                    if is_self_call:
                        is_cpu = False
                        if len(sub.args) >= 1:
                            first_arg = sub.args[0]
                            if isinstance(first_arg, ast.Constant) and first_arg.value == "cpu":
                                is_cpu = True
                        for kw in sub.keywords:
                            if kw.arg in ("device", None) and isinstance(kw.value, ast.Constant) and kw.value.value == "cpu":
                                is_cpu = True
                        if is_cpu:
                            dangerous_calls.append((sub.lineno, "self.to('cpu')"))

    # Also check via regex/text for any occurrence of self.to('cpu')
    text_has_self_to_cpu = "self.to('cpu')" in source or 'self.to("cpu")' in source

    print(f"  - Scanned forward() methods for self.to('cpu') calls: {dangerous_calls}")
    print(f"  - Direct text match for self.to('cpu'):                {text_has_self_to_cpu}")

    if dangerous_calls or text_has_self_to_cpu:
        print("\n[FAIL] FLAW 04 DETECTED: In-place device mutation self.to('cpu') found in forward() OOM fallback.")
        print("       Mutating shared PyTorch modules during forward() causes multi-threaded race conditions,")
        print("       crashes concurrent streaming servers with device mismatch errors, and conceals OOMs")
        print("       in FPS benchmarks by silently dropping from GPU to CPU.")
        return 1
    else:
        print("\n[PASS] Flaw 04 Resolved: No in-place device mutation in forward(). Safe OOM handling verified.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 04 (OOM fallback self.to('cpu')).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Path to chakranet_segmenter.py (default: {DEFAULT_TARGET})"
    )
    args = parser.parse_args()
    sys.exit(check_flaw_04(args.target_file))


if __name__ == "__main__":
    main()
