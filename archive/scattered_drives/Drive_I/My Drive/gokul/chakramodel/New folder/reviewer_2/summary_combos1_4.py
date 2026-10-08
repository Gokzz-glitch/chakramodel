import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"

def print_nb_summary(nb_name):
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    print("=" * 80)
    print(f"NOTEBOOK: {nb_name}")
    print("=" * 80)
    cells = nb.get("cells", [])
    print(f"Total Cells: {len(cells)}")
    for idx, cell in enumerate(cells):
        src = "".join(cell.get("source", []))
        lines = [l.strip() for l in src.splitlines() if l.strip()]
        first = lines[0] if lines else ""
        print(f"  Cell {idx} ({cell.get('cell_type')}, {len(lines)} lines): {first[:70]}")

if __name__ == "__main__":
    for nb in ["Combo1_ChakraNet_Focal.ipynb", "Combo2_Topo_ChakraNet.ipynb", "Combo3_AdaBN_ChakraNet.ipynb", "Combo4_DiffusionAug_ChakraNet.ipynb"]:
        print_nb_summary(nb)
