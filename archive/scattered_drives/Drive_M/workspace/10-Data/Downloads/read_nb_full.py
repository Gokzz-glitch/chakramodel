import json
nb = json.load(open(r'C:\Users\imgk3\Downloads\omteacherstudent.ipynb', 'r', encoding='utf-8'))

# Print full code cells
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        print(f"{'='*80}")
        print(f"CELL {i} [code]")
        print(f"{'='*80}")
        print(src)
        print()
