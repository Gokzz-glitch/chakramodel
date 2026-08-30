import json
import os
import sys

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
    print(f"\n{'='*70}\n{nb}\n{'='*70}")
    for idx, cell in enumerate(data['cells']):
        ctype = cell.get('cell_type')
        lines = cell.get('source', [])
        # Find comments or header lines
        header_lines = [l.strip() for l in lines if l.strip().startswith('#') and len(l.strip()) > 3 and not l.strip().startswith('# ===')]
        hdr = " | ".join(header_lines[:3]) if header_lines else (lines[0].strip() if lines else "EMPTY")
        print(f"[{idx}] {ctype:8s} | {hdr[:100]}")
