import json

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find cell 21 (where the video processing occurs)
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'process_video_benchmark' in ''.join(cell['source']) and 'VIDEO_DATASET' in ''.join(cell['source']):
        source_str = "".join(cell['source'])
        if "sample_vid = os.path.join(VIDEO_DATASET, \"1.mp4\")" in source_str:
            new_logic = """
import glob
if VIDEO_DATASET and os.path.exists(VIDEO_DATASET):
    mp4_files = glob.glob(os.path.join(VIDEO_DATASET, "**/*.mp4"), recursive=True)
    if mp4_files:
        sample_vid = mp4_files[0]
        print(f"Found video: {sample_vid}")
        process_video_benchmark(sample_vid, "/kaggle/working/output_eval.mp4")
    else:
        print(f"No .mp4 files found in {VIDEO_DATASET}")
else:
    print("ClinicVideoDB dataset not found. Attach it to run video benchmarks.")
"""
            # Replace the old logic
            lines = cell['source']
            for i, line in enumerate(lines):
                if line.strip().startswith("if VIDEO_DATASET"):
                    # Delete the rest of the lines
                    cell['source'] = lines[:i] + [new_logic]
                    break
        break

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)
