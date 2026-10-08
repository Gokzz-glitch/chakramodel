import os
import sys
import glob
from collections import defaultdict, Counter
from PIL import Image
import numpy as np

BASE_DIR = r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3"

def analyze_dataset():
    print(f"Analyzing PolypGen dataset at: {BASE_DIR}")
    if not os.path.exists(BASE_DIR):
        print(f"Error: Path {BASE_DIR} does not exist.")
        return

    # 1. Centers analysis: data_C1 to data_C6
    print("\n" + "="*50)
    print("1. CENTERS ANALYSIS (Single Frames: data_C1 to data_C6)")
    print("="*50)
    
    centers = [f"C{i}" for i in range(1, 7)]
    center_stats = {}

    for c in centers:
        c_dir = os.path.join(BASE_DIR, f"data_{c}")
        if not os.path.exists(c_dir):
            print(f"Warning: {c_dir} does not exist!")
            continue
        
        subdirs = os.listdir(c_dir)
        print(f"\n--- Center {c} ({c_dir}) ---")
        print(f"Subdirs: {subdirs}")
        
        img_dir = os.path.join(c_dir, f"images_{c}")
        mask_dir = os.path.join(c_dir, f"masks_{c}")
        bbox_dir = os.path.join(c_dir, f"bbox_{c}")
        bbox_img_dir = os.path.join(c_dir, f"bbox_image_{c}")
        if not os.path.exists(bbox_img_dir):
            # Check alternate naming e.g. bbox_images_C6
            bbox_img_dir = os.path.join(c_dir, f"bbox_images_{c}")
            
        img_files = os.listdir(img_dir) if os.path.exists(img_dir) else []
        mask_files = os.listdir(mask_dir) if os.path.exists(mask_dir) else []
        bbox_files = os.listdir(bbox_dir) if os.path.exists(bbox_dir) else []
        bbox_img_files = os.listdir(bbox_img_dir) if os.path.exists(bbox_img_dir) else []
        
        # Extensions
        img_exts = Counter(os.path.splitext(f)[1].lower() for f in img_files)
        mask_exts = Counter(os.path.splitext(f)[1].lower() for f in mask_files)
        
        print(f"Images count: {len(img_files)}, exts: {dict(img_exts)}")
        print(f"Masks count: {len(mask_files)}, exts: {dict(mask_exts)}")
        print(f"Bbox txt count: {len(bbox_files)}")
        print(f"Bbox image count: {len(bbox_img_files)}")
        
        # Check stem matching
        # Strategy 1: image stem X -> mask stem X + '_mask'
        # Strategy 2: image stem X -> mask stem X
        matched_mask = 0
        unmatched_img = []
        positive_masks = 0
        negative_masks = 0 # all black
        mask_shapes = set()
        img_shapes = set()
        img_channels = Counter()
        mask_channels = Counter()
        mask_unique_vals_sample = set()
        
        # Check matching
        for img_f in img_files:
            stem, ext = os.path.splitext(img_f)
            # Try expected mask names
            cand1 = f"{stem}_mask.jpg"
            cand2 = f"{stem}_mask.png"
            cand3 = f"{stem}.jpg"
            cand4 = f"{stem}.png"
            
            mask_path = None
            for cand in [cand1, cand2, cand3, cand4]:
                p = os.path.join(mask_dir, cand)
                if os.path.exists(p):
                    mask_path = p
                    break
            
            if mask_path:
                matched_mask += 1
            else:
                unmatched_img.append(img_f)

        print(f"Matched images to masks: {matched_mask} / {len(img_files)}")
        if unmatched_img:
            print(f"Unmatched images sample ({len(unmatched_img)}): {unmatched_img[:5]}")
            
        # Check if masks have extra files
        extra_masks = []
        for mf in mask_files:
            stem, ext = os.path.splitext(mf)
            # reverse candidate
            if stem.endswith("_mask"):
                img_stem = stem[:-5]
            else:
                img_stem = stem
            cand_img1 = os.path.join(img_dir, f"{img_stem}.jpg")
            cand_img2 = os.path.join(img_dir, f"{img_stem}.png")
            if not os.path.exists(cand_img1) and not os.path.exists(cand_img2):
                extra_masks.append(mf)
        if extra_masks:
            print(f"Extra masks not corresponding to images: {len(extra_masks)}, sample: {extra_masks[:5]}")
        else:
            print("All masks correspond to images.")
            
        # Inspect a sample of images and masks for shapes, channels, pixel values
        sample_size = min(len(img_files), 50)
        for img_f in img_files[:sample_size]:
            p_img = os.path.join(img_dir, img_f)
            stem, ext = os.path.splitext(img_f)
            with Image.open(p_img) as im:
                img_shapes.add(im.size) # (width, height)
                img_channels[im.mode] += 1
                
            # mask
            for cand in [f"{stem}_mask.jpg", f"{stem}_mask.png", f"{stem}.jpg", f"{stem}.png"]:
                p_m = os.path.join(mask_dir, cand)
                if os.path.exists(p_m):
                    with Image.open(p_m) as mim:
                        mask_shapes.add(mim.size)
                        mask_channels[mim.mode] += 1
                        m_arr = np.array(mim)
                        if m_arr.max() == 0:
                            negative_masks += 1
                        else:
                            positive_masks += 1
                            mask_unique_vals_sample.update(np.unique(m_arr)[:10])
                    break
                    
        print(f"Image modes (sample {sample_size}): {dict(img_channels)}")
        print(f"Image resolutions sample: {list(img_shapes)[:5]}")
        print(f"Mask modes (sample {sample_size}): {dict(mask_channels)}")
        print(f"Mask sample positive vs negative (all zero): {positive_masks} pos, {negative_masks} neg")
        print(f"Mask sample unique values (first 10): {sorted(list(mask_unique_vals_sample))[:15]}")
        
        center_stats[c] = {
            'images': len(img_files),
            'masks': len(mask_files),
            'bbox': len(bbox_files),
            'bbox_img': len(bbox_img_files),
            'matched': matched_mask,
            'unmatched': len(unmatched_img),
            'img_shapes': list(img_shapes),
            'mask_shapes': list(mask_shapes)
        }

    return center_stats

if __name__ == "__main__":
    analyze_dataset()
