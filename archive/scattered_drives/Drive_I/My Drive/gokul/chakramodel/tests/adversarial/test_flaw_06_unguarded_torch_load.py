#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 06:
Unguarded torch.load() calls across the codebase without weights_only=True.

Security Risk:
  Arbitrary Code Execution (ACE) via unpickling untrusted serialized checkpoints (CWE-502).

Exit Codes:
  1: Flaw detected (one or more torch.load() calls lack weights_only=True).
  0: Flaw resolved (all torch.load() calls explicitly specify weights_only=True).
  2: Configuration or target error.
"""

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def scan_ast_for_torch_load_violations(file_path: Path, tree: ast.AST) -> list[tuple[Path, int]]:
    violations = []
    torch_modules = {"torch"}
    torch_load_funcs = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "torch" and alias.asname:
                    torch_modules.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "torch" or node.module.startswith("torch.")):
                for alias in node.names:
                    if alias.name == "load":
                        torch_load_funcs.add(alias.asname or alias.name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            is_torch_load = False
            if isinstance(node.func, ast.Attribute) and node.func.attr == "load":
                if isinstance(node.func.value, ast.Name) and node.func.value.id in torch_modules:
                    is_torch_load = True
            elif isinstance(node.func, ast.Name) and node.func.id in torch_load_funcs:
                is_torch_load = True

            if is_torch_load:
                has_weights_only = False
                for kw in node.keywords:
                    if kw.arg == "weights_only":
                        if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            has_weights_only = True
                if not has_weights_only:
                    violations.append((file_path, node.lineno))

    return violations


def check_file(file_path: Path) -> list[tuple[Path, int]]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    if "load" not in content:
        return []

    try:
        tree = ast.parse(content, filename=str(file_path))
    except Exception:
        return []

    return scan_ast_for_torch_load_violations(file_path, tree)


def check_flaw_06(target_file: Path | None, target_dirs: list[Path]) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 06 - Unguarded torch.load() Deserialization")
    print("=" * 75)

    all_violations = []

    if target_file is not None:
        print(f"Target File: {target_file}")
        if not target_file.exists():
            print(f"[ERROR] Target file not found: {target_file}", file=sys.stderr)
            return 2
        try:
            content = target_file.read_text(encoding="utf-8")
        except Exception as err:
            print(f"[ERROR] Failed to read target file: {err}", file=sys.stderr)
            return 2
        try:
            tree = ast.parse(content, filename=str(target_file))
        except Exception as err:
            print(f"[ERROR] Failed to parse target file AST: {err}", file=sys.stderr)
            return 2
        all_violations.extend(scan_ast_for_torch_load_violations(target_file, tree))
    else:
        print("Target Directories: " + ", ".join(str(d.relative_to(REPO_ROOT) if d.is_relative_to(REPO_ROOT) else d) for d in target_dirs if d.exists()))
        for tdir in target_dirs:
            if not tdir.exists():
                continue
            for py_path in tdir.rglob("*.py"):
                all_violations.extend(check_file(py_path))

    if all_violations:
        print(f"\n[FAIL] FLAW 06 DETECTED: {len(all_violations)} unguarded torch.load() calls found without weights_only=True:")
        for path, line in all_violations:
            rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
            print(f"  - {rel}:{line}")
        print("\nSecurity Impact: Remote / Arbitrary Code Execution (ACE) via unpickling vulnerability (CVE-2024 class).")
        return 1
    else:
        print("\n[PASS] Flaw 06 Resolved: All torch.load() calls strictly specify weights_only=True.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 06 (Unguarded torch.load).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=None,
        help="Path to an individual file to audit."
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="Path to a single directory to audit."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help=f"Root directory of repository (default: {REPO_ROOT})"
    )
    args = parser.parse_args()

    if args.target_file is not None:
        target_dirs = []
    elif args.target_dir is not None:
        target_dirs = [args.target_dir]
    else:
        target_dirs = [
            args.repo_root / "src",
            args.repo_root / "scripts",
            args.repo_root / "kaggle_package",
            args.repo_root / "kaggle_bundle"
        ]

    sys.exit(check_flaw_06(args.target_file, target_dirs))


if __name__ == "__main__":
    main()
