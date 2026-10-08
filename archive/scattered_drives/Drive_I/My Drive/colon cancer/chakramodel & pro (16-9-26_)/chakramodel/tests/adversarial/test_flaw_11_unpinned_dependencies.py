#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 11:
Unpinned dependencies across requirements manifests (floating '>=' specifications).

Reproducibility & Operational Risk:
  Floating lower bounds (e.g. timm>=0.9.0, torch>=2.0.0, numpy>=1.23.0) permit installation
  of breaking major releases (such as NumPy 2.x C-ABI incompatibility or timm 1.0.x Vision
  Transformer output tensor shape changes from 3D to 4D/pooled), preventing reproduction
  of evaluation results and crashing pipeline forward passes.

Exit Codes:
  1: Flaw detected (unpinned '>=' dependencies found in requirements files).
  0: Flaw resolved (all dependencies strictly pinned with '==' for deterministic reproduction).
  2: Configuration or target file error.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_REQ_ROOT = REPO_ROOT / "requirements.txt"
DEFAULT_REQ_KAGGLE = REPO_ROOT / "kaggle_bundle" / "requirements.txt"


def check_requirements_file(req_path: Path) -> list[str]:
    violations = []
    if not req_path.exists():
        return violations

    lines = req_path.read_text(encoding="utf-8").splitlines()
    for line_idx, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        pkg_spec = line.split("#")[0].strip()
        if ">=" in pkg_spec and "==" not in pkg_spec:
            violations.append(f"{req_path.name}:{line_idx}: Unpinned floating dependency '{pkg_spec}'")
        elif not any(op in pkg_spec for op in ["==", "~=", "<="]):
            violations.append(f"{req_path.name}:{line_idx}: Completely unpinned dependency '{pkg_spec}'")

    return violations


def check_flaw_11(req_files: list[Path]) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 11 - Unpinned Dependencies Manifest")
    print("=" * 75)

    all_violations = []
    for rf in req_files:
        print(f"Checking: {rf}")
        if not rf.exists():
            print(f"  [WARN] File not found: {rf}")
            continue
        v = check_requirements_file(rf)
        all_violations.extend(v)

    print(f"  - Total unpinned package specifications found: {len(all_violations)}")

    if all_violations:
        print(f"\n[FAIL] FLAW 11 DETECTED: {len(all_violations)} unpinned floating dependencies detected:")
        for viol in all_violations:
            print(f"  - {viol}")
        print("\nReproducibility Impact: Floating lower bounds allow silent installation of breaking upstream")
        print("releases (NumPy 2.x ABI breakage, timm 1.0.x ViT output shape shifts from 3D to 4D/pooled),")
        print("preventing deterministic environment reproduction and crashing inference decoders.")
        return 1
    else:
        print("\n[PASS] Flaw 11 Resolved: All dependencies are strictly pinned for deterministic reproduction.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 11 (Unpinned dependencies).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=None,
        help="Path to an individual requirements file to audit."
    )
    parser.add_argument(
        "--req-file",
        type=Path,
        default=None,
        help="Alias for --target-file."
    )
    args = parser.parse_args()

    target = args.target_file or args.req_file
    if target is not None:
        req_files = [target]
    else:
        req_files = [DEFAULT_REQ_ROOT, DEFAULT_REQ_KAGGLE]

    sys.exit(check_flaw_11(req_files))


if __name__ == "__main__":
    main()
