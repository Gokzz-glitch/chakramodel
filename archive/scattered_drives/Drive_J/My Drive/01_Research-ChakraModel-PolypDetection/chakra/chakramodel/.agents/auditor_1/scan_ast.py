import json
import re
import ast
import os
import sys
import traceback

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"
NOTEBOOK_FILES = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb",
]

def clean_code_for_ast(code_lines):
    cleaned = []
    for line in code_lines:
        stripped = line.strip()
        # Remove shell commands and ipython magics
        if stripped.startswith('!') or stripped.startswith('%'):
            cleaned.append('# ' + line)
        else:
            cleaned.append(line)
    return ''.join(cleaned)

def audit_notebook_structure(nb_path):
    with open(nb_path, 'r', encoding='utf-8') as f:
        nb_json = json.load(f)
    
    nbformat = nb_json.get('nbformat', None)
    cells = nb_json.get('cells', [])
    
    code_cells = [c for c in cells if c.get('cell_type') == 'code']
    markdown_cells = [c for c in cells if c.get('cell_type') == 'markdown']
    
    return {
        'nbformat': nbformat,
        'total_cells': len(cells),
        'code_cells_count': len(code_cells),
        'markdown_cells_count': len(markdown_cells),
        'cells': cells
    }

def main():
    print("=== STARTING FORENSIC INTEGRITY AUDIT ===")
    results = {}
    
    for nb_file in NOTEBOOK_FILES:
        nb_path = os.path.join(NOTEBOOKS_DIR, nb_file)
        print(f"\n--- Auditing {nb_file} ---")
        if not os.path.exists(nb_path):
            print(f"ERROR: File not found: {nb_path}")
            continue
            
        struct = audit_notebook_structure(nb_path)
        print(f"Format: v{struct['nbformat']}, Total Cells: {struct['total_cells']}, Code: {struct['code_cells_count']}, MD: {struct['markdown_cells_count']}")
        
        all_code_blocks = []
        ast_errors = []
        empty_stubs = []
        hardcoded_returns = []
        not_implemented = []
        classes_found = []
        functions_found = []
        
        for idx, cell in enumerate(struct['cells']):
            if cell.get('cell_type') == 'code':
                raw_code = ''.join(cell.get('source', []))
                cleaned_code = clean_code_for_ast(cell.get('source', []))
                all_code_blocks.append((idx, cleaned_code, raw_code))
                
                try:
                    tree = ast.parse(cleaned_code)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            classes_found.append(node.name)
                        elif isinstance(node, ast.FunctionDef):
                            functions_found.append(node.name)
                            # Check body for empty stub (only pass)
                            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                                empty_stubs.append((node.name, idx, 'only pass'))
                            # Check body for NotImplementedError
                            if len(node.body) == 1 and isinstance(node.body[0], ast.Raise):
                                not_implemented.append((node.name, idx))
                            # Check body for return constant without logic
                            if len(node.body) == 1 and isinstance(node.body[0], ast.Return):
                                if isinstance(node.body[0].value, ast.Constant):
                                    hardcoded_returns.append((node.name, idx, node.body[0].value.value))
                except Exception as e:
                    ast_errors.append((idx, str(e)))
        
        print(f"Classes Found ({len(classes_found)}): {classes_found}")
        print(f"Functions Found ({len(functions_found)}): {functions_found[:10]}... (total {len(functions_found)})")
        print(f"AST Parse Errors: {len(ast_errors)}")
        if ast_errors:
            for err in ast_errors:
                print(f"  Cell {err[0]}: {err[1]}")
        print(f"Empty Stubs (pass only): {len(empty_stubs)} -> {empty_stubs}")
        print(f"NotImplemented Raises: {len(not_implemented)} -> {not_implemented}")
        print(f"Single Constant Returns: {len(hardcoded_returns)} -> {hardcoded_returns}")

if __name__ == '__main__':
    main()
