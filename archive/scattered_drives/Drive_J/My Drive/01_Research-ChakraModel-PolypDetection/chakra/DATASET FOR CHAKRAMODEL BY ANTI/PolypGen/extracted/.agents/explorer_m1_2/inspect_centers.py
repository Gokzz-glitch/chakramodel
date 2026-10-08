import os
import sys
import glob
from pathlib import Path
from collections import Counter, defaultdict
import cv2
import numpy as np
from PIL import Image

DATASET_ROOT = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")

def analyze_centers():
    print("=== ANALYZING CENTERS C1 to C6 ===")
    results = {}
    for c_idx in range(1, 7):
        c_name = f"data_C{c_idx}"
        c_dir = DATASET_ROOT / c_name
        if not c_dir.exists():
            print(f"Directory {c_dir} does not exist!")
            continue
        
        subdirs = [d.name for d in c_dir.iterdir() if d.is_dir()]
        print(f"\n--- {c_name} ---")
        print(f"Subdirectories: {subdirs}")
        
        c_res = {"subdirs": subdirs}
        
        # Find images and masks folder names
        img_dirs = [d for d in subdirs if d.startswith("images_") or d == "images"]
        mask_dirs = [d for d in subdirs if d.startswith("masks_") or d == "masks"]
        bbox_dirs = [d for d in subdirs if d.startswith("bbox_") and not d.startswith("bbox_image")]
        bbox_img_dirs = [d for d in subdirs if d.startswith("bbox_image")]
        
        c_res["img_dir"] = img_dirs[0] if img_dirs else None
        c_res["mask_dir"] = mask_dirs[0] if mask_dirs else None
        c_res["bbox_dir"] = bbox_dirs[0] if bbox_dirs else None
        c_res["bbox_img_dir"] = bbox_img_dirs[0] if bbox_img_dirs else None
        
        for sd in subdirs:
            p = c_dir / sd
            files = [f for f in p.iterdir() if f.is_file()]
            exts = Counter(f.suffix.lower() for f in files)
            print(f"  {sd}: {len(files)} files, extensions: {dict(exts)}")
            c_res[f"{sd}_count"] = len(files)
            c_res[f"{sd}_exts"] = dict(exts)
            
        # Analyze pairing between images and masks
        if c_res["img_dir"] and c_res["mask_dir"]:
            img_path = c_dir / c_res["img_dir"]
            mask_path = c_dir / c_res["mask_dir"]
            
            img_files = {f.stem: f for f in img_path.iterdir() if f.is_file() and not f.name.startswith(".")}
            mask_files = {f.stem: f for f in mask_path.iterdir() if f.is_file() and not f.name.startswith(".")}
            
            common_stems = set(img_files.keys()) & set(mask_files.keys())
            only_in_imgs = set(img_files.keys()) - set(mask_files.keys())
            only_in_masks = set(mask_files.keys()) - set(img_files.keys())
            
            print(f"  Pairing stats:")
            print(f"    Total images: {len(img_files)}, Total masks: {len(mask_files)}")
            print(f"    Matching stems: {len(common_stems)}")
            print(f"    Images without mask: {len(only_in_imgs)}")
            print(f"    Masks without image: {len(only_in_masks)}")
            
            if only_in_imgs:
                print(f"    Sample images without mask: {list(only_in_imgs)[:5]}")
            if only_in_masks:
                print(f"    Sample masks without image: {list(only_in_masks)[:5]}")
                
            # Sample inspect images & masks
            sample_stems = list(common_stems)[:10] if common_stems else list(img_files.keys())[:10]
            
            # Check dimensions, channels, values for all or sample
            img_resolutions = Counter()
            mask_resolutions = Counter()
            mask_val_types = Counter()
            img_channels = Counter()
            mask_channels = Counter()
            
            for stem in list(img_files.keys()):
                im_file = img_files[stem]
                try:
                    with Image.open(im_file) as im:
                        img_resolutions[im.size] += 1
                        img_channels[im.mode] += 1
                except Exception as e:
                    print(f"Error opening image {im_file}: {e}")
                    
            for stem in list(mask_files.keys()):
                m_file = mask_files[stem]
                try:
                    with Image.open(m_file) as m:
                        mask_resolutions[m.size] += 1
                        mask_channels[m.mode] += 1
                except Exception as e:
                    print(f"Error opening mask {m_file}: {e}")
            
            print(f"  Image resolutions (width, height): {dict(img_resolutions)}")
            print(f"  Image channels/modes: {dict(img_channels)}")
            print(f"  Mask resolutions (width, height): {dict(mask_resolutions)}")
            print(f"  Mask channels/modes: {dict(mask_channels)}")
            
            # Check mask pixel values on sample of 20 masks
            print("  Inspecting mask pixel values (sample of 20):")
            sample_masks = list(mask_files.values())[:20]
            for sm in sample_masks:
                arr = cv2.imread(str(sm), cv2.IMREAD_UNCHANGED)
                if arr is None:
                    continue
                unq = np.unique(arr)
                has_intermediate = len(unq) > 2 or (len(unq) == 2 and not set(unq).issubset({0, 1, 255}))
                print(f"    {sm.name}: shape={arr.shape}, dtype={arr.dtype}, min={arr.min()}, max={arr.max()}, unq_len={len(unq)}, unq[:5]={unq[:5]}, unq[-5:]={unq[-5:]}")
                break # Just print one detailed, test others below
            
            # Check all masks for intermediate values
            jpeg_compression_artifacts = 0
            binary_0_255 = 0
            binary_0_1 = 0
            all_zero = 0
            other_types = 0
            for sm in mask_files.values():
                arr = cv2.imread(str(sm), cv2.IMREAD_GRAYSCALE)
                if arr is None:
                    continue
                unq = np.unique(arr)
                if len(unq) == 1 and unq[0] == 0:
                    all_zero += 1
                elif set(unq) == {0, 255}:
                    binary_0_255 += 1
                elif set(unq) == {0, 1}:
                    binary_0_1 += 1
                elif len(unq) > 2:
                    jpeg_compression_artifacts += 1
                else:
                    other_types += 1
            print(f"  Mask value distribution across all {len(mask_files)} masks:")
            print(f"    Strict binary (0, 255): {binary_0_255}")
            print(f"    Strict binary (0, 1): {binary_0_1}")
            print(f"    All zero: {all_zero}")
            print(f"    Non-binary / JPEG artifact masks (>2 unique values): {jpeg_compression_artifacts}")
            print(f"    Other unique sets: {other_types}")

analyze_centers()
