import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
import os

OUT_DIR = r"m:\chakramodel\notebooks"
os.makedirs(OUT_DIR, exist_ok=True)

# -------------------------------------------------------------------------
# HELPER TO BUILD IMAGE/MASK EVALUATION NOTEBOOKS (HyperKvasir, PolypDB)
# -------------------------------------------------------------------------
def create_eval_notebook(notebook_name, dataset_title, dataset_kaggle_path):
    nb = new_notebook()
    
    nb.cells.append(new_markdown_cell(
        f"# ChakraTransformer {dataset_title} Evaluation\n"
        "**Zero-shot cross-dataset evaluation** on newly uploaded Kaggle datasets.\n\n"
        "### Required Dataset Mounts\n"
        f"- `{dataset_kaggle_path}`\n"
        "- `/kaggle/input/chakratransformer-weights` (or wherever your weights are)\n"
    ))

    # Cell 1: Environment
    cell1 = """\
import subprocess
subprocess.run(["pip", "install", "-q", "timm", "opencv-python-headless", "albumentations"], check=True)

import os, sys, cv2, torch
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from torch.amp import autocast

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True
    print(f"GPU: {torch.cuda.get_device_name(0)}")
"""
    nb.cells.append(new_code_cell(cell1))

    # Cell 2: Architecture
    cell2 = """\
import timm

class ChakraTransformerSegmenter(nn.Module):
    def __init__(self, backbone_name='vit_large_patch16_384', pretrained=False, num_classes=1):
        super(ChakraTransformerSegmenter, self).__init__()
        self.backbone = timm.create_model(backbone_name, pretrained=pretrained, features_only=False)
        self.embed_dim = self.backbone.embed_dim
        self.decode_head = nn.Sequential(
            nn.ConvTranspose2d(self.embed_dim, 256, kernel_size=4, stride=4),
            nn.BatchNorm2d(256), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4),
            nn.BatchNorm2d(64), nn.ReLU(inplace=True),
            nn.Conv2d(64, num_classes, kernel_size=3, padding=1)
        )
        self.dropout1 = nn.Dropout2d(p=0.5)
        self.dropout2 = nn.Dropout2d(p=0.5)

    def forward(self, x):
        B, C, H, W = x.shape
        features = self.backbone.forward_features(x)
        if features.dim() == 3:
            expected_patches = (H // 16) * (W // 16)
            if features.shape[1] == expected_patches + 1:
                features = features[:, 1:, :] 
            grid_h = H // 16
            grid_w = W // 16
            features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)

        x_dec = features
        for i, layer in enumerate(self.decode_head):
            x_dec = layer(x_dec)
            if i == 2: x_dec = self.dropout1(x_dec)
            elif i == 5: x_dec = self.dropout2(x_dec)
        logits = x_dec
        if logits.shape[2:] != (H, W):
            logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)
        return logits
"""
    nb.cells.append(new_code_cell(cell2))

    # Cell 3: Metrics & Loader
    cell3 = """\
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}

class EvalPolypDataset(Dataset):
    def __init__(self, file_paths, mask_dict, img_size=384):
        self.file_paths = file_paths
        self.mask_dict  = mask_dict
        self.img_size   = img_size
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        self.std  = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)

    def __len__(self):
        return len(self.file_paths)

    def __getitem__(self, idx):
        img_path  = self.file_paths[idx]
        mask_path = self.mask_dict.get(img_path.stem)
        img = cv2.imread(str(img_path))
        img = np.zeros((self.img_size, self.img_size, 3), dtype=np.uint8) if img is None else cv2.resize(img, (self.img_size, self.img_size))
        
        if mask_path is not None and Path(mask_path).exists():
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            mask = np.zeros((self.img_size, self.img_size), dtype=np.uint8) if mask is None else cv2.resize(mask, (self.img_size, self.img_size), interpolation=cv2.INTER_NEAREST)
        else:
            mask = np.zeros((self.img_size, self.img_size), dtype=np.uint8)

        img_t = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float() / 255.0
        img_t = (img_t - self.mean) / self.std
        mask_t = torch.from_numpy((mask > 127).astype(np.float32)).unsqueeze(0)
        return img_t, mask_t

def compute_metrics(model, loader, device):
    model.eval().to(device)
    dices, ious, precs, recs = [], [], [], []
    with torch.no_grad():
        for imgs, masks in loader:
            imgs = imgs.to(device, non_blocking=True)
            with autocast(device_type='cuda', dtype=torch.float16):
                logits = model(imgs)
            probs = torch.sigmoid(logits).cpu().numpy()
            gts   = masks.numpy()
            for i in range(len(probs)):
                p  = (probs[i, 0] > 0.5).astype(np.float32)
                g  = (gts[i, 0]   > 0.5).astype(np.float32)
                tp = (p * g).sum()
                fp = (p * (1.0 - g)).sum()
                fn = ((1.0 - p) * g).sum()
                dices.append((2.0*tp + 1e-6) / (2.0*tp + fp + fn + 1e-6))
                ious.append((tp + 1e-6) / (tp + fp + fn + 1e-6))
                precs.append((tp + 1e-6) / (tp + fp + 1e-6))
                recs.append((tp + 1e-6) / (tp + fn + 1e-6))
    return {
        'dice': float(np.mean(dices)), 'iou': float(np.mean(ious)), 
        'precision': float(np.mean(precs)), 'recall': float(np.mean(recs))
    }
"""
    nb.cells.append(new_code_cell(cell3))
    
    # Cell 4: Load Weights
    cell4 = """\
print("Initializing ChakraTransformer...")
model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=False)

import glob
weights_path = glob.glob("/kaggle/input/**/chakra_transformer_best.pth", recursive=True)
if not weights_path:
    print("WARNING: Could not find chakra_transformer_best.pth in Kaggle inputs. Upload it to evaluate!")
else:
    print(f"Loading weights from: {weights_path[0]}")
    state_dict = torch.load(weights_path[0], map_location=device, weights_only=True)
    model.load_state_dict(state_dict, strict=True)
model.to(device).eval()
print("Model ready.")
"""
    nb.cells.append(new_code_cell(cell4))
    
    # Cell 5: Evaluation
    cell5 = f"""\
def discover_dataset(root_dir):
    root = Path(root_dir)
    img_dirs = [p for p in root.rglob("*") if p.is_dir() and "image" in p.name.lower() or p.name.lower() in ("images", "original")]
    mask_dirs = [p for p in root.rglob("*") if p.is_dir() and "mask" in p.name.lower() or p.name.lower() in ("masks", "groundtruth", "gt")]
    
    img_files = []
    for d in img_dirs:
        img_files += [f for f in d.iterdir() if f.suffix.lower() in IMAGE_EXTS]
        
    mask_dict = {{}}
    for d in mask_dirs:
        for f in d.iterdir():
            if f.suffix.lower() in IMAGE_EXTS:
                mask_dict[f.stem] = f
                
    return img_files, mask_dict

# Run Evaluation on Dataset
dataset_path = "{dataset_kaggle_path}"
# Fuzzy find actual path inside kaggle
found_paths = glob.glob(f"/kaggle/input/**/*", recursive=True)
matching_paths = [p for p in found_paths if dataset_path.split("/")[-1].lower() in p.lower() and os.path.isdir(p)]
root_dir = matching_paths[0] if matching_paths else dataset_path

img_files, mask_dict = discover_dataset(root_dir)
if len(img_files) == 0:
    print(f"No images found in {{root_dir}}. Make sure the dataset is correctly attached.")
else:
    dataset = EvalPolypDataset(img_files, mask_dict, img_size=384)
    loader  = DataLoader(dataset, batch_size=8, shuffle=False, num_workers=2, pin_memory=True)
    metrics = compute_metrics(model, loader, device)

    print("\\n=== {dataset_title} EVALUATION RESULTS ===")
    print(f"Dice (DSC) : {{metrics['dice']:.4f}}")
    print(f"mIoU       : {{metrics['iou']:.4f}}")
    print(f"Precision  : {{metrics['precision']:.4f}}")
    print(f"Recall     : {{metrics['recall']:.4f}}")
"""
    nb.cells.append(new_code_cell(cell5))
    
    out_file = os.path.join(OUT_DIR, notebook_name)
    with open(out_file, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)
    print(f"Created {out_file}")

# -------------------------------------------------------------------------
# HELPER TO BUILD VIDEO EVALUATION NOTEBOOK
# -------------------------------------------------------------------------
def create_video_notebook():
    nb = new_notebook()
    nb.cells.append(new_markdown_cell(
        f"# ChakraModel Video Inference\n"
        "Tests YOLOv8 + ChakraTransformer Segmenter on `cvc-sample-video`.\n"
    ))
    
    with open(r"m:\chakramodel\ChakraModel_Video_Evaluation_Kaggle.ipynb", 'r', encoding='utf-8') as f:
        video_nb = nbformat.read(f, as_version=4)
        
    for cell in video_nb.cells:
        if cell.cell_type == 'code':
            # Modify the inference function call to use explicit dataset path
            source = cell.source
            source = source.replace('run_video_inference()', 'run_video_inference(input_dir="/kaggle/input/cvc-sample-video")')
            nb.cells.append(new_code_cell(source))
        elif cell.cell_type == 'markdown':
            # Skip the first markdown as we already added ours
            if "ChakraModel Video Inference & Pros/Cons Benchmark" not in cell.source:
                nb.cells.append(new_markdown_cell(cell.source))
                
    out_file = os.path.join(OUT_DIR, "Kaggle_CVC_Video_Eval.ipynb")
    with open(out_file, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)
    print(f"Created {out_file}")

# Generate notebooks
create_eval_notebook("Kaggle_HyperKvasir_Eval.ipynb", "HyperKvasir", "/kaggle/input/hyperkvasir-dataset-first-half-ld-dataset")
create_eval_notebook("Kaggle_PolypDB_Stress_Test.ipynb", "PolypDB Stress Test", "/kaggle/input/polypdb-polyp-raw-stress-testdataset")
create_video_notebook()
