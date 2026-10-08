import json

with open("notebooks/Kaggle_Final_Proof_Eval.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

print(f"Total cells: {len(nb['cells'])}")

code_idx = 0
for idx, cell in enumerate(nb['cells']):
    c_type = cell.get('cell_type')
    src = cell.get('source', [])
    first_line = src[0].strip() if src else ""
    if c_type == 'code':
        print(f"Cell {idx} (Code #{code_idx}): {first_line[:80]}")
        code_idx += 1
    else:
        print(f"Cell {idx} (Markdown): {first_line[:80]}")
