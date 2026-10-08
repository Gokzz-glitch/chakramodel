import json, os, sys
nb_path = r'J:\My Drive\downloads\fork-of-fork-of-claudev7 (2).ipynb'
out_path = r'J:\My Drive\downloads\fork-of-fork-of-claudev7_final.ipynb'

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

dataset_logic = '''# ─────────────────────────────────────────────────────────────
# Dataset map — 15 datasets classified by type
# Update DATASET_MAP keys if Kaggle renames the mount points.
# ─────────────────────────────────────────────────────────────

DATASET_MAP = {
    # ── CODE & WEIGHTS ──────────────────────────────────────────
    "chakramodel-kaggle-code":       {"role": "code"},
    "finalmuruga-harae":             {"role": "weights"},
    "chakratransformer-weights":     {"role": "weights"},
    "final-om-evlautation-upload":   {"role": "eval_output"},
    "om-finalkaggle-upload":         {"role": "eval_output"},

    # ── IMAGE datasets (with GT masks) ──────────────────────────
    "endoscene-cvc300-polyp-raw-dataset": {
        "role": "image", "name": "CVC-300",
        "img_sub": "CVC-300/Original",
        "mask_sub": "CVC-300/Ground Truth",
    },
    "chakramodel-evaluation-datasets": {
        "role": "image_multi", "name": "Eval Pack",
        "sub_datasets": [
            {"name": "CVC-ClinicDB",  "img_sub": "cvc-clinicdb/images", "mask_sub": "cvc-clinicdb/masks"},
            {"name": "Kvasir-SEG",    "img_sub": "kvasir-seg/images",   "mask_sub": "kvasir-seg/masks"},
            {"name": "ETIS-LARIB",    "img_sub": "etis-larib/images",   "mask_sub": "etis-larib/masks"},
        ],
    },
    "hyperkvasir-dataset-first-half-and-and-ld-dataset": {
        "role": "image_multi", "name": "HyperKvasir+LD Images",
        "sub_datasets": [
            {"name": "HyperKvasir-Seg",
             "img_sub": "hyper-kvasir-segmented-images-part 3/segmented-images/images",
             "mask_sub": "hyper-kvasir-segmented-images-part 3/segmented-images/masks"},
        ],
    },
    "polypdb-polyp-raw": {
        "role": "image_multi", "name": "PolypDB",
        "sub_datasets": [
            {"name": "PolypDB/Simula/NBI",   "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/Simula/NBI/images",   "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/Simula/NBI/masks"},
            {"name": "PolypDB/Simula/WLI",   "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/Simula/WLI/images",   "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/Simula/WLI/masks"},
            {"name": "PolypDB/BKAI/WLI",     "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/WLI/images",     "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/WLI/masks"},
            {"name": "PolypDB/BKAI/NBI",     "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/NBI/images",     "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/NBI/masks"},
            {"name": "PolypDB/BKAI/BLI",     "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/BLI/images",     "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/BLI/masks"},
            {"name": "PolypDB/BKAI/FICE",    "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/FICE/images",    "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/FICE/masks"},
            {"name": "PolypDB/BKAI/LCI",     "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/LCI/images",     "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/LCI/masks"},
            {"name": "PolypDB/Karolinska",   "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/Karolinska/WLI/images","mask_sub":"PolypDB/PolypDB/PolypDB_center_wise/Karolinska/WLI/masks"},
            {"name": "PolypDB/FICE",         "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/FICE/images",       "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/FICE/masks"},
            {"name": "PolypDB/BLI",          "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/BLI/images",        "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/BLI/masks"},
            {"name": "PolypDB/NBI",          "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/NBI/images",        "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/NBI/masks"},
            {"name": "PolypDB/WLI",          "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/WLI/images",        "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/WLI/masks"},
            {"name": "PolypDB/LCI",          "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/LCI/images",        "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/LCI/masks"},
        ],
    },

    # ── VIDEO datasets ──────────────────────────────────────────
    "polypgen20021-video": {
        "role": "video_positive", "name": "PolypGen2021-Video",
        "note": "Polyps present — dice/IoU per frame",
    },
    "ldpolypvideowithoutpolyps": {
        "role": "video_negative", "name": "LDPolyp-NoPolyp",
        "note": "NO polyps — specificity check (false positive rate)",
    },
    "ldpolypvideopolyponly": {
        "role": "video_positive", "name": "LDPolyp-PolypOnly",
        "note": "Polyps only — sensitivity check (dice/IoU per frame)",
    },
    "hperkvasir-labeled-videos-part2-002": {
        "role": "video_positive", "name": "HyperKvasir-Video-P2B",
        "note": "HyperKvasir labeled video frames part 2 (B)",
    },
    "hyperkvasir-labeled-videos-part2-001": {
        "role": "video_positive", "name": "HyperKvasir-Video-P2A",
        "note": "HyperKvasir labeled video frames part 2 (A)",
    },
    "cvc-sample-video": {
        "role": "video_positive", "name": "CVC-Video",
        "note": "CVC sample video clips",
    },
}

# Resolve actual paths recursively for nested datasets on Kaggle
def resolve_dataset(ds_key, ds_cfg):
    import os
    for root, dirs, files in os.walk(INPUT_DIR):
        # Prevent digging too deep if not needed
        depth = root[len(INPUT_DIR):].count(os.sep)
        if depth > 2:
            continue
            
        base_name = os.path.basename(root)
        if ds_key in base_name or base_name in ds_key:
            return root
            
        # Try partial match
        if any(part in base_name for part in ds_key.split("-") if len(part) > 4):
            return root
    return None

RESOLVED = {}
print("\\nDataset resolution:")
for key, cfg in DATASET_MAP.items():
    path = resolve_dataset(key, cfg)
    RESOLVED[key] = path
    role = cfg["role"]
    status = "✓ found" if path else "✗ not found"
    print(f"  [{role:15s}] {key:50s} {status}")
'''

load_yolo_chakra = '''# ─────────────────────────────────────────────────────────────
# Load YOLO + ChakraNet Transformer
# ─────────────────────────────────────────────────────────────

# 1. Find & copy source code
CODE_PATH = None
import os, sys, shutil
for root, dirs, files in os.walk(INPUT_DIR):
    if "chakranet_segmenter.py" in files and os.path.basename(root) == "src":
        CODE_PATH = os.path.dirname(root)
        break

if CODE_PATH:
    shutil.copytree(CODE_PATH, f"{WORKING_DIR}/chakramodel", dirs_exist_ok=True)
    os.chdir(f"{WORKING_DIR}/chakramodel")
    if f"{WORKING_DIR}/chakramodel/src" not in sys.path:
        sys.path.insert(0, f"{WORKING_DIR}/chakramodel/src")
    print(f"Source code loaded from: {CODE_PATH}")
else:
    print("WARNING: chakranet_segmenter.py not found — segmenter will be mocked.")

# 2. Find weights
os.makedirs(f"{WORKING_DIR}/chakramodel/weights", exist_ok=True)

TRANSFORMER_PTH = None
YOLO_PT         = None

for root, dirs, files in os.walk(INPUT_DIR):
    for f in files:
        if f == "chakra_transformer_best.pth" and TRANSFORMER_PTH is None:
            TRANSFORMER_PTH = os.path.join(root, f)
        if f == "best.pt" and YOLO_PT is None:
            YOLO_PT = os.path.join(root, f)

if TRANSFORMER_PTH:
    shutil.copy(TRANSFORMER_PTH, f"{WORKING_DIR}/chakramodel/weights/chakra_transformer_best.pth")
    print(f"Transformer weights: {TRANSFORMER_PTH}")
else:
    print("WARNING: chakra_transformer_best.pth not found.")

if YOLO_PT:
    shutil.copy(YOLO_PT, f"{WORKING_DIR}/chakramodel/weights/best.pt")
    YOLO_PT_LOCAL = f"{WORKING_DIR}/chakramodel/weights/best.pt"
    print(f"YOLO weights: {YOLO_PT}")
else:
    print("WARNING: best.pt not found.")
    YOLO_PT_LOCAL = None

# 3. Load YOLO
YOLO_MODEL = None
if YOLO_PT_LOCAL:
    try:
        from ultralytics import YOLO
        YOLO_MODEL = YOLO(YOLO_PT_LOCAL)
        print("YOLO loaded ✓")
    except Exception as e:
        print(f"YOLO load failed: {e}")

# 4. Load ChakraNet segmenter
SEG_MODEL = None
try:
    from chakranet_segmenter import ChakraNet
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    SEG_MODEL = ChakraNet(
        device=device,
        img_size=(448, 448),
        weights_path=f"{WORKING_DIR}/chakramodel/weights/chakra_transformer_best.pth"
    )
    print(f"ChakraNet loaded ✓ (device={device}, img_size=(448,448))")
except Exception as e:
    print(f"Segmenter load failed: {e}")
    print("Will use fallback mock segmenter for testing.")
'''

eval_utils = '''# ─────────────────────────────────────────────────────────────
# Core evaluation utilities
# ─────────────────────────────────────────────────────────────

IMG_EXTS  = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
VID_EXTS  = {".mp4", ".avi", ".mov", ".mkv"}

def dice_iou(pred_bin, gt_bin):
    pred = pred_bin.astype(bool)
    gt   = gt_bin.astype(bool)
    inter = (pred & gt).sum()
    union = (pred | gt).sum()
    dice  = 2 * inter / (pred.sum() + gt.sum() + 1e-8)
    iou   = inter / (union + 1e-8)
    return float(dice), float(iou)


def run_yolo_segment(img_bgr, yolo_model, seg_model, fallback=True):
    """
    Run YOLO detect → crop → segment_roi().
    If YOLO finds nothing and fallback=True, uses full image as ROI.
    Returns (pred_mask_hw, n_detections, mode).
    """
    import numpy as np
    import cv2
    
    h, w = img_bgr.shape[:2]
    pred_mask = np.zeros((h, w), dtype=np.uint8)
    mode      = "none"

    # YOLO
    boxes = []
    if yolo_model is not None:
        try:
            res = yolo_model(img_bgr, verbose=False)
            if len(res) > 0 and res[0].boxes is not None and len(res[0].boxes) > 0:
                boxes = res[0].boxes.xyxy.cpu().numpy().tolist()
        except Exception:
            pass

    if len(boxes) == 0:
        if fallback:
            boxes = [[0, 0, w, h]]
            mode  = "fallback"
        else:
            return pred_mask, 0, "no_detection"
    else:
        mode = "yolo"

    if seg_model is None:
        # Mock: return empty mask (for testing pipeline without weights)
        return pred_mask, len(boxes), mode + "_mock"

    for box in boxes:
        x1, y1, x2, y2 = [int(v) for v in box]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        crop = img_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        try:
            result = seg_model.segment_roi(crop)
            if result is None:
                continue
            
            # UNPACK THE TUPLE CORRECTLY
            if isinstance(result, tuple):
                crop_mask = result[0]
            elif isinstance(result, dict):
                crop_mask = result.get("mask", result.get("seg_mask", None))
            elif isinstance(result, np.ndarray):
                crop_mask = result
            else:
                continue
                
            if crop_mask is None:
                continue
                
            crop_h, crop_w = y2 - y1, x2 - x1
            if crop_mask.shape != (crop_h, crop_w):
                crop_mask = cv2.resize(
                    crop_mask.astype(np.uint8), (crop_w, crop_h),
                    interpolation=cv2.INTER_NEAREST
                )
            pred_mask[y1:y2, x1:x2] = np.maximum(
                pred_mask[y1:y2, x1:x2], crop_mask.astype(np.uint8)
            )
        except Exception as ex:
            pass

    return pred_mask, len(boxes), mode


def find_mask_for_image(img_path, mask_root):
    """Find the GT mask file for a given image path."""
    import os
    from pathlib import Path
    
    stem = Path(img_path).stem
    for ext in [".png", ".jpg", ".bmp", ".tif"]:
        candidate = os.path.join(mask_root, stem + ext)
        if os.path.exists(candidate):
            return candidate
    # Search recursively
    for root, _, files in os.walk(mask_root):
        for f in files:
            if Path(f).stem == stem:
                return os.path.join(root, f)
    return None


def auto_find_img_mask_dirs(dataset_root):
    """
    Auto-detect images/ and masks/ subdirectories in a dataset root.
    Returns list of (img_dir, mask_dir, label) tuples.
    """
    import os
    from pathlib import Path
    
    found = []
    for root, dirs, files in os.walk(dataset_root):
        img_exts_here = sum(1 for f in files if Path(f).suffix.lower() in IMG_EXTS)
        if img_exts_here < 3:
            continue
        # Look for sibling mask directory
        parent = os.path.dirname(root)
        base   = os.path.basename(root).lower()
        if any(k in base for k in ("image", "img", "frame", "original", "photo")):
            mask_candidates = ["masks", "mask", "gt", "ground_truth",
                               "groundtruth", "annotation", "ann", "label"]
            for mc in mask_candidates:
                mp = os.path.join(parent, mc)
                if os.path.isdir(mp):
                    found.append((root, mp, os.path.basename(parent)))
                    break
    return found if found else []


print("Evaluation utilities loaded ✓")
'''

def make_cell(source):
    lines = source.split('\\n')
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [s + '\\n' for s in lines[:-1]] + [lines[-1]]
    }

new_cells = []
for c in nb['cells']:
    if c['cell_type'] != 'code':
        new_cells.append(c)
        continue
    
    src = ''.join(c['source'])
    
    if src.startswith("# =================================================================\\n# REPLACEMENT FOR CELL 3"):
        continue
        
    elif src.startswith("# ─────────────────────────────────────────────────────────────\\n# Dataset map — 15 datasets"):
        new_cells.append(make_cell(dataset_logic))
        
    elif src.startswith("# ─────────────────────────────────────────────────────────────\\n# Load YOLO + ChakraNet"):
        new_cells.append(make_cell(load_yolo_chakra))
        
    elif src.startswith("# ─────────────────────────────────────────────────────────────\\n# Core evaluation util"):
        new_cells.append(make_cell(eval_utils))
        
    else:
        new_cells.append(c)

nb['cells'] = new_cells

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print(f"Notebook generated and saved to {out_path}")
