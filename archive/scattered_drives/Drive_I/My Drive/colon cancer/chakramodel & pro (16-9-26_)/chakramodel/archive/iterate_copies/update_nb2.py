import json
import os

notebook_path = r"C:\Users\imgk3\Downloads\om-krish-4 (2).ipynb"
script_path = r"m:\chakramodel\src\chakra_transformer\train_transformer.py"

with open(script_path, 'r', encoding='utf-8') as f:
    code_lines = f.readlines()

new_source = ["%%writefile src/chakra_transformer/train_transformer.py\n"] + code_lines

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# The notebook has the %%writefile cell. Let's find it and update it.
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and len(cell['source']) > 0 and cell['source'][0].startswith('%%writefile src/chakra_transformer/train_transformer.py'):
        cell['source'] = new_source
        
    # Find the execution cell and change batch-size
    if cell['cell_type'] == 'code' and len(cell['source']) > 0 and any('os.system("python src/chakra_transformer/train_transformer.py' in line for line in cell['source']):
        for i, line in enumerate(cell['source']):
            if '--batch-size 8' in line:
                cell['source'][i] = line.replace('--batch-size 8', '--batch-size 16')

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Successfully injected the DataParallel code and updated batch size in the notebook.")
