import json
import os

notebook_path = r"m:\chakramodel\ChakraModel_Video_Evaluation_Kaggle.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        if "IMAGE_DATASETS = {" in source and "cvc-clinicdb/CVC-ClinicDB" in source:
            cell['source'] = [
                "import os\n",
                "\n",
                "DATASET_ROOT = \"/kaggle/input/\"\n",
                "\n",
                "# Expected folder names to search for\n",
                "DATASET_TARGETS = {\n",
                "    \"Kvasir-SEG\": \"Kvasir-SEG\",\n",
                "    \"CVC-ClinicDB\": \"CVC-ClinicDB\",\n",
                "    \"CVC-ColonDB\": \"CVC-ColonDB\",\n",
                "    \"CVC-300\": \"CVC-300\",\n",
                "    \"ETIS-Larib\": \"ETIS-LaribPolypDB\",\n",
                "    \"ClinicVideoDB\": \"CVC-ClinicVideoDB\"\n",
                "}\n",
                "\n",
                "IMAGE_DATASETS = {}\n",
                "VIDEO_DATASET = None\n",
                "YOLO_WEIGHTS = None\n",
                "VIT_WEIGHTS = None\n",
                "\n",
                "print(\"Scanning /kaggle/input/ for datasets...\")\n",
                "for root, dirs, files in os.walk(DATASET_ROOT):\n",
                "    for name, target_dir in DATASET_TARGETS.items():\n",
                "        if target_dir in dirs:\n",
                "            path = os.path.join(root, target_dir)\n",
                "            if name == \"ClinicVideoDB\":\n",
                "                VIDEO_DATASET = path\n",
                "            else:\n",
                "                IMAGE_DATASETS[name] = path\n",
                "                \n",
                "    for f in files:\n",
                "        if f == \"yolov8x_polyp.pt\":\n",
                "            YOLO_WEIGHTS = os.path.join(root, f)\n",
                "        elif f == \"combo6_best.pth\":\n",
                "            VIT_WEIGHTS = os.path.join(root, f)\n",
                "\n",
                "print(\"\\n--- Detection Results ---\")\n",
                "for name in [\"Kvasir-SEG\", \"CVC-ClinicDB\", \"CVC-ColonDB\", \"CVC-300\", \"ETIS-Larib\"]:\n",
                "    print(f\"{name}: {'Found at ' + IMAGE_DATASETS[name] if name in IMAGE_DATASETS else 'NOT FOUND'}\")\n",
                "\n",
                "print(f\"\\nVideo Dataset (ClinicVideoDB): {'Found at ' + VIDEO_DATASET if VIDEO_DATASET else 'NOT FOUND'}\")\n",
                "print(f\"YOLOv8 Weights: {'Found' if YOLO_WEIGHTS else 'NOT FOUND'}\")\n",
                "print(f\"ViT-Large Weights: {'Found' if VIT_WEIGHTS else 'NOT FOUND'}\")\n",
                "\n",
                "if not VIDEO_DATASET:\n",
                "    print(\"\\n[!] To run the video evaluation, you need to add the 'cvc-clinicvideodb' dataset via 'Add Data'.\")\n"
            ]

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Updated Notebook successfully!")
