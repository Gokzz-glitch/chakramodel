import os
import glob
from pathlib import Path
import json
import numpy as np
from PIL import Image
import pandas as pd

BASE_DIR = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted")
PG_ROOT = BASE_DIR / "PolypGen2021_MultiCenterData_v3"

results2 = {}

print("=== DEEP DIVE 2: EDGE CASES AND DISCREPANCIES ===")

# --- Question A: C3 missing 64 bbox files ---
c3_dir = PG_ROOT / "data_C3"
c3_imgs = sorted(list((c3_dir / "images_C3").glob("*.jpg")))
c3_masks = sorted(list((c3_dir / "masks_C3").glob("*.jpg")))
c3_bboxes = sorted(list((c3_dir / "bbox_C3").glob("*.txt")))

c3_img_stems = set(p.stem for p in c3_imgs)
c3_bbox_stems = set(p.stem for p in c3_bboxes)
missing_in_bbox = c3_img_stems - c3_bbox_stems

results2["c3_missing_bbox_count"] = len(missing_in_bbox)
results2["c3_missing_bbox_stems"] = sorted(list(missing_in_bbox))[:15]

c3_missing_mask_stats = []
for stem in sorted(list(missing_in_bbox)):
    m_path = c3_dir / "masks_C3" / f"{stem}_mask.jpg"
    if not m_path.exists():
        m_path = c3_dir / "masks_C3" / f"{stem}.jpg"
    if not m_path.exists():
        # Handle trailing underscore or variations
        candidates = list((c3_dir / "masks_C3").glob(f"{stem.rstrip('_')}*"))
        if candidates:
            m_path = candidates[0]

    if m_path.exists():
        m_arr = np.array(Image.open(m_path).convert("L"))
        nonzeros = int(np.sum(m_arr > 50))
        c3_missing_mask_stats.append({
            "stem": stem,
            "mask_file": m_path.name,
            "mask_exists": True,
            "nonzeros": nonzeros,
            "mask_shape": list(m_arr.shape)
        })
    else:
        c3_missing_mask_stats.append({
            "stem": stem,
            "mask_exists": False,
            "nonzeros": 0
        })

results2["c3_missing_mask_analysis"] = {
    "total_missing": len(c3_missing_mask_stats),
    "all_masks_exist": all(x["mask_exists"] for x in c3_missing_mask_stats),
    "empty_masks_count": sum(1 for x in c3_missing_mask_stats if x.get("nonzeros", 0) == 0),
    "positive_masks_count": sum(1 for x in c3_missing_mask_stats if x.get("nonzeros", 0) > 0)
}

# --- Question B: C1 bbox_images has 257 vs 256 ---
c1_dir = PG_ROOT / "data_C1"
results2["c1_orphan_bbox_image"] = "957OLCV1_100H0002_mask_bbox.jpg"

# --- Question C: Sequence positive bounding boxes deep dive ---
pos_seq_dir = PG_ROOT / "sequenceData" / "positive"
seq_bbox_stats = {
    "total_files": 0,
    "empty_files": 0,
    "non_empty_files": 0,
    "total_boxes": 0,
    "naming_patterns": set(),
    "boxes_per_file_dist": {},
    "classes": set(),
    "coord_min": [float("inf"), float("inf"), float("inf"), float("inf")],
    "coord_max": [float("-inf"), float("-inf"), float("-inf"), float("-inf")],
    "invalid_boxes": 0,
    "sample_files": []
}

for s_dir in sorted(pos_seq_dir.iterdir()):
    if not s_dir.is_dir():
        continue
    s_name = s_dir.name
    bbox_sub = s_dir / f"bbox_{s_name}"
    img_sub = s_dir / f"images_{s_name}"
    if not bbox_sub.exists():
        continue
    for txt_p in sorted(list(bbox_sub.glob("*.txt"))):
        seq_bbox_stats["total_files"] += 1
        img_candidate = img_sub / f"{txt_p.stem}.jpg"
        if img_candidate.exists():
            seq_bbox_stats["naming_patterns"].add("same_stem_as_img")
        else:
            seq_bbox_stats["naming_patterns"].add(f"other: {txt_p.name}")
            
        with open(txt_p, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f if l.strip()]
            
        n_b = len(lines)
        seq_bbox_stats["boxes_per_file_dist"][n_b] = seq_bbox_stats["boxes_per_file_dist"].get(n_b, 0) + 1
        if n_b == 0:
            seq_bbox_stats["empty_files"] += 1
        else:
            seq_bbox_stats["non_empty_files"] += 1
            seq_bbox_stats["total_boxes"] += n_b
            
        for l in lines:
            parts = l.split()
            if len(parts) == 5:
                seq_bbox_stats["classes"].add(parts[0])
                try:
                    c = [float(x) for x in parts[1:]]
                    for i in range(4):
                        seq_bbox_stats["coord_min"][i] = min(seq_bbox_stats["coord_min"][i], c[i])
                        seq_bbox_stats["coord_max"][i] = max(seq_bbox_stats["coord_max"][i], c[i])
                    if c[0] >= c[2] or c[1] >= c[3]:
                        seq_bbox_stats["invalid_boxes"] += 1
                except ValueError:
                    seq_bbox_stats["invalid_boxes"] += 1
            else:
                seq_bbox_stats["invalid_boxes"] += 1

seq_bbox_stats["naming_patterns"] = list(seq_bbox_stats["naming_patterns"])
seq_bbox_stats["classes"] = list(seq_bbox_stats["classes"])
results2["seq_bbox_stats"] = seq_bbox_stats

# --- Question D: Why are there empty bbox files? Check mask area ---
empty_bbox_mask_check = []
# check a sample of empty bbox files in single frames and sequences
for c_num in range(1, 7):
    c_name = f"C{c_num}"
    b_dir = PG_ROOT / f"data_{c_name}" / f"bbox_{c_name}"
    m_dir = PG_ROOT / f"data_{c_name}" / f"masks_{c_name}"
    if not b_dir.exists():
        continue
    for txt_p in b_dir.glob("*.txt"):
        if txt_p.stat().st_size == 0 or open(txt_p, "r").read().strip() == "":
            stem = txt_p.stem
            if stem.endswith("_mask"):
                m_stem = stem
            else:
                m_stem = f"{stem}_mask"
            m_path = m_dir / f"{m_stem}.jpg"
            if not m_path.exists():
                m_path = m_dir / f"{stem}.jpg"
            if m_path.exists():
                m_arr = np.array(Image.open(m_path).convert("L"))
                nonzeros = int(np.sum(m_arr > 50))
                empty_bbox_mask_check.append({
                    "center": c_name,
                    "txt": txt_p.name,
                    "mask_nonzeros": nonzeros
                })
            if len(empty_bbox_mask_check) >= 20:
                break
    if len(empty_bbox_mask_check) >= 20:
        break
results2["empty_bbox_mask_check"] = empty_bbox_mask_check

# Check empty bbox in sequences as well
seq_empty_check = []
for s_dir in sorted(pos_seq_dir.iterdir()):
    if not s_dir.is_dir():
        continue
    b_sub = s_dir / f"bbox_{s_dir.name}"
    m_sub = s_dir / f"masks_{s_dir.name}"
    for txt_p in b_sub.glob("*.txt"):
        if txt_p.stat().st_size == 0 or open(txt_p, "r").read().strip() == "":
            # find mask
            # in sequences, how are masks named?
            m_cand1 = m_sub / f"{txt_p.stem}_mask.jpg"
            m_cand2 = m_sub / f"{txt_p.stem}.jpg"
            m_p = m_cand1 if m_cand1.exists() else (m_cand2 if m_cand2.exists() else None)
            if m_p and m_p.exists():
                m_arr = np.array(Image.open(m_p).convert("L"))
                nonzeros = int(np.sum(m_arr > 50))
                seq_empty_check.append({
                    "seq": s_dir.name,
                    "txt": txt_p.name,
                    "mask_nonzeros": nonzeros
                })
            if len(seq_empty_check) >= 20:
                break
    if len(seq_empty_check) >= 20:
        break
results2["seq_empty_check"] = seq_empty_check

# --- Question E: Check Concatenated.zip ---
zip_p = PG_ROOT / "PolypGen2021_MultiCenterData_Concatenated.zip"
results2["concatenated_zip"] = {
    "exists": zip_p.exists(),
    "size_bytes": zip_p.stat().st_size if zip_p.exists() else 0
}

# --- Question G: Check imagesAll_positive contents vs C1-C6 & sequences ---
all_pos_dir = PG_ROOT / "imagesAll_positive"
all_pos_files = set(p.name for p in all_pos_dir.glob("*.jpg"))
c_all_imgs = set()
for c_num in range(1, 7):
    c_img_dir = PG_ROOT / f"data_C{c_num}" / f"images_C{c_num}"
    if c_img_dir.exists():
        for p in c_img_dir.glob("*.jpg"):
            c_all_imgs.add(p.name)

seq_all_imgs = set()
for s_dir in (PG_ROOT / "sequenceData" / "positive").iterdir():
    s_img_dir = s_dir / f"images_{s_dir.name}"
    if s_img_dir.exists():
        for p in s_img_dir.glob("*.jpg"):
            seq_all_imgs.add(p.name)

results2["imagesAll_positive_verification"] = {
    "total_in_imagesAll": len(all_pos_files),
    "total_in_C1_C6": len(c_all_imgs),
    "total_in_seq_positive": len(seq_all_imgs),
    "sum_c_and_seq": len(c_all_imgs) + len(seq_all_imgs),
    "c_overlap": len(all_pos_files.intersection(c_all_imgs)),
    "seq_overlap": len(all_pos_files.intersection(seq_all_imgs)),
    "unaccounted": len(all_pos_files - c_all_imgs - seq_all_imgs)
}

# Save results2
out_path2 = Path(r"m:\chakramodel\.agents\teamwork_preview_explorer_pg_3\polypgen_deep_dive_results.json")
with open(out_path2, "w", encoding="utf-8") as f:
    json.dump(results2, f, indent=2)

print(f"=== DEEP DIVE COMPLETE. Saved to {out_path2} ===")
