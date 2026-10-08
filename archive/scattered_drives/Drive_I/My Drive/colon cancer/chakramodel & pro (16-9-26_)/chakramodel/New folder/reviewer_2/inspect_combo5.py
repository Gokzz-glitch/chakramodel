import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r"m:\chakramodel\notebooks\Combo5_Federated_ChakraNet.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

for idx, cell in enumerate(nb["cells"]):
    src = "".join(cell.get("source", []))
    print(f"=== CELL {idx} ({cell.get('cell_type')}) ===")
    if idx in [5, 6, 7]:
        print(src)
