import json

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'r') as f:
    nb = json.load(f)

# Remove the old Section 6 (last two cells)
if len(nb['cells']) >= 2 and '### 6.' in nb['cells'][-2]['source'][0]:
    nb['cells'] = nb['cells'][:-2]

md_cell = {
    'cell_type': 'markdown',
    'metadata': {},
    'source': [
        '### 6. Automated Multi-Archive Download & Extraction (Kvasir-Capsule)\n',
        'This section automates the downloading of the 5 selected archives (e.g., `foreign_body.tar.gz`) directly to Kaggle using `gdown`.'
    ]
}

code_cell = {
    'cell_type': 'code',
    'execution_count': None,
    'metadata': {},
    'outputs': [],
    'source': [
        '!pip install -q gdown\n',
        'import gdown\n',
        'import os\n',
        'import glob\n',
        '\n',
        '# Define the archives to download. Replace file_ids with the real ones if you have all 5.\n',
        'archives = {\n',
        '    "foreign_body.tar.gz": "1QEMKV632XGGs9202iTyH-QggV_F3dSED",\n',
        '    # "archive2.tar.gz": "YOUR_FILE_ID_2",\n',
        '    # "archive3.tar.gz": "YOUR_FILE_ID_3",\n',
        '    # "archive4.tar.gz": "YOUR_FILE_ID_4",\n',
        '    # "archive5.tar.gz": "YOUR_FILE_ID_5"\n',
        '}\n',
        '\n',
        'print("📥 Downloading archives from Google Drive...")\n',
        'for filename, file_id in archives.items():\n',
        '    url = f"https://drive.google.com/uc?id={file_id}"\n',
        '    dest_path = f"/kaggle/working/{filename}"\n',
        '    if not os.path.exists(dest_path):\n',
        '        print(f"Downloading {filename}...")\n',
        '        gdown.download(url, dest_path, quiet=False)\n',
        '    \n',
        '    print(f"📦 Extracting {filename}...")\n',
        '    os.system(f"tar -xf {dest_path} -C /kaggle/working/")\n',
        '\n',
        'print("\\n🔍 Searching for extracted .mp4 video files...")\n',
        'video_files = glob.glob("/kaggle/working/**/*.mp4", recursive=True)\n',
        '\n',
        'if video_files:\n',
        '    print(f"✅ Found {len(video_files)} video(s) to test!")\n',
        '    # Test the first extracted video as a proof of concept\n',
        '    test_video = video_files[0]\n',
        '    output_video = "/kaggle/working/custom_test_output.mp4"\n',
        '    \n',
        '    print(f"🚀 Running ChakraModel on: {test_video}")\n',
        '    process_video_benchmark(test_video, output_video)\n',
        '    print(f"🎉 Done! Download your processed video from: {output_video}")\n',
        'else:\n',
        '    print("⚠️ No .mp4 files found. Check if the archives contained videos or just images.")'
    ]
}

nb['cells'].extend([md_cell, code_cell])

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'w') as f:
    json.dump(nb, f, indent=1)
