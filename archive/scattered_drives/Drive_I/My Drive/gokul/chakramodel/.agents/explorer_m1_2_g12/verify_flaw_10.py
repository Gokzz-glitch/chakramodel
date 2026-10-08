import json
import math
import sys
from pathlib import Path

repo_root = Path(r"M:\chakramodel")
f_a = repo_root / "weights" / "calibration" / "conformal_calibration.json"
f_b = repo_root / "results" / "combo1_metrics.json"

if not f_a.exists() or not f_b.exists():
    print("Files missing!")
    sys.exit(1)

with open(f_a, "r") as fp:
    data_a = json.load(fp)
with open(f_b, "r") as fp:
    data_b = json.load(fp)

q_hat_pos_a = data_a["q_hat_pos"]
threshold_b = data_b["conformal"]["alpha_5"]["threshold"]
q_hat_b = data_b["conformal"]["alpha_5"]["q_hat"]

diff_orders = abs(math.log10(q_hat_pos_a) - math.log10(threshold_b))
ratio = q_hat_pos_a / threshold_b

print(f"File A (weights/calibration/conformal_calibration.json): q_hat_pos = {q_hat_pos_a}")
print(f"File B (results/combo1_metrics.json): threshold = {threshold_b} (q_hat = {q_hat_b})")
print(f"Ratio A / B: {ratio:.2f}")
print(f"Orders of magnitude difference: {diff_orders:.2f}")
