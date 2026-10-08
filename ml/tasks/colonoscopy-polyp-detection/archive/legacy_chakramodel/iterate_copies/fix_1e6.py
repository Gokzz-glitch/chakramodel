import glob
import json
import re

notebooks = glob.glob(r'm:\chakramodel\notebooks\Combo*.ipynb') + \
            glob.glob(r'm:\chakramodel\notebooks\deprecated\Combo*.ipynb')

for nb_path in notebooks:
    try:
        with open(nb_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
            
        changed = False
        for cell in nb.get('cells', []):
            if cell.get('cell_type') == 'code':
                new_source = []
                for line in cell['source']:
                    # Simple regex to replace 1e6 with 1e-6 in IoU context
                    if '1e6' in line and ('iou' in line.lower() or 'dice' in line.lower() or 'prec' in line.lower() or 'rec' in line.lower() or 'spec' in line.lower()):
                        line = re.sub(r'1e6', '1e-6', line)
                        changed = True
                    new_source.append(line)
                cell['source'] = new_source
                
        if changed:
            with open(nb_path, 'w', encoding='utf-8') as f:
                json.dump(nb, f, indent=1)
            print(f"Fixed typo in: {nb_path}")
    except Exception as e:
        print(f"Failed {nb_path}: {e}")

print("Done fixing 1e6 typos.")
