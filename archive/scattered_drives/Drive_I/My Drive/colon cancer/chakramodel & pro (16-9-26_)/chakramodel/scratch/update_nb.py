import json
from pathlib import Path

notebook_path = Path(r"m:\chakramodel\kaggle_bundle\notebooks\ChakraModel_Kaggle_Evaluation.ipynb")
with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

# Update pip cell to include ffmpeg
for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "!pip install" in "".join(cell["source"]):
        cell["source"] = [
            "!apt-get update && apt-get install -y ffmpeg\n",
            "!pip install ultralytics opencv-python-headless pandas numpy torch torchvision"
        ]

# Update the video cell to auto-find mp4 and handle env better
for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "process_video" in "".join(cell["source"]):
        cell["source"] = [
            "from app import process_video\n",
            "import glob\n",
            "from pathlib import Path\n",
            "import shutil\n",
            "import os\n",
            "\n",
            "# 1. Automatically find any .mp4 file in the dataset\n",
            "mp4_files = list(Path(REPO_PATH).rglob(\"*.mp4\"))\n",
            "if not mp4_files:\n",
            "    print(\"No .mp4 files found in your dataset. Upload one to test the video pipeline.\")\n",
            "else:\n",
            "    video_file = mp4_files[0]\n",
            "    print(f\"Found video: {video_file}\")\n",
            "    print(f\"Processing video (this may take a moment)...\")\n",
            "    \n",
            "    # process_video args: video_path, use_persistence, window_size, persistence_threshold, doubt_policy, imgsz_val\n",
            "    out_video_path, df_timeline = process_video(\n",
            "        str(video_file), \n",
            "        use_persistence=True, \n",
            "        window_size=10, \n",
            "        persistence_threshold=0.6, \n",
            "        doubt_policy=\"Warn Only\", \n",
            "        imgsz_val=\"1024\"\n",
            "    )\n",
            "    \n",
            "    # 2. Safely handle the Kaggle/Colab output environment\n",
            "    working_dir = Path(\"/kaggle/working\") if os.path.exists(\"/kaggle/working\") else Path(\".\")\n",
            "    final_vid = working_dir / f\"output_{video_file.name}\"\n",
            "    \n",
            "    try:\n",
            "        shutil.copy2(out_video_path, final_vid)\n",
            "        print(f\"Processed video saved to output: {final_vid}\")\n",
            "        print(\"\\nTimeline of Detections:\")\n",
            "        display(df_timeline)\n",
            "    except Exception as e:\n",
            "        print(f\"Error copying to output: {e}\")"
        ]

with open(notebook_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)
