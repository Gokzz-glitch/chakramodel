import json

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find cell 21 (where the video processing occurs)
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'process_video_benchmark' in ''.join(cell['source']):
        new_logic = """
import glob
import os

print("Searching for real clinical videos in all attached datasets...")
mp4_files = glob.glob("/kaggle/input/**/*.mp4", recursive=True)

if mp4_files:
    sample_vid = mp4_files[0]
    print(f"✅ Found real video: {sample_vid}")
    process_video_benchmark(sample_vid, "/kaggle/working/output_eval.mp4")
    print(f"🎉 Done! Download your processed video from: /kaggle/working/output_eval.mp4")
else:
    print("❌ No .mp4 files found in /kaggle/input/!")
    print("Please click '+ Add Input' -> 'Public Datasets', search for 'polyp video' or 'kvasir capsule', and attach any public video dataset.")
"""
        
        # Replace the synthetic data logic with this real data search logic
        lines = cell['source']
        for i, line in enumerate(lines):
            if "import urllib.request" in line or "print(\"Downloading a sample" in line:
                cell['source'] = lines[:i] + [new_logic]
                break
        break

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)
