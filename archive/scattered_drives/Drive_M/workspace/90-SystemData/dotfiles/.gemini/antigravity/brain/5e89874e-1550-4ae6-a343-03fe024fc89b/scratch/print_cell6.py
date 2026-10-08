import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = 'm:/chakramodelpro/all-in-one-comapriosn-18-9-7am(error found).ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

print("=== CELL 6 FULL SOURCE ===")
print(''.join(nb['cells'][6]['source']))
