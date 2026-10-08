import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

nb = new_notebook()

nb.cells.append(new_markdown_cell(
    "# ChakraNet GPU Verification (Direct Google Drive Edition)\n"
    "This notebook securely mounts your Google Drive, dynamically discovers your assets regardless of where they synced, stages them to local NVMe SSD storage to avoid FUSE latency, and executes zero-hardcoded verification."
))

cell_1_src = """\
# ==============================================================================
# STAGE 1: ENVIRONMENT INITIALIZATION & DRIVE MOUNT
# ==============================================================================
!pip install -q ultralytics timm einops albumentations

import os
import sys
import shutil
import zipfile
from pathlib import Path
from google.colab import drive

# Mount Google Drive
drive.mount('/content/drive')\
"""
nb.cells.append(new_code_cell(cell_1_src))

cell_2_src = """\
# ==============================================================================
# STAGE 2: DYNAMIC ASSET DISCOVERY & LOCAL SSD STAGING (ZERO HARDCODED PATHS)
# ==============================================================================
drive_root = Path('/content/drive/MyDrive')
content_dir = Path('/content')
local_project = content_dir / 'chakramodel'
local_project.mkdir(parents=True, exist_ok=True)
local_weights = local_project / 'weights'
local_weights.mkdir(parents=True, exist_ok=True)

print("🔍 Searching Google Drive for ChakraModel assets (Targeted Discovery)...")

# 1. Locate project directories in Drive (bounded search: immediate children matching *chakra*)
candidate_dirs = list(drive_root.glob('*chakra*')) + [drive_root]

weights_src = None
yolo_src = None
zip_src = None
src_dir_src = None
data_dir_src = None

for cdir in candidate_dirs:
    if not cdir.is_dir():
        continue
    # Check for ViT-Large segmenter weights
    for w_cand in [cdir / 'weights' / 'chakra_transformer_best.pth', cdir / 'chakra_transformer_best.pth']:
        if w_cand.exists() and weights_src is None:
            weights_src = w_cand
    # Check for YOLO weights
    for y_cand in [cdir / 'weights' / 'best.pt', cdir / 'best.pt']:
        if y_cand.exists() and yolo_src is None:
            yolo_src = y_cand
    # Check for data/code zip archives
    for z_cand in [cdir / 'chakramodel_data_scripts.zip', cdir / 'chakramodel-weights.zip']:
        if z_cand.exists() and zip_src is None:
            zip_src = z_cand
    # Check for uncompressed src/ and data/
    if (cdir / 'src').exists() and src_dir_src is None:
        src_dir_src = cdir / 'src'
    if (cdir / 'data').exists() and data_dir_src is None:
        data_dir_src = cdir / 'data'

# 2. Stage Source Code and Datasets
if (local_project / 'src').exists():
    print("✅ Local src/ directory already staged.")
elif zip_src and zip_src.name == 'chakramodel_data_scripts.zip':
    print(f"📦 Extracting code and data from {zip_src}...")
    with zipfile.ZipFile(zip_src, 'r') as zf:
        zf.extractall(local_project)
elif src_dir_src:
    print(f"📁 Copying source code from {src_dir_src}...")
    shutil.copytree(src_dir_src, local_project / 'src', dirs_exist_ok=True)
    if data_dir_src:
        print(f"📁 Copying dataset from {data_dir_src}...")
        shutil.copytree(data_dir_src, local_project / 'data', dirs_exist_ok=True)
else:
    raise FileNotFoundError("❌ CRITICAL: Could not locate 'src/' directory or 'chakramodel_data_scripts.zip' in Google Drive!")

# 3. Stage Model Weights
if weights_src:
    dest_w = local_weights / 'chakra_transformer_best.pth'
    if not dest_w.exists():
        print(f"📄 Staging ViT Segmenter weights from {weights_src} -> {dest_w}...")
        shutil.copy2(weights_src, dest_w)
    else:
        print("✅ ViT Segmenter weights already staged.")
else:
    raise FileNotFoundError("❌ CRITICAL: Could not locate 'chakra_transformer_best.pth' anywhere in Google Drive!")

if yolo_src:
    dest_y = local_weights / 'best.pt'
    if not dest_y.exists():
        print(f"📄 Staging YOLO detector weights from {yolo_src} -> {dest_y}...")
        shutil.copy2(yolo_src, dest_y)
    else:
        print("✅ YOLO detector weights already staged.")

print("\\n🚀 All assets successfully staged to local NVMe SSD storage!")\
"""
nb.cells.append(new_code_cell(cell_2_src))

cell_3_src = """\
# ==============================================================================
# STAGE 3: EXECUTE VERIFICATION VIA ABSOLUTE RESOLVED PATHS
# ==============================================================================
script_path = local_project / 'src' / 'verify_strict.py'
assert script_path.exists(), f"❌ Script not found at: {script_path}"

# Execute script with Python (the script now dynamically discovers its own root)
!python {script_path}\
"""
nb.cells.append(new_code_cell(cell_3_src))

with open('m:/chakramodel/Colab_GPU_Fast_Verify.ipynb', 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)
print("Notebook updated successfully.")
