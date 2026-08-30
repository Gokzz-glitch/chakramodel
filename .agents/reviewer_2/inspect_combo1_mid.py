import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r"m:\chakramodel\notebooks\Combo1_ChakraNet_Focal.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

for idx in [4, 5, 6]:
    cell = nb["cells"][idx]
    src = "".join(cell.get("source", []))
    print(f"=== CELL {idx} ({cell.get('cell_type')}) ===")
    print(src[:500])
    print("...")
