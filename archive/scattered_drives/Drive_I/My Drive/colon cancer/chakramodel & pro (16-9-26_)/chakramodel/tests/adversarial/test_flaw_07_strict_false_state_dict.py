#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 07:
strict=False in load_state_dict() without key assertions (silently loads 0/312 keys on prefix mismatch).

Clinical & Statistical Risk:
  Silently runs inference on uninitialized Gaussian random weights when DDP/module prefixes mismatch,
  collapsing Dice to 0.1835 (blank-mask output) and missing 100% of polyps intraoperatively.

Exit Codes:
  1: Flaw detected (strict=False used without raising RuntimeError / asserting empty missing/unexpected keys).
  0: Flaw resolved (strict key matching enforced; missing/unexpected keys raise fatal RuntimeError).
  2: Configuration or target file error.
"""

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET = REPO_ROOT / "src" / "models" / "chakranet_segmenter.py"


def check_flaw_07(target_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 07 - Unchecked strict=False in load_state_dict()")
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

    # Track all load_state_dict calls and their enclosing function/method scope
    class ScopeTracker(ast.NodeVisitor):
        def __init__(self):
            self.current_scope = None  # None indicates module-level scope
            self.calls = []

        def visit_FunctionDef(self, node):
            prev = self.current_scope
            self.current_scope = node
            self.generic_visit(node)
            self.current_scope = prev

        def visit_AsyncFunctionDef(self, node):
            prev = self.current_scope
            self.current_scope = node
            self.generic_visit(node)
            self.current_scope = prev

        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "load_state_dict":
                strict_val = True  # default in PyTorch
                for kw in node.keywords:
                    if kw.arg == "strict":
                        if isinstance(kw.value, ast.Constant):
                            strict_val = kw.value.value
                self.calls.append({
                    "node": node,
                    "scope": self.current_scope,
                    "scope_name": getattr(self.current_scope, "name", "<module>"),
                    "lineno": node.lineno,
                    "strict_val": strict_val
                })
            self.generic_visit(node)

    tracker = ScopeTracker()
    tracker.visit(tree)

    unguarded_calls = []
    for call_info in tracker.calls:
        if call_info["strict_val"] is False:
            scope_node = call_info["scope"] or tree

            # Determine target variables assigned from this load_state_dict call within the scope
            target_vars = set()
            for sub in ast.walk(scope_node):
                if isinstance(sub, ast.Assign):
                    assigns_call = any(val is call_info["node"] for val in ast.walk(sub.value))
                    if assigns_call:
                        for tgt in sub.targets:
                            if isinstance(tgt, (ast.Tuple, ast.List)):
                                for elt in tgt.elts:
                                    if isinstance(elt, ast.Name):
                                        target_vars.add(elt.id)
                            elif isinstance(tgt, ast.Name):
                                target_vars.add(tgt.id)

            # Check if this enclosing function/method body raises or asserts on mismatch
            has_guard = False
            for sub in ast.walk(scope_node):
                if isinstance(sub, ast.If):
                    test_names = {n.id for n in ast.walk(sub.test) if isinstance(n, ast.Name)}
                    test_str = ast.unparse(sub.test)
                    cond_matches = (
                        bool(test_names & target_vars)
                        or "missing" in test_str
                        or "unexpected" in test_str
                    )
                    if cond_matches:
                        for stmt in ast.walk(sub):
                            if isinstance(stmt, (ast.Raise, ast.Assert)):
                                has_guard = True
                                break
                elif isinstance(sub, ast.Assert):
                    test_names = {n.id for n in ast.walk(sub.test) if isinstance(n, ast.Name)}
                    test_str = ast.unparse(sub.test)
                    if bool(test_names & target_vars) or "missing" in test_str or "unexpected" in test_str:
                        has_guard = True
                        break

            if not has_guard:
                unguarded_calls.append(call_info)

    load_state_dict_sites = [(c["lineno"], c["strict_val"]) for c in tracker.calls]
    unguarded_sites = [(c["lineno"], c["scope_name"]) for c in unguarded_calls]

    print(f"  - Scanned load_state_dict() calls: {load_state_dict_sites}")
    print(f"  - Unguarded strict=False calls:    {unguarded_sites}")

    if unguarded_calls:
        print("\n[FAIL] FLAW 07 DETECTED: load_state_dict() uses strict=False without raising on key mismatch.")
        for c in unguarded_calls:
            print(f"       Line {c['lineno']} in {c['scope_name']} lacks mismatch exception/assertion.")
        print("       When DDP 'module.' prefixes mismatch, 0/312 keys load silently and the model runs")
        print("       with completely uninitialized random weights (Dice collapses to 0.1835 blank masks).")
        return 1
    else:
        print("\n[PASS] Flaw 07 Resolved: Strict key validation is enforced on checkpoint loading.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 07 (Unchecked strict=False).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Path to chakranet_segmenter.py (default: {DEFAULT_TARGET})"
    )
    args = parser.parse_args()
    sys.exit(check_flaw_07(args.target_file))


if __name__ == "__main__":
    main()
