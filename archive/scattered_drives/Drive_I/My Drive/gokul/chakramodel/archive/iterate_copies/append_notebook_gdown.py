import json

from pathlib import Path
root = Path(__file__).resolve().parent
nb_path = root / 'ChakraModel_Video_Evaluation_Kaggle.ipynb'

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

md_cell = {
    'cell_type': 'markdown',
    'metadata': {},
    'source': [
        '### 6. Custom Archive Download & Test (gdown)\n',
        'Use this section to directly download and test datasets (like Kvasir-Capsule) using Google Drive links, bypassing local uploads.'
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
        'print("📥 Downloading Kvasir-Capsule or Custom Video Dataset...")\n',
        '# Replace with your Google Drive File ID\n',
        'file_id = \'1QEMKV632XGGs9202iTyH-QggV_F3dSED\'\n',
        'url = f\'https://drive.google.com/uc?id={file_id}\'\n',
        'gdown.download(url, \'/kaggle/working/custom_videos.tar.gz\', quiet=False)\n',
        '\n',
        'print("📦 Extracting videos...")\n',
        'os.system("tar -xf /kaggle/working/custom_videos.tar.gz -C /kaggle/working/")\n',
        '\n',
        'print("🔍 Searching for the extracted .mp4 files...")\n',
        'video_files = glob.glob("/kaggle/working/**/*.mp4", recursive=True)\n',
        '\n',
        'if video_files:\n',
        '    print(f"✅ Found {len(video_files)} video(s)!")\n',
        '    test_video = video_files[0]\n',
        '    output_video = "/kaggle/working/custom_test_output.mp4"\n',
        '    print(f"🚀 Running ChakraModel on: {test_video}")\n',
        '    process_video_benchmark(test_video, output_video)\n',
        '    print(f"🎉 Done! Download your processed video from: {output_video}")\n',
        'else:\n',
        '    print("⚠️ No .mp4 files found after extraction. Check the contents of the tar file.")'
    ]
}

nb['cells'].extend([md_cell, code_cell])

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)
