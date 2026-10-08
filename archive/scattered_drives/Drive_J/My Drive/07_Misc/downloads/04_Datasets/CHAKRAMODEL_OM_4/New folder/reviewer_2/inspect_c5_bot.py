import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r"m:\chakramodel\notebooks\Combo1_ChakraNet_Focal.ipynb"
with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

c5 = "".join(nb["cells"][5].get("source", []))
for idx, line in enumerate(c5.splitlines()[-25:]):
    print(f"{idx}: {line}")
