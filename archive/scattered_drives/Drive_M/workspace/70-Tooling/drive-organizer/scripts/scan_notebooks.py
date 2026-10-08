import os
import json
import csv
import re
import datetime
from pathlib import Path

# Directories to skip during traversal
SKIP_DIRS = {
    '.git', '__pycache__', '.venv', 'venv', 'node_modules', '.cache', 
    'AppData', '.gemini', '.claude', '.codex', '.devin', '.codeium', 
    '.copilot', '.vscode', 'tmp_chrome_user_data', 'drive-organizer', 
    'pranet_env'
}

def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

def extract_imports_and_libs(source):
    imports = []
    libraries = set()
    
    # Matches 'import foo', 'import foo as f', 'from foo import bar'
    import_pattern = re.compile(r'^\s*(?:from\s+([a-zA-Z0-9_.]+)\s+import|import\s+([a-zA-Z0-9_.,\s]+))', re.MULTILINE)
    
    for match in import_pattern.finditer(source):
        full_match = match.group(0).strip()
        imports.append(full_match)
        
        # Extract base library name
        if match.group(1): # from XYZ import
            base_lib = match.group(1).split('.')[0]
            libraries.add(base_lib)
        elif match.group(2): # import XYZ
            # Handle multiple imports separated by commas
            for lib in match.group(2).split(','):
                base_lib = lib.strip().split()[0].split('.')[0]
                libraries.add(base_lib)
                
    return imports, list(libraries)

def extract_datasets(source):
    datasets = set()
    
    # Match common reading patterns
    patterns = [
        r'pd\.read_[a-z]+\(\s*[\'"]([^\'"]+)[\'"]', # pandas read
        r'open\(\s*[\'"]([^\'"]+)[\'"]',            # open file
        r'load\(\s*[\'"]([^\'"]+)[\'"]',            # load file
        r'[\'"]([^\'"]+\.(?:csv|json|npy|npz|zip|h5|hdf5|txt|parquet))[\'"]' # explicit extensions
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, source):
            datasets.add(match.group(1))
            
    return list(datasets)

def parse_notebook(filepath):
    try:
        path = Path(filepath)
        stat = path.stat()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            nb = json.load(f)
            
        metadata = nb.get('metadata', {})
        kernelspec = metadata.get('kernelspec', {})
        cells = nb.get('cells', [])
        
        kernel = kernelspec.get('display_name', 'Unknown')
        language = kernelspec.get('language', 'Unknown')
        
        code_cells = [c for c in cells if c.get('cell_type') == 'code']
        markdown_cells = [c for c in cells if c.get('cell_type') == 'markdown']
        raw_cells = [c for c in cells if c.get('cell_type') == 'raw']
        
        has_outputs = any(len(c.get('outputs', [])) > 0 for c in code_cells)
        
        exec_counts = [c.get('execution_count') for c in code_cells if c.get('execution_count') is not None]
        execution_count_max = max(exec_counts) if exec_counts else 0
        
        created_date = datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()
        modified_date = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
        file_size_bytes = stat.st_size
        
        # Analyze code cells for imports and datasets
        all_code = "\n".join(["".join(c.get('source', [])) for c in code_cells])
        imports, libraries_used = extract_imports_and_libs(all_code)
        datasets_referenced = extract_datasets(all_code)
        
        # Analyze markdown for description
        description = ""
        if markdown_cells:
            first_md_source = "".join(markdown_cells[0].get('source', []))
            description = first_md_source[:200].strip() + ("..." if len(first_md_source) > 200 else "")
            # Remove newlines for cleaner display
            description = description.replace('\n', ' ')
            
        return {
            'notebook_path': str(path.absolute()),
            'notebook_name': path.name,
            'kernel': kernel,
            'language': language,
            'cell_count': len(cells),
            'code_cell_count': len(code_cells),
            'markdown_cell_count': len(markdown_cells),
            'raw_cell_count': len(raw_cells),
            'has_outputs': has_outputs,
            'execution_count_max': execution_count_max,
            'created_date': created_date,
            'modified_date': modified_date,
            'file_size_bytes': file_size_bytes,
            'file_size_human': human_readable_size(file_size_bytes),
            'imports': imports,
            'datasets_referenced': datasets_referenced,
            'libraries_used': libraries_used,
            'description': description
        }
        
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None

def main():
    search_dir = r"C:\Users\imgk3"
    output_dir = Path(search_dir) / "drive-organizer" / "catalog"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    json_out = output_dir / "notebooks.json"
    csv_out = output_dir / "notebooks_summary.csv"
    md_out = output_dir / "notebooks_README.md"
    
    notebooks_data = []
    
    print(f"Scanning for notebooks in {search_dir}...")
    
    for root, dirs, files in os.walk(search_dir):
        # Modify dirs in-place to skip specific directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        
        for file in files:
            if file.endswith('.ipynb'):
                filepath = os.path.join(root, file)
                print(f"Processing: {filepath}")
                nb_data = parse_notebook(filepath)
                if nb_data:
                    notebooks_data.append(nb_data)
                    
    print(f"Found {len(notebooks_data)} valid notebooks.")
    
    if not notebooks_data:
        print("No notebooks found to save.")
        return
        
    # Save JSON
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump(notebooks_data, f, indent=2, ensure_ascii=False)
    print(f"Saved catalog to {json_out}")
    
    # Save CSV
    csv_fields = [
        'notebook_name', 'notebook_path', 'kernel', 'language', 'cell_count', 
        'code_cell_count', 'has_outputs', 'execution_count_max', 'modified_date', 
        'file_size_human', 'description'
    ]
    
    with open(csv_out, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction='ignore')
        writer.writeheader()
        for nb in notebooks_data:
            writer.writerow(nb)
    print(f"Saved CSV summary to {csv_out}")
    
    # Save Markdown README
    with open(md_out, 'w', encoding='utf-8') as f:
        f.write("# Jupyter Notebooks Catalog\n\n")
        f.write(f"Generated on: {datetime.datetime.now().isoformat()}\n")
        f.write(f"Total Notebooks: {len(notebooks_data)}\n\n")
        
        f.write("| Notebook Name | Kernel | Cells | Modified | Size | Description |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        
        for nb in sorted(notebooks_data, key=lambda x: x['notebook_name']):
            name = nb['notebook_name']
            kernel = nb['kernel']
            cells = nb['cell_count']
            mod = nb['modified_date'][:10] # Just the date
            size = nb['file_size_human']
            desc = nb['description']
            
            f.write(f"| {name} | {kernel} | {cells} | {mod} | {size} | {desc} |\n")
            
    print(f"Saved README snippet to {md_out}")
    print("Done!")

if __name__ == "__main__":
    main()
