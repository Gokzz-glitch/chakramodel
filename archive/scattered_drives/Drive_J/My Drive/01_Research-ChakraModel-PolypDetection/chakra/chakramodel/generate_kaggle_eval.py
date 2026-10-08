import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

nb = new_notebook()

# ─── CELL 0: Intro ──────────────────────────────────────────────────────────
nb.cells.append(new_markdown_cell(
    "# ChakraTransformer Kaggle Standalone Evaluation\n"
    "**Combo #6 (ViT-Large 384)** — 100% standalone, no `src/` folder required.\n\n"
    "Evaluates Kvasir-SEG (held-out 15% test split), CVC-ClinicDB (zero-shot), ETIS-Larib (zero-shot).\n\n"
    "### Required Dataset Mounts\n"
    "- `/kaggle/input/datasets/gokulrocky/kaggle-upload-zip4`\n"
    "- `/kaggle/input/notebooks/ivannikov2002/kvasir-seg-data-polyp-segmentation-detection`\n"
    "- `/kaggle/input/notebooks/ahaan2/cvc-clinicdb`\n"
    "- `/kaggle/input/notebooks/tamimm91437/etis-laribpolypdb`\n"
))

# ─── CELL 1: Environment Setup ───────────────────────────────────────────────
cell1 = """\
# CELL 1: ENVIRONMENT SETUP
# NOTE: torchvision is intentionally NOT installed via pip.
#       Kaggle base image has torch+torchvision pinned to matching CUDA versions.
#       Installing torchvision via pip would break CUDA operator compatibility.
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
    torch.backends.cuda.matmul.allow_tf32 = True
    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {gpu_name}  VRAM: {vram_gb:.1f} GB  | AMP FP16 Enabled")
else:
    print("WARNING: CUDA unavailable — running on CPU.")
print(f"Using device: {device}")
"""
nb.cells.append(new_code_cell(cell1))

# ─── CELL 2: EXACT Model Architecture ────────────────────────────────────────
cell2 = """\
# CELL 2: EXACT CHAKRATRANSFORMER ARCHITECTURE
# ─────────────────────────────────────────────────────────────────────────────
# This is an exact 1-to-1 copy of:
#   src/chakra_transformer/transformer_segmenter.py
#
# Layer names, dtypes, and tensor shapes MUST match the saved checkpoint
# so that model.load_state_dict(strict=True) succeeds without any key errors.
# ─────────────────────────────────────────────────────────────────────────────
import timm

class ChakraTransformerSegmenter(nn.Module):
    """
    High-Accuracy Vision Transformer (ViT) based segmentation model for Polyp Detection.
    ViT-Large with 384x384 resolution.
    """
    def __init__(self, backbone_name='vit_large_patch16_384', pretrained=False, num_classes=1):
        super(ChakraTransformerSegmenter, self).__init__()

        # ViT backbone via timm
        self.backbone = timm.create_model(backbone_name, pretrained=pretrained, features_only=False)

        # embed_dim = 1024 for ViT-Large
        self.embed_dim = self.backbone.embed_dim

        # Decode head: exact sequential matching the training checkpoint.
        # Patch grid at 384px input: 384/16 = 24x24
        # ConvTranspose2d(k=4, s=4): 24 -> 96 -> ConvTranspose2d(k=4,s=4): 96 -> 384
        self.decode_head = nn.Sequential(
            nn.ConvTranspose2d(self.embed_dim, 256, kernel_size=4, stride=4),  # idx 0
            nn.BatchNorm2d(256),                                                # idx 1
            nn.ReLU(inplace=True),                                              # idx 2
            nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4),              # idx 3
            nn.BatchNorm2d(64),                                                 # idx 4
            nn.ReLU(inplace=True),                                              # idx 5
            nn.Conv2d(64, num_classes, kernel_size=3, padding=1)               # idx 6
        )
        self.dropout1 = nn.Dropout2d(p=0.5)
        self.dropout2 = nn.Dropout2d(p=0.5)

    def enable_mc_dropout(self):
        """Enable Dropout layers during evaluation for Monte Carlo sampling."""
        for m in self.modules():
            if m.__class__.__name__.startswith('Dropout'):
                m.train()

    def forward(self, x):
        B, C, H, W = x.shape

        features = self.backbone.forward_features(x)

        if features.dim() == 3:
            # Safe CLS token strip: count actual expected patches.
            # Do NOT use self.backbone.global_pool attribute which can change with timm version.
            expected_patches = (H // 16) * (W // 16)
            if features.shape[1] == expected_patches + 1:
                features = features[:, 1:, :]  # strip CLS

            grid_h = H // 16
            grid_w = W // 16
            features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)

        # Decode with MC Dropout applied at correct indices
        x_dec = features
        for i, layer in enumerate(self.decode_head):
            x_dec = layer(x_dec)
            if i == 2:
                x_dec = self.dropout1(x_dec)
            elif i == 5:
                x_dec = self.dropout2(x_dec)
        logits = x_dec

        # Bilinear upsample if needed (handles edge-case resolution drift)
        if logits.shape[2:] != (H, W):
            logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)

        return logits

print("ChakraTransformerSegmenter defined (exact architecture match).")
"""
nb.cells.append(new_code_cell(cell2))

# ─── CELL 3: Dataset + Metrics ───────────────────────────────────────────────
cell3 = """\
# CELL 3: EVALUATION DATASET AND METRICS
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}

class EvalPolypDataset(Dataset):
    """Augmentation-free evaluation dataset. Accepts a pre-sorted file list and stem->mask dict."""
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
        img = np.zeros((self.img_size, self.img_size, 3), dtype=np.uint8) if img is None \
              else cv2.resize(img, (self.img_size, self.img_size), interpolation=cv2.INTER_LINEAR)

        if mask_path is not None and Path(mask_path).exists():
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            mask = np.zeros((self.img_size, self.img_size), dtype=np.uint8) if mask is None \
                   else cv2.resize(mask, (self.img_size, self.img_size), interpolation=cv2.INTER_NEAREST)
        else:
            mask = np.zeros((self.img_size, self.img_size), dtype=np.uint8)

        img_t = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float() / 255.0
        img_t = (img_t - self.mean) / self.std
        mask_t = torch.from_numpy((mask > 127).astype(np.float32)).unsqueeze(0)
        return img_t, mask_t


def compute_metrics(model, loader, device):
    """Compute mean Dice, mIoU, Precision, Recall over DataLoader."""
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
        'dice':      float(np.mean(dices)),
        'iou':       float(np.mean(ious)),
        'precision': float(np.mean(precs)),
        'recall':    float(np.mean(recs))
    }

print("EvalPolypDataset and compute_metrics defined.")
"""
nb.cells.append(new_code_cell(cell3))

# ─── CELL 4: Weight Loading ───────────────────────────────────────────────────
cell4 = """\
# CELL 4: SAFE WEIGHT LOADING
print("Initializing ChakraTransformer (ViT-Large 384, pretrained=False)...")
model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=False)

WEIGHT_FILENAME = "chakra_transformer_best.pth"
candidate_paths = [
    Path("/kaggle/working") / WEIGHT_FILENAME,
    Path("/kaggle/working/weights") / WEIGHT_FILENAME,
    Path(".") / WEIGHT_FILENAME,
]
# Recursive search across all Kaggle input mounts as last-resort fallback
for p in Path("/kaggle/input").rglob(WEIGHT_FILENAME):
    candidate_paths.append(p)

weight_path = None
for p in candidate_paths:
    if p.exists():
        weight_path = p
        break

if weight_path is None:
    raise FileNotFoundError(
        "\\n" + "="*62 + "\\n"
        f" ERROR: '{WEIGHT_FILENAME}' not found!\\n"
        + "="*62 + "\\n"
        " Please run Combo6_ChakraTransformer.ipynb first to train\\n"
        " the model, then mount the output here as a Kaggle dataset.\\n"
        " Expected location: /kaggle/working/chakra_transformer_best.pth\\n"
        + "="*62
    )

print(f"Loading weights from: {weight_path}")
state_dict = torch.load(weight_path, map_location=device, weights_only=True)
model.load_state_dict(state_dict, strict=True)
model.to(device).eval()
total_params = sum(p.numel() for p in model.parameters())
print(f"Model loaded successfully. Parameters: {total_params/1e6:.2f}M")
"""
nb.cells.append(new_code_cell(cell4))

# ─── CELL 5: Discovery + Eval Driver ─────────────────────────────────────────
cell5 = """\
# CELL 5: ROBUST DATASET DISCOVERY (CASE-INSENSITIVE) + EVALUATION DRIVER
def discover_img_mask_paths(root_dir, img_dir_names, mask_dir_names):
    """
    Recursively walk root_dir, find image/mask directories using
    case-insensitive name matching. Returns (sorted_img_files, mask_dict).
    """
    root = Path(root_dir)
    if not root.exists():
        return [], {}

    img_names_lower  = {n.lower() for n in img_dir_names}
    mask_names_lower = {n.lower() for n in mask_dir_names}

    img_dirs, mask_dirs = [], []
    for p in root.rglob("*"):
        if not p.is_dir():
            continue
        lo = p.name.lower()
        if lo in img_names_lower:
            img_dirs.append(p)
        if lo in mask_names_lower:
            mask_dirs.append(p)

    # Sort by filename - critical to match training notebook sort order
    img_files = []
    for d in img_dirs:
        img_files += sorted(
            [f for f in d.iterdir() if f.suffix.lower() in IMAGE_EXTS],
            key=lambda x: x.name
        )

    mask_dict = {}
    for d in mask_dirs:
        for f in d.iterdir():
            if f.suffix.lower() in IMAGE_EXTS:
                mask_dict[f.stem] = f

    return img_files, mask_dict


def run_evaluation(dataset_root, dataset_name, img_dir_names, mask_dir_names, is_kvasir=False):
    """Discover, split (for Kvasir), and evaluate a single dataset."""
    sep = "=" * 60
    print(f"\\n{sep}\\n  {dataset_name}\\n{sep}")

    img_files, mask_dict = discover_img_mask_paths(dataset_root, img_dir_names, mask_dir_names)
    if not img_files:
        print(f"  WARNING: No images found under {dataset_root}. Skipping.")
        return None
    if not mask_dict:
        print(f"  WARNING: No masks found under {dataset_root}. Skipping.")
        return None
    print(f"  Discovered: {len(img_files)} images, {len(mask_dict)} masks")

    if is_kvasir:
        # EXACT replication of Combo6 tri-split (70/15/15, seed=42).
        # img_files already sorted by name — same as training's sorted(Path.glob("*")).
        np.random.seed(42)
        perm    = np.random.permutation(len(img_files))
        n_total = len(img_files)
        n_train = int(0.70 * n_total)
        n_cal   = int(0.15 * n_total)
        idx_test = perm[n_train + n_cal:]
        eval_files = [img_files[i] for i in idx_test]
        print(f"  Kvasir held-out test split: {len(eval_files)} images (70/15/15, seed=42)")
    else:
        eval_files = img_files
        print(f"  Zero-shot on full dataset: {len(eval_files)} images")

    dataset = EvalPolypDataset(eval_files, mask_dict, img_size=384)
    loader  = DataLoader(dataset, batch_size=8, shuffle=False, num_workers=2, pin_memory=True)
    metrics = compute_metrics(model, loader, device)

    print(f"\\n  Dice (DSC) : {metrics['dice']:.4f}")
    print(f"  mIoU       : {metrics['iou']:.4f}")
    print(f"  Precision  : {metrics['precision']:.4f}")
    print(f"  Recall     : {metrics['recall']:.4f}")
    return metrics

print("Evaluation driver defined.")
"""
nb.cells.append(new_code_cell(cell5))

# ─── CELL 6: Kvasir ──────────────────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 1. Kvasir-SEG (Held-Out 15% Test Split)"))
cell6 = """\
kvasir_metrics = run_evaluation(
    "/kaggle/input/notebooks/ivannikov2002/kvasir-seg-data-polyp-segmentation-detection",
    "Kvasir-SEG",
    img_dir_names=["images", "Images"],
    mask_dir_names=["masks", "Masks"],
    is_kvasir=True
)
# Fallback: user's primary zip upload
if kvasir_metrics is None:
    kvasir_metrics = run_evaluation(
        "/kaggle/input/datasets/gokulrocky/kaggle-upload-zip4",
        "Kvasir-SEG (from zip upload)",
        img_dir_names=["images", "Images"],
        mask_dir_names=["masks", "Masks"],
        is_kvasir=True
    )
"""
nb.cells.append(new_code_cell(cell6))

# ─── CELL 7: CVC ─────────────────────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 2. CVC-ClinicDB (Zero-Shot)"))
cell7 = """\
cvc_metrics = run_evaluation(
    "/kaggle/input/notebooks/ahaan2/cvc-clinicdb",
    "CVC-ClinicDB",
    img_dir_names=["images", "Images", "original", "Original"],
    mask_dir_names=["masks", "Masks", "ground truth", "Ground Truth", "groundtruth"],
    is_kvasir=False
)
"""
nb.cells.append(new_code_cell(cell7))

# ─── CELL 8: ETIS ────────────────────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 3. ETIS-Larib (Zero-Shot)"))
cell8 = """\
etis_metrics = run_evaluation(
    "/kaggle/input/notebooks/tamimm91437/etis-laribpolypdb",
    "ETIS-Larib",
    img_dir_names=["images", "Images", "etis-laribpolypdb"],
    mask_dir_names=["masks", "Masks", "etis-laribpolypdb-gt"],
    is_kvasir=False
)
"""
nb.cells.append(new_code_cell(cell8))

# ─── CELL 9: Summary Table ────────────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## Final Summary"))
cell9 = """\
results = {
    "Kvasir-SEG":   kvasir_metrics,
    "CVC-ClinicDB": cvc_metrics,
    "ETIS-Larib":   etis_metrics,
}

header = f"{'Dataset':<22} | {'Dice (DSC)':<12} | {'mIoU':<10} | {'Precision':<12} | {'Recall':<10}"
sep    = "=" * len(header)
print(f"\\n{sep}\\n  CHAKRATRANSFORMER (ViT-LARGE 384) — FINAL RESULTS\\n{sep}")
print(header)
print("-" * len(header))
for name, m in results.items():
    if m is None:
        print(f"{name:<22} | {'(not evaluated)'}")
    else:
        print(f"{name:<22} | {m['dice']:<12.4f} | {m['iou']:<10.4f} | {m['precision']:<12.4f} | {m['recall']:<10.4f}")
print(sep)
"""
nb.cells.append(new_code_cell(cell9))

# ─── Save ─────────────────────────────────────────────────────────────────────
out = r'm:\chakramodel\notebooks\Kaggle_ChakraTransformer_Evaluation_Standalone.ipynb'
with open(out, 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)
print(f"SUCCESS: Notebook saved to {out}")
