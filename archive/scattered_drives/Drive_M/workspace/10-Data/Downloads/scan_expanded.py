import os
import json
import time

# EXPANDED keyword list to catch anything missed
keywords = [
    'chakra', 'polyp', 'colonoscopy', 'pranet', 'teacherstudent', 'kvasir',
    'yolo', 'segformer', 'unet', 'endoscop', 'colon', 'gastro',
    'segmentation', 'adenoma', 'lesion', 'mucosa', 'gi_tract',
    'piccolo', 'polypgen', 'hyperkvasir', 'cvc-300', 'cvc-612',
    'etis', 'clinicdb', 'neoplasm', 'adabn', 'leakbench',
    'xattn', 'pvt', 'rfb', 'reverse_attention', 'endo_fm',
    'dice_focal', 'seg_metrics'
]

# Drives to scan - Google Drive mounts
drives_to_scan = ['G:\\', 'H:\\', 'I:\\', 'J:\\']

# Also do a wider scan of C:\ user folder and D:\ with expanded keywords
drives_to_scan += ['C:\\Users\\imgk3\\', 'D:\\']

skip_folders = {
    'windows', 'program files', 'program files (x86)', 'appdata', 
    'node_modules', '$recycle.bin', 'system volume information', 
    'perflogs', 'programdata', '.git', '__pycache__', 'venv', '.venv',
    '.gemini', '.cache', '.npm', '.nuget', 'temp', 'tmp'
}

results = []
seen_paths = set()

start_time = time.time()

for drive in drives_to_scan:
    print(f"Scanning {drive}...")
    try:
        for root, dirs, files in os.walk(drive):
            dirs[:] = [d for d in dirs if d.lower() not in skip_folders]
            
            for file in files:
                file_lower = file.lower()
                path_lower = root.lower()
                
                if any(kw in file_lower for kw in keywords) or any(kw in path_lower for kw in keywords):
                    try:
                        filepath = os.path.join(root, file)
                        if filepath in seen_paths:
                            continue
                        seen_paths.add(filepath)
                        size = os.path.getsize(filepath)
                        results.append({
                            'path': filepath,
                            'name': file,
                            'size': size,
                            'drive': drive
                        })
                    except OSError:
                        pass
    except Exception as e:
        print(f"Error on {drive}: {e}")

output_file = r"C:\Users\imgk3\Downloads\scan_results_expanded.json"
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)

elapsed = time.time() - start_time
print(f"\nExpanded scan complete in {elapsed:.1f} seconds.")
print(f"Total files matched: {len(results)}")

# Quick breakdown by drive
from collections import Counter
drive_counts = Counter(item['drive'] for item in results)
for d, c in sorted(drive_counts.items()):
    print(f"  {d}: {c} files")

print(f"\nResults saved to {output_file}")
