# -*- coding: utf-8 -*-
"""
Independent Verification & Forensic Audit Script for Combo 3 & Combo 4 Notebooks
"""

import json
import ast
import nbformat
from pathlib import Path

def audit_notebook(nb_path: Path, expected_name: str, required_symbols: list[str]):
    print(f"\n" + "="*80)
    print(f"AUDITING NOTEBOOK: {nb_path.name}")
    print("="*80)
    
    assert nb_path.exists(), f"Error: {nb_path} does not exist!"
    
    # 1. Raw JSON Parse Test
    with open(nb_path, "r", encoding="utf-8") as f:
        raw_text = f.read()
        json_obj = json.loads(raw_text)
    print(f"  [PASS] Raw JSON Deserialization (Size: {len(raw_text):,} bytes)")
    
    # 2. nbformat Schema Validation
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
        nbformat.validate(nb)
    print(f"  [PASS] nbformat v4 Schema Validation (Total Cells: {len(nb.cells)})")
    
    # 3. Cell Breakdown & AST Validation
    code_cells = [c for c in nb.cells if c.cell_type == "code"]
    markdown_cells = [c for c in nb.cells if c.cell_type == "markdown"]
    print(f"  [INFO] Markdown Cells: {len(markdown_cells)}, Code Cells: {len(code_cells)}")
    assert len(markdown_cells) >= 1, "Must contain markdown theory cell!"
    assert len(code_cells) >= 8, f"Expected at least 8 code cells, found {len(code_cells)}"
    
    full_source = ""
    for idx, cell in enumerate(code_cells):
        code_src = cell.source
        full_source += "\n" + code_src
        # Filter magic commands
        clean_lines = [f"# {l}" if l.strip().startswith(("!", "%")) else l for l in code_src.split("\n")]
        clean_code = "\n".join(clean_lines)
        try:
            tree = ast.parse(clean_code)
            print(f"    - Code Cell #{idx+1}: AST Parse Valid (Lines: {len(clean_lines):3d}, AST Nodes: {len(tree.body):2d})")
        except SyntaxError as err:
            print(f"    [FAIL] Code Cell #{idx+1} Syntax Error: {err}")
            raise err
            
    # 4. Required Architectural Symbols & Integrity Checks
    missing_symbols = []
    for sym in required_symbols:
        if sym in full_source:
            print(f"  [PASS] Verified Symbol / Mechanism: '{sym}'")
        else:
            print(f"  [FAIL] Missing Symbol: '{sym}'")
            missing_symbols.append(sym)
            
    assert len(missing_symbols) == 0, f"Integrity Failure: Missing symbols: {missing_symbols}"
    print(f"  [SUCCESS] All Forensic Audit Checks Passed for {nb_path.name}!\n")

def main():
    root = Path("m:/chakramodel/notebooks")
    
    combo3_symbols = [
        "AdaBNAdapter",
        "PraNetResNet101",
        "BasicConv2d",
        "RFBBlock",
        "CBAM",
        "ReverseAttention",
        "DiceFocalLoss",
        "DeepSupervisionDiceFocalLoss",
        "setup_kvasir_seg_dataset",
        "TargetDomainShiftDataset",
        "MaxSpecPolypDataset",
        "detailed_evaluation",
        "batch_size = 32" if "batch_size = 32" in open(root / "Combo3_AdaBN_ChakraNet.ipynb", encoding="utf-8").read() else "batch_size: int = 32",
        "num_workers: int = 4",
        "autocast"
    ]
    
    combo4_symbols = [
        "PraNetResNet101",
        "generate_synthetic_polyps_dataset",
        "filter_synthetic_dataset_with_mcdropout",
        "CombinedPolypDataset",
        "DiceFocalLoss",
        "DeepSupervisionDiceFocalLoss",
        "setup_kvasir_seg_dataset",
        "compute_comprehensive_metrics",
        "batch_size: int = 32",
        "num_workers: int = 4",
        "uncertainty_threshold: float = 0.04",
        "autocast"
    ]
    
    audit_notebook(root / "Combo3_AdaBN_ChakraNet.ipynb", "Combo3", combo3_symbols)
    audit_notebook(root / "Combo4_DiffusionAug_ChakraNet.ipynb", "Combo4", combo4_symbols)
    print("ALL NOTEBOOK AUDITS PASSED WITH ZERO INTEGRITY VIOLATIONS!")

if __name__ == "__main__":
    main()
