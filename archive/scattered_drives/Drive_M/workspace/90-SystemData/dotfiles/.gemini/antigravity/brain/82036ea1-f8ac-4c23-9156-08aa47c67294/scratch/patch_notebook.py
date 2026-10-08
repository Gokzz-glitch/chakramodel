import json
import os

nb_path = r"C:\Users\imgk3\Downloads\notebook75ecf07fa0 (1).ipynb"
out_path = r"C:\Users\imgk3\Downloads\notebook75ecf07fa0_fixed.ipynb"
md_path = r"C:\Users\imgk3\.gemini\antigravity\brain\82036ea1-f8ac-4c23-9156-08aa47c67294\diagnostic_script.md"

if not os.path.exists(nb_path):
    print("Could not find notebook file.")
    exit(1)

with open(md_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

script_lines = []
in_code = False
for line in lines:
    if line.startswith("```python"):
        in_code = True
        continue
    if line.startswith("```"):
        in_code = False
        continue
    if in_code:
        script_lines.append(line)

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

replaced = False
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        if "def run_diagnostics():" in source:
            cell['source'] = script_lines
            replaced = True
            break

if not replaced:
    print("Could not find the diagnostic cell in the notebook.")
    exit(1)

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"Successfully saved updated notebook to: {out_path}")
