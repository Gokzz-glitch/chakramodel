import os
import sys
from collections import defaultdict, Counter
from PIL import Image
import numpy as np

BASE_DIR = r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3"

def deep_check():
    print("=== DEEP VERIFICATION SCRIPT ===")
    
    # 1. Investigate _mask.txt files in seq2, seq7, seq8
    print("\n--- 1. Investigating _mask.txt in seq2, seq7, seq8 ---")
    pos_seq_dir = os.path.join(BASE_DIR, "sequenceData", "positive")
    for s in ["seq2", "seq7", "seq8"]:
        mask_d = os.path.join(pos_seq_dir, s, f"masks_{s}")
        txt_masks = [f for f in os.listdir(mask_d) if f.endswith(".txt")]
        print(f"{s}: {len(txt_masks)} .txt files in masks folder.")
        if txt_masks:
            sample_p = os.path.join(mask_d, txt_masks[0])
            with open(sample_p, "r") as f:
                content = f.read()
            print(f"Sample content of {txt_masks[0]}:\n{content.strip()[:300]}")
            
    # 2. Check C3 missing bboxes (457 images vs 393 bboxes)
    print("\n--- 2. Investigating C3 missing bboxes ---")
    c3_dir = os.path.join(BASE_DIR, "data_C3")
    c3_imgs = set(os.listdir(os.path.join(c3_dir, "images_C3")))
    c3_bboxes = set(os.listdir(os.path.join(c3_dir, "bbox_C3")))
    c3_masks = os.path.join(c3_dir, "masks_C3")
    
    missing_bboxes = []
    for img_f in c3_imgs:
        stem = os.path.splitext(img_f)[0]
        if f"{stem}.txt" not in c3_bboxes:
            # check mask status for this image
            cand_mask = f"{stem}_mask.jpg"
            if not os.path.exists(os.path.join(c3_masks, cand_mask)) and stem.endswith("_"):
                cand_mask = f"{stem[:-1]}_mask.jpg"
            m_path = os.path.join(c3_masks, cand_mask)
            if os.path.exists(m_path):
                with Image.open(m_path) as mim:
                    arr = np.array(mim)
                    missing_bboxes.append((img_f, arr.max()))
            else:
                missing_bboxes.append((img_f, "NO_MASK"))
                
    print(f"Total C3 images missing bbox: {len(missing_bboxes)}")
    print(f"Sample missing bbox images with mask max value: {missing_bboxes[:10]}")
    # Count how many of missing bboxes have mask max == 0 vs max > 0
    neg_missing = sum(1 for _, mx in missing_bboxes if mx == 0)
    pos_missing = sum(1 for _, mx in missing_bboxes if isinstance(mx, (int, np.integer, np.uint8)) and mx > 0)
    print(f"Of the 64 missing bboxes: {neg_missing} have all-zero masks, {pos_missing} have non-zero masks!")

    # 3. Check sequenceData positive: are any masks all-zero?
    print("\n--- 3. Positive Sequences: Pos vs Neg Masks ---")
    pos_seqs = sorted([d for d in os.listdir(pos_seq_dir) if os.path.isdir(os.path.join(pos_seq_dir, d))],
                      key=lambda x: int(x.replace("seq", "")) if x.replace("seq", "").isdigit() else x)
    seq_pos_masks = 0
    seq_neg_masks = 0
    for s in pos_seqs:
        mask_d = os.path.join(pos_seq_dir, s, f"masks_{s}")
        jpg_masks = [f for f in os.listdir(mask_d) if f.endswith(".jpg")]
        s_pos = 0
        s_neg = 0
        for jm in jpg_masks:
            with Image.open(os.path.join(mask_d, jm)) as mim:
                arr = np.array(mim)
                if arr.max() == 0:
                    s_neg += 1
                else:
                    s_pos += 1
        seq_pos_masks += s_pos
        seq_neg_masks += s_neg
        if s_neg > 0:
            print(f"  {s}: has {s_neg} empty masks out of {len(jpg_masks)}")
            
    print(f"Total across all 23 positive sequences: {seq_pos_masks} positive masks, {seq_neg_masks} negative (all-zero) masks.")

    # 4. Dimension match check: image size vs mask size across the entire dataset
    print("\n--- 4. Checking Image vs Mask Dimension Matching ---")
    mismatched_dims = []
    
    # Centers
    for c in [f"C{i}" for i in range(1, 7)]:
        c_dir = os.path.join(BASE_DIR, f"data_{c}")
        img_d = os.path.join(c_dir, f"images_{c}")
        mask_d = os.path.join(c_dir, f"masks_{c}")
        for img_f in os.listdir(img_d):
            stem, _ = os.path.splitext(img_f)
            cand_mask = f"{stem}_mask.jpg"
            if not os.path.exists(os.path.join(mask_d, cand_mask)) and stem.endswith("_"):
                cand_mask = f"{stem[:-1]}_mask.jpg"
            m_path = os.path.join(mask_d, cand_mask)
            if os.path.exists(m_path):
                with Image.open(os.path.join(img_d, img_f)) as im, Image.open(m_path) as mim:
                    if im.size != mim.size:
                        mismatched_dims.append((c, img_f, im.size, mim.size))

    # Positive sequences
    for s in pos_seqs:
        img_d = os.path.join(pos_seq_dir, s, f"images_{s}")
        mask_d = os.path.join(pos_seq_dir, s, f"masks_{s}")
        for img_f in os.listdir(img_d):
            stem, _ = os.path.splitext(img_f)
            m_path = os.path.join(mask_d, f"{stem}_mask.jpg")
            if os.path.exists(m_path):
                with Image.open(os.path.join(img_d, img_f)) as im, Image.open(m_path) as mim:
                    if im.size != mim.size:
                        mismatched_dims.append((s, img_f, im.size, mim.size))
                        
    print(f"Total dimension mismatches between image and mask: {len(mismatched_dims)}")
    if mismatched_dims:
        print(f"Sample mismatches: {mismatched_dims[:5]}")
    else:
        print("PERFECT MATCH: 100% of images and masks have identical dimensions!")

    # 5. imagesAll_positive composition
    print("\n--- 5. Composition of imagesAll_positive ---")
    all_pos_dir = os.path.join(BASE_DIR, "imagesAll_positive")
    all_pos_files = set(os.listdir(all_pos_dir))
    
    # Collect all image files from C1..C6
    single_frame_files = set()
    for c in [f"C{i}" for i in range(1, 7)]:
        img_d = os.path.join(BASE_DIR, f"data_{c}", f"images_{c}")
        single_frame_files.update(os.listdir(img_d))
        
    seq_pos_files = set()
    for s in pos_seqs:
        img_d = os.path.join(pos_seq_dir, s, f"images_{s}")
        seq_pos_files.update(os.listdir(img_d))
        
    in_single = all_pos_files.intersection(single_frame_files)
    in_seq = all_pos_files.intersection(seq_pos_files)
    neither = all_pos_files - single_frame_files - seq_pos_files
    
    print(f"imagesAll_positive total: {len(all_pos_files)}")
    print(f"Matches single frames: {len(in_single)} / {len(single_frame_files)}")
    print(f"Matches positive sequences: {len(in_seq)} / {len(seq_pos_files)}")
    print(f"Neither: {len(neither)}")

if __name__ == "__main__":
    deep_check()
