import json
from pathlib import Path
from collections import Counter
import cv2
import numpy as np
from PIL import Image

DATASET_ROOT = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")

def deep_dive():
    print("=== DEEP DIVE INVESTIGATION ===", flush=True)

    # 1. Check C1 extra file in bbox_image_C1
    print("\n--- 1. C1 extra file check ---", flush=True)
    c1_img_p = DATASET_ROOT / "data_C1" / "images_C1"
    c1_bbox_img_p = DATASET_ROOT / "data_C1" / "bbox_image_C1"
    c1_img_names = {f.stem for f in c1_img_p.iterdir() if f.is_file() and not f.name.startswith(".")}
    c1_bbox_img_names = {f.name for f in c1_bbox_img_p.iterdir() if f.is_file() and not f.name.startswith(".")}
    print(f"C1 images count: {len(c1_img_names)}, C1 bbox_images count: {len(c1_bbox_img_names)}")
    # Find which bbox image does not correspond to an image
    orphan_bbox_imgs = []
    for bf in c1_bbox_img_names:
        # standard is stem_mask_bbox.jpg
        orig_stem = bf.replace("_mask_bbox.jpg", "").replace("_bbox.jpg", "")
        if orig_stem not in c1_img_names:
            orphan_bbox_imgs.append((bf, orig_stem))
    print(f"Orphan bbox images in C1: {orphan_bbox_imgs}")

    # 2. Check C3 pairing discrepancy & bbox count
    print("\n--- 2. C3 pairing & bbox discrepancy ---", flush=True)
    c3_img_p = DATASET_ROOT / "data_C3" / "images_C3"
    c3_mask_p = DATASET_ROOT / "data_C3" / "masks_C3"
    c3_bbox_p = DATASET_ROOT / "data_C3" / "bbox_C3"
    
    c3_imgs = {f.stem: f for f in c3_img_p.iterdir() if f.is_file() and not f.name.startswith(".")}
    c3_masks = {f.name: f for f in c3_mask_p.iterdir() if f.is_file() and not f.name.startswith(".")}
    c3_bboxes = {f.stem: f for f in c3_bbox_p.iterdir() if f.is_file() and not f.name.startswith(".")}
    
    # check which image or mask didn't match
    mask_stem_map = {}
    for mf_name in c3_masks:
        if mf_name.endswith("_mask.jpg"):
            stem = mf_name[:-9]
        elif mf_name.endswith(".jpg"):
            stem = mf_name[:-4]
        else:
            stem = mf_name
        mask_stem_map[stem] = mf_name
        
    imgs_without_mask = set(c3_imgs.keys()) - set(mask_stem_map.keys())
    masks_without_img = set(mask_stem_map.keys()) - set(c3_imgs.keys())
    print(f"C3 images without mask: {imgs_without_mask}")
    print(f"C3 masks without image: {masks_without_img}")
    
    # Also check the 1 non-suffix match
    for mf_name in c3_masks:
        if not mf_name.endswith("_mask.jpg"):
            print(f"  Non-standard mask filename in C3: {mf_name}")
            
    # Check bbox vs images in C3 (393 vs 457)
    # Bbox txt names: are they stem.txt or stem_mask.txt?
    bbox_stem_map = {}
    for bf in c3_bboxes:
        stem = bf.replace("_mask", "")
        bbox_stem_map[stem] = bf
    imgs_without_bbox = set(c3_imgs.keys()) - set(bbox_stem_map.keys())
    print(f"C3 images without bbox: count={len(imgs_without_bbox)}, sample={list(imgs_without_bbox)[:5]}")

    # 3. Check sequenceData positive discrepancy (2225 images vs 2409 masks)
    print("\n--- 3. SequenceData positive discrepancy ---", flush=True)
    pos_dir = DATASET_ROOT / "sequenceData" / "positive"
    seq_diffs = []
    for seq_p in sorted(pos_dir.iterdir()):
        if not seq_p.is_dir():
            continue
        subdirs = [d.name for d in seq_p.iterdir() if d.is_dir()]
        img_d = next((d for d in subdirs if d.startswith("images_")), None)
        mask_d = next((d for d in subdirs if d.startswith("masks_")), None)
        bbox_d = next((d for d in subdirs if d.startswith("bbox_") and not d.startswith("bbox_image")), None)
        
        imgs = [f for f in (seq_p / img_d).iterdir() if f.is_file() and not f.name.startswith(".")] if img_d else []
        masks = [f for f in (seq_p / mask_d).iterdir() if f.is_file() and not f.name.startswith(".")] if mask_d else []
        bboxes = [f for f in (seq_p / bbox_d).iterdir() if f.is_file() and not f.name.startswith(".")] if bbox_d else []
        
        if len(imgs) != len(masks):
            seq_diffs.append((seq_p.name, len(imgs), len(masks), len(bboxes)))
            print(f"  {seq_p.name}: images={len(imgs)}, masks={len(masks)}, bboxes={len(bboxes)}")
            # Investigate why: what are mask stems vs image stems?
            img_stems = {f.stem for f in imgs}
            mask_stems = {f.stem.replace("_mask", ""): f.name for f in masks}
            extra_masks = set(mask_stems.keys()) - img_stems
            extra_imgs = img_stems - set(mask_stems.keys())
            if extra_masks:
                print(f"    extra mask stems (sample 5): {list(extra_masks)[:5]}")
            if extra_imgs:
                print(f"    extra img stems (sample 5): {list(extra_imgs)[:5]}")

    # 4. Check RGB mask channels consistency: are R, G, B identical in 3-channel masks?
    print("\n--- 4. Mask channel consistency (R==G==B in RGB masks?) ---", flush=True)
    c1_masks_dir = DATASET_ROOT / "data_C1" / "masks_C1"
    rgb_masks = [f for f in c1_masks_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
    channels_differ_count = 0
    checked_count = 0
    for mf in rgb_masks[:50]:
        im = Image.open(mf)
        if im.mode == "RGB":
            checked_count += 1
            arr = np.array(im)
            r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
            if not (np.array_equal(r, g) and np.array_equal(g, b)):
                channels_differ_count += 1
                diff_rg = np.max(np.abs(r.astype(int) - g.astype(int)))
                diff_gb = np.max(np.abs(g.astype(int) - b.astype(int)))
                print(f"    Difference in channels for {mf.name}: max diff RG={diff_rg}, GB={diff_gb}")
    print(f"Checked {checked_count} RGB masks: {channels_differ_count} had channel differences (due to JPEG chroma subsampling / compression).")

    # 5. Check mask binarization thresholding
    print("\n--- 5. Mask value range & thresholding analysis ---", flush=True)
    threshold_stats = []
    for mf in list(c1_masks_dir.iterdir())[:30]:
        if mf.name.startswith("."):
            continue
        arr = cv2.imread(str(mf), cv2.IMREAD_GRAYSCALE)
        # count pixels in ranges
        total_px = arr.size
        zero_px = np.sum(arr == 0)
        low_noise = np.sum((arr > 0) & (arr < 50))
        mid_noise = np.sum((arr >= 50) & (arr <= 200))
        high_noise = np.sum((arr > 200) & (arr < 255))
        pure_255 = np.sum(arr == 255)
        threshold_stats.append({
            "name": mf.name,
            "zero": zero_px,
            "low": low_noise,
            "mid": mid_noise,
            "high": high_noise,
            "pure_255": pure_255
        })
    print(f"Sample mask stats (first 3): {threshold_stats[:3]}")

if __name__ == "__main__":
    deep_dive()
