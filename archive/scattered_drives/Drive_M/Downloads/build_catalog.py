import os
import ast

def extract_docstring(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # If it's python, use AST to get module docstring
        if filepath.endswith('.py'):
            module = ast.parse(content)
            docstring = ast.get_docstring(module)
            if docstring:
                return docstring.strip().split('\n')[0]
            
            # Fallback to finding the first comment
            for line in content.split('\n'):
                if line.strip().startswith('#'):
                    return line.strip('#').strip()
                elif line.strip() != '':
                    break
        elif filepath.endswith('.ps1') or filepath.endswith('.sh'):
            for line in content.split('\n'):
                if line.strip().startswith('#'):
                    return line.strip('#').strip()
                elif line.strip() != '':
                    break
                    
        return "No description available."
    except Exception as e:
        return f"Could not read: {e}"

# Read the file list from the previously run task-249 log, or just scan D:\ChakraModelPro
base_dir = r"D:\ChakraModelPro"
skip_folders = {'.git', '__pycache__', 'venv', '.venv', 'node_modules', '.agents'}

catalog = []

for root, dirs, files in os.walk(base_dir):
    dirs[:] = [d for d in dirs if d.lower() not in skip_folders]
    for file in files:
        if file.endswith(('.py', '.ps1', '.sh', '.ipynb')):
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, base_dir)
            desc = "Jupyter Notebook" if file.endswith('.ipynb') else extract_docstring(filepath)
            
            # Simple heuristic categorization based on folder or name
            cat = "Miscellaneous"
            if 'model' in rel_path.lower(): cat = "Modeling & Core"
            elif 'data' in rel_path.lower(): cat = "Data Processing"
            elif 'script' in rel_path.lower(): cat = "Automation Scripts"
            elif 'report' in rel_path.lower() or 'audit' in rel_path.lower(): cat = "Audits & Reporting"
            elif 'eval' in file.lower() or 'infer' in file.lower(): cat = "Evaluation & Inference"
            elif 'train' in file.lower(): cat = "Core Training"
            
            catalog.append({
                'file': file,
                'rel_path': rel_path,
                'desc': desc[:150] + "..." if len(desc) > 150 else desc,
                'category': cat,
                'path_uri': filepath.replace('\\', '/')
            })

# Generate Markdown Draft
output_file = r"C:\Users\imgk3\.gemini\antigravity\brain\ed10122d-e091-4566-9916-252437fa3b14\draft_code_catalog.md"

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("# Draft Code and Automation Catalog\n\n")
    f.write("Please review this automatically generated catalog of all scripts. Once approved, I will build the master README.\n\n")
    
    # Group by category
    categories = set(item['category'] for item in catalog)
    for cat in sorted(categories):
        f.write(f"## {cat}\n\n")
        f.write("| Script | Path | Description |\n")
        f.write("|---|---|---|\n")
        for item in sorted([i for i in catalog if i['category'] == cat], key=lambda x: x['file']):
            f.write(f"| `[{item['file']}](file:///{item['path_uri']})` | `{item['rel_path']}` | {item['desc']} |\n")
        f.write("\n")

print(f"Draft catalog generated at {output_file}")
