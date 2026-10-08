import json
import os
import copy

notebook_path = r'm:\chakramodel\notebooks\Kaggle_ChakraTransformer_Evaluation.ipynb'
with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        
        # Patch BASE_DIR logic
        if 'BASE_DIR =' in source and 'timm' in source:
            new_source = [
                "!pip install -q timm opencv-python torchvision\n",
                "\n",
                "import sys\n",
                "import os\n",
                "import glob\n",
                "\n",
                "# Auto-detect the uploaded zip dataset folder\n",
                "base_dirs = glob.glob('/kaggle/input/*kaggle*upload*zip*') + glob.glob('/kaggle/input/*chakramodel*')\n",
                "if len(base_dirs) > 0:\n",
                "    BASE_DIR = base_dirs[0]\n",
                "    print(f\"Found dataset at: {BASE_DIR}\")\n",
                "else:\n",
                "    # Fallback\n",
                "    BASE_DIR = '/kaggle/input/kaggle-upload-zip4'\n",
                "    print(f\"Dataset not auto-detected, using fallback: {BASE_DIR}\")\n",
                "\n",
                "if not os.path.exists(BASE_DIR):\n",
                "    print(f\"WARNING: BASE_DIR '{BASE_DIR}' not found. Please check /kaggle/input/ folder names.\")\n",
                "else:\n",
                "    # Copy src to working directory to allow imports\n",
                "    !cp -r {BASE_DIR}/src /kaggle/working/\n",
                "    sys.path.append('/kaggle/working/src')\n",
                "    print(\"Source code successfully mounted.\")\n"
            ]
            cell['source'] = new_source
            
        # Patch Kvasir-SEG logic
        if 'KvasirSEGDataset' in source and 'images_dir =' in source:
            new_source = [
                "import glob\n",
                "from pathlib import Path\n",
                "# Auto-detect Kvasir-SEG dataset folder\n",
                "kvasir_paths = glob.glob('/kaggle/input/*kvasir*')\n",
                "if len(kvasir_paths) > 0:\n",
                "    KVASIR_ROOT = kvasir_paths[0]\n",
                "else:\n",
                "    KVASIR_ROOT = '/kaggle/input/kvasir-seg'\n",
                "\n",
                "# Some versions have a nested 'Kvasir-SEG' folder, others don't\n",
                "if os.path.exists(os.path.join(KVASIR_ROOT, 'Kvasir-SEG', 'images')):\n",
                "    images_dir = Path(KVASIR_ROOT) / 'Kvasir-SEG' / 'images'\n",
                "    masks_dir = Path(KVASIR_ROOT) / 'Kvasir-SEG' / 'masks'\n",
                "elif os.path.exists(os.path.join(KVASIR_ROOT, 'images')):\n",
                "    images_dir = Path(KVASIR_ROOT) / 'images'\n",
                "    masks_dir = Path(KVASIR_ROOT) / 'masks'\n",
                "else:\n",
                "    images_dir = Path(KVASIR_ROOT) / 'Kvasir-SEG' / 'images'\n",
                "    masks_dir = Path(KVASIR_ROOT) / 'Kvasir-SEG' / 'masks'\n",
                "\n",
                "print(f\"Using Kvasir-SEG images path: {images_dir}\")\n",
                "\n",
                "if images_dir.exists() and masks_dir.exists():\n",
                "    dataset = KvasirSEGDataset(images_dir, masks_dir, img_size=384, augment=False)\n",
                "    \n",
                "    np.random.seed(42)\n",
                "    all_indices = np.random.permutation(len(dataset)).tolist()\n",
                "\n",
                "    n_train = int(0.7 * len(dataset))\n",
                "    n_cal = int(0.15 * len(dataset))\n",
                "    test_indices = all_indices[n_train + n_cal:]\n",
                "    test_set = torch.utils.data.Subset(dataset, test_indices)\n",
                "    test_loader = DataLoader(test_set, batch_size=8, shuffle=False, num_workers=2)\n",
                "    print(f\"Test set size: {len(test_set)}\")\n",
                "\n",
                "    print(\"Running Evaluation...\")\n",
                "    metrics = evaluate_model(model, test_loader, device)\n",
                "    print(\"\\n=== FINAL RESULTS ===\")\n",
                "    print(f\"Dice Score: {metrics['dice']:.4f}\")\n",
                "    print(f\"mIoU Score: {metrics['iou']:.4f}\")\n",
                "    print(f\"Precision:  {metrics['precision']:.4f}\")\n",
                "    print(f\"Recall:     {metrics['recall']:.4f}\")\n",
                "else:\n",
                "    print(f\"WARNING: Dataset not found at {images_dir}. Skipping static evaluation.\")\n"
            ]
            cell['source'] = new_source

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print('Updated notebook successfully.')
