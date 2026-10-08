import os
import glob
from pathlib import Path
import json
import numpy as np
from PIL import Image
import pandas as pd

BASE_DIR = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted")
PG_ROOT = BASE_DIR / "PolypGen2021_MultiCenterData_v3"

results = {}

print("=== STARTING POLYPGEN INSPECTION ===")

# 1. Top level check
results["pg_root_exists"] = PG_ROOT.exists()
if not PG_ROOT.exists():
    print(f"ERROR: {PG_ROOT} does not exist!")
    exit(1)

# List all items in PG_ROOT
root_items = [p.name for p in PG_ROOT.iterdir()]
results["root_items"] = root_items

# 2. Check centers C1 to C6
centers_info = {}
for c_num in range(1, 7):
    c_name = f"C{c_num}"
    c_dir = PG_ROOT / f"data_{c_name}"
    cInfo = {
        "exists": c_dir.exists(),
        "subdirs": [p.name for p in c_dir.iterdir() if p.is_dir()] if c_dir.exists() else []
    }
    if c_dir.exists():
        # Look for images, masks, bbox, bbox_image
        img_dir = c_dir / f"images_{c_name}"
        mask_dir = c_dir / f"masks_{c_name}"
        bbox_dir = c_dir / f"bbox_{c_name}"
        # notice C6 might be bbox_image_C6 or bbox_images_C6
        bbox_img_dirs = [d for d in cInfo["subdirs"] if "bbox_image" in d]
        
        cInfo["images_count"] = len(list(img_dir.glob("*.jpg"))) if img_dir.exists() else 0
        cInfo["masks_count"] = len(list(mask_dir.glob("*.jpg"))) if mask_dir.exists() else 0
        cInfo["bbox_count"] = len(list(bbox_dir.glob("*.txt"))) if bbox_dir.exists() else 0
        cInfo["bbox_img_dir_name"] = bbox_img_dirs[0] if bbox_img_dirs else None
        if bbox_img_dirs:
            cInfo["bbox_images_count"] = len(list((c_dir / bbox_img_dirs[0]).glob("*.jpg")))
        else:
            cInfo["bbox_images_count"] = 0
            
        # Sample naming check
        if img_dir.exists() and mask_dir.exists() and bbox_dir.exists():
            img_files = sorted(list(img_dir.glob("*.jpg")))
            if img_files:
                sample_img = img_files[0]
                stem = sample_img.stem
                cInfo["sample_img"] = sample_img.name
                # check corresponding mask
                mask_candidate1 = mask_dir / f"{stem}_mask.jpg"
                mask_candidate2 = mask_dir / f"{stem}.jpg"
                cInfo["mask_naming"] = "_mask.jpg" if mask_candidate1.exists() else (".jpg" if mask_candidate2.exists() else "UNKNOWN")
                
                # check corresponding bbox
                bbox_candidate1 = bbox_dir / f"{stem}_mask.txt"
                bbox_candidate2 = bbox_dir / f"{stem}.txt"
                cInfo["bbox_naming"] = "_mask.txt" if bbox_candidate1.exists() else (".txt" if bbox_candidate2.exists() else "UNKNOWN")
                
    centers_info[c_name] = cInfo

results["centers_info"] = centers_info
print("Centers overview complete.")

# 3. Deep parse bounding boxes in single frames (C1-C6)
bbox_stats = {
    "total_bbox_files": 0,
    "empty_bbox_files": 0,
    "non_empty_bbox_files": 0,
    "total_boxes": 0,
    "boxes_per_file_dist": {},
    "classes_found": set(),
    "coord_min": [float("inf"), float("inf"), float("inf"), float("inf")],
    "coord_max": [float("-inf"), float("-inf"), float("-inf"), float("-inf")],
    "invalid_boxes": 0, # xmin >= xmax or ymin >= ymax
    "out_of_bounds_boxes": 0,
    "sample_lines": []
}

# Also verify box vs mask on a sample of images per center
mask_iou_checks = []

for c_num in range(1, 7):
    c_name = f"C{c_num}"
    bbox_dir = PG_ROOT / f"data_{c_name}" / f"bbox_{c_name}"
    img_dir = PG_ROOT / f"data_{c_name}" / f"images_{c_name}"
    mask_dir = PG_ROOT / f"data_{c_name}" / f"masks_{c_name}"
    
    if not bbox_dir.exists():
        continue
        
    txt_files = sorted(list(bbox_dir.glob("*.txt")))
    for idx, txt_p in enumerate(txt_files):
        bbox_stats["total_bbox_files"] += 1
        with open(txt_p, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f if l.strip()]
            
        num_boxes = len(lines)
        bbox_stats["boxes_per_file_dist"][num_boxes] = bbox_stats["boxes_per_file_dist"].get(num_boxes, 0) + 1
        
        if num_boxes == 0:
            bbox_stats["empty_bbox_files"] += 1
        else:
            bbox_stats["non_empty_bbox_files"] += 1
            bbox_stats["total_boxes"] += num_boxes
            
        if len(bbox_stats["sample_lines"]) < 10 and lines:
            bbox_stats["sample_lines"].append(f"{txt_p.name}: {lines[0]}")
            
        # Parse lines
        parsed_boxes = []
        for line in lines:
            tokens = line.split()
            if len(tokens) == 5:
                cls_name = tokens[0]
                bbox_stats["classes_found"].add(cls_name)
                try:
                    coords = [float(t) for t in tokens[1:]]
                    for i in range(4):
                        bbox_stats["coord_min"][i] = min(bbox_stats["coord_min"][i], coords[i])
                        bbox_stats["coord_max"][i] = max(bbox_stats["coord_max"][i], coords[i])
                    xmin, ymin, xmax, ymax = coords
                    if xmin >= xmax or ymin >= ymax:
                        bbox_stats["invalid_boxes"] += 1
                    parsed_boxes.append((xmin, ymin, xmax, ymax))
                except ValueError:
                    bbox_stats["invalid_boxes"] += 1
            else:
                bbox_stats["invalid_boxes"] += 1
                
        # Check against image dimensions and mask for first 5 per center
        if idx < 5 and img_dir.exists() and mask_dir.exists() and parsed_boxes:
            # find corresponding image
            # Stem might be filename without _mask
            stem = txt_p.stem
            if stem.endswith("_mask"):
                img_stem = stem[:-5]
            else:
                img_stem = stem
            img_p = img_dir / f"{img_stem}.jpg"
            mask_p = mask_dir / f"{img_stem}_mask.jpg"
            if not mask_p.exists():
                mask_p = mask_dir / f"{img_stem}.jpg"
                
            if img_p.exists() and mask_p.exists():
                with Image.open(img_p) as im:
                    w, h = im.size
                with Image.open(mask_p) as m_im:
                    mw, mh = m_im.size
                    m_arr = np.array(m_im.convert("L"))
                
                # Check bounds
                for xmin, ymin, xmax, ymax in parsed_boxes:
                    if xmin < 0 or ymin < 0 or xmax > w or ymax > h:
                        bbox_stats["out_of_bounds_boxes"] += 1
                        
                # Check mask bounding box
                y_indices, x_indices = np.where(m_arr > 50)
                if len(x_indices) > 0:
                    m_xmin, m_xmax = x_indices.min(), x_indices.max()
                    m_ymin, m_ymax = y_indices.min(), y_indices.max()
                else:
                    m_xmin, m_xmax, m_ymin, m_ymax = 0, 0, 0, 0
                    
                mask_iou_checks.append({
                    "center": c_name,
                    "txt": txt_p.name,
                    "img_wh": (w, h),
                    "mask_wh": (mw, mh),
                    "bbox_txt": parsed_boxes[0],
                    "mask_extent": (int(m_xmin), int(m_ymin), int(m_xmax), int(m_ymax))
                })

bbox_stats["classes_found"] = list(bbox_stats["classes_found"])
results["bbox_stats_single_frames"] = bbox_stats
results["sample_mask_iou_checks"] = mask_iou_checks
print("Single frames bbox parsing complete.")

# 4. Deep dive on sequenceData
seq_root = PG_ROOT / "sequenceData"
results["sequence_data_exists"] = seq_root.exists()
seq_info = {
    "negative_sequences": {},
    "positive_sequences": {},
    "total_negative_images": 0,
    "total_positive_images": 0,
    "total_positive_masks": 0,
    "total_positive_bboxes": 0,
    "negative_bboxes_found": 0
}

if seq_root.exists():
    # Negative sequences
    neg_dir = seq_root / "negativeOnly"
    if neg_dir.exists():
        for seq_folder in sorted(neg_dir.iterdir()):
            if seq_folder.is_dir():
                jpgs = list(seq_folder.glob("*.jpg"))
                txts = list(seq_folder.glob("*.txt"))
                csvs = list(seq_folder.glob("*.csv"))
                seq_info["negative_sequences"][seq_folder.name] = {
                    "images": len(jpgs),
                    "txts": len(txts),
                    "csvs": len(csvs)
                }
                seq_info["total_negative_images"] += len(jpgs)
                seq_info["negative_bboxes_found"] += len(txts)
                
    # Positive sequences
    pos_dir = seq_root / "positive"
    if pos_dir.exists():
        for seq_folder in sorted(pos_dir.iterdir()):
            if seq_folder.is_dir():
                subdirs = [p.name for p in seq_folder.iterdir() if p.is_dir()]
                s_name = seq_folder.name
                
                img_sub = seq_folder / f"images_{s_name}"
                mask_sub = seq_folder / f"masks_{s_name}"
                bbox_sub = seq_folder / f"bbox_{s_name}"
                bbox_img_sub = seq_folder / f"bbox_image_{s_name}"
                
                imgs = len(list(img_sub.glob("*.jpg"))) if img_sub.exists() else 0
                masks = len(list(mask_sub.glob("*.jpg"))) if mask_sub.exists() else 0
                bboxes = len(list(bbox_sub.glob("*.txt"))) if bbox_sub.exists() else 0
                bbox_imgs = len(list(bbox_img_sub.glob("*.jpg"))) if bbox_img_sub.exists() else 0
                
                seq_info["positive_sequences"][s_name] = {
                    "subdirs": subdirs,
                    "images": imgs,
                    "masks": masks,
                    "bboxes": bboxes,
                    "bbox_images": bbox_imgs
                }
                seq_info["total_positive_images"] += imgs
                seq_info["total_positive_masks"] += masks
                seq_info["total_positive_bboxes"] += bboxes

# Sample check bbox in positive sequences
sample_seq_boxes = []
if seq_root.exists() and (seq_root / "positive").exists():
    for s_folder in sorted((seq_root / "positive").iterdir()):
        bbox_sub = s_folder / f"bbox_{s_folder.name}"
        if bbox_sub.exists():
            txts = list(bbox_sub.glob("*.txt"))
            for t in txts[:2]:
                with open(t, "r") as f:
                    content = f.read().strip()
                sample_seq_boxes.append(f"{s_folder.name}/{t.name}: {content}")
        if len(sample_seq_boxes) >= 6:
            break

seq_info["sample_seq_boxes"] = sample_seq_boxes
results["seq_info"] = seq_info
print("Sequence data parsing complete.")

# 5. Check imagesAll_positive
all_pos_dir = PG_ROOT / "imagesAll_positive"
results["imagesAll_positive"] = {
    "exists": all_pos_dir.exists(),
    "count": len(list(all_pos_dir.glob("*.jpg"))) if all_pos_dir.exists() else 0,
    "has_masks": len(list(all_pos_dir.glob("*mask*"))) if all_pos_dir.exists() else 0,
    "has_txt": len(list(all_pos_dir.glob("*.txt"))) if all_pos_dir.exists() else 0
}

# 6. Check dataDetails_PolypGen_SingleFrames
data_details_dir = PG_ROOT / "dataDetails_PolypGen_SingleFrames"
details_info = {}
if data_details_dir.exists():
    csv_files = sorted(list(data_details_dir.glob("*.csv")))
    for c_file in csv_files:
        df = pd.read_csv(c_file)
        details_info[c_file.name] = {
            "rows": len(df),
            "columns": list(df.columns),
            "head": df.head(2).to_dict(orient="records")
        }
results["dataDetails_SingleFrames"] = details_info

# 7. Check root metadata files
root_files_info = {}
for fname in ["fileStructure_all.txt", "fileStructure_directories.txt", "folderStructure", "license.txt", "readme.html", "readme.md"]:
    fp = PG_ROOT / fname
    if fp.exists():
        root_files_info[fname] = {
            "size_bytes": fp.stat().st_size,
            "lines_count": sum(1 for _ in open(fp, "r", encoding="utf-8", errors="ignore"))
        }
results["root_files_info"] = root_files_info

# Save full results json
out_path = Path(r"m:\chakramodel\.agents\teamwork_preview_explorer_pg_3\polypgen_inspection_results.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"=== INSPECTION COMPLETE. Saved to {out_path} ===")
