import json
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"

for nb_name in ["Combo3_AdaBN_ChakraNet.ipynb", "Combo4_DiffusionAug_ChakraNet.ipynb"]:
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    print("=" * 80)
    print(f"NOTEBOOK: {nb_name}")
    print("=" * 80)
    for idx, cell in enumerate(nb["cells"]):
        source = "".join(cell.get("source", []))
        print(f"\n--- Cell {idx} [{cell.get('cell_type')}] ---")
        for line in source.splitlines():
            if any(k in line.lower() for k in ["batch", "worker", "resnet", "dataloader", "bs", "loaders"]):
                print(f"    {line}")
