import json
from collections import Counter
import os

input_file = r"C:\Users\imgk3\Downloads\scan_results_expanded.json"

try:
    with open(input_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
        
    print(f"Loaded {len(results)} records.")
    
    # Focus on I:\ and J:\
    i_j_files = [f for f in results if f['drive'] in ['I:\\', 'J:\\']]
    
    ext_counter = Counter()
    dir_counter = Counter()
    size_by_ext = Counter()
    
    for item in i_j_files:
        ext = os.path.splitext(item['name'].lower())[1]
        if not ext: ext = "NO_EXTENSION"
        
        ext_counter[ext] += 1
        size_by_ext[ext] += item['size']
        
        # Get top level dir after drive letter
        parts = item['path'].split('\\')
        if len(parts) > 2:
            top_dir = parts[1]
            dir_counter[top_dir] += 1
            
    print("\n--- Top Extensions on I:\ and J:\ ---")
    for ext, count in ext_counter.most_common(10):
        mb = size_by_ext[ext] / (1024*1024)
        print(f"{ext}: {count} files ({mb:.2f} MB)")
        
    print("\n--- Top Directories on I:\ and J:\ ---")
    for d, count in dir_counter.most_common(10):
        print(f"{d}: {count} files")
        
except Exception as e:
    print(f"Error: {e}")
