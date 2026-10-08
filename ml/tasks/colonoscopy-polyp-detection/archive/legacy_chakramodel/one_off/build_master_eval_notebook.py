"""
build_master_eval_notebook.py
============================
Builds ONE master Kaggle evaluation notebook that tests ALL available datasets:

FROM SPREADSHEET STATUS:
  ✅ Completed Uploads:
    - EndoScene CVC-300         (gokulrocky/endoscene-cvc300-polyp-raw-dataset)
    - PolypDB                   (gokulrocky/polypdb-polyp-raw-stress-testdataset)
    - PICCOLO Dataset           (uploaded, private)
    - HyperKvasir Segmented     (1000 images subset, gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset)
  ⏳ Pending / Missing:
    - SUN-SEG                   (not uploaded yet, 12.5 GB)
    - LDPolyp Video             (in progress, 7.5 GB)
    - HyperKvasir Full          (30 GB - partitioning needed)

NOTEBOOK TESTS (in order of priority):
  1. Kvasir-SEG test split     (from ChakraModel Evaluation Datasets)
  2. EndoScene / CVC-300       (gokulrocky/endoscene-cvc300-polyp-raw-dataset)
  3. HyperKvasir Segmented     (hyper-kvasir-segmented-images from LD dataset)
  4. PolypDB (all 5 modalities) (gokulrocky/polypdb-polyp-raw-stress-testdataset)
  5. PICCOLO                   (if attached)
  6. LDPolyp Images            (if attached)
"""
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
import os

OUT_DIR = r"m:\chakramodel\notebooks"
os.makedirs(OUT_DIR, exist_ok=True)

nb = new_notebook()

# ─── CELL 0: Header ───────────────────────────────────────────────────────────
nb.cells.append(new_markdown_cell("""\
# ChakraModel — Master Cross-Dataset Evaluation Notebook (v3)

**Comprehensive zero-shot cross-dataset evaluation of ChakraTransformer (ViT-Large 384)**  
Tests ALL uploaded Kaggle datasets in one run. Reports Dice, mIoU, Precision, Recall per dataset.

---

## Required Kaggle Dataset Mounts
| Dataset | Kaggle Slug | Priority |
|---------|-------------|---------|
| ChakraModel Eval Datasets (Kvasir-SEG test) | `gokulrocky/chakramodel-evaluation-datasets` | 🔴 Required |
| ChakraTransformer Weights | `gokulrocky/chakratransformer-weights` | 🔴 Required |
| EndoScene CVC-300 | `gokulrocky/endoscene-cvc300-polyp-raw-dataset` | 🔴 Required |
| HyperKvasir + LD (has segmented subset) | `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset` | 🟡 Optional |
| PolypDB Stress Test | `gokulrocky/polypdb-polyp-raw-stress-testdataset` | 🟡 Optional |
| PICCOLO Dataset | *(attach if available)* | 🟢 Optional |
| LDPolyp Images | *(attach if available)* | 🟢 Optional |

> **GPU:** Use T4 x2 or P100 — ViT-Large requires ≥8 GB VRAM  
> **Runtime:** ~15–20 min per dataset
"""))

# ─── CELL 1: Environment ─────────────────────────────────────────────────────
nb.cells.append(new_code_cell("""\
import subprocess
subprocess.run(["pip", "install", "-q", "timm", "opencv-python-headless", "albumentations", "pandas", "tabulate"], check=True)

import os, glob, cv2, torch, json
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
import timm
from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from torch.amp import autocast
import warnings
warnings.filterwarnings('ignore')

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
    print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
else:
    print("⚠️  CUDA not available — running on CPU (very slow)")
print(f"Device: {device}")

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
"""))

# ─── CELL 2: Model Architecture ──────────────────────────────────────────────
nb.cells.append(new_code_cell("""\
# ─────────────────────────────────────────────────────────────────────
# EXACT ChakraTransformerSegmenter — must match training checkpoint
# Layer names and tensor shapes MUST match so strict=True succeeds
# ─────────────────────────────────────────────────────────────────────
class ChakraTransformerSegmenter(nn.Module):
    def __init__(self, backbone_name='vit_large_patch16_384', pretrained=False, num_classes=1):
        super().__init__()
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
            expected = (H // 16) * (W // 16)
            if features.shape[1] == expected + 1:
                features = features[:, 1:, :]
            features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, H // 16, W // 16)
        x_dec = features
        for i, layer in enumerate(self.decode_head):
            x_dec = layer(x_dec)
            if i == 2: x_dec = self.dropout1(x_dec)
            elif i == 5: x_dec = self.dropout2(x_dec)
        if x_dec.shape[2:] != (H, W):
            x_dec = F.interpolate(x_dec, size=(H, W), mode='bilinear', align_corners=False)
        return x_dec

# Load weights
print("Initializing ChakraTransformer (ViT-Large 384)...")
model = ChakraTransformerSegmenter()

weights_path = glob.glob("/kaggle/input/**/chakra_transformer_best.pth", recursive=True)
if not weights_path:
    # Fallback: try .pt files
    weights_path = glob.glob("/kaggle/input/**/*.pth", recursive=True) + glob.glob("/kaggle/input/**/*.pt", recursive=True)

if weights_path:
    print(f"Loading: {weights_path[0]}")
    sd = torch.load(weights_path[0], map_location=device, weights_only=True)
    model.load_state_dict(sd, strict=True)
    print(f"✅ Weights loaded ({sum(p.numel() for p in model.parameters())/1e6:.1f}M params)")
else:
    print("⚠️  No weights found! Running with random init (metrics will be near-zero).")
    print("   Please attach the 'ChakraTransformer_Weights' dataset.")

model.to(device).eval()
"""))

# ─── CELL 3: Dataset Loader & Metrics ────────────────────────────────────────
nb.cells.append(new_code_cell("""\
# ─── Dataset Loader ───────────────────────────────────────────────────────────
class EvalDataset(Dataset):
    def __init__(self, img_files, mask_dict, img_size=384):
        self.files = img_files
        self.masks = mask_dict
        self.size = img_size
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3,1,1)
        self.std  = torch.tensor([0.229, 0.224, 0.225]).view(3,1,1)

    def __len__(self): return len(self.files)

    def __getitem__(self, idx):
        p = self.files[idx]
        img = cv2.imread(str(p))
        if img is None:
            img = np.zeros((self.size, self.size, 3), dtype=np.uint8)
        else:
            img = cv2.resize(img, (self.size, self.size))

        mp = self.masks.get(p.stem)
        if mp and Path(mp).exists():
            msk = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
            msk = np.zeros((self.size, self.size), dtype=np.uint8) if msk is None else cv2.resize(msk, (self.size, self.size), interpolation=cv2.INTER_NEAREST)
        else:
            msk = np.zeros((self.size, self.size), dtype=np.uint8)

        t = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).permute(2,0,1).float() / 255.0
        t = (t - self.mean) / self.std
        m = torch.from_numpy((msk > 127).astype(np.float32)).unsqueeze(0)
        return t, m

# ─── Metrics ──────────────────────────────────────────────────────────────────
def compute_metrics(model, loader):
    model.eval()
    dices, ious, precs, recs = [], [], [], []
    with torch.no_grad():
        for imgs, masks in loader:
            imgs = imgs.to(device, non_blocking=True)
            with autocast(device_type='cuda', dtype=torch.float16):
                logits = model(imgs)
            probs = torch.sigmoid(logits).cpu().float().numpy()
            gts   = masks.numpy()
            for i in range(len(probs)):
                p = (probs[i,0] > 0.5).astype(np.float32)
                g = (gts[i,0]   > 0.5).astype(np.float32)
                tp = (p*g).sum(); fp = (p*(1-g)).sum(); fn = ((1-p)*g).sum()
                dices.append((2*tp+1e-6)/(2*tp+fp+fn+1e-6))
                ious.append((tp+1e-6)/(tp+fp+fn+1e-6))
                precs.append((tp+1e-6)/(tp+fp+1e-6))
                recs.append((tp+1e-6)/(tp+fn+1e-6))
    n = max(len(dices), 1)
    return {
        'dice': float(np.mean(dices)), 'std': float(np.std(dices)),
        'iou': float(np.mean(ious)),
        'precision': float(np.mean(precs)),
        'recall': float(np.mean(recs)),
        'n_images': n
    }

# ─── Universal Dataset Discovery ─────────────────────────────────────────────
def discover(root, img_hints=None, mask_hints=None):
    \"\"\"
    Walk root looking for image/mask directories using name hints.
    Falls back to any PNG/JPG files if no hint directories found.
    Returns (img_files, mask_dict).
    \"\"\"
    root = Path(root)
    if not root.exists(): return [], {}

    img_hints  = img_hints  or ['images','Images','image','Image','imgs','Imgs','original','Original']
    mask_hints = mask_hints or ['masks','Masks','mask','Mask','groundtruth','GroundTruth','gt','GT','ground truth']

    img_dirs, mask_dirs = [], []
    for p in root.rglob('*'):
        if not p.is_dir(): continue
        lo = p.name.lower().strip()
        if lo in {h.lower() for h in img_hints}:  img_dirs.append(p)
        if lo in {h.lower() for h in mask_hints}: mask_dirs.append(p)

    # Fallback: if no hints matched, collect all image files recursively
    img_files = []
    if img_dirs:
        for d in img_dirs:
            img_files += sorted([f for f in d.iterdir() if f.suffix.lower() in IMAGE_EXTS])
    else:
        img_files = sorted([f for f in root.rglob('*') if f.suffix.lower() in IMAGE_EXTS])

    mask_dict = {}
    if mask_dirs:
        for d in mask_dirs:
            for f in d.iterdir():
                if f.suffix.lower() in IMAGE_EXTS:
                    mask_dict[f.stem] = f
    
    return img_files, mask_dict

# ─── Evaluation Runner ────────────────────────────────────────────────────────
ALL_RESULTS = {}

def eval_dataset(name, root, img_hints=None, mask_hints=None,
                 is_kvasir=False, batch_size=8, note=''):
    print(f\"\\n{'='*62}\")
    print(f\"  {name}\")
    if note: print(f\"  Note: {note}\")
    print(f\"{'='*62}\")
    
    img_files, mask_dict = discover(root, img_hints, mask_hints)
    if not img_files:
        print(f\"  ⚠️  No images found at {root}\")
        ALL_RESULTS[name] = None
        return None
    
    print(f\"  Found: {len(img_files)} images, {len(mask_dict)} masks\")
    
    if is_kvasir:
        # Replicate exact 70/15/15 split used during training
        np.random.seed(42)
        perm = np.random.permutation(len(img_files))
        n_train = int(0.70 * len(img_files))
        n_cal   = int(0.15 * len(img_files))
        idx_test = perm[n_train + n_cal:]
        img_files = [img_files[i] for i in idx_test]
        print(f\"  Using held-out test split: {len(img_files)} images (70/15/15, seed=42)\")
    
    ds = EvalDataset(img_files, mask_dict)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)
    m = compute_metrics(model, dl)
    
    print(f\"  ✅ Dice (DSC)  : {m['dice']:.4f} ± {m['std']:.4f}\")
    print(f\"     mIoU        : {m['iou']:.4f}\")
    print(f\"     Precision   : {m['precision']:.4f}\")
    print(f\"     Recall      : {m['recall']:.4f}\")
    print(f\"     Images eval : {m['n_images']}\")
    
    ALL_RESULTS[name] = m
    return m

print("✅ All utilities ready. Starting evaluations...")
"""))

# ─── CELL 4: Evaluation 1 — Kvasir-SEG test split ────────────────────────────
nb.cells.append(new_markdown_cell("## 📊 Eval 1: Kvasir-SEG (Held-Out 15% Test Split)\n*In-distribution validation — expected: ~0.90 DSC*"))
nb.cells.append(new_code_cell("""\
# Try multiple possible Kvasir paths
kvasir_roots = [
    "/kaggle/input/chakramodel-evaluation-datasets",
    "/kaggle/input/kvasir-seg-data-polyp-segmentation-detection",
    "/kaggle/input/kvasir-seg",
]
kvasir_root = next((r for r in kvasir_roots if Path(r).exists()), None)

if kvasir_root:
    eval_dataset("Kvasir-SEG (test split)", kvasir_root,
                 img_hints=['images','Images'], mask_hints=['masks','Masks'],
                 is_kvasir=True, note="Held-out 15%, seed=42 — same split as training")
else:
    print("⚠️  Kvasir-SEG not found. Attach 'chakramodel-evaluation-datasets'.")
    ALL_RESULTS["Kvasir-SEG (test split)"] = None
"""))

# ─── CELL 5: Evaluation 2 — EndoScene CVC-300 ────────────────────────────────
nb.cells.append(new_markdown_cell(
    "## 📊 Eval 2: EndoScene / CVC-300 (Zero-Shot)\n"
    "*Unseen-domain: flat and peduncular polyp morphologies — expected: 0.60–0.80 DSC if generalizing*\n\n"
    "Dataset: `gokulrocky/endoscene-cvc300-polyp-raw-dataset`  \n"
    "Structure: `CVC-300/Images/` (60 files) and `CVC-300/masks/` (60 files)"
))
nb.cells.append(new_code_cell("""\
# Exact path from Kaggle dataset explorer screenshot
cvc300_roots = [
    "/kaggle/input/endoscene-cvc300-polyp-raw-dataset/CVC-300",
    "/kaggle/input/endoscene-cvc300-polyp-raw-dataset",
]
cvc300_root = next((r for r in cvc300_roots if Path(r).exists()), None)

if cvc300_root:
    eval_dataset("EndoScene CVC-300", cvc300_root,
                 img_hints=['Images','images','image'],
                 mask_hints=['masks','Masks','mask'],
                 is_kvasir=False,
                 note="60 images, flat+peduncular polyps, strict unseen-domain test")
else:
    print("⚠️  CVC-300 not found. Attach 'endoscene-cvc300-polyp-raw-dataset'.")
    ALL_RESULTS["EndoScene CVC-300"] = None
"""))

# ─── CELL 6: Evaluation 3 — HyperKvasir Segmented ───────────────────────────
nb.cells.append(new_markdown_cell(
    "## 📊 Eval 3: HyperKvasir Segmented (1,000 Images, Zero-Shot)\n"
    "*Large-scale in-distribution test — expected: ~0.85–0.92 DSC*\n\n"
    "Dataset: `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset`  \n"
    "Structure: `hyper-kvasir-segmented-images/` directory"
))
nb.cells.append(new_code_cell("""\
# HyperKvasir has multiple subdirs — we want the segmented polyp subset
hk_base = "/kaggle/input/hyperkvasir-dataset-first-half-and-and-ld-dataset"

# Try to find the segmented images dir
hk_seg_candidates = [
    f"{hk_base}/hyper-kvasir-segmented-images",
    f"{hk_base}/hyper-kvasir-segmented-ima",  # truncated dir name in Kaggle explorer
    f"{hk_base}/LDPolyp_images labeled-part 1/hyper-kvasir-segmented-images",
]

hk_root = next((r for r in hk_seg_candidates if Path(r).exists()), None)

if hk_root is None:
    # Fallback: search anywhere in the dataset for a 'hyper-kvasir' named dir
    all_dirs = list(Path(hk_base).rglob("*")) if Path(hk_base).exists() else []
    for d in all_dirs:
        if d.is_dir() and 'segmented' in d.name.lower() and 'hyper' in d.name.lower():
            hk_root = str(d)
            break
    if hk_root is None and Path(hk_base).exists():
        # Print directory tree to help debug
        print("🔍 Contents of HyperKvasir dataset:")
        for d in sorted(Path(hk_base).iterdir()):
            print(f"  {d.name}/")
            for dd in sorted(d.iterdir())[:5] if d.is_dir() else []:
                print(f"    {dd.name}")

if hk_root:
    eval_dataset("HyperKvasir Segmented (1k)", hk_root,
                 img_hints=['images','Images','polyp'],
                 mask_hints=['masks','Masks','mask'],
                 is_kvasir=False,
                 note="1,000 labeled polyp images from HyperKvasir segmented subset")
else:
    print("⚠️  HyperKvasir segmented subset not found or dataset not attached.")
    ALL_RESULTS["HyperKvasir Segmented (1k)"] = None
"""))

# ─── CELL 7: Evaluation 4 — PolypDB ─────────────────────────────────────────
nb.cells.append(new_markdown_cell(
    "## 📊 Eval 4: PolypDB Stress Test (5 Optical Modalities, Zero-Shot)\n"
    "*Extreme generalization test — WLI, NBI, LCI, BLI, FICE modalities*\n\n"
    "Dataset: `gokulrocky/polypdb-polyp-raw-stress-testdataset`  \n"
    "~3,934 images across 5 lighting conditions — hardest cross-modal test"
))
nb.cells.append(new_code_cell("""\
pdb_root = "/kaggle/input/polypdb-polyp-raw-stress-testdataset"

if Path(pdb_root).exists():
    # Print what's there first
    print("🔍 PolypDB structure:")
    for d in sorted(Path(pdb_root).iterdir())[:10]:
        print(f"  {d.name}")
    
    # Eval all modalities together
    eval_dataset("PolypDB (All Modalities)", pdb_root,
                 img_hints=['images','Images','image','imgs'],
                 mask_hints=['masks','Masks','mask','annotations'],
                 is_kvasir=False,
                 note="3,934 images: WLI+NBI+LCI+BLI+FICE — stress test across optical modalities")
    
    # Then try modality-by-modality if directories exist
    for modality in ['WLI','NBI','LCI','BLI','FICE']:
        mod_dir = Path(pdb_root) / modality
        if mod_dir.exists():
            eval_dataset(f"PolypDB ({modality})", str(mod_dir),
                         is_kvasir=False, batch_size=16,
                         note=f"Single modality: {modality}")
else:
    print("⚠️  PolypDB not found. Attach 'polypdb-polyp-raw-stress-testdataset'.")
    ALL_RESULTS["PolypDB (All Modalities)"] = None
"""))

# ─── CELL 8: Evaluation 5 — PICCOLO ─────────────────────────────────────────
nb.cells.append(new_markdown_cell(
    "## 📊 Eval 5: PICCOLO Dataset (WLI + NBI, Zero-Shot)\n"
    "*Narrow-Band Imaging test — if dataset attached*"
))
nb.cells.append(new_code_cell("""\
# PICCOLO dataset - search by keyword since slug may vary
piccolo_candidates = glob.glob("/kaggle/input/*piccolo*", recursive=False) + \
                     glob.glob("/kaggle/input/*PICCOLO*", recursive=False)

if piccolo_candidates:
    piccolo_root = piccolo_candidates[0]
    print(f"Found PICCOLO at: {piccolo_root}")
    eval_dataset("PICCOLO (WLI+NBI)", piccolo_root,
                 img_hints=['images','Images','image','WLI','NBI'],
                 mask_hints=['masks','Masks','mask','annotations'],
                 is_kvasir=False,
                 note="3,433 images in White-Light + Narrow-Band Imaging modalities")
else:
    print("ℹ️  PICCOLO dataset not attached — skipping.")
    ALL_RESULTS["PICCOLO (WLI+NBI)"] = None
"""))

# ─── CELL 9: Evaluation 6 — LDPolyp Images ───────────────────────────────────
nb.cells.append(new_markdown_cell(
    "## 📊 Eval 6: LDPolyp Images (Video Frames, Zero-Shot)\n"
    "*If LDPolyp data is attached via HyperKvasir combined dataset*"
))
nb.cells.append(new_code_cell("""\
# LDPolyp labeled images inside the combined HyperKvasir LD dataset
ldpolyp_candidates = [
    "/kaggle/input/hyperkvasir-dataset-first-half-and-and-ld-dataset/LDPolyp_images labeled-part 1",
    "/kaggle/input/hyperkvasir-dataset-first-half-and-and-ld-dataset/LDPolyp_images labelled",
]
# Also search for it
for p in Path("/kaggle/input/hyperkvasir-dataset-first-half-and-and-ld-dataset").rglob("*") if Path("/kaggle/input/hyperkvasir-dataset-first-half-and-and-ld-dataset").exists() else []:
    if p.is_dir() and 'ldpolyp' in p.name.lower():
        ldpolyp_candidates.insert(0, str(p))

ldpolyp_root = next((r for r in ldpolyp_candidates if Path(r).exists()), None)

if ldpolyp_root:
    eval_dataset("LDPolyp Images", ldpolyp_root,
                 is_kvasir=False, batch_size=8,
                 note="LDPolyp labeled frames from 160-video colonoscopy benchmark")
else:
    print("ℹ️  LDPolyp labeled images not found — may not be attached yet.")
    ALL_RESULTS["LDPolyp Images"] = None
"""))

# ─── CELL 10: Final Summary Table ────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 📋 Final Results Summary"))
nb.cells.append(new_code_cell("""\
import pandas as pd
import json

print("\\n" + "="*75)
print("  CHAKRATRANSFORMER (ViT-LARGE 384) — CROSS-DATASET EVALUATION RESULTS")
print("="*75)

rows = []
for name, m in ALL_RESULTS.items():
    if m is None:
        rows.append({'Dataset': name, 'Dice (DSC)': 'N/A', 'mIoU': 'N/A',
                     'Precision': 'N/A', 'Recall': 'N/A', 'N Images': 'N/A', 'Status': '⚠️ Skipped'})
    else:
        rows.append({
            'Dataset': name,
            'Dice (DSC)': f"{m['dice']:.4f} ± {m['std']:.4f}",
            'mIoU': f"{m['iou']:.4f}",
            'Precision': f"{m['precision']:.4f}",
            'Recall': f"{m['recall']:.4f}",
            'N Images': m['n_images'],
            'Status': '✅ Done'
        })

df = pd.DataFrame(rows)
print(df.to_string(index=False))
print("="*75)

# Save results to JSON for record-keeping
json_path = "/kaggle/working/cross_dataset_results_v3.json"
saveable = {k: v for k, v in ALL_RESULTS.items() if v is not None}
with open(json_path, 'w') as f:
    json.dump(saveable, f, indent=2)
print(f"\\n✅ Results saved to: {json_path}")

# SOTA comparison reminder
print(\"\\n\" + \"-\"*75)
print(\"SOTA COMPARISON (Avg Dice across 5 standard datasets):\")
print(\"  PolypMamba (2025) : 89.00%  | CASCADE (2023) : 88.46%\")
print(\"  Polyp-PVT (2021)  : 86.98%  | FCBFormer (2022): 86.54%\")
print(\"  PraNet (2020)     : 80.10%\")
print(\"-\"*75)

# ChakraModel avg
valid = [v['dice'] for v in ALL_RESULTS.values() if v is not None]
if valid:
    avg = sum(valid) / len(valid)
    print(f\"  ChakraModel avg Dice ({len(valid)} datasets): {avg:.4f} ({avg*100:.2f}%)\")
print(\"-\"*75)
"""))

# ─── Save ─────────────────────────────────────────────────────────────────────
out = os.path.join(OUT_DIR, "Kaggle_Master_CrossDataset_Eval_v3.ipynb")
with open(out, 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)
print(f"SUCCESS: Created {out}")
print(f"Notebook has {len(nb.cells)} cells")
