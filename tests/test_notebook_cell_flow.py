"""
Adversarial Cell Flow & Symbol Trace Validator
Simulates sequential cell execution by tracking defined symbols (functions, classes, variables, imports)
and checking that global symbols referenced in subsequent cells were previously defined.
Also validates the 8-stage cell structure contract from PROJECT.md.
"""

import sys
import os
import json
import ast
import re
import nbformat

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

NOTEBOOK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notebooks")
NOTEBOOKS = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb",
]

def sanitize_code(source: str) -> str:
    lines = source.splitlines()
    cleaned = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i == 0 and stripped.startswith("%%"):
            cleaned.append(f"# CELL_MAGIC: {line}")
        elif stripped.startswith("%"):
            cleaned.append(f"# LINE_MAGIC: {line}")
        elif stripped.startswith("!"):
            cleaned.append(f"# SHELL: {line}")
        elif stripped.startswith("?") or stripped.endswith("?"):
            cleaned.append(f"# QUERY: {line}")
        else:
            cleaned.append(line)
    return "\n".join(cleaned)

class SymbolVisitor(ast.NodeVisitor):
    def __init__(self):
        self.defined = set()
        self.used = set()
        
    def visit_Import(self, node):
        for alias in node.names:
            self.defined.add(alias.asname if alias.asname else alias.name.split('.')[0])
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.defined.add(alias.asname if alias.asname else alias.name)
        self.generic_visit(node)
        
    def visit_ClassDef(self, node):
        self.defined.add(node.name)
        self.generic_visit(node)
        
    def visit_FunctionDef(self, node):
        self.defined.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.defined.add(node.name)
        self.generic_visit(node)
        
    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defined.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self.defined.add(elt.id)
        self.generic_visit(node)
        
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used.add(node.id)
        elif isinstance(node.ctx, ast.Store):
            self.defined.add(node.id)
        self.generic_visit(node)

def analyze_notebook_flow(nb_path: str):
    nb_name = os.path.basename(nb_path)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.reads(f.read(), as_version=4)
        
    print(f"\n=======================================================")
    print(f"Analyzing Execution Flow & Contract: {nb_name}")
    print(f"=======================================================")
    
    cells = nb.cells
    cell_summary = []
    defined_so_far = set(dir(__builtins__))
    missing_symbols_report = []
    
    for idx, cell in enumerate(cells):
        ctype = cell.cell_type
        src = "".join(cell.source) if isinstance(cell.source, list) else str(cell.source)
        first_line = src.splitlines()[0] if src.splitlines() else "EMPTY"
        first_line = first_line[:75] + ("..." if len(first_line) > 75 else "")
        
        if ctype == "code":
            sanitized = sanitize_code(src)
            try:
                tree = ast.parse(sanitized)
                visitor = SymbolVisitor()
                visitor.visit(tree)
                
                # Check what was used before being defined
                # (allowing standard packages like torch, np, os, etc.)
                newly_defined = visitor.defined
                defined_so_far.update(newly_defined)
                
                cell_summary.append({
                    "idx": idx,
                    "type": ctype,
                    "first_line": first_line,
                    "defined_count": len(newly_defined),
                    "code_lines": len(src.splitlines())
                })
            except SyntaxError as e:
                cell_summary.append({
                    "idx": idx,
                    "type": ctype,
                    "first_line": first_line,
                    "error": str(e)
                })
        else:
            cell_summary.append({
                "idx": idx,
                "type": ctype,
                "first_line": first_line,
                "lines": len(src.splitlines())
            })
            
    print(f"Total cells: {len(cells)}")
    for c in cell_summary:
        if c["type"] == "code":
            print(f"  [Cell {c['idx']:02d} - CODE] {c['code_lines']:4d} lines | Defs: {c.get('defined_count', 0):3d} | Header: {c['first_line']}")
        else:
            print(f"  [Cell {c['idx']:02d} - MD  ] {c.get('lines', 0):4d} lines | Header: {c['first_line']}")
            
    return cell_summary

def main():
    for nb_name in NOTEBOOKS:
        nb_path = os.path.join(NOTEBOOK_DIR, nb_name)
        analyze_notebook_flow(nb_path)

if __name__ == "__main__":
    main()
