import json
import os

nb_path = r'C:\Users\imgk3\Downloads\chakramodel-testing (3).ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# 1. Fix the Pip Install cell to include ffmpeg
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        if '!pip install ultralytics' in src:
            new_src = '!apt-get update && apt-get install -y ffmpeg\n!pip install ultralytics opencv-python-headless pandas numpy torch torchvision'
            cell['source'] = [new_src]
            break

# 2. Add the monkey patch cell before the benchmark
bench_idx = -1
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code' and 'run_benchmark' in ''.join(cell['source']):
        bench_idx = i
        break

if bench_idx != -1:
    patch_source = [
        "import sys\n",
        "sys.path.append(REPO_PATH)\n",
        "from src.pranet_segmenter import PraNetSegmenter\n",
        "\n",
        "# Intercept the initialization in memory to force 352x352 resolution\n",
        "original_init = PraNetSegmenter.__init__\n",
        "\n",
        "def patched_init(self, device=None, img_size=(352, 352), weights_path=None):\n",
        "    original_init(self, device=device, img_size=(352, 352), weights_path=weights_path)\n",
        "\n",
        "PraNetSegmenter.__init__ = patched_init\n",
        "print('✅ Monkey-patched PraNetSegmenter! Full-resolution benchmarking enabled.')"
    ]
    # Check if we already inserted a patch cell (to avoid duplicates if run multiple times)
    prev_src = ''.join(nb['cells'][bench_idx - 1]['source'])
    if 'PraNetSegmenter.__init__' not in prev_src:
        patch_cell = {
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {},
            'outputs': [],
            'source': patch_source
        }
        nb['cells'].insert(bench_idx, patch_cell)

# 3. Update the video testing cell
vid_source = [
        "from app import process_video\n",
        "import glob\n",
        "from pathlib import Path\n",
        "import shutil\n",
        "import os\n",
        "\n",
        "# 1. Automatically find any .mp4 file in your dataset\n",
        "mp4_files = list(Path(REPO_PATH).rglob('*.mp4'))\n",
        "if not mp4_files:\n",
        "    print('No .mp4 files found in your dataset. Upload one to test the video pipeline.')\n",
        "else:\n",
        "    video_file = mp4_files[0]\n",
        "    print(f'Found video: {video_file}')\n",
        "    print(f'Processing video (this may take a moment)...')\n",
        "    \n",
        "    # Run the ChakraModel tracker\n",
        "    out_video_path, df_timeline = process_video(\n",
        "        str(video_file), \n",
        "        use_persistence=True, \n",
        "        window_size=10, \n",
        "        persistence_threshold=0.6, \n",
        "        doubt_policy='Warn Only', \n",
        "        imgsz_val='1024'\n",
        "    )\n",
        "    \n",
        "    # 2. Safely handle the Kaggle output environment\n",
        "    working_dir = Path('/kaggle/working') if os.path.exists('/kaggle/working') else Path('.')\n",
        "    final_vid = working_dir / f'output_{video_file.name}'\n",
        "    \n",
        "    try:\n",
        "        shutil.copy2(out_video_path, final_vid)\n",
        "        print(f'Processed video saved to output: {final_vid}')\n",
        "        print('\\nTimeline of Detections:')\n",
        "        display(df_timeline)\n",
        "    except Exception as e:\n",
        "        print(f'Error copying to output: {e}')"
]

for cell in reversed(nb['cells']):
    if cell['cell_type'] == 'code' and 'process_video' in ''.join(cell['source']):
        cell['source'] = vid_source
        break

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print('Updated successfully!')
