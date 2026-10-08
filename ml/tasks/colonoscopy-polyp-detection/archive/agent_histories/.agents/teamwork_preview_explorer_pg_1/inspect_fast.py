import os
import csv
import json
import zipfile
from collections import Counter
from pathlib import Path

DATASET_ROOT = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted")
POLYPGEN_DIR = DATASET_ROOT / "PolypGen2021_MultiCenterData_v3"
OUT_FILE = Path(r"m:\chakramodel\.agents\teamwork_preview_explorer_pg_1\fast_stats.json")

def get_dir_file_counts(dir_path):
    if not dir_path.exists():
        return None
    files = []
    subdirs = []
    for entry in os.scandir(dir_path):
        if entry.is_file():
            files.append(entry.name)
        elif entry.is_dir():
            subdirs.append(entry.name)
    exts = Counter(os.path.splitext(f)[1].lower() for f in files)
    return {
        "file_count": len(files),
        "extensions": dict(exts),
        "subdirs": subdirs,
        "sample_files": files[:3],
        "hidden_files": [f for f in files if f.startswith('.')]
    }

def run_inspection():
    results = {}

    # 1. Extracted Root
    results["extracted_root"] = {}
    for entry in os.scandir(DATASET_ROOT):
        results["extracted_root"][entry.name] = {
            "is_dir": entry.is_dir(),
            "size": entry.stat().st_size if entry.is_file() else None
        }

    # 2. PolypGen root files
    results["polypgen_root_files"] = {}
    for entry in os.scandir(POLYPGEN_DIR):
        if entry.is_file():
            results["polypgen_root_files"][entry.name] = entry.stat().st_size
        elif entry.is_dir():
            results["polypgen_root_files"][f"[DIR] {entry.name}"] = None

    # 3. Codes directory
    codes_dir = POLYPGEN_DIR / "codes"
    results["codes"] = {}
    if codes_dir.exists():
        for root, dirs, files in os.walk(codes_dir):
            rel = os.path.relpath(root, codes_dir)
            results["codes"][rel] = {
                "dirs": dirs,
                "files": files
            }

    # 4. Data details (CSV files)
    details_dir = POLYPGEN_DIR / "dataDetails_PolypGen_SingleFrames"
    results["dataDetails"] = {}
    if details_dir.exists():
        for f in details_dir.iterdir():
            if f.is_file() and f.name.endswith('.csv'):
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        reader = csv.reader(fp)
                        header = next(reader, None)
                        rows = list(reader)
                        results["dataDetails"][f.name] = {
                            "size": f.stat().st_size,
                            "header": header,
                            "row_count": len(rows),
                            "sample_row": rows[0] if rows else None
                        }
                except Exception as e:
                    results["dataDetails"][f.name] = {"error": str(e)}

    # 5. Centers C1 through C6
    results["centers"] = {}
    total_single_images = 0
    total_single_masks = 0
    total_single_bboxes = 0
    total_single_bbox_images = 0

    for c_num in range(1, 7):
        c_name = f"data_C{c_num}"
        c_path = POLYPGEN_DIR / c_name
        c_res = {}
        if c_path.exists():
            for entry in os.scandir(c_path):
                if entry.is_dir():
                    stats = get_dir_file_counts(Path(entry.path))
                    c_res[entry.name] = stats
                    if "images_" in entry.name:
                        total_single_images += stats["file_count"]
                    elif "masks_" in entry.name:
                        total_single_masks += stats["file_count"]
                    elif entry.name.startswith("bbox_C"):
                        total_single_bboxes += stats["file_count"]
                    elif "bbox_image" in entry.name:
                        total_single_bbox_images += stats["file_count"]
                elif entry.is_file():
                    c_res[f"FILE:{entry.name}"] = entry.stat().st_size
        results["centers"][c_name] = c_res

    results["single_frames_totals"] = {
        "images": total_single_images,
        "masks": total_single_masks,
        "bboxes": total_single_bboxes,
        "bbox_images": total_single_bbox_images
    }

    # 6. Sequence Data: Positive
    pos_dir = POLYPGEN_DIR / "sequenceData" / "positive"
    results["sequence_positive"] = {}
    total_seq_pos_images = 0
    total_seq_pos_masks = 0
    total_seq_pos_bboxes = 0
    total_seq_pos_bbox_images = 0

    if pos_dir.exists():
        # sort sequences naturally
        def pos_sort_key(x):
            digits = x.replace("seq", "")
            return (0, int(digits)) if x.startswith("seq") and digits.isdigit() else (1, x)
        seq_folders = sorted(os.listdir(pos_dir), key=pos_sort_key)
        for seq in seq_folders:
            seq_p = pos_dir / seq
            if seq_p.is_dir():
                s_res = {}
                for sub in os.scandir(seq_p):
                    if sub.is_dir():
                        st = get_dir_file_counts(Path(sub.path))
                        s_res[sub.name] = st
                        if "images_" in sub.name:
                            total_seq_pos_images += st["file_count"]
                        elif "masks_" in sub.name:
                            total_seq_pos_masks += st["file_count"]
                        elif sub.name.startswith("bbox_seq"):
                            total_seq_pos_bboxes += st["file_count"]
                        elif "bbox_image" in sub.name:
                            total_seq_pos_bbox_images += st["file_count"]
                    elif sub.is_file():
                        s_res[f"FILE:{sub.name}"] = sub.stat().st_size
                results["sequence_positive"][seq] = s_res

    results["sequence_positive_totals"] = {
        "images": total_seq_pos_images,
        "masks": total_seq_pos_masks,
        "bboxes": total_seq_pos_bboxes,
        "bbox_images": total_seq_pos_bbox_images
    }

    # 7. Sequence Data: Negative
    neg_dir = POLYPGEN_DIR / "sequenceData" / "negativeOnly"
    results["sequence_negative"] = {}
    total_seq_neg_images = 0

    if neg_dir.exists():
        def neg_sort_key(x):
            digits = x.replace("seq", "").replace("_neg", "")
            return (0, int(digits)) if x.startswith("seq") and digits.isdigit() else (1, x)
        seq_folders = sorted(os.listdir(neg_dir), key=neg_sort_key)
        for seq in seq_folders:
            seq_p = neg_dir / seq
            if seq_p.is_dir():
                st = get_dir_file_counts(seq_p)
                results["sequence_negative"][seq] = st
                total_seq_neg_images += st["file_count"]
            elif seq_p.is_file():
                results["sequence_negative"][f"FILE:{seq}"] = seq_p.stat().st_size

    results["sequence_negative_totals"] = {
        "total_negative_images": total_seq_neg_images
    }

    # 8. imagesAll_positive
    img_all_dir = POLYPGEN_DIR / "imagesAll_positive"
    results["imagesAll_positive"] = get_dir_file_counts(img_all_dir)

    # 9. Inspect Zip file contents
    zip_path = POLYPGEN_DIR / "PolypGen2021_MultiCenterData_Concatenated.zip"
    if zip_path.exists():
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                info_list = zf.infolist()
                results["concatenated_zip"] = {
                    "total_entries": len(info_list),
                    "file_count": len([i for i in info_list if not i.is_dir()]),
                    "dir_count": len([i for i in info_list if i.is_dir()]),
                    "total_uncompressed_size": sum(i.file_size for i in info_list),
                    "sample_entries": [i.filename for i in info_list[:10]],
                    "top_level_in_zip": list(set(i.filename.split('/')[0] for i in info_list))
                }
        except Exception as e:
            results["concatenated_zip"] = {"error": str(e)}

    with open(OUT_FILE, "w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)
    print("Done! Saved results to", OUT_FILE)

if __name__ == "__main__":
    run_inspection()
