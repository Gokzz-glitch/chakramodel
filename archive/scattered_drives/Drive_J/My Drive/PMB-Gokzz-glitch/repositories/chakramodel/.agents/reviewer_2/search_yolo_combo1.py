import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r"m:\chakramodel\notebooks\Combo1_ChakraNet_Focal.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

for idx, cell in enumerate(nb["cells"]):
    src = "".join(cell.get("source", []))
    if "yolo" in src.lower():
        print(f"=== Cell {idx} ({cell.get('cell_type')}) ===")
        for line in src.splitlines():
            if "yolo" in line.lower():
                print(f"  {line}")
