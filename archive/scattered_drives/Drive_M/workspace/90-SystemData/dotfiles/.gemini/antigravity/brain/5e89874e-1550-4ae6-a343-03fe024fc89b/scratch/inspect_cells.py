import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = 'm:/chakramodelpro/all-in-one-comapriosn-18-9-7am(error found).ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

print("=== CELL 3 OUTPUTS ===")
for o in nb['cells'][3].get('outputs', []):
    print(''.join(o.get('text', [])))

print("=== CELL 6 SOURCE ===")
print(''.join(nb['cells'][6]['source']))

print("=== CELL 7 SOURCE ===")
print(''.join(nb['cells'][7]['source']))

print("=== CELL 7 OUTPUTS ===")
for o in nb['cells'][7].get('outputs', []):
    if 'text' in o:
        print(''.join(o.get('text', [])))
    if 'traceback' in o:
        print('\n'.join(o['traceback']))
