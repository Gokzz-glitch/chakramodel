import json
import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"
NOTEBOOKS = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb"
]

for nb in NOTEBOOKS:
    path = os.path.join(NOTEBOOKS_DIR, nb)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"\n==================== {nb} ====================")
    for idx, cell in enumerate(data['cells']):
        ctype = cell.get('cell_type')
        lines = cell.get('source', [])
        first_line = lines[0].strip() if lines else "<EMPTY>"
        print(f"Cell {idx:02d} [{ctype:8s}] (lines: {len(lines):3d}): {first_line[:75]}")
