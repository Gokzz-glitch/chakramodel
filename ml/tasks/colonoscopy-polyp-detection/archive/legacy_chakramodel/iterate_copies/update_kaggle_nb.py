import json
import os

notebook_path = r'm:\chakramodel\notebooks\Kaggle_ChakraTransformer_Evaluation.ipynb'
with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Clear existing cells
nb['cells'] = []

def add_markdown(text):
    nb['cells'].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [text + "\n"]
    })

def add_code(lines):
    nb['cells'].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in lines]
    })

add_markdown("# ChakraTransformer Kaggle Full Evaluation")
add_markdown("This notebook evaluates the model across Kvasir-SEG, CVC-ClinicDB, and ETIS-Larib using exact Kaggle paths.")

add_code([
    "!pip install -q timm opencv-python torchvision",
    "import sys",
    "import os",
    "from pathlib import Path",
    "import glob",
    "",
    "BASE_DIR = '/kaggle/input/datasets/gokulrocky/kaggle-upload-zip4'",
    "",
    "if not os.path.exists(BASE_DIR):",
    "    print(f\"WARNING: BASE_DIR '{BASE_DIR}' not found.\")",
    "    print(\"Trying alternative paths...\")",
    "    alts = glob.glob('/kaggle/input/*/*kaggle*upload*zip*')",
    "    if alts: BASE_DIR = alts[0]",
    "",
    "print(f\"Using BASE_DIR = {BASE_DIR}\")",
    "!cp -r {BASE_DIR}/src /kaggle/working/",
    "sys.path.append('/kaggle/working/src')",
    "print('Source code successfully mounted.')"
])

add_code([
    "import torch",
    "import cv2",
    "import numpy as np",
    "from torch.utils.data import DataLoader",
    "",
    "from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter",
    "from train_pranet import KvasirSEGDataset",
    "from evaluate_all import evaluate_model",
    "",
    "device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')",
    "print(f\"Using device: {device}\")"
])

add_code([
    "print('Loading ChakraTransformer...')",
    "model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=False)",
    "",
    "weight_path = f\"{BASE_DIR}/chakra_transformer_best.pth\"",
    "if not os.path.exists(weight_path):",
    "    weight_path = f\"{BASE_DIR}/weights/chakra_transformer_best.pth\"",
    "",
    "model.load_state_dict(torch.load(weight_path, map_location=device))",
    "model.to(device).eval()",
    "print(f\"Model weights loaded successfully from: {weight_path}\")"
])

add_markdown("## 1. Helper Function to Evaluate Datasets")
add_code([
    "def run_eval(images_path, masks_path, dataset_name, is_kvasir=False):",
    "    print(f\"\\n{'='*40}\")",
    "    print(f\"Evaluating {dataset_name}\")",
    "    print(f\"{'='*40}\")",
    "    if not os.path.exists(images_path) or not os.path.exists(masks_path):",
    "        print(f\"ERROR: Paths not found for {dataset_name}.\")",
    "        print(f\"Images: {images_path}\")",
    "        print(f\"Masks: {masks_path}\")",
    "        return",
    "        ",
    "    dataset = KvasirSEGDataset(images_path, masks_path, img_size=384, augment=False)",
    "    ",
    "    if is_kvasir:",
    "        # Use the standard 10% test split from Kvasir (Train 70, Cal 15, Test 15)",
    "        np.random.seed(42)",
    "        all_indices = np.random.permutation(len(dataset)).tolist()",
    "        n_train = int(0.7 * len(dataset))",
    "        n_cal = int(0.15 * len(dataset))",
    "        test_indices = all_indices[n_train + n_cal:]",
    "        test_set = torch.utils.data.Subset(dataset, test_indices)",
    "    else:",
    "        # Zero-shot on entire dataset",
    "        test_set = dataset",
    "        ",
    "    print(f\"Test set size: {len(test_set)} images.\")",
    "    test_loader = DataLoader(test_set, batch_size=8, shuffle=False, num_workers=2)",
    "    ",
    "    metrics = evaluate_model(model, test_loader, device)",
    "    print(f\"\\n--- {dataset_name} RESULTS ---\")",
    "    print(f\"Dice Score: {metrics['dice']:.4f}\")",
    "    print(f\"mIoU Score: {metrics['iou']:.4f}\")",
    "    print(f\"Precision:  {metrics['precision']:.4f}\")",
    "    print(f\"Recall:     {metrics['recall']:.4f}\")"
])

add_markdown("## 2. Kvasir-SEG (Held-out Test Split)")
add_code([
    "kvasir_root = '/kaggle/input/notebooks/ivannikov2002/kvasir-seg-data-polyp-segmentation-detection'",
    "# Let's auto-find the images and masks subfolders inside this path",
    "kvasir_imgs = glob.glob(kvasir_root + '/**/images', recursive=True)",
    "kvasir_msks = glob.glob(kvasir_root + '/**/masks', recursive=True)",
    "if kvasir_imgs and kvasir_msks:",
    "    run_eval(kvasir_imgs[0], kvasir_msks[0], 'Kvasir-SEG', is_kvasir=True)",
    "else:",
    "    print('Could not locate images/masks folder inside Kvasir-SEG.')"
])

add_markdown("## 3. CVC-ClinicDB (Zero-Shot)")
add_code([
    "cvc_root = '/kaggle/input/notebooks/ahaan2/cvc-clinicdb'",
    "cvc_imgs = glob.glob(cvc_root + '/**/images', recursive=True) + glob.glob(cvc_root + '/**/Original', recursive=True)",
    "cvc_msks = glob.glob(cvc_root + '/**/masks', recursive=True) + glob.glob(cvc_root + '/**/Ground Truth', recursive=True)",
    "if cvc_imgs and cvc_msks:",
    "    run_eval(cvc_imgs[0], cvc_msks[0], 'CVC-ClinicDB', is_kvasir=False)",
    "else:",
    "    print('Could not locate images/masks folder inside CVC-ClinicDB.')"
])

add_markdown("## 4. ETIS-Larib (Zero-Shot)")
add_code([
    "etis_root = '/kaggle/input/notebooks/tamimm91437/etis-laribpolypdb'",
    "etis_imgs = glob.glob(etis_root + '/**/images', recursive=True) + glob.glob(etis_root + '/**/ETIS-LaribPolypDB', recursive=True)",
    "etis_msks = glob.glob(etis_root + '/**/masks', recursive=True) + glob.glob(etis_root + '/**/ETIS-LaribPolypDB-GT', recursive=True)",
    "if etis_imgs and etis_msks:",
    "    run_eval(etis_imgs[0], etis_msks[0], 'ETIS-Larib', is_kvasir=False)",
    "else:",
    "    print('Could not locate images/masks folder inside ETIS-Larib.')"
])

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Created updated all-in-one notebook.")
