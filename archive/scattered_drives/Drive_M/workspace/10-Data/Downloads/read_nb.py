import json
import sys

nb = json.load(open(r'C:\Users\imgk3\Downloads\omteacherstudent.ipynb', 'r', encoding='utf-8'))

print(f"Notebook: {len(nb['cells'])} cells")
print(f"Kernel: {nb.get('metadata', {}).get('kernelspec', {}).get('display_name', '?')}")
print()

for i, cell in enumerate(nb['cells']):
    src = ''.join(cell['source'])
    cell_type = cell['cell_type']
    lines = src.split('\n')
    preview = src[:300].replace('\n', '\n  ')
    print(f"{'='*80}")
    print(f"CELL {i} [{cell_type}] ({len(lines)} lines)")
    print(f"{'='*80}")
    print(f"  {preview}")
    if len(src) > 300:
        print(f"  ... ({len(src)} chars total)")
    print()
