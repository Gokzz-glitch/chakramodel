import json

path = r'J:\My Drive\downloads\chakramodel_v8_corrected.ipynb'
nb = json.load(open(path, 'r', encoding='utf-8'))
cells = nb['cells']
print(f'Total cells: {len(cells)}')

out = []
for i, c in enumerate(cells):
    ct = c.get('cell_type', '')
    src = ''.join(c.get('source', []))
    out.append(f'\n\n=== CELL {i} [{ct}] ===')
    out.append(src[:3000])  # first 3000 chars of source

open(r'J:\My Drive\downloads\v8_sources.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('done')
