import json
import ast
import os
import re

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"
NOTEBOOKS = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb",
]

def analyze_notebook(nb_name):
    nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
    if not os.path.exists(nb_path):
        return {"error": f"File {nb_name} not found"}
    
    with open(nb_path, "r", encoding="utf-8") as f:
        try:
            nb = json.load(f)
        except Exception as e:
            return {"error": f"Failed to parse JSON: {e}"}
            
    cells = nb.get("cells", [])
    markdown_cells = []
    code_cells = []
    
    combined_code = []
    syntax_errors = []
    
    for idx, cell in enumerate(cells):
        cell_type = cell.get("cell_type", "")
        source = "".join(cell.get("source", []))
        if cell_type == "markdown":
            markdown_cells.append((idx, source))
        elif cell_type == "code":
            code_cells.append((idx, source))
            # Test AST syntax parsing (stripping IPython magic lines like ! or %)
            clean_lines = []
            for line in cell.get("source", []):
                stripped = line.strip()
                if stripped.startswith("!") or stripped.startswith("%"):
                    clean_lines.append(f"# {line}")
                else:
                    clean_lines.append(line)
            code_to_parse = "".join(clean_lines)
            try:
                ast.parse(code_to_parse)
            except SyntaxError as e:
                syntax_errors.append({"cell_index": idx, "error": str(e), "line": e.lineno, "text": e.text})
            combined_code.append(code_to_parse)
            
    full_code = "\n\n# --- NEXT CELL ---\n\n".join(combined_code)
    
    # Check max-spec elements
    has_resnet101 = "resnet101" in full_code.lower()
    has_vit_large = "vit_large_patch16_384" in full_code
    has_yolov8x = "yolov8x" in full_code.lower()
    has_bs32 = bool(re.search(r'batch_size\s*=\s*32|BATCH_SIZE\s*=\s*32', full_code))
    has_workers4 = bool(re.search(r'num_workers\s*=\s*4|NUM_WORKERS\s*=\s*4', full_code))
    
    # Check dataset download and path
    has_kvasir_download = ("kvasir" in full_code.lower() or "kvasir" in "".join([m[1] for m in markdown_cells]).lower()) and ("download" in full_code.lower() or "wget" in full_code.lower() or "urllib" in full_code.lower() or "requests" in full_code.lower() or "curl" in full_code.lower() or "zipfile" in full_code.lower())
    has_kaggle_working_path = "/kaggle/working/data/kvasir-seg" in full_code or "kvasir-seg" in full_code.lower()
    
    # Check external repo cloning
    has_git_clone = "git clone" in full_code
    
    # Check integrity / dummy markers
    suspicious_patterns = []
    if re.search(r'#.*hardcoded|fake_metric|dummy_data|# TODO: implement', full_code, re.I):
        suspicious_patterns.append("Found suspicious dummy/TODO comments")
        
    return {
        "nb_name": nb_name,
        "total_cells": len(cells),
        "markdown_cells_count": len(markdown_cells),
        "code_cells_count": len(code_cells),
        "syntax_errors": syntax_errors,
        "has_resnet101": has_resnet101,
        "has_vit_large": has_vit_large,
        "has_yolov8x": has_yolov8x,
        "has_bs32": has_bs32,
        "has_workers4": has_workers4,
        "has_kvasir_download": has_kvasir_download,
        "has_kaggle_working_path": has_kaggle_working_path,
        "has_git_clone": has_git_clone,
        "suspicious_patterns": suspicious_patterns,
        "full_code_len": len(full_code),
    }

if __name__ == "__main__":
    results = {}
    for nb in NOTEBOOKS:
        res = analyze_notebook(nb)
        results[nb] = res
        print(f"=== {nb} ===")
        for k, v in res.items():
            if k != "full_code":
                print(f"  {k}: {v}")
        print()
