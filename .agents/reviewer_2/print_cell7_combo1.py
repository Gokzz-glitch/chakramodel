import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r"m:\chakramodel\notebooks\Combo1_ChakraNet_Focal.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

src = "".join(nb["cells"][7].get("source", []))
print("=== CELL 7 FULL CONTENT ===")
print(src)
