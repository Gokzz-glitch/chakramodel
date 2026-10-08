import json
import os
import sys
import torch
import torch.nn as nn
import numpy as np

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

def extract_code_cells(nb_path):
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    code_cells = []
    for idx, cell in enumerate(nb["cells"]):
        if cell.get("cell_type") == "code":
            src = "".join(cell.get("source", []))
            # Remove pip/apt/ipython magic commands
            lines = []
            for l in src.splitlines(True):
                s = l.strip()
                if s.startswith("!") or s.startswith("%"):
                    lines.append(f"# {l}")
                elif "subprocess.run" in l and "pip" in l:
                    lines.append(f"# {l}")
                elif "subprocess.check_call" in l and "pip" in l:
                    lines.append(f"# {l}")
                else:
                    lines.append(l)
            code_cells.append((idx, "".join(lines)))
    return code_cells

def test_notebook_mechanics(nb_name):
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    code_cells = extract_code_cells(nb_path)
    
    print(f"\n==========================================")
    print(f"TESTING MECHANICS: {nb_name}")
    print(f"==========================================")
    
    # We create a local execution environment
    exec_env = {
        "__name__": "__main__",
        "__file__": nb_name,
    }
    
    # For testing, mock dataset download or execution if it tries to actually download 100MB over network
    # We test architectural classes, loss functions, metrics, etc.
    
    for cell_idx, code in code_cells:
        print(f"Evaluating Cell {cell_idx}...")
        try:
            # We skip data download and large training execution during quick architectural unit testing
            # by providing mocked data paths or overriding training epochs
            if "setup_kvasir_seg_dataset" in code and "DATASET_PATH =" in code:
                # Mock execution of dataset download for fast local verification
                exec(code.replace("DATASET_PATH = setup_kvasir_seg_dataset()", "DATASET_PATH = Path('./dummy_data')").replace("DATASET_PATH = setup_kvasir_seg_dataset(target_dir=DATA_DIR)", "DATASET_PATH = Path('./dummy_data')"), exec_env)
            elif "train_combo" in code or "for epoch in range" in code or "for rnd in range" in code:
                # Compile the functions but don't execute 50 epochs
                # Replace heavy execution calls
                test_code = code
                if "training_history = train_combo1(" in test_code:
                    test_code = test_code.replace("epochs=30", "epochs=1")
                exec(test_code, exec_env)
            else:
                exec(code, exec_env)
            print(f"  Cell {cell_idx}: PASS")
        except Exception as e:
            print(f"  Cell {cell_idx}: EXCEPTION -> {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    for nb in NOTEBOOKS:
        try:
            test_notebook_mechanics(nb)
        except Exception as e:
            print(f"Error testing {nb}: {e}")
