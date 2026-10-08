"""
build_crossval_v5_PATHS_FIXED.py
================================
CRITICAL FIX: Kaggle is mounting datasets under:
  /kaggle/input/datasets/gokulrocky/<dataset-name>/

NOT the expected:
  /kaggle/input/<dataset-name>/

Discovered from the scout cell output in crossvali (2).ipynb:

EXACT PATHS CONFIRMED:
  Images:
    /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/images  [495 images]
    /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/etis-larib/images    [5 images]
    /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/images    [1000 images]
    /kaggle/input/datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset/CVC-300/images    [60 images]
  Masks:
    /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/masks   [495 masks]
    /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/etis-larib/masks     [5 masks]
    /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/masks     [1000 masks]
    /kaggle/input/datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset/CVC-300/masks     [60 masks]

TOTAL: 3,184 files, 3,120 images, 13.8 GB

DATASETS ALREADY AVAILABLE (confirmed in scout):
  ✅ Kvasir-SEG: 1000 images
  ✅ CVC-ClinicDB: 495 images  
  ✅ ETIS-Larib: 5 images (subset only!)
  ✅ EndoScene CVC-300: 60 images
  (HyperKvasir + PolypDB were attached but not showing — may be in datasets/ subpath too)
"""
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
import os

OUT = r"m:\chakramodel\notebooks\Kaggle_CrossVal_v5_PATHS_FIXED.ipynb"

nb = new_notebook()

# ─── CELL 0: Header ──────────────────────────────────────────────────────────
nb.cells.append(new_markdown_cell("""\
# ChakraModel — Cross-Dataset Evaluation v5 (Paths Fixed)

**Key fix:** Kaggle mounts datasets under `/kaggle/input/datasets/gokulrocky/` — not `/kaggle/input/` directly.

All paths have been corrected based on the scout cell output from the previous run.

## Confirmed Available Datasets
| Dataset | Path | N Images |
|---------|------|---------|
| Kvasir-SEG | `datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/` | 1,000 |
| CVC-ClinicDB | `datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/` | 495 |
| ETIS-Larib | `datasets/gokulrocky/chakramodel-evaluation-datasets/etis-larib/` | 5 (subset) |
| EndoScene CVC-300 | `datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset/CVC-300/` | 60 |
| HyperKvasir | Searching under `datasets/` prefix | ~1,000 |
| PolypDB | Searching under `datasets/` prefix | ~3,934 |
"""))

# ─── CELL 1: Env ─────────────────────────────────────────────────────────────
nb.cells.append(new_code_cell("""\
import subprocess
subprocess.run(["pip", "install", "-q", "timm", "opencv-python-headless", "pandas"], check=True)

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
    print("⚠️  No GPU")
print(f"Device: {device}")
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}

# ── CORRECTED BASE PATH ───────────────────────────────────────────────────────
# From scout: datasets are at /kaggle/input/datasets/gokulrocky/<slug>/
BASE = "/kaggle/input/datasets/gokulrocky"
print(f"\\nBase path: /kaggle/input/datasets/gokulrocky")
print(f"Exists: {Path(BASE).exists()}")

if Path(BASE).exists():
    print("\\nTop-level directories:")
    for d in sorted(Path(BASE).iterdir()):
        print(f"  {d.name}/")
"""))

# ─── CELL 2: Model ───────────────────────────────────────────────────────────
nb.cells.append(new_code_cell("""\
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

print("Initializing ChakraTransformer...")
model = ChakraTransformerSegmenter()

# Search in BOTH standard and datasets/ subpath
weights_search = (
    glob.glob(f"/kaggle/input/datasets/gokulrocky/**/chakra_transformer_best.pth", recursive=True) +
    glob.glob("/kaggle/input/**/chakra_transformer_best.pth", recursive=True) +
    glob.glob(f"/kaggle/input/datasets/gokulrocky/**/*.pth", recursive=True) +
    glob.glob("/kaggle/input/**/*.pth", recursive=True)
)

if weights_search:
    wp = weights_search[0]
    print(f"Loading: {wp}")
    sd = torch.load(wp, map_location=device, weights_only=True)
    model.load_state_dict(sd, strict=True)
    print(f"✅ Weights loaded: {sum(p.numel() for p in model.parameters())/1e6:.1f}M params")
else:
    raise FileNotFoundError("No .pth weights found! Check ChakraTransformer_Weights is attached.")

model.to(device).eval()
"""))

# ─── CELL 3: Utilities ───────────────────────────────────────────────────────
nb.cells.append(new_code_cell("""\
class EvalDataset(Dataset):
    MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
    STD  = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
    def __init__(self, imgs, masks, size=384):
        self.files, self.masks, self.size = imgs, masks, size
    def __len__(self): return len(self.files)
    def __getitem__(self, idx):
        p = self.files[idx]
        img = cv2.imread(str(p))
        img = np.zeros((self.size,self.size,3),dtype=np.uint8) if img is None else cv2.resize(img,(self.size,self.size))
        mp = self.masks.get(p.stem) or self.masks.get(p.name)
        if mp and Path(str(mp)).exists():
            msk = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
            msk = cv2.resize(msk,(self.size,self.size),interpolation=cv2.INTER_NEAREST) if msk is not None else np.zeros((self.size,self.size),dtype=np.uint8)
        else:
            msk = np.zeros((self.size,self.size),dtype=np.uint8)
        t = torch.from_numpy(cv2.cvtColor(img,cv2.COLOR_BGR2RGB)).permute(2,0,1).float()/255.
        t = (t - self.MEAN)/self.STD
        m = torch.from_numpy((msk>127).astype(np.float32)).unsqueeze(0)
        return t, m

def metrics(model, loader):
    dices,ious,precs,recs = [],[],[],[]
    with torch.no_grad():
        for imgs,masks in loader:
            imgs = imgs.to(device, non_blocking=True)
            with autocast(device_type='cuda', dtype=torch.float16):
                logits = model(imgs)
            probs = torch.sigmoid(logits).cpu().float().numpy()
            gts   = masks.numpy()
            for i in range(len(probs)):
                pred = (probs[i,0]>0.5).astype(np.float32)
                gt   = (gts[i,0]>0.5).astype(np.float32)
                tp=(pred*gt).sum(); fp=(pred*(1-gt)).sum(); fn=((1-pred)*gt).sum()
                dices.append((2*tp+1e-6)/(2*tp+fp+fn+1e-6))
                ious.append((tp+1e-6)/(tp+fp+fn+1e-6))
                precs.append((tp+1e-6)/(tp+fp+1e-6))
                recs.append((tp+1e-6)/(tp+fn+1e-6))
    return {'dice':float(np.mean(dices)),'std':float(np.std(dices)),
            'iou':float(np.mean(ious)),'precision':float(np.mean(precs)),
            'recall':float(np.mean(recs)),'n':len(dices)}

ALL_RESULTS = {}

def run(name, img_dir, mask_dir, kvasir_split=False, batch=8, note=''):
    img_dir, mask_dir = Path(img_dir), Path(mask_dir)
    print(f"\\n{'='*65}")
    print(f"  {name}")
    if note: print(f"  {note}")
    print(f"{'='*65}")
    
    if not img_dir.exists():
        print(f"  ❌ img_dir not found: {img_dir}")
        ALL_RESULTS[name] = None; return None
    
    imgs = sorted([f for f in img_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS])
    masks = {}
    if mask_dir.exists():
        for f in mask_dir.iterdir():
            if f.suffix.lower() in IMAGE_EXTS:
                masks[f.stem] = str(f)
                masks[f.name] = str(f)
    
    print(f"  Images: {len(imgs)} | Masks: {len(masks)//2}")
    
    if kvasir_split:
        np.random.seed(42)
        perm = np.random.permutation(len(imgs))
        n_tr = int(0.70*len(imgs)); n_ca = int(0.15*len(imgs))
        imgs = [imgs[i] for i in perm[n_tr+n_ca:]]
        print(f"  Using held-out test split: {len(imgs)} images")
    
    if not imgs:
        print("  ⚠️  No images — skipping"); ALL_RESULTS[name]=None; return None
    
    dl = DataLoader(EvalDataset(imgs,masks), batch_size=batch,
                    shuffle=False, num_workers=2, pin_memory=True)
    m = metrics(model, dl)
    print(f"  ✅ DSC  : {m['dice']:.4f} ± {m['std']:.4f}")
    print(f"     mIoU : {m['iou']:.4f}")
    print(f"     Prec : {m['precision']:.4f}  Recall: {m['recall']:.4f}")
    print(f"     N    : {m['n']}")
    ALL_RESULTS[name] = m
    return m

print("✅ Utilities ready.")
"""))

# ─── CELL 4: Eval 1 — Kvasir-SEG ─────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 📊 Eval 1 — Kvasir-SEG (In-Distribution, Held-Out 15%)"))
nb.cells.append(new_code_cell("""\
# CONFIRMED path from scout output
run("Kvasir-SEG (test split)",
    img_dir  = "/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/images",
    mask_dir = "/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/masks",
    kvasir_split = True,
    note = "1000 imgs total → 150 held-out test, seed=42, 70/15/15 split")
"""))

# ─── CELL 5: Eval 2 — CVC-ClinicDB ──────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 📊 Eval 2 — CVC-ClinicDB (Zero-Shot) — Previously 0.5401 DSC"))
nb.cells.append(new_code_cell("""\
# CONFIRMED path from scout output: 495 images, 495 masks
run("CVC-ClinicDB (zero-shot)",
    img_dir  = "/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/images",
    mask_dir = "/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/masks",
    note = "495 images — white-light colonoscopy, different center from Kvasir")
"""))

# ─── CELL 6: Eval 3 — ETIS-Larib ────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 📊 Eval 3 — ETIS-Larib (Zero-Shot) — Previously 0.0000 DSC"))
nb.cells.append(new_code_cell("""\
# CONFIRMED path: only 5 images in subset! (full dataset has 196)
etis_img_dir = Path("/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/etis-larib/images")
n_etis = len(list(etis_img_dir.iterdir())) if etis_img_dir.exists() else 0
print(f"ETIS-Larib images found: {n_etis}")
if n_etis < 10:
    print("⚠️  Only a subset of ETIS-Larib is available (5 images vs 196 full dataset)")
    print("   Recording historical score: Dice=0.0000 (documented catastrophic failure)")
    ALL_RESULTS["ETIS-Larib (zero-shot)"] = {
        "dice":0.0000,"std":0.0000,"iou":0.0000,
        "precision":0.0,"recall":0.0,"n":196,
        "_historical": True,
        "_note": "Full dataset: catastrophic failure, Dice=0.0000. Only 5-image subset available on Kaggle."
    }
else:
    run("ETIS-Larib (zero-shot)",
        img_dir  = f"/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/etis-larib/images",
        mask_dir = f"/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/etis-larib/masks",
        note = "196 images — hardest unseen domain, irregular lighting")
"""))

# ─── CELL 7: Eval 4 — EndoScene CVC-300 ─────────────────────────────────────
nb.cells.append(new_markdown_cell("## 📊 Eval 4 — EndoScene CVC-300 (Zero-Shot) ← NEW"))
nb.cells.append(new_code_cell("""\
# CONFIRMED path from scout: 60 images, 60 masks
run("EndoScene CVC-300 (zero-shot)",
    img_dir  = "/kaggle/input/datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset/CVC-300/images",
    mask_dir = "/kaggle/input/datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset/CVC-300/masks",
    note = "60 images — flat+peduncular morphologies, EndoScene benchmark")
"""))

# ─── CELL 8: Eval 5 — HyperKvasir ────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 📊 Eval 5 — HyperKvasir Segmented (Zero-Shot) ← NEW"))
nb.cells.append(new_code_cell("""\
# HyperKvasir — search under datasets/ prefix
hk_img, hk_mask = None, None
hk_candidates = list(Path("/kaggle/input/datasets/gokulrocky").rglob("*")) if Path("/kaggle/input/datasets/gokulrocky").exists() else []

for d in hk_candidates:
    if d.is_dir() and d.name.lower() in {'images','image','imgs'}:
        parent = d.parent.name.lower()
        if 'hyper' in parent or 'kvasir' in parent or 'segmented' in parent:
            n_imgs = len([f for f in d.iterdir() if f.suffix.lower() in IMAGE_EXTS])
            if n_imgs >= 50:  # must be a real image set
                hk_img = str(d)
                # find corresponding mask dir
                for sibling in d.parent.iterdir():
                    if sibling.is_dir() and sibling.name.lower() in {'masks','mask'}:
                        hk_mask = str(sibling)
                print(f"Found HyperKvasir images: {hk_img} [{n_imgs} imgs]")
                break

if hk_img:
    run("HyperKvasir Segmented", img_dir=hk_img, mask_dir=hk_mask or hk_img,
        note="Segmented polyp subset from HyperKvasir benchmark")
else:
    # Print what we can find under BASE to debug
    print("⚠️  HyperKvasir not auto-discovered. Searching dataset paths...")
    for d in sorted(Path("/kaggle/input/datasets/gokulrocky").iterdir()) if Path("/kaggle/input/datasets/gokulrocky").exists() else []:
        print(f"  {d.name}/")
    ALL_RESULTS["HyperKvasir Segmented"] = None
"""))

# ─── CELL 9: Eval 6 — PolypDB ────────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 📊 Eval 6 — PolypDB Multi-Modality (Zero-Shot) ← NEW"))
nb.cells.append(new_code_cell("""\
# PolypDB — search under datasets/ prefix
pdb_root = None
for d in sorted(Path("/kaggle/input/datasets/gokulrocky").iterdir()) if Path("/kaggle/input/datasets/gokulrocky").exists() else []:
    if 'polyp' in d.name.lower() and 'db' in d.name.lower():
        pdb_root = str(d); break
    if 'stress' in d.name.lower() or 'polypdb' in d.name.lower():
        pdb_root = str(d); break

# Also try direct slug
direct = Path("/kaggle/input/datasets/gokulrocky/polypdb-polyp-raw-stress-testdataset")
if direct.exists(): pdb_root = str(direct)

if pdb_root:
    print(f"Found PolypDB at: {pdb_root}")
    for item in sorted(Path(pdb_root).iterdir())[:8]:
        print(f"  {{item.name}}/")
    
    # Find all image/mask pairs
    all_imgs = sorted([f for f in Path(pdb_root).rglob("*")
                       if f.suffix.lower() in IMAGE_EXTS
                       and f.parent.name.lower() in {'images','image','imgs'}])
    all_masks_dir = [d for d in Path(pdb_root).rglob("*")
                     if d.is_dir() and d.name.lower() in {'masks','mask'}]
    mask_dict = {}
    for md in all_masks_dir:
        for f in md.iterdir():
            if f.suffix.lower() in IMAGE_EXTS:
                mask_dict[f.stem] = str(f)
    
    print(f"PolypDB: {len(all_imgs)} images, {len(mask_dict)} masks found")
    if all_imgs:
        dl = DataLoader(EvalDataset(all_imgs, mask_dict), batch_size=16,
                        shuffle=False, num_workers=2, pin_memory=True)
        m = metrics(model, dl)
        print(f"  ✅ DSC  : {m['dice']:.4f} ± {m['std']:.4f}")
        print(f"     mIoU : {m['iou']:.4f}")
        print(f"     N    : {m['n']}")
        ALL_RESULTS["PolypDB (All Modalities)"] = m
    else:
        ALL_RESULTS["PolypDB (All Modalities)"] = None
else:
    print("⚠️  PolypDB not found under", "/kaggle/input/datasets/gokulrocky")
    print("Available datasets:")
    for d in sorted(Path("/kaggle/input/datasets/gokulrocky").iterdir()) if Path("/kaggle/input/datasets/gokulrocky").exists() else []:
        print(f"  {{d.name}}")
    ALL_RESULTS["PolypDB (All Modalities)"] = None
"""))

# ─── CELL 10: Summary ─────────────────────────────────────────────────────────
nb.cells.append(new_markdown_cell("## 📋 Results Summary & SOTA Comparison"))
nb.cells.append(new_code_cell("""\
import json

print("\\n" + "="*80)
print("  CHAKRATRANSFORMER (ViT-LARGE 384) — FULL CROSS-DATASET EVALUATION v5")
print("="*80)
print(f"  {'Dataset':<40} {'Dice DSC':>14} {'mIoU':>8} {'N':>6}  Status")
print("-"*80)

for name, m in ALL_RESULTS.items():
    if m is None:
        print(f"  {name:<40} {'—':>14} {'—':>8} {'—':>6}  ⚠️ Skipped")
    elif m.get('_historical'):
        print(f"  {name:<40} {m['dice']:.4f}(historical)  {m['iou']:.4f}  {m['n']:>6}  📌 Historical")
    else:
        print(f"  {name:<40} {m['dice']:.4f}±{m['std']:.4f}  {m['iou']:.4f}  {m['n']:>6}  ✅")

print("="*80)

# Summary stats
valid = [(n, v) for n, v in ALL_RESULTS.items() if v is not None and not v.get('_historical')]
hist  = [(n, v) for n, v in ALL_RESULTS.items() if v is not None and v.get('_historical')]
all_dices = [v['dice'] for _, v in ALL_RESULTS.items() if v is not None]

if valid:
    print(f"\\n  New evals completed : {len(valid)}")
    print(f"  Avg Dice (new only) : {np.mean([v['dice'] for _,v in valid]):.4f}")
if all_dices:
    print(f"  Avg Dice (all incl.): {np.mean(all_dices):.4f} ({np.mean(all_dices)*100:.2f}%)")

print("\\n" + "-"*80)
print("  SOTA REFERENCE (5-dataset avg Dice):")
print("    PolypMamba 2025 : 89.00% | CASCADE 2023 : 88.46% | Polyp-PVT : 86.98%")
print("    FCBFormer 2022  : 86.54% | PraNet 2020  : 80.10%")
print("-"*80)

# Save
out = "/kaggle/working/cross_dataset_results_v5.json"
saveable = {k: {kk:vv for kk,vv in v.items()} for k,v in ALL_RESULTS.items() if v is not None}
with open(out, 'w') as f:
    json.dump(saveable, f, indent=2)
print(f"\\n✅ Saved: {out}")
print("   Download from Kaggle output tab to share results.")
"""))

# Save notebook
with open(OUT, 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)
print(f"SUCCESS: {OUT}")
print(f"Cells: {len(nb.cells)}")
