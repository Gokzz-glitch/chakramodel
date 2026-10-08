import os
import sys
import glob
from collections import defaultdict, Counter
from PIL import Image
import numpy as np

BASE_DIR = r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3"

def inspect_details():
    print("--- Detailed inspection of PolypGen ---")
    
    # 1. Exact Positive/Negative breakdown across C1..C6
    print("\n--- 1. C1..C6 Mask Values & Pos/Neg Count ---")
    centers = [f"C{i}" for i in range(1, 7)]
    for c in centers:
        c_dir = os.path.join(BASE_DIR, f"data_{c}")
        img_dir = os.path.join(c_dir, f"images_{c}")
        mask_dir = os.path.join(c_dir, f"masks_{c}")
        bbox_dir = os.path.join(c_dir, f"bbox_{c}")
        
        img_files = sorted(os.listdir(img_dir)) if os.path.exists(img_dir) else []
        mask_files = sorted(os.listdir(mask_dir)) if os.path.exists(mask_dir) else []
        bbox_files = set(os.listdir(bbox_dir)) if os.path.exists(bbox_dir) else set()
        
        pos_count = 0
        neg_count = 0
        max_vals = []
        mask_modes = Counter()
        mismatched_stems = []
        
        for img_f in img_files:
            stem, ext = os.path.splitext(img_f)
            # Check mask existence
            # normal stem
            expected_mask = f"{stem}_mask.jpg"
            if not os.path.exists(os.path.join(mask_dir, expected_mask)):
                # check if trailing underscore
                if stem.endswith("_") and os.path.exists(os.path.join(mask_dir, f"{stem[:-1]}_mask.jpg")):
                    mismatched_stems.append((img_f, f"{stem[:-1]}_mask.jpg"))
                    mask_path = os.path.join(mask_dir, f"{stem[:-1]}_mask.jpg")
                else:
                    mismatched_stems.append((img_f, "NOT_FOUND"))
                    continue
            else:
                mask_path = os.path.join(mask_dir, expected_mask)
                
            with Image.open(mask_path) as mim:
                mask_modes[mim.mode] += 1
                arr = np.array(mim)
                mx = arr.max()
                max_vals.append(mx)
                if mx == 0:
                    neg_count += 1
                else:
                    pos_count += 1
                    
        print(f"Center {c}: Total Images={len(img_files)}, Total Masks={len(mask_files)}, Total Bboxes={len(bbox_files)}")
        print(f"  Positive Masks (max > 0): {pos_count}")
        print(f"  Negative Masks (max == 0): {neg_count}")
        print(f"  Mask modes across all files: {dict(mask_modes)}")
        print(f"  Max val distribution: min of max={min(max_vals) if max_vals else None}, max of max={max(max_vals) if max_vals else None}")
        if mismatched_stems:
            print(f"  Mismatched/Special Stems ({len(mismatched_stems)}): {mismatched_stems}")
            
    # 2. Sequence Data: Positive sequences
    print("\n--- 2. Sequence Data (Positive: seq1 to seq23) ---")
    pos_seq_dir = os.path.join(BASE_DIR, "sequenceData", "positive")
    seq_dirs = sorted([d for d in os.listdir(pos_seq_dir) if os.path.isdir(os.path.join(pos_seq_dir, d))], 
                      key=lambda x: int(x.replace("seq", "")) if x.replace("seq", "").isdigit() else x)
    print(f"Positive sequences found: {len(seq_dirs)} -> {seq_dirs}")
    
    total_pos_seq_imgs = 0
    total_pos_seq_masks = 0
    total_pos_seq_bboxes = 0
    seq_exts_img = Counter()
    seq_exts_mask = Counter()
    seq_mask_modes = Counter()
    seq_img_modes = Counter()
    seq_resolutions = set()
    seq_special_files = []
    
    for s in seq_dirs:
        s_path = os.path.join(pos_seq_dir, s)
        img_d = os.path.join(s_path, f"images_{s}")
        mask_d = os.path.join(s_path, f"masks_{s}")
        bbox_d = os.path.join(s_path, f"bbox_{s}")
        bbox_img_d = os.path.join(s_path, f"bbox_image_{s}")
        
        imgs = os.listdir(img_d) if os.path.exists(img_d) else []
        masks = os.listdir(mask_d) if os.path.exists(mask_d) else []
        bboxes = os.listdir(bbox_d) if os.path.exists(bbox_d) else []
        
        total_pos_seq_imgs += len(imgs)
        total_pos_seq_masks += len(masks)
        total_pos_seq_bboxes += len(bboxes)
        
        for f in imgs:
            seq_exts_img[os.path.splitext(f)[1].lower()] += 1
        for f in masks:
            ext = os.path.splitext(f)[1].lower()
            seq_exts_mask[ext] += 1
            if ext != '.jpg':
                seq_special_files.append((s, f))
                
        # Sample check matching in this sequence
        unmatched = 0
        for f in imgs[:10]:
            stem, _ = os.path.splitext(f)
            if not os.path.exists(os.path.join(mask_d, f"{stem}_mask.jpg")):
                unmatched += 1
                
        # Sample mode and resolution
        if imgs:
            with Image.open(os.path.join(img_d, imgs[0])) as im:
                seq_img_modes[im.mode] += 1
                seq_resolutions.add(im.size)
        if masks:
            # find first jpg mask
            jpg_masks = [m for m in masks if m.endswith('.jpg')]
            if jpg_masks:
                with Image.open(os.path.join(mask_d, jpg_masks[0])) as mim:
                    seq_mask_modes[mim.mode] += 1
                    
        print(f"  {s}: images={len(imgs)}, masks={len(masks)}, bboxes={len(bboxes)} | Sample img={imgs[0] if imgs else 'None'}")

    print(f"\nPositive Sequences Totals: Images={total_pos_seq_imgs}, Masks={total_pos_seq_masks}, Bboxes={total_pos_seq_bboxes}")
    print(f"Image extensions: {dict(seq_exts_img)}, Mask extensions: {dict(seq_exts_mask)}")
    print(f"Special/Non-jpg mask files in positive sequences: {seq_special_files}")
    print(f"Sample resolutions across positive sequences: {seq_resolutions}")
    print(f"Mask modes across sequences: {dict(seq_mask_modes)}")

    # 3. Sequence Data: Negative sequences
    print("\n--- 3. Sequence Data (Negative Only: seq1_neg to seq23_neg) ---")
    neg_seq_dir = os.path.join(BASE_DIR, "sequenceData", "negativeOnly")
    neg_dirs = sorted([d for d in os.listdir(neg_seq_dir) if os.path.isdir(os.path.join(neg_seq_dir, d))],
                      key=lambda x: int(x.replace("seq", "").replace("_neg", "")) if x.replace("seq", "").replace("_neg", "").isdigit() else x)
    print(f"Negative sequences found: {len(neg_dirs)} -> {neg_dirs}")
    
    total_neg_imgs = 0
    neg_exts = Counter()
    neg_img_modes = Counter()
    neg_resolutions = set()
    neg_subdirs_info = []
    
    for nd in neg_dirs:
        p = os.path.join(neg_seq_dir, nd)
        # Check subdirs or files directly in p
        sub_items = os.listdir(p)
        subdirs = [x for x in sub_items if os.path.isdir(os.path.join(p, x))]
        files = [x for x in sub_items if os.path.isfile(os.path.join(p, x))]
        
        # If files in subdirs, e.g. images_seq1_neg
        if subdirs:
            for sd in subdirs:
                sd_files = os.listdir(os.path.join(p, sd))
                total_neg_imgs += len(sd_files)
                for f in sd_files:
                    neg_exts[os.path.splitext(f)[1].lower()] += 1
                if sd_files:
                    with Image.open(os.path.join(p, sd, sd_files[0])) as im:
                        neg_img_modes[im.mode] += 1
                        neg_resolutions.add(im.size)
            neg_subdirs_info.append((nd, subdirs, [len(os.listdir(os.path.join(p, sd))) for sd in subdirs]))
        else:
            total_neg_imgs += len(files)
            for f in files:
                neg_exts[os.path.splitext(f)[1].lower()] += 1
            if files:
                with Image.open(os.path.join(p, files[0])) as im:
                    neg_img_modes[im.mode] += 1
                    neg_resolutions.add(im.size)
            neg_subdirs_info.append((nd, "root", len(files)))
            
    print(f"Total Negative Images in sequenceData/negativeOnly: {total_neg_imgs}")
    print(f"Negative image extensions: {dict(neg_exts)}")
    print(f"Negative image modes: {dict(neg_img_modes)}")
    print(f"Sample resolutions across negative sequences: {neg_resolutions}")
    print(f"Structure sample in negative sequences: {neg_subdirs_info[:5]}")

    # 4. imagesAll_positive analysis
    print("\n--- 4. imagesAll_positive Directory ---")
    all_pos_dir = os.path.join(BASE_DIR, "imagesAll_positive")
    if os.path.exists(all_pos_dir):
        all_pos_files = os.listdir(all_pos_dir)
        pos_exts = Counter(os.path.splitext(f)[1].lower() for f in all_pos_files)
        print(f"Total files in imagesAll_positive: {len(all_pos_files)}")
        print(f"Extensions: {dict(pos_exts)}")
        print(f"Sample filenames: {all_pos_files[:5]}")
        # Check where these images come from: single frames or sequences or both?
        # Check sample matching
        c_samples = [f for f in all_pos_files if f.startswith("C") or "OLCV" in f or "100H" in f][:5]
        seq_samples = [f for f in all_pos_files if "seq" in f.lower()][:5]
        print(f"Center-like sample in imagesAll_positive: {c_samples}")
        print(f"Sequence-like sample in imagesAll_positive: {seq_samples}")

if __name__ == "__main__":
    inspect_details()
