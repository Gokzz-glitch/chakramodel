import json
from pathlib import Path
from collections import Counter
import cv2
import numpy as np

DATASET_ROOT = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")

def run_details():
    print("=== INVESTIGATING SEQUENCE DATA AND C3 MASKS ===", flush=True)

    # 1. Investigate seq2, seq7, seq8 masks
    pos_dir = DATASET_ROOT / "sequenceData" / "positive"
    for s_name in ["seq2", "seq7", "seq8"]:
        p = pos_dir / s_name
        mask_p = p / f"masks_{s_name}"
        img_p = p / f"images_{s_name}"
        mask_files = sorted([f.name for f in mask_p.iterdir() if f.is_file() and not f.name.startswith(".")])
        img_files = sorted([f.name for f in img_p.iterdir() if f.is_file() and not f.name.startswith(".")])
        print(f"\n--- {s_name} (Images: {len(img_files)}, Masks: {len(mask_files)}) ---")
        print(f"Sample images (first 5): {img_files[:5]}")
        print(f"Sample masks (first 10): {mask_files[:10]}")
        
        # Check patterns in mask filenames
        mask_extensions = Counter(f.split(".")[-1] for f in mask_files)
        print(f"Mask extensions: {dict(mask_extensions)}")
        
        # Are there two files per image? E.g. image_001.jpg and image_001_mask.jpg or something else?
        stems = [f.replace("_mask", "").split(".")[0] for f in mask_files]
        stem_counts = Counter(stems)
        most_common = stem_counts.most_common(5)
        print(f"Most common mask stems: {most_common}")
        
        # Show all masks for the first image
        first_img_stem = img_files[0].split(".")[0]
        matching_masks = [m for m in mask_files if first_img_stem in m]
        print(f"Masks matching first image '{first_img_stem}': {matching_masks}")

    # 2. Check 64 images in C3 without bbox: are masks all-zero?
    print("\n--- 2. Checking 64 C3 images without bbox ---", flush=True)
    c3_img_p = DATASET_ROOT / "data_C3" / "images_C3"
    c3_mask_p = DATASET_ROOT / "data_C3" / "masks_C3"
    c3_bbox_p = DATASET_ROOT / "data_C3" / "bbox_C3"
    c3_bboxes = {f.stem.replace("_mask", "") for f in c3_bbox_p.iterdir() if f.is_file() and not f.name.startswith(".")}
    c3_imgs = {f.stem: f for f in c3_img_p.iterdir() if f.is_file() and not f.name.startswith(".")}
    
    no_bbox_stems = sorted(list(set(c3_imgs.keys()) - c3_bboxes))
    print(f"Total C3 images without bbox: {len(no_bbox_stems)}")
    
    empty_mask_count = 0
    non_empty_mask_count = 0
    missing_mask_count = 0
    non_empty_samples = []
    
    for stem in no_bbox_stems:
        # mask name might be stem_mask.jpg or handle trailing underscore
        mask_name = f"{stem}_mask.jpg"
        if stem == "C3_EndoCV2021_00489_":
            mask_name = "C3_EndoCV2021_00489_mask.jpg"
        mask_file = c3_mask_p / mask_name
        if not mask_file.exists():
            missing_mask_count += 1
            continue
        arr = cv2.imread(str(mask_file), cv2.IMREAD_GRAYSCALE)
        if arr is None:
            continue
        max_val = np.max(arr)
        if max_val == 0:
            empty_mask_count += 1
        else:
            non_empty_mask_count += 1
            non_empty_samples.append((stem, max_val, np.sum(arr > 127)))
            
    print(f"For 64 C3 images without bbox:")
    print(f"  Empty masks (max val == 0): {empty_mask_count}")
    print(f"  Non-empty masks (max val > 0): {non_empty_mask_count}")
    print(f"  Missing masks: {missing_mask_count}")
    if non_empty_samples:
        print(f"  Sample non-empty masks: {non_empty_samples[:5]}")

    # 3. Inspect sequenceData negativeOnly
    print("\n--- 3. Inspecting sequenceData negativeOnly ---", flush=True)
    neg_dir = DATASET_ROOT / "sequenceData" / "negativeOnly"
    neg_seqs = sorted([d for d in neg_dir.iterdir() if d.is_dir()])
    print(f"Total negative sequences: {len(neg_seqs)}")
    has_subfolders = []
    has_masks = []
    for ns in neg_seqs:
        sub_items = list(ns.iterdir())
        sub_dirs = [d.name for d in sub_items if d.is_dir()]
        files = [f.name for f in sub_items if f.is_file()]
        if sub_dirs:
            has_subfolders.append((ns.name, sub_dirs))
        if any("mask" in f.lower() for f in files):
            has_masks.append(ns.name)
    print(f"Negative sequences with subfolders: {has_subfolders}")
    print(f"Negative sequences with mask files: {has_masks}")
    print(f"Sample sequence {neg_seqs[0].name}: {len(list(neg_seqs[0].iterdir()))} files, sample: {[f.name for f in list(neg_seqs[0].iterdir())[:3]]}")

    # 4. Check dataDetails CSVs against actual file lists
    print("\n--- 4. Checking dataDetails CSVs ---", flush=True)
    csv_dir = DATASET_ROOT / "dataDetails_PolypGen_SingleFrames"
    if csv_dir.exists():
        for csv_f in sorted(csv_dir.glob("*.csv")):
            with open(csv_f, "r") as fp:
                lines = [l.strip() for l in fp if l.strip()]
            header = lines[0]
            data_rows = lines[1:]
            print(f"  {csv_f.name}: {len(data_rows)} rows (header: {header})")

if __name__ == "__main__":
    run_details()
