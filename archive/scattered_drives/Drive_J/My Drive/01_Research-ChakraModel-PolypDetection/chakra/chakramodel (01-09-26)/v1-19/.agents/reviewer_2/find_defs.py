import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"
NOTEBOOKS = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb",
]

for nb_name in NOTEBOOKS:
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    print(f"=== {nb_name} ===")
    for idx, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        defs = [line for line in src.splitlines() if line.startswith("class ") or line.startswith("def ")]
        if defs:
            print(f"  Cell {idx}: {defs[:4]}")
