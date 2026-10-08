#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 10:
Two contradictory calibration q_hat files coexisting in the repository differing by ~4.85 orders of magnitude (71,183x).

Provenance & Clinical Hazard:
  File A: weights/calibration/conformal_calibration.json -> q_hat_pos = 0.521484375 (~0.52)
  File B: results/combo1_metrics.json                   -> threshold = 7.326006889e-06 (~7.33e-06)
  The discrepancy is 71,183x (4.85 orders of magnitude).
  README/paper sections cite File B, while deployment weights distribute File A.
  Switching between these files alters the conformal safety margin by 5 orders of magnitude.

Exit Codes:
  1: Flaw detected (contradictory calibration threshold values coexist without reconciliation).
  0: Flaw resolved (provenance unified, values harmonized or legacy run explicitly marked deprecated).
  2: Configuration or target file error.
"""

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CALIB = REPO_ROOT / "weights" / "calibration" / "conformal_calibration.json"
DEFAULT_METRICS = REPO_ROOT / "results" / "combo1_metrics.json"


def check_flaw_10(calib_file: Path, metrics_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 10 - Contradictory Calibration q_hat Files")
    print(f"Calib File:   {calib_file}")
    print(f"Metrics File: {metrics_file}")
    print("=" * 75)

    if not calib_file.exists():
        print(f"[ERROR] Calibration file not found: {calib_file}", file=sys.stderr)
        return 2
    if not metrics_file.exists():
        print(f"[ERROR] Metrics file not found: {metrics_file}", file=sys.stderr)
        return 2

    try:
        calib_data = json.loads(calib_file.read_text(encoding="utf-8"))
        metrics_data = json.loads(metrics_file.read_text(encoding="utf-8"))
    except Exception as err:
        print(f"[ERROR] Failed to parse JSON files: {err}", file=sys.stderr)
        return 2

    q_hat_pos = calib_data.get("q_hat_pos")
    conf_a5 = metrics_data.get("conformal", {}).get("alpha_5", {})
    threshold_combo1 = conf_a5.get("threshold")
    conformal_status = metrics_data.get("conformal_status", "")

    print(f"  - File 1 (weights/calibration): q_hat_pos = {q_hat_pos}")
    print(f"  - File 2 (results/combo1):       threshold = {threshold_combo1}")
    print(f"  - Conformal reconciliation note in metrics: '{conformal_status}'")

    if q_hat_pos is not None and threshold_combo1 is not None:
        ratio = q_hat_pos / threshold_combo1
        orders_diff = abs(math.log10(q_hat_pos) - math.log10(threshold_combo1))
        print(f"  - Calculated discrepancy ratio: {ratio:.2f}x ({orders_diff:.2f} orders of magnitude)")

        # If they differ by > 3 orders of magnitude and no reconciliation status is present:
        if orders_diff > 3.0 and "DEPRECATED" not in conformal_status and "SUPERSEDED" not in conformal_status:
            print("\n[FAIL] FLAW 10 DETECTED: Contradictory calibration files coexist in repository!")
            print(f"       File 1: {calib_file.name} -> q_hat_pos = {q_hat_pos}")
            print(f"       File 2: {metrics_file.name} -> threshold = {threshold_combo1}")
            print(f"       Discrepancy: Ratio = {ratio:.1f}x ({orders_diff:.2f} orders of magnitude).")
            print("       README cites 95.5% coverage with threshold ~7.33e-06 (File 2) derived from collapsed")
            print("       variance, while deployed weights distribute File 1 (~0.5215). Dual conflicting SSOTs.")
            return 1

    print("\n[PASS] Flaw 10 Resolved: Calibration thresholds are harmonized and provenance is reconciled.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 10 (Contradictory calibration q_hat).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=None,
        help="Path to an individual file to check."
    )
    parser.add_argument(
        "--calib-file",
        type=Path,
        default=DEFAULT_CALIB,
        help=f"Path to conformal_calibration.json (default: {DEFAULT_CALIB})"
    )
    parser.add_argument(
        "--metrics-file",
        type=Path,
        default=DEFAULT_METRICS,
        help=f"Path to combo1_metrics.json (default: {DEFAULT_METRICS})"
    )
    args = parser.parse_args()

    calib_path = args.calib_file
    metrics_path = args.metrics_file

    if args.target_file is not None:
        if "calib" in args.target_file.name.lower():
            calib_path = args.target_file
        else:
            metrics_path = args.target_file

    sys.exit(check_flaw_10(calib_path, metrics_path))


if __name__ == "__main__":
    main()
