import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"

for nb_name in ["Combo1_ChakraNet_Focal.ipynb", "Combo2_Topo_ChakraNet.ipynb", "Combo3_AdaBN_ChakraNet.ipynb", "Combo4_DiffusionAug_ChakraNet.ipynb", "Combo5_Federated_ChakraNet.ipynb", "Combo6_ChakraTransformer.ipynb"]:
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    print("=" * 80)
    print(f"NOTEBOOK: {nb_name} (Cell 1)")
    print("=" * 80)
    src = "".join(nb["cells"][1].get("source", []))
    print(src[:600])
