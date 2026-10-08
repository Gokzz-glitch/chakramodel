#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 14:
Headline metric 0.7304 has no producing artifact (exists only in prose).

Scientific Integrity Violation:
  FIXES.md Section 5 asserts a 'Genuine Measured Evaluation' of Mean DSC 0.7304 and Mean IoU 0.6452
  on N=50 images, citing results/corrected_eval_kvasir_seg.json.
  In reality, that JSON artifact contains Mean DSC 0.80225, Mean IoU 0.73481, N=60 images, a different
  timestamp, no confidence field, and none of the six cited highlight filenames exist in the file.
  Furthermore, docs/HONEST_METRICS.md retracted other inflated metrics but failed to retract 0.7304.

Exit Codes:
  1: Flaw detected (0.7304 asserted in prose without backing JSON artifact or missing from retractions).
  0: Flaw resolved (prose metrics match true artifact values and 0.7304 is formally retracted).
  2: Configuration or target file error.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_FIXES = REPO_ROOT / "FIXES.md"
DEFAULT_ARTIFACT = REPO_ROOT / "results" / "corrected_eval_kvasir_seg.json"
DEFAULT_HONEST_METRICS = REPO_ROOT / "docs" / "HONEST_METRICS.md"


def check_flaw_14(fixes_file: Path, artifact_file: Path, honest_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 14 - Headline Metric 0.7304 Artifact Absence")
    print(f"FIXES Document:   {fixes_file}")
    print(f"Cited Artifact:   {artifact_file}")
    print(f"Honest Metrics:   {honest_file}")
    print("=" * 75)

    errors = []

    # 1. Audit FIXES.md
    if not fixes_file.exists():
        print(f"[ERROR] FIXES.md not found: {fixes_file}", file=sys.stderr)
        return 2

    fixes_content = fixes_file.read_text(encoding="utf-8")
    claims_07304 = "0.7304" in fixes_content

    actual_dsc = None
    actual_n = None
    if artifact_file.exists():
        try:
            artifact_data = json.loads(artifact_file.read_text(encoding="utf-8"))
            actual_dsc = artifact_data.get("mean_dsc")
            actual_n = artifact_data.get("n_images")
        except Exception as err:
            print(f"[WARN] Failed to parse {artifact_file}: {err}")

    print(f"  - FIXES.md asserts 0.7304:                   {claims_07304}")
    print(f"  - Cited artifact actual mean_dsc:            {actual_dsc}")
    print(f"  - Cited artifact actual n_images:            {actual_n}")

    if claims_07304 and actual_dsc is not None and abs(actual_dsc - 0.7304) > 0.001:
        errors.append(
            f"FIXES.md claims Mean DSC 0.7304 (N=50) citing '{artifact_file.name}', "
            f"but artifact actually contains mean_dsc = {actual_dsc} (N={actual_n}). "
            f"The score 0.7304 exists in no JSON, CSV, or log artifact."
        )

    # 2. Audit docs/HONEST_METRICS.md
    honest_retracts_07304 = False
    if honest_file.exists():
        honest_content = honest_file.read_text(encoding="utf-8")
        if "0.7304" in honest_content and ("retract" in honest_content.lower() or "unsubstantiated" in honest_content.lower()):
            honest_retracts_07304 = True

    print(f"  - docs/HONEST_METRICS.md retracts 0.7304:     {honest_retracts_07304}")

    if claims_07304 and not honest_retracts_07304:
        errors.append(
            "docs/HONEST_METRICS.md fails to retract '0.7304' in its RETRACTED table, "
            "allowing an uncorroborated prose metric with fabricated highlights to persist as an honest baseline."
        )

    if errors:
        print("\n[FAIL] FLAW 14 DETECTED: Headline metric 0.7304 is unsubstantiated by empirical artifacts:")
        for err in errors:
            print(f"  - {err}")
        print("\nIntegrity Hazard: Remediation document FIXES.md asserts an unsourced score (0.7304)")
        print("with fabricated per-image filenames, contradicting its own cited JSON artifact (0.80225).")
        return 1
    else:
        print("\n[PASS] Flaw 14 Resolved: Headline metrics match empirical artifacts and unbacked scores are retracted.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 14 (Headline metric 0.7304).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=None,
        help="Path to FIXES.md or target document."
    )
    parser.add_argument(
        "--artifact-file",
        type=Path,
        default=DEFAULT_ARTIFACT,
        help=f"Path to corrected_eval_kvasir_seg.json (default: {DEFAULT_ARTIFACT})"
    )
    parser.add_argument(
        "--honest-metrics",
        type=Path,
        default=DEFAULT_HONEST_METRICS,
        help=f"Path to HONEST_METRICS.md (default: {DEFAULT_HONEST_METRICS})"
    )
    args = parser.parse_args()

    fixes_path = args.target_file or DEFAULT_FIXES
    sys.exit(check_flaw_14(fixes_path, args.artifact_file, args.honest_metrics))


if __name__ == "__main__":
    main()
