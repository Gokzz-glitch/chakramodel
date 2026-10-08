import re

path = r"M:\chakramodel\src\evaluation\run_all_combos.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Look for combo1 or mc_passes or unc_list or mean_uncertainty
lines = text.splitlines()
for i, l in enumerate(lines):
    if any(k in l.lower() for k in ["combo 1", "combo1", "mean_uncertainty", "unc_list", "var_map", "variance"]):
        print(f"{i+1}: {l}")
