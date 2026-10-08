import json
import os

notebook_path = r"C:\Users\imgk3\Downloads\notebookb7c036bec1 (2).ipynb"
script_path = r"m:\chakramodel\src\chakra_transformer\train_transformer.py"

with open(script_path, 'r', encoding='utf-8') as f:
    code_lines = f.readlines()

new_source = ["%%writefile src/chakra_transformer/train_transformer.py\n"] + code_lines

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# The notebook has cells. 
# We want to insert the overwrite cell right before the training cell.
# The training cell is the last one (index 2).
# Let's just insert it at index 2 (so it becomes the 3rd cell, pushing the training cell to 4th).
new_cell = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": new_source
}

nb['cells'].insert(2, new_cell)

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Successfully injected the updated code into the notebook.")
