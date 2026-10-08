import os
import sys
import json
from pathlib import Path
from collections import Counter, defaultdict
import cv2
import numpy as np
from PIL import Image

DATASET_ROOT = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")

def run_fast_inspection():
    report = {}
    print("--- Starting fast inspection ---", flush=True)

    # 1. Centers C1 - C6
    centers_data = {}
    for c in range(1, 7):
        c_name = f"data_C{c}"
        c_dir = DATASET_ROOT / c_name
        if not c_dir.exists():
            print(f"Directory {c_dir} does not exist!", flush=True)
            continue
        
        subdirs = sorted([d.name for d in c_dir.iterdir() if d.is_dir()])
        print(f"\nProcessing {c_name} (subdirs: {subdirs})...", flush=True)
        
        c_info = {"subdirs": subdirs, "folders": {}}
        
        for sd in subdirs:
            p = c_dir / sd
            files = [f for f in p.iterdir() if f.is_file() and not f.name.startswith(".")]
            exts = Counter(f.suffix.lower() for f in files)
            sample_names = [f.name for f in files[:5]]
            c_info["folders"][sd] = {
                "count": len(files),
                "extensions": dict(exts),
                "samples": sample_names
            }
            print(f"  {sd}: {len(files)} files, exts: {dict(exts)}, samples: {sample_names[:2]}", flush=True)
            
        # Analyze pairing between images and masks
        img_folder_name = next((sd for sd in subdirs if sd.startswith("images_") or sd == "images"), None)
        mask_folder_name = next((sd for sd in subdirs if sd.startswith("masks_") or sd == "masks"), None)
        bbox_folder_name = next((sd for sd in subdirs if sd.startswith("bbox_") and not sd.startswith("bbox_image")), None)
        bbox_img_folder_name = next((sd for sd in subdirs if sd.startswith("bbox_image") or sd.startswith("bbox_images")), None)
        
        c_info["img_folder"] = img_folder_name
        c_info["mask_folder"] = mask_folder_name
        c_info["bbox_folder"] = bbox_folder_name
        c_info["bbox_img_folder"] = bbox_img_folder_name
        
        if img_folder_name and mask_folder_name:
            img_p = c_dir / img_folder_name
            mask_p = c_dir / mask_folder_name
            
            img_files = sorted([f for f in img_p.iterdir() if f.is_file() and not f.name.startswith(".")])
            mask_files = sorted([f for f in mask_p.iterdir() if f.is_file() and not f.name.startswith(".")])
            
            img_stems = {f.stem: f for f in img_files}
            mask_stems = {f.stem: f for f in mask_files}
            
            # Check exact stem match vs suffix match (e.g. stem_mask)
            exact_matches = set(img_stems.keys()) & set(mask_stems.keys())
            
            # Check if mask has _mask suffix
            mask_stems_stripped = {stem.replace("_mask", "") if stem.endswith("_mask") else stem: stem for stem in mask_stems}
            suffix_matches = set(img_stems.keys()) & set(mask_stems_stripped.keys())
            
            c_info["pairing"] = {
                "num_images": len(img_files),
                "num_masks": len(mask_files),
                "exact_stem_matches": len(exact_matches),
                "suffix_stem_matches": len(suffix_matches),
                "mask_has_mask_suffix": any(stem.endswith("_mask") for stem in mask_stems)
            }
            print(f"  Pairing: {len(img_files)} images, {len(mask_files)} masks, exact_matches: {len(exact_matches)}, suffix_matches: {len(suffix_matches)}", flush=True)
            
            # Read resolutions fast using PIL header parsing (does not load pixel data)
            img_res = Counter()
            img_modes = Counter()
            for f in img_files:
                try:
                    with Image.open(f) as im:
                        img_res[f"{im.size[0]}x{im.size[1]}"] += 1
                        img_modes[im.mode] += 1
                except Exception as e:
                    print(f"    Error reading img header {f.name}: {e}", flush=True)
                    
            mask_res = Counter()
            mask_modes = Counter()
            for f in mask_files:
                try:
                    with Image.open(f) as im:
                        mask_res[f"{im.size[0]}x{im.size[1]}"] += 1
                        mask_modes[im.mode] += 1
                except Exception as e:
                    print(f"    Error reading mask header {f.name}: {e}", flush=True)
                    
            c_info["image_resolutions"] = dict(img_res)
            c_info["image_modes"] = dict(img_modes)
            c_info["mask_resolutions"] = dict(mask_res)
            c_info["mask_modes"] = dict(mask_modes)
            
            print(f"  Img resolutions: {dict(img_res)}, modes: {dict(img_modes)}", flush=True)
            print(f"  Mask resolutions: {dict(mask_res)}, modes: {dict(mask_modes)}", flush=True)
            
            # Check mask values on a sample of 25 masks
            sample_masks = mask_files[:25]
            sample_mask_val_types = []
            for mf in sample_masks:
                arr = cv2.imread(str(mf), cv2.IMREAD_UNCHANGED)
                if arr is None:
                    continue
                unq = np.unique(arr)
                info = {
                    "file": mf.name,
                    "shape": list(arr.shape),
                    "dtype": str(arr.dtype),
                    "min": int(arr.min()),
                    "max": int(arr.max()),
                    "num_unique": len(unq),
                    "unique_sample": [int(x) for x in unq[:10]]
                }
                sample_mask_val_types.append(info)
            c_info["sample_mask_analysis"] = sample_mask_val_types
            if sample_mask_val_types:
                s0 = sample_mask_val_types[0]
                print(f"  Sample mask 0: {s0['file']} shape={s0['shape']} min={s0['min']} max={s0['max']} num_unq={s0['num_unique']} unq[:5]={s0['unique_sample'][:5]}", flush=True)
                
        centers_data[c_name] = c_info
        
    report["centers"] = centers_data
    
    # 2. imagesAll_positive
    print("\n--- Inspecting imagesAll_positive ---", flush=True)
    img_all_dir = DATASET_ROOT / "imagesAll_positive"
    if img_all_dir.exists():
        files = [f for f in img_all_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
        exts = Counter(f.suffix.lower() for f in files)
        res = Counter()
        modes = Counter()
        for f in files[:200]: # Sample 200 headers
            with Image.open(f) as im:
                res[f"{im.size[0]}x{im.size[1]}"] += 1
                modes[im.mode] += 1
        subdirs = [d.name for d in img_all_dir.iterdir() if d.is_dir()]
        report["imagesAll_positive"] = {
            "total_files": len(files),
            "subdirs": subdirs,
            "extensions": dict(exts),
            "samples": [f.name for f in files[:10]],
            "sample_resolutions": dict(res),
            "sample_modes": dict(modes)
        }
        print(f"  imagesAll_positive: {len(files)} files, exts: {dict(exts)}, subdirs: {subdirs}", flush=True)
        print(f"  Sample files: {[f.name for f in files[:5]]}", flush=True)
    
    # 3. sequenceData
    print("\n--- Inspecting sequenceData ---", flush=True)
    seq_dir = DATASET_ROOT / "sequenceData"
    seq_report = {}
    if seq_dir.exists():
        seq_subdirs = [d.name for d in seq_dir.iterdir() if d.is_dir()]
        seq_report["subdirs"] = seq_subdirs
        print(f"  sequenceData subdirs: {seq_subdirs}", flush=True)
        
        # negativeOnly
        neg_dir = seq_dir / "negativeOnly"
        if neg_dir.exists():
            neg_seqs = sorted([d.name for d in neg_dir.iterdir() if d.is_dir()])
            total_neg_files = 0
            neg_exts = Counter()
            neg_details = {}
            for ns in neg_seqs:
                p = neg_dir / ns
                f_list = [f for f in p.iterdir() if f.is_file() and not f.name.startswith(".")]
                total_neg_files += len(f_list)
                for f in f_list:
                    neg_exts[f.suffix.lower()] += 1
                sample_res = None
                if f_list:
                    with Image.open(f_list[0]) as im:
                        sample_res = f"{im.size[0]}x{im.size[1]} ({im.mode})"
                neg_details[ns] = {"count": len(f_list), "sample_res": sample_res, "sample_file": f_list[0].name if f_list else None}
            seq_report["negativeOnly"] = {
                "num_sequences": len(neg_seqs),
                "total_frames": total_neg_files,
                "extensions": dict(neg_exts),
                "sequences": neg_details
            }
            print(f"  negativeOnly: {len(neg_seqs)} sequences, {total_neg_files} total frames, exts: {dict(neg_exts)}", flush=True)
            
        # positive
        pos_dir = seq_dir / "positive"
        if pos_dir.exists():
            pos_seqs = sorted([d.name for d in pos_dir.iterdir() if d.is_dir()])
            pos_details = {}
            total_pos_imgs = 0
            total_pos_masks = 0
            for ps in pos_seqs:
                p = pos_dir / ps
                sub_d = [d.name for d in p.iterdir() if d.is_dir()]
                img_d = next((d for d in sub_d if d.startswith("images_")), None)
                mask_d = next((d for d in sub_d if d.startswith("masks_")), None)
                bbox_d = next((d for d in sub_d if d.startswith("bbox_") and not d.startswith("bbox_image")), None)
                bbox_img_d = next((d for d in sub_d if d.startswith("bbox_image")), None)
                
                n_imgs = len(list((p / img_d).glob("*.*"))) if img_d else 0
                n_masks = len(list((p / mask_d).glob("*.*"))) if mask_d else 0
                n_bbox = len(list((p / bbox_d).glob("*.*"))) if bbox_d else 0
                n_bbox_img = len(list((p / bbox_img_d).glob("*.*"))) if bbox_img_d else 0
                total_pos_imgs += n_imgs
                total_pos_masks += n_masks
                
                sample_img_res = None
                sample_mask_val = None
                if img_d and n_imgs > 0:
                    first_img = next((p / img_d).iterdir())
                    with Image.open(first_img) as im:
                        sample_img_res = f"{im.size[0]}x{im.size[1]} ({im.mode})"
                if mask_d and n_masks > 0:
                    first_mask = next((p / mask_d).iterdir())
                    arr = cv2.imread(str(first_mask), cv2.IMREAD_UNCHANGED)
                    if arr is not None:
                        unq = np.unique(arr)
                        sample_mask_val = f"shape={arr.shape}, min={arr.min()}, max={arr.max()}, unq={len(unq)}"
                
                pos_details[ps] = {
                    "subdirs": sub_d,
                    "img_count": n_imgs,
                    "mask_count": n_masks,
                    "bbox_count": n_bbox,
                    "bbox_img_count": n_bbox_img,
                    "sample_img_res": sample_img_res,
                    "sample_mask_val": sample_mask_val
                }
            seq_report["positive"] = {
                "num_sequences": len(pos_seqs),
                "total_images": total_pos_imgs,
                "total_masks": total_pos_masks,
                "sequences": pos_details
            }
            print(f"  positive: {len(pos_seqs)} sequences, total imgs: {total_pos_imgs}, total masks: {total_pos_masks}", flush=True)
            
    report["sequenceData"] = seq_report
    
    # Save full report to json
    out_path = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\.agents\explorer_m1_2\inspection_results.json")
    with open(out_path, "w") as fp:
        json.dump(report, fp, indent=2)
    print(f"\nSaved full results to {out_path}", flush=True)

if __name__ == "__main__":
    run_fast_inspection()
