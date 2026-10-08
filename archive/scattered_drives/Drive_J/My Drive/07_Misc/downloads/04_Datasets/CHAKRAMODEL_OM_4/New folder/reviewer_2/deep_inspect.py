import json
import os
import sys

# Ensure UTF-8 output
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

def deep_inspect(nb_name):
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    
    print("=" * 80)
    print(f"NOTEBOOK: {nb_name}")
    print("=" * 80)
    
    for idx, cell in enumerate(nb["cells"]):
        cell_type = cell.get("cell_type")
        source = "".join(cell.get("source", []))
        lines = source.splitlines()
        first_few_lines = "\n".join(lines[:3])
        print(f"\n--- Cell {idx} [{cell_type}] ({len(lines)} lines, {len(source)} chars) ---")
        print(first_few_lines)
        
        # Check specific config or dataloader lines
        for line_no, line in enumerate(lines):
            l = line.lower()
            if any(k in l for k in ["batch_size", "num_workers", "resnet", "vit", "yolo", "kvasir", "download", "dataset", "dataloader"]):
                if len(line.strip()) < 140:
                    print(f"    L{line_no+1}: {line.strip()}")

if __name__ == "__main__":
    for nb in NOTEBOOKS:
        deep_inspect(nb)
