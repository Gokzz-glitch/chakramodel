import os
import json
from pathlib import Path

POLYPGEN = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")

def run_validation():
    print("=== Checking Centers C1 through C6 ===")
    center_report = {}
    for c_idx in range(1, 7):
        c_name = f"data_C{c_idx}"
        c_path = POLYPGEN / c_name
        
        img_dir = c_path / f"images_C{c_idx}"
        mask_dir = c_path / f"masks_C{c_idx}"
        bbox_dir = c_path / f"bbox_C{c_idx}"
        bbox_img_dir = c_path / (f"bbox_images_C{c_idx}" if c_idx == 6 else f"bbox_image_C{c_idx}")
        
        imgs = set(os.path.splitext(f)[0] for f in os.listdir(img_dir) if f.endswith('.jpg'))
        masks = set(f.replace('_mask.jpg', '') for f in os.listdir(mask_dir) if f.endswith('.jpg'))
        
        # In C3, bboxes are named <id>.txt, in others <id>_mask.txt
        bbox_files = [f for f in os.listdir(bbox_dir) if f.endswith('.txt')]
        if c_idx == 3:
            bboxes = set(os.path.splitext(f)[0] for f in bbox_files)
        else:
            bboxes = set(f.replace('_mask.txt', '') for f in bbox_files)
            
        bbox_imgs = set(f.replace('_mask_bbox.jpg', '') for f in os.listdir(bbox_img_dir) if f.endswith('.jpg'))
        
        # Check hidden or non-expected files
        other_files = {}
        for sub in [img_dir, mask_dir, bbox_dir, bbox_img_dir, c_path]:
            non_std = [f for f in os.listdir(sub) if not f.endswith(('.jpg', '.txt')) and os.path.isfile(os.path.join(sub, f))]
            if non_std:
                other_files[sub.name] = non_std
                
        center_report[c_name] = {
            "images_count": len(imgs),
            "masks_count": len(masks),
            "bboxes_count": len(bboxes),
            "bbox_imgs_count": len(bbox_imgs),
            "imgs_minus_masks": len(imgs - masks),
            "masks_minus_imgs": len(masks - imgs),
            "imgs_minus_bboxes": len(imgs - bboxes),
            "bboxes_minus_imgs": len(bboxes - imgs),
            "imgs_minus_bbox_imgs": len(imgs - bbox_imgs),
            "bbox_imgs_minus_imgs": len(bbox_imgs - imgs),
            "non_std_files": other_files
        }
        print(f"[{c_name}] imgs={len(imgs)}, masks={len(masks)}, bboxes={len(bboxes)}, bbox_imgs={len(bbox_imgs)}")
        if imgs != masks:
            print(f"  MISMATCH imgs vs masks: imgs-masks={imgs-masks}, masks-imgs={masks-imgs}")
        if imgs - bboxes:
            print(f"  imgs without bbox: {len(imgs - bboxes)}")
        if bboxes - imgs:
            print(f"  bboxes without img: {len(bboxes - imgs)}")
        if bbox_imgs - imgs:
            print(f"  bbox_imgs without img: {bbox_imgs - imgs}")
        if other_files:
            print(f"  non standard files: {other_files}")

    print("\n=== Checking Sequences Positive (seq1 to seq23) ===")
    seq_pos_dir = POLYPGEN / "sequenceData" / "positive"
    seq_report = {}
    for i in range(1, 24):
        s_name = f"seq{i}"
        s_path = seq_pos_dir / s_name
        img_dir = s_path / f"images_{s_name}"
        mask_dir = s_path / f"masks_{s_name}"
        bbox_dir = s_path / f"bbox_{s_name}"
        bbox_img_dir = s_path / f"bbox_image_{s_name}"
        
        imgs = [f for f in os.listdir(img_dir) if f.endswith('.jpg')]
        masks_jpg = [f for f in os.listdir(mask_dir) if f.endswith('.jpg')]
        masks_txt = [f for f in os.listdir(mask_dir) if f.endswith('.txt')]
        bboxes = [f for f in os.listdir(bbox_dir) if f.endswith('.txt')]
        bbox_imgs = [f for f in os.listdir(bbox_img_dir) if f.endswith('.jpg')]
        
        seq_report[s_name] = {
            "imgs": len(imgs),
            "masks_jpg": len(masks_jpg),
            "masks_txt": len(masks_txt),
            "bboxes": len(bboxes),
            "bbox_imgs": len(bbox_imgs)
        }
        if not (len(imgs) == len(masks_jpg) == len(bboxes) == len(bbox_imgs)):
            print(f"  MISMATCH in {s_name}: imgs={len(imgs)}, masks_jpg={len(masks_jpg)}, bboxes={len(bboxes)}, bbox_imgs={len(bbox_imgs)}")
        if masks_txt:
            print(f"  NOTE: {s_name} has {len(masks_txt)} .txt files inside masks_{s_name}!")

    print("\n=== Checking Sequences Negative (seq1_neg to seq23_neg) ===")
    seq_neg_dir = POLYPGEN / "sequenceData" / "negativeOnly"
    neg_report = {}
    total_neg_files = 0
    non_jpg_in_neg = []
    for i in range(1, 24):
        s_name = f"seq{i}_neg"
        s_path = seq_neg_dir / s_name
        files = os.listdir(s_path)
        jpgs = [f for f in files if f.endswith('.jpg')]
        non_jpg = [f for f in files if not f.endswith('.jpg')]
        neg_report[s_name] = len(jpgs)
        total_neg_files += len(jpgs)
        if non_jpg:
            non_jpg_in_neg.append((s_name, non_jpg))
    print(f"Total negative sequences: 23, total negative images: {total_neg_files}")
    if non_jpg_in_neg:
        print(f"Non-jpg in negative sequences: {non_jpg_in_neg}")
    else:
        print("All negative sequence items are purely .jpg images!")

    # Check imagesAll_positive completeness
    print("\n=== Checking imagesAll_positive ===")
    all_pos_dir = POLYPGEN / "imagesAll_positive"
    all_pos_files = set(os.listdir(all_pos_dir))
    
    # Collect all single frame image filenames
    all_single_imgs = set()
    for c_idx in range(1, 7):
        img_dir = POLYPGEN / f"data_C{c_idx}" / f"images_C{c_idx}"
        all_single_imgs.update(os.listdir(img_dir))
        
    # Collect all sequence positive image filenames
    all_seq_pos_imgs = set()
    for i in range(1, 24):
        img_dir = seq_pos_dir / f"seq{i}" / f"images_seq{i}"
        all_seq_pos_imgs.update(os.listdir(img_dir))
        
    expected_pos = all_single_imgs.union(all_seq_pos_imgs)
    print(f"Total expected positive images: {len(expected_pos)} ({len(all_single_imgs)} single + {len(all_seq_pos_imgs)} sequence)")
    print(f"Total images in imagesAll_positive: {len(all_pos_files)}")
    print(f"Difference (expected - actual): {len(expected_pos - all_pos_files)}")
    print(f"Difference (actual - expected): {len(all_pos_files - expected_pos)}")

    # Check all .DS_Store files across the dataset
    print("\n=== Locating all .DS_Store files in PolypGen ===")
    ds_stores = []
    for root, dirs, files in os.walk(POLYPGEN):
        for f in files:
            if f == ".DS_Store":
                ds_stores.append(os.path.relpath(os.path.join(root, f), POLYPGEN))
    print(f"Total .DS_Store files in PolypGen: {len(ds_stores)}")
    for ds in ds_stores:
        print(f"  {ds}")

    # Write full validation report
    val_file = Path(r"m:\chakramodel\.agents\teamwork_preview_explorer_pg_1\validation_report.json")
    with open(val_file, "w", encoding="utf-8") as fp:
        json.dump({
            "centers": center_report,
            "sequences_positive": seq_report,
            "sequences_negative": neg_report,
            "imagesAll_positive_count": len(all_pos_files),
            "expected_positive_count": len(expected_pos),
            "ds_store_files": ds_stores
        }, fp, indent=2)
    print("\nSaved validation report to validation_report.json")

if __name__ == "__main__":
    run_validation()
