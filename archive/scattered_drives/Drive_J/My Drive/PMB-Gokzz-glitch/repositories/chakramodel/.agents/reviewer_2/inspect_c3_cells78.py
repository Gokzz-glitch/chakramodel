import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r"m:\chakramodel\notebooks\Combo3_AdaBN_ChakraNet.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

print("=== CELL 7 ===")
print("".join(nb["cells"][7].get("source", [])))

print("=== CELL 8 ===")
print("".join(nb["cells"][8].get("source", [])))
