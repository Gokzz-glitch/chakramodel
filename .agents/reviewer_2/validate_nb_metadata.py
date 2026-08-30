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
    print(f"File: {nb_name}")
    print(f"  nbformat: {nb.get('nbformat')}.{nb.get('nbformat_minor')}")
    print(f"  kernelspec: {nb.get('metadata', {}).get('kernelspec', {}).get('display_name')}")
    print(f"  language_info: {nb.get('metadata', {}).get('language_info', {}).get('name')}")
    print(f"  cells: {len(nb.get('cells', []))} total ({sum(1 for c in nb.get('cells', []) if c.get('cell_type')=='code')} code, {sum(1 for c in nb.get('cells', []) if c.get('cell_type')=='markdown')} markdown)")
    print()
