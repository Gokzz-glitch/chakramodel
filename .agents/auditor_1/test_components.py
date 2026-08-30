import json
import os
import sys
import torch
import torch.nn as nn
import numpy as np

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"

def extract_and_exec_cells(nb_name, cell_indices_to_run, global_scope=None):
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    with open(nb_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if global_scope is None:
        global_scope = {}
        
    for idx in cell_indices_to_run:
        cell = data['cells'][idx]
        if cell.get('cell_type') == 'code':
            lines = cell.get('source', [])
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('!') or stripped.startswith('%'):
                    continue
                # Skip actual download/training loop invocation if cell contains execution
                cleaned_lines.append(line)
            code = ''.join(cleaned_lines)
            exec(code, global_scope)
    return global_scope

def main():
    print("=== BEHAVIORAL & EMPIRICAL EXECUTION TESTS ===")
    
    # ----------------------------------------------------
    # TEST COMBO 1: PraNetResNet101 + DeepSupervisionDiceFocalLoss
    # ----------------------------------------------------
    print("\n[TEST 1] Combo 1: PraNetResNet101 & Deep Supervision Loss")
    try:
        scope1 = {}
        # Cells 3 (BasicConv/RFB/CBAM/PraNet) and 4 (Loss)
        # Let's inspect cell contents of Combo 1
        with open(os.path.join(NOTEBOOKS_DIR, "Combo1_ChakraNet_Focal.ipynb"), 'r', encoding='utf-8') as f:
            c1_data = json.load(f)
            
        print(f"Combo 1 total cells: {len(c1_data['cells'])}")
        for i, c in enumerate(c1_data['cells']):
            first_line = c.get('source', [''])[0].strip() if c.get('source') else ''
            print(f"  Cell {i} ({c.get('cell_type')}): {first_line[:50]}")
            
    except Exception as e:
        print(f"Error reading Combo 1: {e}")

if __name__ == '__main__':
    main()
