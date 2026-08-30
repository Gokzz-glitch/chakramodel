"""
Victory Auditor Comprehensive Verification Suite
Performs zero-context adversarial inspection of the 6 Kaggle notebooks.
"""

import os
import sys
import json
import ast
import re
import nbformat
import torch
import torch.nn as nn

# Ensure utf-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"
NOTEBOOK_FILES = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb",
]

def check_file_properties():
    print("=== CHECK 1: File Existence, Sizes, JSON & nbformat Validation ===")
    results = {}
    for nb_file in NOTEBOOK_FILES:
        path = os.path.join(NOTEBOOKS_DIR, nb_file)
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        json_ok = False
        nb_ok = False
        cell_types = []
        if exists:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                json_ok = True
            except Exception as e:
                json_ok = f"Error: {e}"
            try:
                nb = nbformat.read(path, as_version=4)
                nb_ok = True
                cell_types = [c.cell_type for c in nb.cells]
            except Exception as e:
                nb_ok = f"Error: {e}"
        results[nb_file] = {
            "exists": exists,
            "size_bytes": size,
            "json_valid": json_ok,
            "nbformat_v4_valid": nb_ok,
            "cell_count": len(cell_types),
            "cell_breakdown": cell_types
        }
        print(f"[{'PASS' if exists and json_ok is True and nb_ok is True else 'FAIL'}] {nb_file}: size={size}B, cells={len(cell_types)} ({cell_types.count('markdown')} md, {cell_types.count('code')} code)")
    return results

def check_syntax_and_ast():
    print("\n=== CHECK 2: Python Code Cell AST Compilation & Syntax Checks ===")
    ast_results = {}
    total_cells = 0
    total_syntax_errors = 0
    for nb_file in NOTEBOOK_FILES:
        path = os.path.join(NOTEBOOKS_DIR, nb_file)
        nb = nbformat.read(path, as_version=4)
        nb_errors = []
        cell_idx = 0
        for i, cell in enumerate(nb.cells):
            if cell.cell_type == 'code':
                total_cells += 1
                source = cell.source
                # Comment out notebook magics / shell commands
                cleaned_lines = []
                for line in source.splitlines():
                    if line.strip().startswith('!') or line.strip().startswith('%'):
                        cleaned_lines.append('# ' + line)
                    else:
                        cleaned_lines.append(line)
                code_text = '\n'.join(cleaned_lines)
                try:
                    tree = ast.parse(code_text)
                except SyntaxError as e:
                    total_syntax_errors += 1
                    nb_errors.append(f"Cell {i} SyntaxError: {e}")
        ast_results[nb_file] = {
            "syntax_errors": nb_errors,
            "clean": len(nb_errors) == 0
        }
        print(f"[{'PASS' if len(nb_errors) == 0 else 'FAIL'}] {nb_file}: {len(nb_errors)} syntax errors")
    print(f"Total Code Cells Tested: {total_cells}, Total Syntax Errors: {total_syntax_errors}")
    return ast_results

def check_dataset_and_paths():
    print("\n=== CHECK 3: Dataset Accessibility & Destination Path (/kaggle/working/data/kvasir-seg) ===")
    results = {}
    for nb_file in NOTEBOOK_FILES:
        path = os.path.join(NOTEBOOKS_DIR, nb_file)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_kvasir = "kvasir-seg" in content.lower() or "kvasir" in content.lower()
        has_dest_path = "/kaggle/working/data/kvasir-seg" in content or "data/kvasir-seg" in content
        has_download_url = any(domain in content for domain in ["datasets.simula.no", "zenodo.org", "huggingface.co", "github.com", "kaggle.com"])
        has_unzip = "zipfile" in content or "tarfile" in content or "unzip" in content
        
        pass_check = has_kvasir and has_dest_path and has_download_url and has_unzip
        results[nb_file] = {
            "has_kvasir": has_kvasir,
            "has_dest_path": has_dest_path,
            "has_download_url": has_download_url,
            "has_unzip": has_unzip,
            "passed": pass_check
        }
        print(f"[{'PASS' if pass_check else 'FAIL'}] {nb_file}: kvasir={has_kvasir}, dest_path={has_dest_path}, download_url={has_download_url}, unzip={has_unzip}")
    return results

def check_max_spec():
    print("\n=== CHECK 4: Max-Spec Model Backbones, Batch Sizes, & Hardware Settings ===")
    results = {}
    expected_backbones = {
        "Combo1_ChakraNet_Focal.ipynb": ["resnet101", "yolov8x", "batch_size = 32"],
        "Combo2_Topo_ChakraNet.ipynb": ["resnet101", "batch_size = 32"],
        "Combo3_AdaBN_ChakraNet.ipynb": ["resnet101", "batch_size = 32"],
        "Combo4_DiffusionAug_ChakraNet.ipynb": ["resnet101", "batch_size = 32"],
        "Combo5_Federated_ChakraNet.ipynb": ["resnet101", "batch_size = 32"],
        "Combo6_ChakraTransformer.ipynb": ["vit_large_patch16_384", "batch_size = 32"],
    }
    
    for nb_file, reqs in expected_backbones.items():
        path = os.path.join(NOTEBOOKS_DIR, nb_file)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().lower()
        
        matched = {}
        for req in reqs:
            req_normalized = req.lower().replace(" ", "").replace("_", "")
            content_normalized = content.replace(" ", "").replace("_", "")
            matched[req] = req.lower() in content or req_normalized in content_normalized
        
        all_matched = all(matched.values())
        results[nb_file] = {
            "requirements": reqs,
            "matched": matched,
            "passed": all_matched
        }
        print(f"[{'PASS' if all_matched else 'FAIL'}] {nb_file}: {matched}")
    return results

def check_cheating_and_facades():
    print("\n=== CHECK 5: Forensic Integrity & Anti-Cheating (Hardcoded results, facades, stubs) ===")
    results = {}
    for nb_file in NOTEBOOK_FILES:
        path = os.path.join(NOTEBOOKS_DIR, nb_file)
        nb = nbformat.read(path, as_version=4)
        
        flags = []
        for idx, cell in enumerate(nb.cells):
            if cell.cell_type == 'code':
                src = cell.source
                # Check for hollow functions
                if re.search(r"def\s+[a-zA-Z0-9_]+\s*\([^)]*\)\s*:\s*(pass|\.\.\.|return\s+[0-9\.]+|return\s+None)\s*(\n|$)", src):
                    # Check if it's not a dummy mock
                    flags.append(f"Cell {idx}: suspicious short dummy function")
                # Check for NotImplementedError
                if "raise NotImplementedError" in src:
                    flags.append(f"Cell {idx}: NotImplementedError found")
                # Check for hardcoded metrics return
                if re.search(r"def\s+(evaluate|train|validate|calc_metrics)\b[^{}]*return\s+\{[^}]*'dice':\s*0\.[0-9]+", src):
                    flags.append(f"Cell {idx}: hardcoded evaluation metrics dictionary")
        
        passed = len(flags) == 0
        results[nb_file] = {
            "flags": flags,
            "passed": passed
        }
        print(f"[{'PASS' if passed else 'FAIL'}] {nb_file}: {flags if flags else 'CLEAN (No stubs/facades)'}")
    return results

if __name__ == "__main__":
    check_file_properties()
    check_syntax_and_ast()
    check_dataset_and_paths()
    check_max_spec()
    check_cheating_and_facades()
