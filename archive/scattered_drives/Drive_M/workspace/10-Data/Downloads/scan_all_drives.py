import os
import json
import time

drives = ['C:\\', 'M:\\', 'D:\\']
keywords = ['chakra', 'polyp', 'colonoscopy', 'pranet', 'teacherstudent', 'kvasir']

# Folders to skip to save time and avoid permission errors
skip_folders = {
    'windows', 'program files', 'program files (x86)', 'appdata', 'node_modules', 
    '$recycle.bin', 'system volume information', 'perflogs', 'programdata'
}

results = []

start_time = time.time()

for drive in drives:
    print(f"Scanning drive {drive}...")
    try:
        for root, dirs, files in os.walk(drive):
            # Prune skipped directories
            dirs[:] = [d for d in dirs if d.lower() not in skip_folders]
            
            for file in files:
                file_lower = file.lower()
                if any(kw in file_lower for kw in keywords):
                    try:
                        filepath = os.path.join(root, file)
                        size = os.path.getsize(filepath)
                        results.append({
                            'path': filepath,
                            'name': file,
                            'size': size
                        })
                    except OSError:
                        pass
    except Exception as e:
        print(f"Error accessing {drive}: {e}")

output_file = r"C:\Users\imgk3\Downloads\scan_results.json"
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)

elapsed = time.time() - start_time
print(f"Scan complete in {elapsed:.1f} seconds. Found {len(results)} matching files.")
print(f"Results saved to {output_file}")
