import json
import os
import sys
import ast
import re

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

def audit_all_notebooks():
    audit_results = {}
    
    for nb_name in NOTEBOOKS:
        nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
            
        cells = nb.get("cells", [])
        markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]
        code_cells = [c for c in cells if c.get("cell_type") == "code"]
        
        # Aggregate code
        cleaned_code_cells = []
        for c in code_cells:
            src = "".join(c.get("source", []))
            lines = []
            for l in src.splitlines(True):
                s = l.strip()
                if s.startswith("!") or s.startswith("%"):
                    lines.append(f"# {l}")
                else:
                    lines.append(l)
            cleaned_code_cells.append("".join(lines))
            
        full_code = "\n\n# --- CELL DIVIDER ---\n\n".join(cleaned_code_cells)
        
        # 1. AST check
        ast_errors = []
        for idx, c_code in enumerate(cleaned_code_cells):
            try:
                ast.parse(c_code)
            except SyntaxError as e:
                ast_errors.append(f"Cell {idx} SyntaxError: {e}")
                
        # 2. Backbone check
        is_combo6 = "Combo6" in nb_name
        is_combo1 = "Combo1" in nb_name
        
        resnet101_found = "resnet101" in full_code.lower()
        vit_large_found = "vit_large_patch16_384" in full_code
        yolov8x_found = "yolov8x" in full_code.lower()
        
        # 3. Batch size and num_workers check
        # Look for explicit 32 / 4 in DataLoader or Config
        bs_32_matches = re.findall(r'(?:batch_size|BATCH_SIZE)\s*(?::\s*int)?\s*=\s*32', full_code)
        nw_4_matches = re.findall(r'(?:num_workers|NUM_WORKERS)\s*(?::\s*int)?\s*=\s*4', full_code)
        
        # Check DataLoader calls
        dataloader_calls = re.findall(r'DataLoader\([^)]+\)', full_code, re.DOTALL)
        
        # 4. Kvasir-SEG download & extraction path
        kvasir_urls = re.findall(r'https?://[^\s"\']+(?:kvasir|simula|zenodo|huggingface)[^\s"\']+', full_code, re.IGNORECASE)
        kaggle_path_check = "/kaggle/working/data/kvasir-seg" in full_code
        
        # 5. External repo clone check
        git_clone_check = "git clone" in full_code
        
        # 6. Integrity check
        # Check for genuine training loops (optimizer.step, loss.backward, model.train, model.eval, etc.)
        has_backward = "backward()" in full_code
        has_optimizer_step = "optimizer.step()" in full_code or "opt.step()" in full_code or "step()" in full_code
        has_amp = "autocast" in full_code and "GradScaler" in full_code
        
        # Check for hardcoded metrics
        # Look for fake evaluation functions that return fixed constants
        hardcoded_metric_patterns = re.findall(r'return\s*\{\s*["\'](?:DSC|Dice|mIoU|Precision|Recall)["\']\s*:\s*0\.\d+', full_code)
        
        audit_results[nb_name] = {
            "total_cells": len(cells),
            "markdown_cells": len(markdown_cells),
            "code_cells": len(code_cells),
            "ast_errors": ast_errors,
            "resnet101_found": resnet101_found,
            "vit_large_found": vit_large_found,
            "yolov8x_found": yolov8x_found,
            "bs_32_matches": len(bs_32_matches),
            "nw_4_matches": len(nw_4_matches),
            "dataloader_count": len(dataloader_calls),
            "kvasir_urls": kvasir_urls,
            "kaggle_path_present": kaggle_path_check,
            "git_clone_present": git_clone_check,
            "has_backward": has_backward,
            "has_optimizer_step": has_optimizer_step,
            "has_amp": has_amp,
            "hardcoded_metric_patterns": hardcoded_metric_patterns,
        }
        
    return audit_results

if __name__ == "__main__":
    results = audit_all_notebooks()
    print(json.dumps(results, indent=2))
