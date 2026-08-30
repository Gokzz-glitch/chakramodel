import ast
import json
import os
import sys

def extract_defs_from_notebook(nb_path):
    with open(nb_path, 'r', encoding='utf-8') as f:
        nb_json = json.load(f)
        
    code_cells = [c for c in nb_json.get('cells', []) if c.get('cell_type') == 'code']
    
    extracted_classes = {}
    extracted_functions = {}
    
    for cell_idx, cell in enumerate(code_cells):
        lines = cell.get('source', [])
        # Strip magic lines
        clean_lines = []
        for l in lines:
            stripped = l.strip()
            if stripped.startswith('!') or stripped.startswith('%'):
                clean_lines.append('# ' + l)
            else:
                clean_lines.append(l)
        code_str = ''.join(clean_lines)
        
        try:
            tree = ast.parse(code_str)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    class_code = ast.get_source_segment(code_str, node)
                    extracted_classes[node.name] = (cell_idx, class_code)
                elif isinstance(node, ast.FunctionDef):
                    func_code = ast.get_source_segment(code_str, node)
                    extracted_functions[node.name] = (cell_idx, func_code)
        except Exception as e:
            print(f"Error parsing cell {cell_idx} in {nb_path}: {e}")
            
    return extracted_classes, extracted_functions

def main():
    nb_path = r"m:\chakramodel\notebooks\Combo1_ChakraNet_Focal.ipynb"
    classes, funcs = extract_defs_from_notebook(nb_path)
    print("Extracted classes from Combo 1:", list(classes.keys()))
    print("Extracted funcs from Combo 1:", list(funcs.keys()))

if __name__ == '__main__':
    main()
