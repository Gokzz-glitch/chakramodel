import os
import csv
import cv2
import numpy as np
from collections import defaultdict

# ==========================================================
# DEEP KAGGLE DATASET DIAGNOSTIC (A-to-Z)
# Run this FIRST, right after attaching your datasets.
# Goes beyond folder listing: opens sample images/masks,
# reports real dimensions/channels/value ranges, classifies
# each dataset as SEGMENTATION vs YOLO-DETECTION vs UNKNOWN,
# checks weight checkpoints, and previews any CSVs.
# ==========================================================

ROOT = "/kaggle/input"
IMG_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
WEIGHT_EXTS = (".pt", ".pth", ".onnx", ".engine")
MASK_TOKENS = ("mask", "ground", "gt", "label", "seg", "segmentation", "manual")
SAMPLE_N = 5
MAX_TREE_DEPTH = 6


def human_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def is_image(fname):
    return fname.lower().endswith(IMG_EXTS)


def is_weight(fname):
    return fname.lower().endswith(WEIGHT_EXTS)


def looks_like_mask_name(name):
    low = name.lower()
    return any(tok in low for tok in MASK_TOKENS)


def inspect_image(path):
    """Return (h, w, channels, dtype, min, max) or None on failure."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 2:
        h, w = img.shape
        c = 1
    else:
        h, w, c = img.shape
    return (h, w, c, str(img.dtype), int(img.min()), int(img.max()))


def inspect_weight_file(path):
    """Best-effort peek into a torch checkpoint without crashing the script."""
    try:
        import torch
        obj = torch.load(path, map_location="cpu", weights_only=True)
        if isinstance(obj, dict):
            keys = list(obj.keys())
            if "model" in obj and isinstance(obj["model"], dict):
                inner_keys = list(obj["model"].keys())
                return f"dict with top-level keys {keys[:5]}{'...' if len(keys) > 5 else ''}; " \
                       f"'model' sub-dict has {len(inner_keys)} tensor keys, e.g. {inner_keys[:3]}"
            return f"state_dict with {len(keys)} keys, e.g. {keys[:3]}"
        return f"loaded object of type {type(obj)}"
    except Exception as e:
        return f"could not introspect ({type(e).__name__}: {e})"


def preview_csv(path, n=SAMPLE_N):
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = []
            for i, row in enumerate(reader):
                if i >= n:
                    break
                rows.append(row)
        return rows
    except Exception as e:
        return [[f"<could not read: {e}>"]]


def classify_directory_set(files_in_tree):
    """
    Given all file paths under one top-level dataset, decide what kind
    of dataset it looks like: YOLO-detection, segmentation (img+mask),
    plain image collection, or unknown/mixed.
    """
    has_yolo_split = any(
        ("images" + os.sep + "train") in f or ("images" + os.sep + "val") in f
        for f in files_in_tree
    )
    has_label_txt = any(f.lower().endswith(".txt") and "label" in f.lower() for f in files_in_tree)
    has_masks = any(looks_like_mask_name(os.path.basename(f)) for f in files_in_tree if is_image(f))
    has_images = any(is_image(f) and not looks_like_mask_name(os.path.basename(f)) for f in files_in_tree)

    if has_yolo_split and has_label_txt:
        return "YOLO-DETECTION (images/train+val with .txt labels)"
    if has_yolo_split and not has_label_txt:
        return "YOLO-STYLE FOLDERS BUT NO LABEL FILES FOUND (incomplete for training)"
    if has_masks and has_images:
        return "SEGMENTATION (image + mask pairs, no bbox labels)"
    if has_images:
        return "PLAIN IMAGE COLLECTION (no masks, no labels)"
    return "UNKNOWN / NON-IMAGE DATA"


if not os.path.exists(ROOT):
    print(f"!! {ROOT} does not exist. Are you running this on Kaggle?")
else:
    top_entries = sorted(os.listdir(ROOT))
    print("=" * 72)
    print(f"TOP-LEVEL CONTENTS OF {ROOT}  ({len(top_entries)} entries)")
    print("=" * 72)
    for e in top_entries:
        full = os.path.join(ROOT, e)
        print(f"  [{'DIR ' if os.path.isdir(full) else 'FILE'}] {e}")

    # Walk everything once; group by the deepest "dataset-looking" folder
    # (Kaggle convention: /kaggle/input/datasets/<user>/<dataset-slug>/...
    #  or /kaggle/input/<dataset-slug>/...)
    dataset_groups = defaultdict(list)

    for dirpath, dirnames, filenames in os.walk(ROOT):
        for f in filenames:
            full_path = os.path.join(dirpath, f)
            rel = os.path.relpath(full_path, ROOT)
            parts = rel.split(os.sep)
            # group key = up to 3 path segments deep (covers both
            # /input/<slug>/... and /input/datasets/<user>/<slug>/...)
            if parts[0] == "datasets" and len(parts) > 2:
                group_key = os.sep.join(parts[:3])
            else:
                group_key = parts[0]
            dataset_groups[group_key].append(full_path)

    print("\n" + "=" * 72)
    print("PER-DATASET DEEP INSPECTION")
    print("=" * 72)

    for group_key in sorted(dataset_groups.keys()):
        files = dataset_groups[group_key]
        print(f"\n--- {group_key} ---")

        total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        print(f"  Files: {len(files)}  |  Size: {human_size(total_size)}")

        ext_counts = defaultdict(int)
        for f in files:
            ext = os.path.splitext(f)[1].lower() or "(no ext)"
            ext_counts[ext] += 1
        print(f"  Extensions: {dict(sorted(ext_counts.items(), key=lambda x: -x[1]))}")

        classification = classify_directory_set(files)
        print(f"  CLASSIFICATION: {classification}")

        # weight files: full introspection since these gate the whole pipeline
        weight_files = [f for f in files if is_weight(f)]
        for wf in weight_files:
            print(f"  WEIGHT: {wf}  ({human_size(os.path.getsize(wf))})")
            print(f"          -> {inspect_weight_file(wf)}")

        # image / mask content inspection (sample a few real files)
        image_files = [f for f in files if is_image(f) and not looks_like_mask_name(os.path.basename(f))]
        mask_files = [f for f in files if is_image(f) and looks_like_mask_name(os.path.basename(f))]

        if image_files:
            print(f"  Sample image inspection ({min(SAMPLE_N, len(image_files))} of {len(image_files)}):")
            for f in image_files[:SAMPLE_N]:
                info = inspect_image(f)
                if info:
                    h, w, c, dtype, mn, mx = info
                    print(f"    {os.path.basename(f):30s} {w}x{h}  ch={c}  dtype={dtype}  range=[{mn},{mx}]")
                else:
                    print(f"    {os.path.basename(f):30s} <failed to open>")

        if mask_files:
            print(f"  Sample mask inspection ({min(SAMPLE_N, len(mask_files))} of {len(mask_files)}):")
            for f in mask_files[:SAMPLE_N]:
                info = inspect_image(f)
                if info:
                    h, w, c, dtype, mn, mx = info
                    binary_hint = "binary-like (0/255 or 0/1)" if mx <= 255 and mn == 0 and (mx in (1, 255)) else "check manually"
                    print(f"    {os.path.basename(f):30s} {w}x{h}  ch={c}  dtype={dtype}  range=[{mn},{mx}]  {binary_hint}")
                else:
                    print(f"    {os.path.basename(f):30s} <failed to open>")

        # image/mask count parity check
        if image_files and mask_files:
            if len(image_files) != len(mask_files):
                print(f"  !! COUNT MISMATCH: {len(image_files)} images vs {len(mask_files)} masks -- some are likely unpaired")
            else:
                print(f"  Image/mask counts match: {len(image_files)} each")

        # CSV preview
        csv_files = [f for f in files if f.lower().endswith(".csv")]
        for cf in csv_files:
            print(f"  CSV: {cf}")
            for row in preview_csv(cf):
                print(f"    {row}")

    print("\n" + "=" * 72)
    print("PATHS COMMONLY HARDCODED IN CHAKRAMODEL SCRIPTS -- verify these")
    print("=" * 72)
    candidate_paths = [
        "/kaggle/input/chakramodel-weights",
        "/kaggle/input/datasets/gokulrocky/chakramodel-weights",
        "/kaggle/input/datasets/gokulraj324/chakramodel-weights",
        "/kaggle/input/datasets/gokulrocky/chakramodel-yolo-combo-dataset",
        "/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb",
        "/kaggle/working",
    ]
    for p in candidate_paths:
        exists = os.path.exists(p)
        print(f"  [{'OK  ' if exists else 'MISSING'}] {p}")

    print("\nDone. Use the CLASSIFICATION lines above to know which scripts can run as-is")
    print("(SEGMENTATION datasets need bbox generation before YOLO training; only a")
    print("YOLO-DETECTION dataset with images/train+val AND label .txt files is ready to train on).")
