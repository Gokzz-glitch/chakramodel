import json, copy

# We'll build a fresh notebook based on v9 structure with all fixes baked in
cells = []

def md(source):
    return {"cell_type": "markdown", "id": "", "metadata": {}, "source": source if isinstance(source, list) else [source]}

def code(source, cell_id=""):
    return {"cell_type": "code", "execution_count": None, "id": cell_id,
            "metadata": {}, "outputs": [], "source": source if isinstance(source, list) else [source]}

# ── CELL 0: Title markdown ──────────────────────────────────────────────────
cells.append(md("""# ChakraModel — Full Universal Evaluation v10
## All Datasets · Image + Video · Leakage Guard · PolypGen Fixed · NBI Removed

**What's new in v10 (fixes from v9 run):**
- 🗑️ **Removed `PolypDB/BKAI/NBI`** — v9 run confirmed this subfolder doesn't exist in the attached dataset version (`BKAI` only has `FICE/BLI/WLI/LCI`). Removed to stop the noisy skip.
- 🔧 **Fixed PolypGen2021-Video skip** — evaluator now walks `data_C1..C6/images_C*/masks_C*` AND `sequenceData/positive/seqN/images_seqN/masks_seqN` as pre-extracted frame pairs. v9 was skipping this entirely because it only looked for `.avi/.mp4` files.
- 🛡️ **Leakage guard** — before evaluating CVC-ClinicDB / CVC-300 / ETIS-LARIB, any image whose basename appears in the YOLO training manifest (`chakramodel_yolo_combo_dataset/images/train`) is excluded. Dice numbers reflect genuine held-out performance only.
- 🔍 **Full-path mask discovery** — the `smart_join` path resolver now does a case-insensitive os.walk match, so casing differences in subfolder names (e.g. `NBI` vs `nbi`) never cause false skips.

**Carried over from v9:**
- ✅ `ChakraNet(img_size=(384,384))` — correct ViT resolution
- ✅ `segment_roi()` 4-tuple unpacking fixed
- ✅ `fallback=False` for video (no forced full-frame segmentation)
- ✅ `fallback=True` for image datasets with GT masks
- ✅ 15/15 dataset resolution via recursive `os.walk`
"""))

# ── CELL 1: Install ─────────────────────────────────────────────────────────
cells.append(code("""import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install",
    "ultralytics", "timm", "thop", "numpy", "opencv-python",
    "matplotlib", "pandas", "tabulate", "--quiet"], check=False)

# Load HF token from Kaggle Secrets if available
try:
    from kaggle_secrets import UserSecretsClient
    import os
    hf_token = UserSecretsClient().get_secret("HF_TOKEN")
    os.environ["HF_TOKEN"] = hf_token
    print("HF_TOKEN loaded from Kaggle Secrets ✓")
except Exception:
    print("HF_TOKEN not found in Kaggle Secrets — proceeding without (may see rate-limit warnings).")

print("Packages ready.")
"""))

# ── CELL 2: Env setup ────────────────────────────────────────────────────────
cells.append(code("""import os, sys, glob, cv2, json, time, shutil, traceback
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

WORKING_DIR = "/kaggle/working"
INPUT_DIR   = "/kaggle/input"
print(f"Working dir : {WORKING_DIR}")
print(f"Input dir   : {INPUT_DIR}")
print(f"Datasets attached: {len(os.listdir(INPUT_DIR))}")
for d in sorted(os.listdir(INPUT_DIR)):
    print(f"  /kaggle/input/{d}")
"""))

# ── CELL 3: Dataset map + resolution ─────────────────────────────────────────
cells.append(code("""# =================================================================
# DATASET MAP + RESOLUTION
# =================================================================
# PolypDB/BKAI/NBI REMOVED — v9 run confirmed BKAI only has
# [FICE, BLI, WLI, LCI]; NBI subfolder does not exist in this
# version of the dataset.
# =================================================================

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
        "img_sub": "CVC-300/images",
        "mask_sub": "CVC-300/masks",
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
            # PolypDB/BKAI/NBI REMOVED — doesn't exist in this dataset version
            {"name": "PolypDB/Simula/NBI",   "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/Simula/NBI/images",    "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/Simula/NBI/masks"},
            {"name": "PolypDB/Simula/WLI",   "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/Simula/WLI/images",    "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/Simula/WLI/masks"},
            {"name": "PolypDB/BKAI/WLI",     "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/WLI/images",      "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/WLI/masks"},
            {"name": "PolypDB/BKAI/BLI",     "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/BLI/images",      "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/BLI/masks"},
            {"name": "PolypDB/BKAI/FICE",    "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/FICE/images",     "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/FICE/masks"},
            {"name": "PolypDB/BKAI/LCI",     "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/LCI/images",      "mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/BKAI/LCI/masks"},
            {"name": "PolypDB/Karolinska",   "img_sub": "PolypDB/PolypDB/PolypDB_center_wise/Karolinska/WLI/images","mask_sub": "PolypDB/PolypDB/PolypDB_center_wise/Karolinska/WLI/masks"},
            {"name": "PolypDB/FICE",         "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/FICE/images",        "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/FICE/masks"},
            {"name": "PolypDB/BLI",          "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/BLI/images",         "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/BLI/masks"},
            {"name": "PolypDB/NBI",          "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/NBI/images",         "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/NBI/masks"},
            {"name": "PolypDB/WLI",          "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/WLI/images",         "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/WLI/masks"},
            {"name": "PolypDB/LCI",          "img_sub": "PolypDB/PolypDB/PolypDB_modality_wise/LCI/images",         "mask_sub": "PolypDB/PolypDB/PolypDB_modality_wise/LCI/masks"},
        ],
    },

    # ── VIDEO datasets ──────────────────────────────────────────
    "polypgen20021-video": {
        "role": "video_positive", "name": "PolypGen2021-Video",
        "note": "Pre-extracted frames in data_C1..C6 + sequenceData/positive/seqN",
    },
    "ldpolypvideowithoutpolyps": {
        "role": "video_negative", "name": "LDPolyp-NoPolyp",
        "note": "NO polyps — specificity check (false positive rate)",
    },
    "ldpolypvideopolyponly": {
        "role": "video_positive", "name": "LDPolyp-PolypOnly",
        "note": "Polyps only — sensitivity check (detection rate)",
    },
    "hperkvasir-labeled-videos-part2-002": {
        "role": "video_positive", "name": "HyperKvasir-Video-P2B",
    },
    "hyperkvasir-labeled-videos-part2-001": {
        "role": "video_positive", "name": "HyperKvasir-Video-P2A",
    },
    "cvc-sample-video": {
        "role": "video_positive", "name": "CVC-Video",
    },
}


def resolve_dataset(ds_key, ds_cfg):
    \"\"\"Exact-name recursive search, anywhere under INPUT_DIR.\"\"\"
    for root, dirs, files in os.walk(INPUT_DIR):
        if ds_key in dirs:
            return os.path.join(root, ds_key)
    return None


RESOLVED = {}
print("\\nDataset resolution:")
found_count = 0
for key, cfg in DATASET_MAP.items():
    path = resolve_dataset(key, cfg)
    RESOLVED[key] = path
    role = cfg["role"]
    status = "✓ found" if path else "✗ not found"
    if path:
        found_count += 1
    print(f"  [{role:15s}] {key:50s} {status}")

print(f"\\n{found_count}/{len(DATASET_MAP)} dataset keys resolved to a real folder.")

# ── Verify chakranet_segmenter.py class names across all copies ──────────────
import re as _re
print("\\nSearching all attached copies of chakranet_segmenter.py for class names...")
for root, dirs, files in os.walk(INPUT_DIR):
    if "chakranet_segmenter.py" in files:
        fpath = os.path.join(root, "chakranet_segmenter.py")
        with open(fpath, "r", errors="ignore") as f:
            src = f.read()
        classes = _re.findall(r"^class\\s+(\\w+)", src, _re.MULTILINE)
        print(f"  {fpath}")
        print(f"    classes defined: {classes}")
"""))

# ── CELL 4: Load models ───────────────────────────────────────────────────────
cells.append(code("""# ─────────────────────────────────────────────────────────────
# Load YOLO + ChakraNet (on separate GPUs if available)
# ─────────────────────────────────────────────────────────────
import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 1. Find & copy source code
CODE_PATH = None
for root, dirs, files in os.walk(INPUT_DIR):
    if "chakranet_segmenter.py" in files and os.path.basename(root) == "src":
        CODE_PATH = os.path.dirname(root)
        break

if CODE_PATH:
    shutil.copytree(CODE_PATH, f"{WORKING_DIR}/chakramodel", dirs_exist_ok=True)
    os.chdir(f"{WORKING_DIR}/chakramodel")
    src_path = f"{WORKING_DIR}/chakramodel/src"
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
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

# Prefer freshly-trained YOLO if it exists in /kaggle/working
fresh_best = "/kaggle/working/polyp_yolov8x_etis_fix/weights/best.pt"
if os.path.exists(fresh_best):
    YOLO_PT = fresh_best
    print(f"  Preferring freshly-trained YOLO weights: {fresh_best}")

if TRANSFORMER_PTH:
    shutil.copy(TRANSFORMER_PTH, f"{WORKING_DIR}/chakramodel/weights/chakra_transformer_best.pth")
    print(f"Transformer weights: {TRANSFORMER_PTH}")
else:
    print("WARNING: chakra_transformer_best.pth not found.")

YOLO_PT_LOCAL = None
if YOLO_PT:
    shutil.copy(YOLO_PT, f"{WORKING_DIR}/chakramodel/weights/best.pt")
    YOLO_PT_LOCAL = f"{WORKING_DIR}/chakramodel/weights/best.pt"
    print(f"YOLO weights: {YOLO_PT}")
else:
    print("WARNING: best.pt not found.")

# 3. Load YOLO (cuda:0)
YOLO_MODEL = None
if YOLO_PT_LOCAL:
    try:
        from ultralytics import YOLO
        YOLO_MODEL = YOLO(YOLO_PT_LOCAL)
        yolo_device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"YOLO loaded on {yolo_device} ✓")
    except Exception as e:
        print(f"YOLO load failed: {e}")

# 4. Load ChakraNet (cuda:1 if available, else cuda:0)
# img_size=(384, 384) used, since this checkpoint is vit_large_patch16_384
SEG_MODEL  = None
SEG_DEVICE = "cuda:1" if torch.cuda.is_available() and torch.cuda.device_count() > 1 else DEVICE
try:
    from chakranet_segmenter import ChakraNet
    SEG_MODEL = ChakraNet(
        device=SEG_DEVICE,
        img_size=(384, 384),
        weights_path=f"{WORKING_DIR}/chakramodel/weights/chakra_transformer_best.pth",
    )
    print(f"ChakraNet loaded on {SEG_DEVICE} ✓")
except Exception as e:
    print(f"ChakraNet load failed: {e}")
    traceback.print_exc()

# 5. Smoke test — segment_roi returns a 4-tuple: (binary_mask, contours, mean_conf, uncertainty_map)
if SEG_MODEL is not None:
    try:
        _dummy = np.zeros((100, 100, 3), dtype=np.uint8)
        _result = SEG_MODEL.segment_roi(_dummy)
        assert isinstance(_result, tuple) and len(_result) == 4, f"Expected 4-tuple, got {type(_result)}"
        _mask = _result[0]
        assert isinstance(_mask, np.ndarray), f"Expected ndarray mask, got {type(_mask)}"
        print(f"segment_roi() smoke test passed — tuple length: {len(_result)}, mask shape: {_mask.shape} ✓")
    except Exception as e:
        print(f"WARNING: smoke test failed: {e} — check ChakraNet API before proceeding")
"""))

# ── CELL 5: Core utilities + leakage guard ────────────────────────────────────
cells.append(code("""# ─────────────────────────────────────────────────────────────
# Core evaluation utilities
# ─────────────────────────────────────────────────────────────

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
VID_EXTS = {".mp4", ".avi", ".mov", ".mkv"}

# ── Leakage guard ─────────────────────────────────────────────
# Any image whose basename (no ext, no prefix) appears in the
# training manifest is excluded from evaluation, so Dice numbers
# only reflect truly held-out images.
TRAIN_IMAGES_DIR = "/kaggle/working/chakramodel_yolo_combo_dataset/images/train"

def load_train_manifest(train_images_dir):
    \"\"\"Return set of basenames (no ext, no prefix) used during training.\"\"\"
    if not train_images_dir or not os.path.isdir(train_images_dir):
        return set()
    used = set()
    for f in os.listdir(train_images_dir):
        stem = os.path.splitext(f)[0]
        used.add(stem)
        # strip <source>_ prefix that build_yolo_combo_dataset.py adds
        if "_" in stem:
            used.add(stem.split("_", 1)[1])
    return used

TRAIN_MANIFEST = load_train_manifest(TRAIN_IMAGES_DIR)
if TRAIN_MANIFEST:
    print(f"Leakage guard active — {len(TRAIN_MANIFEST)} training basenames loaded.")
else:
    print("Leakage guard inactive (training manifest not found — all images will be evaluated).")


# ── Case-insensitive smart_join ───────────────────────────────
def smart_join(base, *parts):
    \"\"\"
    Like os.path.join but each part is matched case-insensitively
    against the actual directory listing. Falls back to the literal
    path string if no match is found (caller does an isdir check).
    \"\"\"
    current = base
    for part in parts:
        if not os.path.isdir(current):
            current = os.path.join(current, part)
            continue
        lower_map = {d.lower(): d for d in os.listdir(current)}
        actual = lower_map.get(part.lower(), part)
        current = os.path.join(current, actual)
    return current


def dice_iou(pred_bin, gt_bin):
    pred  = pred_bin.astype(bool)
    gt    = gt_bin.astype(bool)
    inter = (pred & gt).sum()
    union = (pred | gt).sum()
    dice  = 2 * inter / (pred.sum() + gt.sum() + 1e-8)
    iou   = inter / (union + 1e-8)
    return float(dice), float(iou)


def find_mask_for_image(img_path, mask_dir):
    \"\"\"Find mask matching img basename (case-insensitive, any IMG_EXTS).\"\"\"
    stem = Path(img_path).stem.lower()
    for f in os.listdir(mask_dir):
        if Path(f).stem.lower() == stem and Path(f).suffix.lower() in IMG_EXTS:
            return os.path.join(mask_dir, f)
    return None


_SEGMENT_ERROR_LOGGED = False

def run_yolo_segment(img_bgr, yolo_model, seg_model, fallback=True):
    \"\"\"
    Run YOLO detect → crop → segment_roi().
    segment_roi() returns (binary_mask, contours, mean_conf, uncertainty_map).
    If YOLO finds nothing and fallback=True, uses full image as ROI.
    Returns (pred_mask_hw, n_detections, mode).
    \"\"\"
    global _SEGMENT_ERROR_LOGGED
    h, w = img_bgr.shape[:2]
    pred_mask = np.zeros((h, w), dtype=np.uint8)
    mode      = "none"

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
            # segment_roi returns (binary_mask, contours, mean_conf, uncertainty_map)
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
            if not _SEGMENT_ERROR_LOGGED:
                print(f"  [segment_roi error, further errors suppressed]: {ex}")
                _SEGMENT_ERROR_LOGGED = True

    return pred_mask, len(boxes), mode

print("Evaluation utilities loaded ✓")
"""))

# ── CELL 6: Image evaluator ───────────────────────────────────────────────────
cells.append(code("""# ─────────────────────────────────────────────────────────────
# Image dataset evaluator (with leakage guard)
# ─────────────────────────────────────────────────────────────

def evaluate_image_dataset(name, img_dir, mask_dir, max_images=500):
    \"\"\"
    Evaluate ChakraModel on an image segmentation dataset.
    Excludes training-set images via TRAIN_MANIFEST leakage guard.
    Returns a result dict.
    \"\"\"
    if not os.path.isdir(img_dir):
        return {"name": name, "status": "skip", "reason": f"img_dir not found: {img_dir}"}
    if not os.path.isdir(mask_dir):
        return {"name": name, "status": "skip", "reason": f"mask_dir not found: {mask_dir}"}

    all_img_files = sorted([
        f for f in os.listdir(img_dir)
        if Path(f).suffix.lower() in IMG_EXTS
    ])

    # Apply leakage guard: exclude images seen during training
    excluded = 0
    img_files = []
    for f in all_img_files:
        stem = Path(f).stem
        if stem in TRAIN_MANIFEST or (stem.split("_", 1)[-1] if "_" in stem else None) in TRAIN_MANIFEST:
            excluded += 1
        else:
            img_files.append(f)

    if excluded:
        print(f"    Leakage guard: excluded {excluded}/{len(all_img_files)} training images. "
              f"{len(img_files)} held-out images remain.")

    img_files = img_files[:max_images]
    if not img_files:
        return {"name": name, "status": "skip",
                "reason": "no held-out image files after leakage guard" if excluded else "no image files found"}

    dices, ious = [], []
    n_yolo, n_fallback, n_skip = 0, 0, 0
    per_image = []

    for fname in img_files:
        img_path  = os.path.join(img_dir, fname)
        mask_path = find_mask_for_image(img_path, mask_dir)
        if mask_path is None:
            n_skip += 1
            continue
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            n_skip += 1
            continue
        gt = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if gt is None:
            n_skip += 1
            continue

        pred_mask, n_boxes, mode = run_yolo_segment(
            img_bgr, YOLO_MODEL, SEG_MODEL, fallback=True
        )

        gt_bin   = (gt > 127).astype(np.uint8)
        pred_bin = (pred_mask > 127).astype(np.uint8)
        d, iou   = dice_iou(pred_bin, gt_bin)
        dices.append(d)
        ious.append(iou)
        if "fallback" in mode: n_fallback += 1
        elif "yolo" in mode:   n_yolo += 1
        per_image.append({"file": fname, "dice": round(d, 4), "iou": round(iou, 4), "mode": mode})

    if not dices:
        return {"name": name, "status": "no_valid_pairs"}

    yolo_pct = round(100 * n_yolo / len(dices)) if dices else 0
    return {
        "name":            name,
        "type":            "image",
        "status":          "done",
        "n_total":         len(all_img_files),
        "n_evaluated":     len(dices),
        "n_excluded_train": excluded,
        "n_skip":          n_skip,
        "dice_mean":       round(float(np.mean(dices)), 4),
        "dice_std":        round(float(np.std(dices)),  4),
        "dice_median":     round(float(np.median(dices)), 4),
        "iou_mean":        round(float(np.mean(ious)),  4),
        "iou_std":         round(float(np.std(ious)),   4),
        "yolo_detections": n_yolo,
        "fallback_used":   n_fallback,
        "yolo_detect_pct": yolo_pct,
        "per_image":       per_image,
    }

print("Image evaluator ready ✓")
"""))

# ── CELL 7: Video evaluator (PolypGen fixed) ──────────────────────────────────
cells.append(code("""# ─────────────────────────────────────────────────────────────
# Video / frame-sequence dataset evaluator
# ─────────────────────────────────────────────────────────────
# FIX (v10): PolypGen2021-Video only has pre-extracted image
# frames, NOT raw video files. This evaluator now handles:
#   a) data_C1..C6 / images_C* + masks_C* pairs
#   b) sequenceData/positive/seqN / images_seqN + masks_seqN
#   c) Raw video files (.avi, .mp4 etc.)
#   d) Negative-only datasets (.avi without masks → FPR)
# ─────────────────────────────────────────────────────────────

def _find_polypgen_frame_pairs(dataset_root):
    \"\"\"
    PolypGen-specific: find all (images_dir, masks_dir, label) pairs
    under data_C*/images_C* + masks_C*, and
    sequenceData/positive/seqN/images_seqN + masks_seqN.
    \"\"\"
    pairs = []
    v3_root = os.path.join(dataset_root, "PolypGen2021_MultiCenterData_v3")
    if not os.path.isdir(v3_root):
        return pairs

    # data_C1 ... data_C6
    for d in sorted(os.listdir(v3_root)):
        dc = os.path.join(v3_root, d)
        if not (d.startswith("data_C") and os.path.isdir(dc)):
            continue
        center = d.replace("data_", "")          # "C1", "C2" …
        img_dir  = smart_join(dc, f"images_{center}")
        mask_dir = smart_join(dc, f"masks_{center}")
        if os.path.isdir(img_dir) and os.path.isdir(mask_dir):
            pairs.append((img_dir, mask_dir, center))

    # sequenceData / positive / seqN / images_seqN + masks_seqN
    seq_pos = smart_join(v3_root, "sequenceData", "positive")
    if os.path.isdir(seq_pos):
        for seq in sorted(os.listdir(seq_pos)):
            seq_dir = os.path.join(seq_pos, seq)
            if not os.path.isdir(seq_dir):
                continue
            img_dir  = smart_join(seq_dir, f"images_{seq}")
            mask_dir = smart_join(seq_dir, f"masks_{seq}")
            if os.path.isdir(img_dir) and os.path.isdir(mask_dir):
                pairs.append((img_dir, mask_dir, seq))

    return pairs


def _auto_find_img_mask_dirs(dataset_root):
    \"\"\"
    Generic: scan the whole subtree for any folder literally named
    'images' or 'imgs' that has a sibling 'masks' or 'gt' folder.
    Returns list of (img_dir, mask_dir, label).
    \"\"\"
    MASK_NAMES = {"masks", "mask", "gt", "ground_truth", "labels"}
    IMAGE_NAMES = {"images", "imgs", "image"}
    pairs = []
    for dirpath, dirnames, _ in os.walk(dataset_root):
        lower_map = {d.lower(): d for d in dirnames}
        for img_key in IMAGE_NAMES:
            if img_key in lower_map:
                for mask_key in MASK_NAMES:
                    if mask_key in lower_map:
                        img_dir  = os.path.join(dirpath, lower_map[img_key])
                        mask_dir = os.path.join(dirpath, lower_map[mask_key])
                        label    = os.path.relpath(dirpath, dataset_root)
                        pairs.append((img_dir, mask_dir, label))
                        break
    return pairs


def evaluate_video_dataset(name, dataset_root, is_negative=False,
                            max_videos=20, max_frames_per_video=150, sample_every=5):
    if not os.path.isdir(dataset_root):
        return {"name": name, "status": "skip", "reason": f"root not found: {dataset_root}"}

    # ── A: PolypGen2021 pre-extracted frames ──────────────────
    polypgen_pairs = _find_polypgen_frame_pairs(dataset_root)
    if polypgen_pairs and not is_negative:
        print(f"    PolypGen mode: found {len(polypgen_pairs)} center/sequence splits")
        all_dices, all_ious = [], []
        for img_dir, mask_dir, label in polypgen_pairs:
            res = evaluate_image_dataset(f"{name}/{label}", img_dir, mask_dir,
                                          max_images=max_frames_per_video)
            if res.get("status") == "done":
                all_dices += [p["dice"] for p in res["per_image"]]
                all_ious  += [p["iou"]  for p in res["per_image"]]
                print(f"      {label}: dice={res['dice_mean']:.4f} n={res['n_evaluated']}")
        if all_dices:
            return {
                "name": name, "type": "video_frames", "status": "done",
                "mode": "polypgen_pre_extracted",
                "n_frame_sets": len(polypgen_pairs),
                "n_frames_total": len(all_dices),
                "dice_mean":   round(float(np.mean(all_dices)), 4),
                "dice_std":    round(float(np.std(all_dices)),  4),
                "dice_median": round(float(np.median(all_dices)), 4),
                "iou_mean":    round(float(np.mean(all_ious)),  4),
                "iou_std":     round(float(np.std(all_ious)),   4),
                "is_negative": False,
            }

    # ── B: Generic pre-extracted frames (auto-discover images+masks) ──
    generic_pairs = _auto_find_img_mask_dirs(dataset_root)
    if generic_pairs and not is_negative:
        print(f"    Generic frame mode: found {len(generic_pairs)} img+mask dir pairs")
        all_dices, all_ious = [], []
        for img_dir, mask_dir, label in generic_pairs:
            res = evaluate_image_dataset(f"{name}/{label}", img_dir, mask_dir,
                                          max_images=max_frames_per_video)
            if res.get("status") == "done":
                all_dices += [p["dice"] for p in res["per_image"]]
                all_ious  += [p["iou"]  for p in res["per_image"]]
        if all_dices:
            return {
                "name": name, "type": "video_frames", "status": "done",
                "mode": "generic_pre_extracted",
                "n_frames_total": len(all_dices),
                "dice_mean":   round(float(np.mean(all_dices)), 4),
                "dice_std":    round(float(np.std(all_dices)),  4),
                "dice_median": round(float(np.median(all_dices)), 4),
                "iou_mean":    round(float(np.mean(all_ious)),  4),
                "iou_std":     round(float(np.std(all_ious)),   4),
                "is_negative": False,
            }

    # ── C: Raw video files ────────────────────────────────────
    video_files = []
    for ext in VID_EXTS:
        video_files += glob.glob(os.path.join(dataset_root, f"**/*{ext}"), recursive=True)
    video_files = sorted(video_files)[:max_videos]

    if not video_files:
        return {"name": name, "status": "skip", "reason": "no video or image files found"}

    fp_frames, total_frames = 0, 0
    detection_count = 0
    n_videos_processed = 0

    for vid_path in video_files:
        cap = cv2.VideoCapture(vid_path)
        if not cap.isOpened():
            continue
        fid = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if fid % sample_every == 0:
                if total_frames >= max_frames_per_video * max_videos:
                    break
                total_frames += 1
                pred_mask, n_boxes, mode = run_yolo_segment(
                    frame, YOLO_MODEL, SEG_MODEL, fallback=False  # fallback=False for video
                )
                detected = (n_boxes > 0 or np.any(pred_mask > 0))
                if is_negative and detected:
                    fp_frames += 1
                elif not is_negative and detected:
                    detection_count += 1
            fid += 1
        cap.release()
        n_videos_processed += 1

    if total_frames == 0:
        return {"name": name, "status": "skip", "reason": "no frames extracted from videos"}

    if is_negative:
        fpr = fp_frames / total_frames
        return {
            "name": name, "type": "video", "status": "done",
            "is_negative": True,
            "n_videos":   n_videos_processed,
            "n_frames_sampled": total_frames,
            "fp_frames":  fp_frames,
            "false_positive_rate": round(fpr, 4),
            "specificity": round(1 - fpr, 4),
        }
    else:
        det_rate = detection_count / total_frames
        return {
            "name": name, "type": "video", "status": "done",
            "is_negative": False,
            "n_videos":   n_videos_processed,
            "n_frames_sampled": total_frames,
            "detection_count": detection_count,
            "detection_rate":  round(det_rate, 4),
        }

print("Video evaluator ready ✓")
"""))

# ── CELL 8: Path diagnostics ──────────────────────────────────────────────────
cells.append(code("""# ─────────────────────────────────────────────────────────────
# Path diagnostics — confirm actual folder structure before eval
# ─────────────────────────────────────────────────────────────

def _ls(path, depth=1):
    if not os.path.isdir(path):
        print(f"  NOT FOUND: {path}")
        return
    items = sorted(os.listdir(path))
    print(f"  Contents of {os.path.basename(path)}: {items}")

# CVC-300
cvc300_root = RESOLVED.get("endoscene-cvc300-polyp-raw-dataset")
if cvc300_root:
    _ls(cvc300_root)
    _ls(os.path.join(cvc300_root, "CVC-300"))

# PolypDB BKAI — confirm NBI truly absent
polypdb_root = RESOLVED.get("polypdb-polyp-raw")
if polypdb_root:
    bkai_path = smart_join(polypdb_root, "PolypDB", "PolypDB", "PolypDB_center_wise", "BKAI")
    print(f"\\nContents of PolypDB_center_wise/BKAI: {sorted(os.listdir(bkai_path)) if os.path.isdir(bkai_path) else 'NOT FOUND'}")

# PolypGen2021 frame pairs
pg_root = RESOLVED.get("polypgen20021-video")
if pg_root:
    pg_pairs = _find_polypgen_frame_pairs(pg_root)
    print(f"\\nPolypGen2021: {len(pg_pairs)} center/sequence splits found:")
    for img_dir, mask_dir, label in pg_pairs[:8]:
        n_imgs = len([f for f in os.listdir(img_dir) if Path(f).suffix.lower() in IMG_EXTS]) if os.path.isdir(img_dir) else 0
        n_masks = len([f for f in os.listdir(mask_dir) if Path(f).suffix.lower() in IMG_EXTS]) if os.path.isdir(mask_dir) else 0
        print(f"  {label}: {n_imgs} imgs / {n_masks} masks")
    if len(pg_pairs) > 8:
        print(f"  ... and {len(pg_pairs)-8} more")
"""))

# ── CELL 9: Run all evaluations ───────────────────────────────────────────────
cells.append(code("""# ─────────────────────────────────────────────────────────────
# Run ALL evaluations
# ─────────────────────────────────────────────────────────────

ALL_RESULTS = []

def run_image_ds(name, ds_key, img_sub, mask_sub):
    root = RESOLVED.get(ds_key)
    if not root:
        print(f"  SKIP {name}: dataset not attached")
        return
    img_dir  = smart_join(root, *img_sub.split("/"))
    mask_dir = smart_join(root, *mask_sub.split("/"))
    print(f"  Evaluating {name} ...")
    r = evaluate_image_dataset(name, img_dir, mask_dir)
    ALL_RESULTS.append(r)
    if r.get("status") == "done":
        excl_note = f" [{r.get('n_excluded_train', 0)} train excluded]" if r.get('n_excluded_train') else ""
        print(f"    dice={r['dice_mean']:.4f}±{r['dice_std']:.4f}  iou={r['iou_mean']:.4f}  "
              f"n={r['n_evaluated']}  YOLO={r.get('yolo_detect_pct','-')}%{excl_note}")
    else:
        print(f"    SKIP: {r.get('reason', '')}")

def run_video_ds(name, ds_key, is_neg=False):
    root = RESOLVED.get(ds_key)
    if not root:
        print(f"  SKIP {name}: dataset not attached")
        return
    print(f"  Evaluating {name} ({'negative control' if is_neg else 'positive'}) ...")
    r = evaluate_video_dataset(name, root, is_negative=is_neg)
    ALL_RESULTS.append(r)
    if r.get("status") == "done":
        if is_neg:
            print(f"    FPR={r['false_positive_rate']:.4f}  specificity={r['specificity']:.4f}")
        else:
            if "dice_mean" in r:
                print(f"    dice={r['dice_mean']:.4f}±{r.get('dice_std',0):.4f}  "
                      f"iou={r.get('iou_mean',0):.4f}  n={r.get('n_frames_total', '-')}")
            else:
                print(f"    detection_rate={r.get('detection_rate', 0):.4f}  (no GT masks)")
    else:
        print(f"    SKIP: {r.get('reason', '')}")

print("=" * 60)
print("IMAGE DATASETS")
print("=" * 60)

# CVC-300
run_image_ds("CVC-300", "endoscene-cvc300-polyp-raw-dataset",
             "CVC-300/images", "CVC-300/masks")

# CVC-ClinicDB, Kvasir-SEG, ETIS-LARIB
for sub in DATASET_MAP["chakramodel-evaluation-datasets"]["sub_datasets"]:
    run_image_ds(sub["name"], "chakramodel-evaluation-datasets",
                 sub["img_sub"], sub["mask_sub"])

# HyperKvasir-Seg
run_image_ds("HyperKvasir-Seg",
    "hyperkvasir-dataset-first-half-and-and-ld-dataset",
    "hyper-kvasir-segmented-images-part 3/segmented-images/images",
    "hyper-kvasir-segmented-images-part 3/segmented-images/masks")

# PolypDB (NBI sub-entry already removed from DATASET_MAP)
for sub in DATASET_MAP["polypdb-polyp-raw"]["sub_datasets"]:
    run_image_ds(sub["name"], "polypdb-polyp-raw", sub["img_sub"], sub["mask_sub"])

print("\\n" + "=" * 60)
print("VIDEO DATASETS")
print("=" * 60)

# PolypGen2021 — now uses pre-extracted frame pairs (PolypGen-specific logic)
run_video_ds("PolypGen2021-Video",    "polypgen20021-video",                 is_neg=False)
run_video_ds("LDPolyp-NoPolyp",      "ldpolypvideowithoutpolyps",           is_neg=True)
run_video_ds("LDPolyp-PolypOnly",    "ldpolypvideopolyponly",               is_neg=False)
run_video_ds("HyperKvasir-Video-P2A","hyperkvasir-labeled-videos-part2-001", is_neg=False)
run_video_ds("HyperKvasir-Video-P2B","hperkvasir-labeled-videos-part2-002",  is_neg=False)
run_video_ds("CVC-Video",            "cvc-sample-video",                    is_neg=False)

print("\\n✓ All evaluations complete.")
"""))

# ── CELL 10: Comparison table ─────────────────────────────────────────────────
cells.append(code("""# ─────────────────────────────────────────────────────────────
# Comprehensive comparison table (v10)
# ─────────────────────────────────────────────────────────────
import pandas as pd

rows = []
for r in ALL_RESULTS:
    if r.get("status") != "done":
        continue

    is_neg  = r.get("is_negative", False)
    ds_type = r.get("type", "unknown")

    if is_neg:
        rows.append({
            "Dataset":     r["name"],
            "Type":        "video-negative",
            "N Samples":   r.get("n_frames_sampled", "-"),
            "Dice Mean":   "N/A (negative ctrl)",
            "Dice Std":    "-",
            "IoU Mean":    "-",
            "Specificity": f"{r['specificity']:.4f}",
            "FP Rate":     f"{r['false_positive_rate']:.4f}",
            "YOLO Detect%":"-",
            "Train Excl.": "-",
            "Verdict":     "✓ PASS" if r["specificity"] >= 0.90 else "✗ FAIL",
        })
    elif "dice_mean" in r:
        yolo_pct = f"{r.get('yolo_detect_pct', '-')}%"
        verdict = ("✓ PASS" if r["dice_mean"] >= 0.60
                   else "~ WEAK" if r["dice_mean"] >= 0.30 else "✗ FAIL")
        rows.append({
            "Dataset":     r["name"],
            "Type":        ds_type,
            "N Samples":   r.get("n_evaluated", r.get("n_frames_total", "-")),
            "Dice Mean":   f"{r['dice_mean']:.4f}",
            "Dice Std":    f"{r['dice_std']:.4f}",
            "IoU Mean":    f"{r['iou_mean']:.4f}",
            "Specificity": "-",
            "FP Rate":     "-",
            "YOLO Detect%":yolo_pct,
            "Train Excl.": str(r.get("n_excluded_train", 0)),
            "Verdict":     verdict,
        })
    else:
        rows.append({
            "Dataset":     r["name"],
            "Type":        ds_type,
            "N Samples":   r.get("n_frames_sampled", "-"),
            "Dice Mean":   "-",
            "Dice Std":    "-",
            "IoU Mean":    "-",
            "Specificity": "-",
            "FP Rate":     "-",
            "YOLO Detect%":f"{100*r.get('detection_rate',0):.0f}%",
            "Train Excl.": "-",
            "Verdict":     "~ INFO (no GT masks)",
        })

df = pd.DataFrame(rows)
print("\\n" + "=" * 100)
print("CHAKRAMODEL v10 — FULL EVALUATION COMPARISON TABLE")
print("=" * 100)
print(df.to_string(index=False))
print("=" * 100)

image_rows = [r for r in ALL_RESULTS
              if r.get("status") == "done" and "dice_mean" in r and r.get("type") in ("image", "video_frames")]
if image_rows:
    all_dice = [r["dice_mean"] for r in image_rows]
    print(f"\\nImage/frame datasets summary:")
    print(f"  Overall mean Dice : {np.mean(all_dice):.4f}")
    print(f"  Best dataset      : {max(image_rows, key=lambda x: x['dice_mean'])['name']} ({max(all_dice):.4f})")
    print(f"  Worst dataset     : {min(image_rows, key=lambda x: x['dice_mean'])['name']} ({min(all_dice):.4f})")
    total_excl = sum(r.get("n_excluded_train", 0) for r in image_rows)
    if total_excl:
        print(f"  Total images excluded (leakage guard): {total_excl}")

df.to_csv(f"{WORKING_DIR}/comparison_table_v10.csv", index=False)
print(f"\\nSaved: {WORKING_DIR}/comparison_table_v10.csv")
"""))

# ── CELL 11: Bar chart ────────────────────────────────────────────────────────
cells.append(code("""import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

image_rows = [r for r in ALL_RESULTS
              if r.get("status") == "done" and "dice_mean" in r]

if image_rows:
    names  = [r["name"].replace("PolypDB/", "").replace("HyperKvasir-", "HK-") for r in image_rows]
    means  = [r["dice_mean"] for r in image_rows]
    stds   = [r["dice_std"]  for r in image_rows]
    colors = ["#2ecc71" if m >= 0.60 else "#e67e22" if m >= 0.30 else "#e74c3c" for m in means]

    fig, ax = plt.subplots(figsize=(max(14, len(names) * 0.75), 6))
    ax.bar(names, means, yerr=stds, capsize=4,
           color=colors, alpha=0.85, edgecolor="white", linewidth=0.5)
    ax.axhline(0.60, color="#2ecc71", linestyle="--", linewidth=1.2, label="Good threshold (0.60)")
    ax.axhline(0.30, color="#e74c3c", linestyle="--", linewidth=1.2, label="Poor threshold (0.30)")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Dice Score")
    ax.set_title("ChakraModel v10 — Dice Score per Dataset", fontsize=13, fontweight="bold")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    p1 = mpatches.Patch(color="#2ecc71", alpha=0.85, label="≥0.60 PASS")
    p2 = mpatches.Patch(color="#e67e22", alpha=0.85, label="0.30-0.60 WEAK")
    p3 = mpatches.Patch(color="#e74c3c", alpha=0.85, label="<0.30 FAIL")
    ax.legend(handles=[p1, p2, p3], loc="upper right", fontsize=9)
    plt.tight_layout()
    plt.savefig(f"{WORKING_DIR}/dice_comparison_v10.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("Plot saved.")
"""))

# ── CELL 12: Save report ──────────────────────────────────────────────────────
cells.append(code("""import json as _json

report = {
    "version":              "v10",
    "timestamp":            time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    "leakage_guard_active": bool(TRAIN_MANIFEST),
    "n_train_basenames":    len(TRAIN_MANIFEST),
    "n_datasets_evaluated": len([r for r in ALL_RESULTS if r.get("status") == "done"]),
    "results":              ALL_RESULTS,
}

out = f"{WORKING_DIR}/combined_report_v10.json"
with open(out, "w") as f:
    _json.dump(report, f, indent=2, default=str)
print(f"Full report saved: {out}")

os.chdir(WORKING_DIR)
os.system("zip -r chakra_v10_artifacts.zip combined_report_v10.json comparison_table_v10.csv dice_comparison_v10.png > /dev/null")
print("Done! Download chakra_v10_artifacts.zip from the output panel.")
"""))

# ── Build the notebook JSON ───────────────────────────────────────────────────
import string, random
def rand_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

for i, c in enumerate(cells):
    c["id"] = rand_id()

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.0"},
    },
    "cells": cells,
}

out_path = r'J:\My Drive\downloads\chakramodel_v10_eval.ipynb'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"Notebook saved: {out_path}")
print(f"Total cells: {len(cells)}")
