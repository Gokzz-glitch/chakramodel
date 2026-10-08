#!/usr/bin/env python3
"""
Setup Complete Mock Dataset Skeleton for End-to-End CLI Verification Testing
Author: Challenger 1 (Milestone 3)
"""

import os
from pathlib import Path
import random
import shutil

def setup_full_mock():
    base = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\.agents\challenger_m3_1\fixtures\mock_dataset")
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    
    dataset_dir = base / "PolypGen2021_MultiCenterData_v3"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    src_img = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\data_C1\images_C1\100H0050.jpg")
    src_mask = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\data_C1\masks_C1\100H0050_mask.jpg")
    
    valid_bytes = src_img.read_bytes()
    mask_bytes = src_mask.read_bytes()
    total_len = len(valid_bytes)
    
    # 1. Centers C1 to C6
    for c in range(1, 7):
        c_dir = dataset_dir / f"data_C{c}"
        img_dir = c_dir / f"images_C{c}"
        mask_dir = c_dir / f"masks_C{c}"
        bbox_dir = c_dir / f"bbox_C{c}"
        bbox_img_dir = c_dir / (f"bbox_images_C{c}" if c == 6 else f"bbox_image_C{c}")
        
        img_dir.mkdir(parents=True, exist_ok=True)
        mask_dir.mkdir(parents=True, exist_ok=True)
        bbox_dir.mkdir(parents=True, exist_ok=True)
        bbox_img_dir.mkdir(parents=True, exist_ok=True)
        
        if c == 1:
            # Put corrupt fixtures in C1
            # Valid image
            (img_dir / "sample_01_valid.jpg").write_bytes(valid_bytes)
            (mask_dir / "sample_01_valid_mask.jpg").write_bytes(mask_bytes)
            
            # Zero-byte image
            (img_dir / "sample_02_zero_byte.jpg").write_bytes(b"")
            (mask_dir / "sample_02_zero_byte_mask.jpg").write_bytes(mask_bytes)
            
            # Random garbage
            random.seed(999)
            garbage = bytes([random.randint(0, 255) for _ in range(4096)])
            (img_dir / "sample_03_garbage.jpg").write_bytes(garbage)
            (mask_dir / "sample_03_garbage_mask.jpg").write_bytes(mask_bytes)
            
            # Truncated
            (img_dir / "sample_04_truncated.jpg").write_bytes(valid_bytes[:20000])
            (mask_dir / "sample_04_truncated_mask.jpg").write_bytes(mask_bytes)
            
            # Corrupted middle bytes (with invalid marker)
            mid_bytes = bytearray(valid_bytes)
            mid_bytes[total_len // 2 : total_len // 2 + 2] = b"\xff\x25"
            (img_dir / "sample_05_corrupt_mid.jpg").write_bytes(mid_bytes)
            (mask_dir / "sample_05_corrupt_mid_mask.jpg").write_bytes(mask_bytes)
            
            # Corrupted end bytes
            end_bytes = bytearray(valid_bytes[:-1000])
            end_bytes.extend(bytes([random.randint(0, 255) for _ in range(1000)]))
            (img_dir / "sample_06_corrupt_end.jpg").write_bytes(end_bytes)
            (mask_dir / "sample_06_corrupt_end_mask.jpg").write_bytes(mask_bytes)
            
            # Subtle middle bytes corruption (silent bypass case)
            subtle = bytearray(valid_bytes)
            for i in range(total_len // 2, total_len // 2 + 4000):
                subtle[i] = 0x00 if (i % 2 == 0) else random.randint(1, 255)
            (img_dir / "sample_07_subtle_corrupt_mid.jpg").write_bytes(subtle)
            (mask_dir / "sample_07_subtle_corrupt_mid_mask.jpg").write_bytes(mask_bytes)
        else:
            # Minimal valid sample
            (img_dir / f"sample_C{c}.jpg").write_bytes(valid_bytes)
            (mask_dir / f"sample_C{c}_mask.jpg").write_bytes(mask_bytes)

    # 2. sequenceData
    seq_dir = dataset_dir / "sequenceData"
    neg_dir = seq_dir / "negativeOnly" / "seq1_neg"
    neg_dir.mkdir(parents=True, exist_ok=True)
    (neg_dir / "neg_frame_01.jpg").write_bytes(valid_bytes)
    
    pos_dir = seq_dir / "positive" / "seq1"
    pos_img_dir = pos_dir / "images_seq1"
    pos_mask_dir = pos_dir / "masks_seq1"
    pos_bbox_dir = pos_dir / "bbox_seq1"
    pos_bbox_img_dir = pos_dir / "bbox_image_seq1"
    
    pos_img_dir.mkdir(parents=True, exist_ok=True)
    pos_mask_dir.mkdir(parents=True, exist_ok=True)
    pos_bbox_dir.mkdir(parents=True, exist_ok=True)
    pos_bbox_img_dir.mkdir(parents=True, exist_ok=True)
    
    (pos_img_dir / "pos_frame_01.jpg").write_bytes(valid_bytes)
    (pos_mask_dir / "pos_frame_01_mask.jpg").write_bytes(mask_bytes)

    # 3. imagesAll_positive
    pool_dir = dataset_dir / "imagesAll_positive"
    pool_dir.mkdir(parents=True, exist_ok=True)
    (pool_dir / "sample_01_valid.jpg").write_bytes(valid_bytes)
    (pool_dir / "pos_frame_01.jpg").write_bytes(valid_bytes)

    # 4. codes & dataDetails
    (dataset_dir / "codes").mkdir(parents=True, exist_ok=True)
    for sc in ["convert2vocFromMask.py", "extract_PolypBoxes.py", "trainingDataAnalysis.py"]:
        (dataset_dir / "codes" / sc).write_text("# mock script")
    
    (dataset_dir / "dataDetails_PolypGen_SingleFrames").mkdir(parents=True, exist_ok=True)
    for i in range(1, 6):
        (dataset_dir / "dataDetails_PolypGen_SingleFrames" / f"dataDetails_C{i}.csv").write_text("mock,csv")

    # 5. Empty subdirectory inside dataset root
    empty_sub = dataset_dir / "anomalous_empty_subdir"
    empty_sub.mkdir(parents=True, exist_ok=True)

    print("Full mock skeleton created successfully.")

if __name__ == "__main__":
    setup_full_mock()
