import json
nb = json.load(open(r'J:\My Drive\downloads\chakramodel_v10_eval.ipynb', 'r', encoding='utf-8'))
cells = nb['cells']
print('Valid JSON, cells:', len(cells))
for i, c in enumerate(cells):
    src = ''.join(c['source'])
    print(f'  Cell {i} [{c["cell_type"]}]: {src[:70].strip()}')
