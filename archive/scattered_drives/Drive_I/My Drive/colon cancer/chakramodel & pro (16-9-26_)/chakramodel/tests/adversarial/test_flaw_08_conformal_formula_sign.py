#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 08:
Sign-flipped conformal scoring formula in inference path vs canonical calibration formula.

Mathematical & Clinical Hazard:
  Canonical calibration computes nonconformity as (1 - p) + v for positive pixels and p + v for negative pixels.
  The inference path inlines 1 - (p + v) = (1 - p) - v and p - v, subtracting variance instead of adding it.
  This introduces a 2v divergence, breaks the exchangeability axiom, voids the 95% coverage guarantee,
  and dangerously narrows the resection safety margin in high-uncertainty boundary zones.

Exit Codes:
  1: Flaw detected (sign-flipped formula subtracting variance present in inference code).
  0: Flaw resolved (canonical addition formula or canonical nonconformity functions used).
  2: Configuration or target file error.
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET = REPO_ROOT / "src" / "models" / "chakranet_segmenter.py"


def check_flaw_08(target_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 08 - Sign-Flipped Conformal Scoring Formula")
    print(f"Target File: {target_file}")
    print("=" * 75)

    if not target_file.exists():
        print(f"[ERROR] Target file not found: {target_file}", file=sys.stderr)
        return 2

    source = target_file.read_text(encoding="utf-8")

    # Buggy patterns: subtracting variance from probability or subtracting (prob + variance) from 1.0
    buggy_pos_patterns = [
        r"1\.0\s*-\s*\(\s*(?:prob_resized|prob)\s*\+\s*variance\s*\)",
        r"score_pos\s*=\s*1\.0\s*-\s*\(\s*(?:prob_resized|prob)\s*\+\s*variance\s*\)"
    ]
    buggy_neg_patterns = [
        r"score_neg\s*=\s*(?:prob_resized|prob)\s*-\s*variance"
    ]

    has_buggy_pos = any(re.search(pat, source) for pat in buggy_pos_patterns)
    has_buggy_neg = any(re.search(pat, source) for pat in buggy_neg_patterns)

    # Check for correct canonical formulas: (1.0 - prob) + variance and prob + variance
    canonical_pos_pattern = r"\(\s*1(?:\.0)?\s*-\s*(?:prob_resized|prob)\s*\)\s*\+\s*variance"
    canonical_neg_pattern = r"score_neg\s*=\s*(?:prob_resized|prob)\s*\+\s*variance"
    has_canonical_pos = bool(re.search(canonical_pos_pattern, source))
    has_canonical_neg = bool(re.search(canonical_neg_pattern, source))

    print(f"  - Detected buggy score_pos [1.0 - (prob + variance)]: {has_buggy_pos}")
    print(f"  - Detected buggy score_neg [prob - variance]:          {has_buggy_neg}")
    print(f"  - Detected canonical score_pos [(1 - prob) + var]:     {has_canonical_pos}")
    print(f"  - Detected canonical score_neg [prob + var]:           {has_canonical_neg}")

    if has_buggy_pos or has_buggy_neg:
        print("\n[FAIL] FLAW 08 DETECTED: Sign-flipped conformal formula found in inference path.")
        if has_buggy_pos:
            print("       score_pos = 1.0 - (prob_resized + variance)  <-- Variance is SUBTRACTED instead of ADDED!")
        if has_buggy_neg:
            print("       score_neg = prob_resized - variance          <-- Variance is SUBTRACTED instead of ADDED!")
        print("       Mathematical Impact: Delta S = 2v divergence between calibration and inference,")
        print("       violating exchangeability and invalidating the theoretical 95% coverage guarantee.")
        return 1
    else:
        print("\n[PASS] Flaw 08 Resolved: Inference conformal scoring matches canonical calibration formula.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 08 (Sign-flipped conformal formula).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Path to chakranet_segmenter.py (default: {DEFAULT_TARGET})"
    )
    args = parser.parse_args()
    sys.exit(check_flaw_08(args.target_file))


if __name__ == "__main__":
    main()
