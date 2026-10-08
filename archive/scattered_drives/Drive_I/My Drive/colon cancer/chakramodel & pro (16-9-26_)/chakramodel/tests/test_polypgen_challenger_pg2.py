"""
Independent Empirical Challenger Test Suite for PolypGen Dataset Integrity
Challenger PG 2 - Teamwork Empirical Verification Harness
Target dataset: J:\\My Drive\\DATASET FOR CHAKRAMODEL BY ANTI\\PolypGen\\extracted\\PolypGen2021_MultiCenterData_v3
Target report: m:\\chakramodel\\POLYPGEN_INTEGRITY_REPORT.md
"""

import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageFile
import numpy as np

# Ensure strict truncation enforcement
ImageFile.LOAD_TRUNCATED_IMAGES = False

DATASET_ROOT = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")

def decode_image_file(file_path: Path):
    """
    Independently verify physical readability and decompression of an image.
    Returns: (is_valid, error_msg, size_bytes, dimensions, mode)
    """
    try:
        size = file_path.stat().st_size
        if size == 0:
            return False, "Zero byte file", 0, None, None
            
        with Image.open(file_path) as im:
            im.verify()
            
        with Image.open(file_path) as im:
            im.load()
            dims = im.size
            mode = im.mode
            
        return True, None, size, dims, mode
    except Exception as e:
        return False, str(e), 0, None, None


def test_census_and_frame_counts():
    """Task 1a: Verify total frame counts (8,037 total: 3,762 positive + 4,275 negative)."""
    print("\n[RUNNING TEST 1a] Census and Frame Counts...")
    assert DATASET_ROOT.exists(), f"Dataset root not found: {DATASET_ROOT}"
    
    # 1. Single frames C1 - C6
    single_counts = {}
    for c in range(1, 7):
        c_tag = f"C{c}"
        c_dir = DATASET_ROOT / f"data_{c_tag}"
        imgs = list((c_dir / f"images_{c_tag}").glob("*.jpg"))
        masks = list((c_dir / f"masks_{c_tag}").glob("*.jpg"))
        bboxes = list((c_dir / f"bbox_{c_tag}").glob("*.txt"))
        overlay_name = f"bbox_images_C6" if c == 6 else f"bbox_image_{c_tag}"
        overlays = list((c_dir / overlay_name).glob("*.jpg"))
        single_counts[c_tag] = {
            "images": len(imgs),
            "masks": len(masks),
            "bboxes": len(bboxes),
            "overlays": len(overlays)
        }
    
    total_single_images = sum(v["images"] for v in single_counts.values())
    total_single_masks = sum(v["masks"] for v in single_counts.values())
    total_single_bboxes = sum(v["bboxes"] for v in single_counts.values())
    total_single_overlays = sum(v["overlays"] for v in single_counts.values())
    
    assert total_single_images == 1537, f"Expected 1,537 single images, got {total_single_images}"
    assert total_single_masks == 1537, f"Expected 1,537 single masks, got {total_single_masks}"
    assert total_single_bboxes == 1473, f"Expected 1,473 single bboxes, got {total_single_bboxes}"
    assert total_single_overlays == 1474, f"Expected 1,474 single overlays, got {total_single_overlays}"
    
    # 2. Positive sequences seq1 - seq23
    pos_seq_counts = {}
    pos_root = DATASET_ROOT / "sequenceData" / "positive"
    for s in range(1, 24):
        s_tag = f"seq{s}"
        s_dir = pos_root / s_tag
        imgs = list((s_dir / f"images_{s_tag}").glob("*.jpg"))
        masks = list((s_dir / f"masks_{s_tag}").glob("*.jpg"))
        bboxes = list((s_dir / f"bbox_{s_tag}").glob("*.txt"))
        overlays = list((s_dir / f"bbox_image_{s_tag}").glob("*.jpg"))
        pos_seq_counts[s_tag] = {
            "images": len(imgs),
            "masks": len(masks),
            "bboxes": len(bboxes),
            "overlays": len(overlays)
        }
        
    total_pos_seq_images = sum(v["images"] for v in pos_seq_counts.values())
    total_pos_seq_masks = sum(v["masks"] for v in pos_seq_counts.values())
    total_pos_seq_bboxes = sum(v["bboxes"] for v in pos_seq_counts.values())
    total_pos_seq_overlays = sum(v["overlays"] for v in pos_seq_counts.values())
    
    assert total_pos_seq_images == 2225, f"Expected 2,225 pos seq images, got {total_pos_seq_images}"
    assert total_pos_seq_masks == 2225, f"Expected 2,225 pos seq masks, got {total_pos_seq_masks}"
    assert total_pos_seq_bboxes == 2225, f"Expected 2,225 pos seq bboxes, got {total_pos_seq_bboxes}"
    assert total_pos_seq_overlays == 2225, f"Expected 2,225 pos seq overlays, got {total_pos_seq_overlays}"
    
    # Positive total
    total_positive_frames = total_single_images + total_pos_seq_images
    assert total_positive_frames == 3762, f"Expected 3,762 positive frames, got {total_positive_frames}"
    
    # 3. Pooled imagesAll_positive reconciliation
    pooled_dir = DATASET_ROOT / "imagesAll_positive"
    pooled_imgs = list(pooled_dir.glob("*.jpg"))
    assert len(pooled_imgs) == 3762, f"Expected 3,762 pooled images, got {len(pooled_imgs)}"
    
    pooled_names = {f.name for f in pooled_imgs}
    single_names = set()
    for c in range(1, 7):
        single_names.update(f.name for f in (DATASET_ROOT / f"data_C{c}" / f"images_C{c}").glob("*.jpg"))
    pos_seq_names = set()
    for s in range(1, 24):
        pos_seq_names.update(f.name for f in (pos_root / f"seq{s}" / f"images_seq{s}").glob("*.jpg"))
        
    combined_positive = single_names | pos_seq_names
    assert single_names.isdisjoint(pos_seq_names), "Overlap between single and sequence frame names!"
    assert pooled_names == combined_positive, "Mismatch between pooled images and (single | sequence)!"
    
    # 4. Negative sequences
    neg_root = DATASET_ROOT / "sequenceData" / "negativeOnly"
    neg_counts = {}
    for s in range(1, 24):
        s_tag = f"seq{s}_neg"
        s_dir = neg_root / s_tag
        imgs = list(s_dir.glob("*.jpg"))
        masks = list(s_dir.glob("*mask*"))
        bboxes = list(s_dir.glob("*.txt"))
        neg_counts[s_tag] = len(imgs)
        assert len(masks) == 0, f"Negative sequence {s_tag} has masks!"
        assert len(bboxes) == 0, f"Negative sequence {s_tag} has bboxes!"
        
    total_neg_images = sum(neg_counts.values())
    assert total_neg_images == 4275, f"Expected 4,275 negative images, got {total_neg_images}"
    
    # Grand total frames
    total_dataset_frames = total_positive_frames + total_neg_images
    assert total_dataset_frames == 8037, f"Expected 8,037 total frames, got {total_dataset_frames}"
    
    print(f"  [PASS] Single frames: {total_single_images}")
    print(f"  [PASS] Positive sequence frames: {total_pos_seq_images}")
    print(f"  [PASS] Total positive frames: {total_positive_frames}")
    print(f"  [PASS] Total pooled imagesAll_positive: {len(pooled_imgs)} (100% exact set identity)")
    print(f"  [PASS] Negative frames: {total_neg_images} (0 masks, 0 bboxes)")
    print(f"  [PASS] Grand total dataset frames: {total_dataset_frames}")


def test_center_c3_missing_bboxes_and_masks():
    """Task 1c: Verify 64 missing bboxes in C3 and confirm corresponding masks are non-empty/positive polyps."""
    print("\n[RUNNING TEST 1c] Center C3 64 Missing Bboxes and Mask Verification...")
    c3_dir = DATASET_ROOT / "data_C3"
    imgs = {f.stem: f for f in (c3_dir / "images_C3").glob("*.jpg")}
    masks = {f.stem: f for f in (c3_dir / "masks_C3").glob("*.jpg")}
    bboxes = {f.stem: f for f in (c3_dir / "bbox_C3").glob("*.txt")}
    overlays = {f.stem: f for f in (c3_dir / "bbox_image_C3").glob("*.jpg")}
    
    assert len(imgs) == 457, f"Expected 457 images in C3, got {len(imgs)}"
    assert len(masks) == 457, f"Expected 457 masks in C3, got {len(masks)}"
    assert len(bboxes) == 393, f"Expected 393 bboxes in C3, got {len(bboxes)}"
    assert len(overlays) == 393, f"Expected 393 overlays in C3, got {len(overlays)}"
    
    # Find exact missing bboxes
    missing = []
    for stem, img_path in sorted(imgs.items()):
        if stem not in bboxes:
            missing.append((stem, img_path))
            
    assert len(missing) == 64, f"Expected exactly 64 missing bboxes in C3, got {len(missing)}"
    
    # Inspect corresponding masks
    mask_stats = []
    for stem, img_path in missing:
        # Check standard stem_mask or handle trailing underscore (C3_EndoCV2021_00489_)
        candidates = [f"{stem}_mask", f"{stem[:-1]}_mask" if stem.endswith("_") else None]
        m_file = None
        for cand in candidates:
            if cand and cand in masks:
                m_file = masks[cand]
                break
                
        assert m_file is not None, f"Mask for missing bbox stem '{stem}' NOT FOUND in masks_C3!"
        
        with Image.open(m_file) as mim:
            arr = np.array(mim.convert("L"))
            max_v = int(arr.max())
            pos_count = int((arr > 127).sum())
            mask_stats.append((stem, m_file.name, max_v, pos_count, arr.shape))
            
    # Assert all masks are positive
    assert all(stat[2] > 0 for stat in mask_stats), "Found mask with max == 0 among C3 missing bboxes!"
    assert all(stat[3] > 0 for stat in mask_stats), "Found mask with 0 positive pixels (>127)!"
    
    min_poly_pixels = min(stat[3] for stat in mask_stats)
    max_poly_pixels = max(stat[3] for stat in mask_stats)
    mean_poly_pixels = sum(stat[3] for stat in mask_stats) / len(mask_stats)
    
    print(f"  [PASS] Exactly 64 images missing bboxes in C3.")
    print(f"  [PASS] Exactly 64 corresponding masks exist in masks_C3 (100% presence).")
    print(f"  [PASS] All 64 masks are positive non-empty polyps (100% positive).")
    print(f"         Min polyp size: {min_poly_pixels} px, Max: {max_poly_pixels} px, Mean: {mean_poly_pixels:.1f} px.")
    print(f"  [PASS] Edge case C3_EndoCV2021_00489_ resolved: mask is C3_EndoCV2021_00489_mask.jpg.")


def test_center_c1_orphan_overlay():
    """Task 1d: Verify orphan overlay file 957OLCV1_100H0002_mask_bbox.jpg in C1."""
    print("\n[RUNNING TEST 1d] Center C1 Orphan Overlay Verification...")
    c1_dir = DATASET_ROOT / "data_C1"
    orphan_path = c1_dir / "bbox_image_C1" / "957OLCV1_100H0002_mask_bbox.jpg"
    
    assert orphan_path.exists(), f"Orphan overlay file not found: {orphan_path}"
    
    # Readability and metadata
    is_valid, err, size, dims, mode = decode_image_file(orphan_path)
    assert is_valid, f"Orphan file failed decoding: {err}"
    assert size == 330729, f"Expected size 330,729 bytes, got {size}"
    assert dims == (1350, 1080), f"Expected dimensions (1350, 1080), got {dims}"
    assert mode == "RGB", f"Expected RGB mode, got {mode}"
    
    # Check absence of matching source image, mask, and bbox
    matching_img = c1_dir / "images_C1" / "957OLCV1_100H0002.jpg"
    matching_mask = c1_dir / "masks_C1" / "957OLCV1_100H0002_mask.jpg"
    matching_bbox = c1_dir / "bbox_C1" / "957OLCV1_100H0002_mask.txt"
    
    assert not matching_img.exists(), f"Unexpected source image found: {matching_img}"
    assert not matching_mask.exists(), f"Unexpected mask found: {matching_mask}"
    assert not matching_bbox.exists(), f"Unexpected bbox found: {matching_bbox}"
    
    # Check total overlays in C1 vs images in C1
    img_count = len(list((c1_dir / "images_C1").glob("*.jpg")))
    overlay_count = len(list((c1_dir / "bbox_image_C1").glob("*.jpg")))
    assert img_count == 256, f"Expected 256 images in C1, got {img_count}"
    assert overlay_count == 257, f"Expected 257 overlays in C1, got {overlay_count}"
    assert overlay_count == img_count + 1, "Overlay count should be exactly img_count + 1"
    
    print(f"  [PASS] Orphan file exists: {orphan_path.name}")
    print(f"  [PASS] File is 100% readable: size={size} bytes, dims={dims}, mode={mode}")
    print(f"  [PASS] Confirmed 0 matching source images, 0 matching masks, 0 matching bboxes in C1.")
    print(f"  [PASS] C1 overlay count is exactly 257 vs 256 images (1 orphan).")


def test_rogue_text_files_and_adversarial_mismatches():
    """Task 1e & Adversarial Challenge: Verify 184 rogue text files and discover bbox content divergences."""
    print("\n[RUNNING TEST 1e & ADVERSARIAL CHALLENGE] Rogue Text Files in Sequence Masks...")
    pos_root = DATASET_ROOT / "sequenceData" / "positive"
    
    rogue_counts = {}
    for s in range(1, 24):
        s_tag = f"seq{s}"
        m_dir = pos_root / s_tag / f"masks_{s_tag}"
        txts = list(m_dir.glob("*.txt"))
        if txts:
            rogue_counts[s_tag] = len(txts)
            
    assert rogue_counts == {"seq2": 63, "seq7": 48, "seq8": 73}, f"Unexpected rogue counts: {rogue_counts}"
    total_rogue = sum(rogue_counts.values())
    assert total_rogue == 184, f"Expected 184 rogue txt files, got {total_rogue}"
    
    # Adversarial Challenge: Compare contents of rogue text files with official bbox files
    mismatches = []
    identical_count = 0
    
    for s_tag, count in rogue_counts.items():
        m_dir = pos_root / s_tag / f"masks_{s_tag}"
        b_dir = pos_root / s_tag / f"bbox_{s_tag}"
        
        for m_txt in m_dir.glob("*.txt"):
            stem = m_txt.name.replace("_mask.txt", "")
            b_txt = b_dir / f"{stem}.txt"
            assert b_txt.exists(), f"Official bbox file does not exist for rogue text: {b_txt}"
            
            c_mask = m_txt.read_text(encoding="utf-8").strip()
            c_bbox = b_txt.read_text(encoding="utf-8").strip()
            
            if c_mask != c_bbox:
                # Load corresponding mask image to establish ground truth
                mask_img_file = m_dir / f"{stem}_mask.jpg"
                with Image.open(mask_img_file) as mim:
                    arr = np.array(mim.convert("L"))
                    pos_pixels = int((arr > 127).sum())
                    
                mismatches.append({
                    "seq": s_tag,
                    "stem": stem,
                    "mask_txt": c_mask,
                    "bbox_txt": c_bbox,
                    "actual_mask_pos_pixels": pos_pixels
                })
            else:
                identical_count += 1
                
    print(f"  [PASS] Total rogue .txt files in masks: exactly 184 (seq2: 63, seq7: 48, seq8: 73).")
    print(f"  [EMPIRICAL CHALLENGE FINDING]:")
    print(f"         Identical files: {identical_count} / 184.")
    print(f"         DIVERGENT files: {len(mismatches)} / 184.")
    
    assert len(mismatches) == 5, f"Expected exactly 5 divergent files, got {len(mismatches)}"
    for m in mismatches:
        print(f"         * [{m['seq']}] {m['stem']}:")
        print(f"           - In masks_{m['seq']}: {repr(m['mask_txt'])}")
        print(f"           - In bbox_{m['seq']}:  {repr(m['bbox_txt'])}")
        print(f"           - Actual mask pos pixels: {m['actual_mask_pos_pixels']}")
        
    print(f"  [CONCLUSION]: POLYPGEN_INTEGRITY_REPORT.md line 204 claims these files are identical.")
    print(f"                Our empirical audit refutes this claim: 5 files diverge due to preprocessing artifacts.")
    print(f"                This makes ignoring rogue files in dataloaders even more critical.")


def test_independent_image_readability_decoding():
    """Task 1b: Full physical image decoding scan across target partitions and random samples."""
    print("\n[RUNNING TEST 1b] Physical Image Readability & Decoding Scan...")
    
    # Collect files to audit:
    # 1. 100% of single frames (images, masks, overlays across C1-C6) -> 4,548 files
    # 2. 100% of C3 (all 457 images, 457 masks, 393 overlays) -> included in above
    # 3. 100% of orphan overlay -> included in above
    # 4. Stratified sample across all 23 positive sequences (50 frames each, or all if < 50)
    # 5. Stratified sample across all 23 negative sequences (50 frames each)
    # 6. Sample of pooled imagesAll_positive (200 frames)
    
    files_to_test = []
    
    # All single frame visual files
    for c in range(1, 7):
        c_tag = f"C{c}"
        c_dir = DATASET_ROOT / f"data_{c_tag}"
        files_to_test.extend((c_dir / f"images_{c_tag}").glob("*.jpg"))
        files_to_test.extend((c_dir / f"masks_{c_tag}").glob("*.jpg"))
        overlay_name = f"bbox_images_C6" if c == 6 else f"bbox_image_{c_tag}"
        files_to_test.extend((c_dir / overlay_name).glob("*.jpg"))
        
    single_count = len(files_to_test)
    print(f"  Single frame visual files queued: {single_count} files (100% full scan).")
    
    # Positive sequences (sample 50 per sequence: images, masks, overlays)
    pos_seq_files = []
    pos_root = DATASET_ROOT / "sequenceData" / "positive"
    for s in range(1, 24):
        s_tag = f"seq{s}"
        s_dir = pos_root / s_tag
        imgs = sorted(list((s_dir / f"images_{s_tag}").glob("*.jpg")))[:50]
        masks = sorted(list((s_dir / f"masks_{s_tag}").glob("*.jpg")))[:50]
        overlays = sorted(list((s_dir / f"bbox_image_{s_tag}").glob("*.jpg")))[:50]
        pos_seq_files.extend(imgs + masks + overlays)
    print(f"  Positive sequence visual files queued: {len(pos_seq_files)} files (stratified sample).")
    files_to_test.extend(pos_seq_files)
    
    # Negative sequences (sample 50 per sequence)
    neg_seq_files = []
    neg_root = DATASET_ROOT / "sequenceData" / "negativeOnly"
    for s in range(1, 24):
        s_tag = f"seq{s}_neg"
        imgs = sorted(list((neg_root / s_tag).glob("*.jpg")))[:50]
        neg_seq_files.extend(imgs)
    print(f"  Negative sequence visual files queued: {len(neg_seq_files)} files (stratified sample).")
    files_to_test.extend(neg_seq_files)
    
    # Pooled images sample
    pooled_files = sorted(list((DATASET_ROOT / "imagesAll_positive").glob("*.jpg")))[:200]
    print(f"  Pooled images queued: {len(pooled_files)} files (sample).")
    files_to_test.extend(pooled_files)
    
    total_scan = len(files_to_test)
    print(f"  Total independent decoding test set: {total_scan} visual files.")
    
    t0 = time.time()
    corrupted = []
    passed = 0
    
    with ThreadPoolExecutor(max_workers=16) as executor:
        future_to_file = {executor.submit(decode_image_file, f): f for f in files_to_test}
        for future in as_completed(future_to_file):
            f = future_to_file[future]
            is_valid, err, size, dims, mode = future.result()
            if is_valid:
                passed += 1
            else:
                corrupted.append((str(f), err))
                
    elapsed = time.time() - t0
    rate = total_scan / elapsed if elapsed > 0 else 0
    print(f"  Decoding scan completed in {elapsed:.2f}s ({rate:.1f} files/sec).")
    print(f"  Passed: {passed}/{total_scan}")
    print(f"  Corrupted / Unreadable: {len(corrupted)}")
    
    assert len(corrupted) == 0, f"Detected corrupted files: {corrupted}"
    print(f"  [PASS] 0 corrupted files detected across {total_scan} audited visual files.")


def main():
    print("================================================================================")
    print("  POLYPGEN DATASET INDEPENDENT EMPIRICAL CHALLENGER TEST SUITE (CHALLENGER PG 2)")
    print("================================================================================")
    t_start = time.time()
    
    test_census_and_frame_counts()
    test_center_c3_missing_bboxes_and_masks()
    test_center_c1_orphan_overlay()
    test_rogue_text_files_and_adversarial_mismatches()
    test_independent_image_readability_decoding()
    
    total_time = time.time() - t_start
    print("\n================================================================================")
    print(f"  ALL EMPIRICAL TESTS EXECUTED AND PASSED IN {total_time:.2f}s.")
    print("================================================================================")

if __name__ == "__main__":
    main()
