import sys
import os
import nbformat

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

NOTEBOOK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notebooks")
NOTEBOOKS = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb",
]

for nb_name in NOTEBOOKS:
    nb_path = os.path.join(NOTEBOOK_DIR, nb_name)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.reads(f.read(), as_version=4)
        
    print(f"\n=======================================================")
    print(f"Cell Breakdown: {nb_name}")
    print(f"=======================================================")
    for idx, cell in enumerate(nb.cells):
        src = "".join(cell.source) if isinstance(cell.source, list) else str(cell.source)
        lines = [l.strip() for l in src.splitlines() if l.strip() and not l.strip().startswith("=")]
        header = lines[0] if lines else "EMPTY"
        print(f"Cell {idx} [{cell.cell_type}]: {header[:100]}")
