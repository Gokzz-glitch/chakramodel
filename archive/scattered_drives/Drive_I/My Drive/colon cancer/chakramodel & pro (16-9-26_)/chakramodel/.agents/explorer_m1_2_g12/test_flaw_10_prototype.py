"""
Adversarial Detection Test for Flaw 10:
Two contradictory calibration q_hat files coexist in the repo with values differing by 5 orders of magnitude.

Exit code:
  1 if weights/calibration/conformal_calibration.json and results/combo1_metrics.json
    coexist with q_hat / threshold values differing by > 3 orders of magnitude without reconciliation.
  0 if calibration threshold provenance is unified and consistent.
"""
import json
import math
import sys
from pathlib import Path

def main():
    repo_root = Path(r"M:\chakramodel")
    f_calib = repo_root / "weights" / "calibration" / "conformal_calibration.json"
    f_metrics = repo_root / "results" / "combo1_metrics.json"

    if not f_calib.exists() or not f_metrics.exists():
        print("[SKIP] One of the calibration files is absent.")
        sys.exit(0)

    with open(f_calib, "r") as f:
        calib_data = json.load(f)
    with open(f_metrics, "r") as f:
        metrics_data = json.load(f)

    q_hat_pos = calib_data.get("q_hat_pos")
    conf_a5 = metrics_data.get("conformal", {}).get("alpha_5", {})
    threshold_combo1 = conf_a5.get("threshold")

    if q_hat_pos is not None and threshold_combo1 is not None:
        ratio = q_hat_pos / threshold_combo1
        orders_diff = abs(math.log10(q_hat_pos) - math.log10(threshold_combo1))

        if orders_diff > 3.0:
            print(f"[FAIL] Flaw 10 detected: Contradictory calibration files coexist in repository!")
            print(f"  File 1: weights/calibration/conformal_calibration.json -> q_hat_pos = {q_hat_pos}")
            print(f"  File 2: results/combo1_metrics.json                    -> threshold = {threshold_combo1}")
            print(f"  Discrepancy: Ratio = {ratio:.2f}x ({orders_diff:.2f} orders of magnitude difference).")
            print("  README cites File 2 while deployed weights contain File 1.")
            sys.exit(1)

    print("[PASS] Flaw 10 resolved: Calibration files are harmonized.")
    sys.exit(0)

if __name__ == "__main__":
    main()
