import json
import os
import sys
import re
import ast
import torch
import torch.nn as nn
import numpy as np

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"
NOTEBOOKS = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb"
]

def extract_code_from_notebook(nb_path):
    with open(nb_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    code_cells = []
    for idx, cell in enumerate(data.get('cells', [])):
        if cell.get('cell_type') == 'code':
            lines = cell.get('source', [])
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('!') or stripped.startswith('%'):
                    cleaned_lines.append('# MAGICC: ' + line)
                else:
                    cleaned_lines.append(line)
            code_cells.append((idx, ''.join(cleaned_lines)))
    return code_cells

def inspect_notebook_details(nb_name):
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    code_cells = extract_code_from_notebook(nb_path)
    full_code = "\n\n# --- NEW CELL ---\n\n".join([c[1] for c in code_cells])
    
    print(f"\n=======================================================")
    print(f"DETAILED AUDIT: {nb_name}")
    print(f"Total Code Cells: {len(code_cells)}")
    
    # 1. Check for mock, dummy, fake, hardcoded patterns
    prohibited_keywords = [
        r'unittest\.mock', r'MagicMock', r'Mock\(',
        r'return\s+0\.9\d+', r'dice\s*=\s*0\.9\d+',
        r'val_dice\s*=\s*0\.9\d+', r'test_dice\s*=\s*0\.9\d+',
        r'return\s+True\s*#\s*mock',
        r'pass\s*#\s*todo',
        r'raise\s+NotImplementedError'
    ]
    
    suspicious_matches = []
    for pat in prohibited_keywords:
        matches = re.findall(pat, full_code, re.IGNORECASE)
        if matches:
            suspicious_matches.append((pat, matches))
            
    print(f"Prohibited Keyword / Pattern Matches: {len(suspicious_matches)}")
    for pat, matches in suspicious_matches:
        print(f"  [ALERT] Found pattern '{pat}': {matches}")
        
    # 2. Check dataset acquisition URLs and paths
    print("\n--- Data Pipeline Checks ---")
    urls = re.findall(r'https?://[^\s\'"<>]+', full_code)
    print(f"Dataset / Resource URLs found ({len(urls)}): {urls}")
    
    has_kvasir = 'kvasir' in full_code.lower()
    has_zip_extract = 'zipfile' in full_code or 'tarfile' in full_code or '.extractall' in full_code or 'shutil.unpack_archive' in full_code
    has_dataset_class = 'Dataset' in full_code and '__getitem__' in full_code and '__len__' in full_code
    has_dataloader = 'DataLoader' in full_code
    
    print(f"Contains 'kvasir' reference: {has_kvasir}")
    print(f"Contains extraction logic: {has_zip_extract}")
    print(f"Contains PyTorch Dataset implementation: {has_dataset_class}")
    print(f"Contains PyTorch DataLoader: {has_dataloader}")
    
    # 3. Check Training & Optimization components
    print("\n--- Training Loop & Optimization Checks ---")
    has_optimizer = 'AdamW' in full_code or 'Adam(' in full_code or 'SGD(' in full_code
    has_scheduler = 'lr_scheduler' in full_code or 'CosineAnnealing' in full_code or 'StepLR' in full_code
    has_amp = 'amp.autocast' in full_code or 'GradScaler' in full_code
    has_backward = 'backward()' in full_code
    has_step = 'optimizer.step()' in full_code or 'scaler.step' in full_code
    
    print(f"Optimizer: {has_optimizer}")
    print(f"Learning Rate Scheduler: {has_scheduler}")
    print(f"Mixed Precision (AMP): {has_amp}")
    print(f"Loss Backward Pass: {has_backward}")
    print(f"Optimizer Step: {has_step}")
    
    # 4. Check Evaluation Metrics calculation
    print("\n--- Evaluation Metrics Checks ---")
    has_dice_calc = 'intersection' in full_code and ('union' in full_code or 'cardinality' in full_code or '2 *' in full_code or '2.0 *' in full_code or '2*' in full_code)
    has_iou_calc = 'iou' in full_code.lower() or 'jaccard' in full_code.lower()
    print(f"Calculates Dice Metric authentically: {has_dice_calc}")
    print(f"Calculates IoU Metric: {has_iou_calc}")
    
    return {
        'suspicious_matches': suspicious_matches,
        'has_kvasir': has_kvasir,
        'has_zip_extract': has_zip_extract,
        'has_dataset_class': has_dataset_class,
        'has_dataloader': has_dataloader,
        'has_optimizer': has_optimizer,
        'has_scheduler': has_scheduler,
        'has_amp': has_amp,
        'has_backward': has_backward,
        'has_step': has_step,
        'has_dice_calc': has_dice_calc
    }

def main():
    summary = {}
    for nb_name in NOTEBOOKS:
        summary[nb_name] = inspect_notebook_details(nb_name)
        
    print("\n\n=======================================================")
    print("ALL NOTEBOOK INSPECTION COMPLETE")

if __name__ == '__main__':
    main()
