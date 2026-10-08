import sys
import os
import glob
import ast
import nbformat

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

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

NOTEBOOK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notebooks")
notebooks = sorted(glob.glob(os.path.join(NOTEBOOK_DIR, "Combo*.ipynb")))

print("==================================================================")
print("INDIVIDUAL CELL-BY-CELL AST PARSE & NODE INVENTORY")
print("==================================================================")

total_code_cells = 0
total_md_cells = 0
total_lines = 0

for nb_path in notebooks:
    nb_name = os.path.basename(nb_path)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = nbformat.reads(f.read(), as_version=4)
        
    print(f"\nNotebook: {nb_name} (nbformat v{nb.nbformat}.{nb.nbformat_minor})")
    for idx, cell in enumerate(nb.cells):
        ctype = cell.cell_type
        src = "".join(cell.source) if isinstance(cell.source, list) else str(cell.source)
        lines = len(src.splitlines())
        total_lines += lines
        
        if ctype == "markdown":
            total_md_cells += 1
            print(f"  Cell {idx} [MD  ]: {lines:3d} lines | Header: {src.splitlines()[0][:60]}")
        elif ctype == "code":
            total_code_cells += 1
            sanitized = sanitize_code(src)
            try:
                tree = ast.parse(sanitized, filename=f"{nb_name}_cell_{idx}.py")
                node_types = {}
                for node in ast.iter_child_nodes(tree):
                    tname = type(node).__name__
                    node_types[tname] = node_types.get(tname, 0) + 1
                    
                node_summary = ", ".join([f"{k}: {v}" for k, v in sorted(node_types.items())])
                print(f"  Cell {idx} [CODE]: {lines:3d} lines | AST: OK ({node_summary})")
            except SyntaxError as e:
                print(f"  Cell {idx} [CODE]: {lines:3d} lines | AST ERROR: {e}")

print("\n==================================================================")
print(f"TOTALS: {len(notebooks)} Notebooks | {total_code_cells} Code Cells | {total_md_cells} Markdown Cells | {total_lines} Total Lines of Code/Markdown")
print("==================================================================")
