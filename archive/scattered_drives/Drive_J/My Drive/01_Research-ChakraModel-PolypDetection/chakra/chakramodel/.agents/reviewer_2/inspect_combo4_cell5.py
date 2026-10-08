import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r"m:\chakramodel\notebooks\Combo4_DiffusionAug_ChakraNet.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

src = "".join(nb["cells"][5].get("source", []))
print("=== CELL 5 ===")
print(src)
