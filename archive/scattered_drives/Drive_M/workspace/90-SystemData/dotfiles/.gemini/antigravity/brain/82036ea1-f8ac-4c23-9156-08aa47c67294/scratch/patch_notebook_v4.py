import json
import os
import re

nb_path = r"C:\Users\imgk3\Downloads\notebook75ecf07fa0 (3).ipynb"
out_path = r"C:\Users\imgk3\Downloads\notebook75ecf07fa0_v4_fully_fixed.ipynb"

if not os.path.exists(nb_path):
    print("Could not find notebook file.")
    exit(1)

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

# 1. Fix verify_kaggle.py (cell containing %%writefile /kaggle/working/verify_kaggle.py)
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        if "%%writefile /kaggle/working/verify_kaggle.py" in source:
            # Replace the sys.path logic
            old_logic = """    # Identify codebase path
    code_dir = None
    for root, dirs, files in os.walk('/kaggle/input'):
        if 'chakranet_segmenter.py' in files and 'src' in root:
            code_dir = root
            break
    if not code_dir:
        for root, dirs, files in os.walk('/kaggle/input'):
            if 'chakranet_segmenter.py' in files:
                code_dir = root
                break
    assert code_dir, "FATAL: ChakraModel codebase not found in /kaggle/input"
    sys.path.insert(0, code_dir)
    print(f"[VERIFY] Codebase found at: {code_dir}")"""
            
            new_logic = """    # Identify codebase path
    src_dirs_added = []
    for root, dirs, files in os.walk('/kaggle/input'):
        if os.path.basename(root) == 'src':
            sys.path.insert(0, root)
            src_dirs_added.append(root)
    if not src_dirs_added:
        for root, dirs, files in os.walk('/kaggle/input'):
            if 'chakranet_segmenter.py' in files:
                sys.path.insert(0, root)
                src_dirs_added.append(root)
    print(f"[VERIFY] Codebase dirs added: {src_dirs_added}")"""
            
            if old_logic in source:
                new_source = source.replace(old_logic, new_logic)
                
                # Also fix the float16 bug in the verify_kaggle.py!
                # Because verify_kaggle.py also does inference and compute_all!
                if "prob_np = prob.squeeze().cpu().numpy()" in new_source:
                    new_source = new_source.replace("prob_np = prob.squeeze().cpu().numpy()", "prob_np = prob.squeeze().float().cpu().numpy().astype(np.float32)")
                    
                # Break new_source into list of lines for Jupyter JSON format
                lines = [line + '\n' for line in new_source.split('\n')]
                # Fix the last line to not have \n if it didn't originally
                if not source.endswith('\n'):
                    lines[-1] = lines[-1].rstrip('\n')
                
                cell['source'] = lines
                print("Patched verify_kaggle.py cell!")
            else:
                print("Could not find the exact old logic in verify_kaggle.py to replace.")

# 2. Fix the diagnostic script (the final cell)
# Wait, I can just replace the whole final cell with the content of diagnostic_script.md
md_path = r"C:\Users\imgk3\.gemini\antigravity\brain\82036ea1-f8ac-4c23-9156-08aa47c67294\diagnostic_script.md"
with open(md_path, "r", encoding="utf-8") as f:
    md_lines = f.readlines()

script_lines = []
in_code = False
for line in md_lines:
    if line.startswith("```python"):
        in_code = True
        continue
    if line.startswith("```"):
        in_code = False
        continue
    if in_code:
        script_lines.append(line)

replaced = False
for cell in reversed(nb['cells']):
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        if "def run_diagnostics():" in source:
            cell['source'] = script_lines
            replaced = True
            print("Patched diagnostic script cell!")
            break

if not replaced:
    print("Could not find the diagnostic cell in the notebook.")

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"Successfully saved updated notebook to: {out_path}")
