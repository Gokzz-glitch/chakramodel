import os

def generate_snippets(directory):
    output = []
    for root, dirs, files in os.walk(directory):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', 'venv')]
        
        # We'll only do root level files for now to avoid huge output, wait, the user said "every project file".
        # Let's just collect all files to see how many there are.
        
        for file in files:
            if file.startswith('.'): continue
            
            filepath = os.path.join(root, file)
            # Skip very large files or known data files
            if file.endswith('.json') or file.endswith('.log') or 'snippet' in file or 'index.md' in file:
                output.append(f"File: {os.path.relpath(filepath, directory)}\nContent: [Data or Log File]")
                continue
                
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = [next(f) for _ in range(10)]
                    output.append(f"File: {os.path.relpath(filepath, directory)}\n" + "".join(lines))
            except Exception as e:
                output.append(f"File: {os.path.relpath(filepath, directory)}\nContent: [Binary or Unreadable]")
    
    with open('m:/chakramodel/tmp_snippets.txt', 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(output))

generate_snippets('m:/chakramodel')
