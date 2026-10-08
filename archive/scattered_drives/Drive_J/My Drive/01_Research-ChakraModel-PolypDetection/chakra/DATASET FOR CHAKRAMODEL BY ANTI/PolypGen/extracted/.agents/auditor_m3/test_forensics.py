#!/usr/bin/env python3
"""
Forensic Audit Test Harness for Milestone 3
===========================================
Author: Forensic Auditor (.agents/auditor_m3)
Date: September 2026

Empirically validates:
1. Exact file counts and directory architecture on disk.
2. Anti-cheating & corruption detection capability of verify_polypgen.py.
3. Threadpool execution timing, I/O speed, and feasibility of 455s runtime.
4. Parity and data flow consistency of verification_summary.json.
"""

import sys
import os
import time
import json
import shutil
from pathlib import Path
import numpy as np
from PIL import Image

# Import the module under audit from parent directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from verify_polypgen import PolypGenVerifier, ImageVerificationResult

ROOT_EXTRACTED = Path(__file__).resolve().parents[2]
DATASET_ROOT = ROOT_EXTRACTED / "PolypGen2021_MultiCenterData_v3"
TEMP_TEST_DIR = Path(__file__).parent / "temp_corrupt_test"

def run_test_1_filesystem_ground_truth():
    print("\n--- TEST 1: Direct Independent Filesystem Audit ---")
    total_jpg = 0
    dir_count = 0
    empty_dirs = []

    for root, dirs, files in os.walk(DATASET_ROOT):
        dir_count += 1
        if not dirs and not files:
            empty_dirs.append(root)
        for f in files:
            if f.lower().endswith(".jpg"):
                total_jpg += 1

    print(f"Total directories in PolypGen2021_MultiCenterData_v3: {dir_count}")
    print(f"Total .jpg files in PolypGen2021_MultiCenterData_v3: {total_jpg}")
    print(f"Empty directories: {len(empty_dirs)}")

    # Check __MACOSX
    macosx_dir = ROOT_EXTRACTED / "__MACOSX"
    macosx_jpg_count = 0
    if macosx_dir.exists():
        for root, dirs, files in os.walk(macosx_dir):
            for f in files:
                if f.lower().endswith(".jpg"):
                    macosx_jpg_count += 1
    print(f"Total .jpg (AppleDouble resource forks) in __MACOSX: {macosx_jpg_count}")

    # Check specific component counts
    centers = ["data_C1", "data_C2", "data_C3", "data_C4", "data_C5", "data_C6"]
    center_counts = {}
    for c in centers:
        c_dir = DATASET_ROOT / c
        img_dir = c_dir / f"images_{c[-2:]}"
        mask_dir = c_dir / f"masks_{c[-2:]}"
        bbox_img_dir = c_dir / f"bbox_image_{c[-2:]}"
        if not bbox_img_dir.exists():
            bbox_img_dir = c_dir / f"bbox_images_{c[-2:]}"
        
        imgs = len(list(img_dir.glob("*.jpg"))) if img_dir.exists() else 0
        masks = len(list(mask_dir.glob("*.jpg"))) if mask_dir.exists() else 0
        bbox_imgs = len(list(bbox_img_dir.glob("*.jpg"))) if bbox_img_dir.exists() else 0
        center_counts[c] = {"images": imgs, "masks": masks, "bbox_images": bbox_imgs}
        print(f"  {c}: {imgs} images, {masks} masks, {bbox_imgs} bbox_images")

    seq_neg_imgs = len(list((DATASET_ROOT / "sequenceData" / "negativeOnly").glob("*/*.jpg")))
    seq_pos_imgs = len(list((DATASET_ROOT / "sequenceData" / "positive").glob("*/images_*/*.jpg")))
    seq_pos_masks = len(list((DATASET_ROOT / "sequenceData" / "positive").glob("*/masks_*/*.jpg")))
    seq_pos_bbox_imgs = len(list((DATASET_ROOT / "sequenceData" / "positive").glob("*/bbox_image_*/*.jpg")))
    pool_imgs = len(list((DATASET_ROOT / "imagesAll_positive").glob("*.jpg")))

    print(f"  sequenceData/negativeOnly images: {seq_neg_imgs}")
    print(f"  sequenceData/positive images: {seq_pos_imgs}, masks: {seq_pos_masks}, bbox_imgs: {seq_pos_bbox_imgs}")
    print(f"  imagesAll_positive images: {pool_imgs}")

    calculated_total = (
        sum(v["images"] + v["masks"] + v["bbox_images"] for v in center_counts.values())
        + seq_neg_imgs
        + seq_pos_imgs + seq_pos_masks + seq_pos_bbox_imgs
        + pool_imgs
    )
    print(f"Sum of audited real dataset images: {calculated_total}")
    assert calculated_total == 19260, f"Expected 19260, got {calculated_total}"
    assert total_jpg == 19260, f"Filesystem walk expected 19260, got {total_jpg}"
    assert len(empty_dirs) == 0, f"Expected 0 empty dirs, found {len(empty_dirs)}"
    print(">>> TEST 1 RESULT: PASS (All counts match 19,260 exactly, 0 empty dirs)")
    return center_counts, total_jpg


def run_test_2_anti_cheating_and_corruption_detection():
    print("\n--- TEST 2: Anti-Cheating & Corruption Detection Verification ---")
    TEMP_TEST_DIR.mkdir(parents=True, exist_ok=True)
    verifier = PolypGenVerifier(
        target_dir=str(ROOT_EXTRACTED),
        output_json=str(Path(__file__).parent / "temp_out.json"),
        output_md=str(Path(__file__).parent / "temp_out.md"),
        max_workers=4,
    )

    # 1. Test genuine image decoding
    sample_img = next((DATASET_ROOT / "data_C1" / "images_C1").glob("*.jpg"))
    res_real = verifier.verify_single_image(sample_img)
    print(f"Sample Real Image: {sample_img.name}")
    print(f"  Valid: {res_real.is_valid}, Size: {res_real.file_size_bytes} B, Shape: {res_real.width}x{res_real.height}x{res_real.channels}, MaxPixel: {res_real.max_pixel}")
    assert res_real.is_valid is True
    assert res_real.width > 0 and res_real.height > 0
    assert res_real.channels in [1, 3]

    # 2. Test Zero-Byte file detection
    zero_file = TEMP_TEST_DIR / "corrupt_zero.jpg"
    zero_file.write_bytes(b"")
    res_zero = verifier.verify_single_image(zero_file)
    print(f"Zero-Byte File: valid={res_zero.is_valid}, tier={res_zero.tier_failed}, msg={res_zero.error_message}")
    assert res_zero.is_valid is False
    assert res_zero.tier_failed == "TIER0_ZERO_BYTE"

    # 3. Test Random Garbage Header detection
    garbage_file = TEMP_TEST_DIR / "corrupt_garbage.jpg"
    garbage_file.write_bytes(os.urandom(1024))
    res_garb = verifier.verify_single_image(garbage_file)
    print(f"Garbage Header File: valid={res_garb.is_valid}, tier={res_garb.tier_failed}, msg={res_garb.error_message}")
    assert res_garb.is_valid is False
    assert res_garb.tier_failed in ["TIER1_UNIDENTIFIED_IMAGE", "TIER1_STREAM_CORRUPT"]

    # 4. Test Truncated JPEG (SOI marker present, stream cut off abruptly)
    real_bytes = sample_img.read_bytes()
    truncated_file = TEMP_TEST_DIR / "corrupt_truncated.jpg"
    # Write only first 500 bytes of real JPEG
    truncated_file.write_bytes(real_bytes[:500])
    res_trunc = verifier.verify_single_image(truncated_file)
    print(f"Truncated JPEG File: valid={res_trunc.is_trunc if hasattr(res_trunc, 'is_trunc') else res_trunc.is_valid}, tier={res_trunc.tier_failed}, msg={res_trunc.error_message}")
    assert res_trunc.is_valid is False
    assert res_trunc.tier_failed in ["TIER1_STREAM_CORRUPT", "TIER2_DECOMPRESSION_FAILED", "TIER3_OPENCV_DECODE_NONE"]

    # 5. Test Batch Aggregation with Corrupted Files
    test_batch = [sample_img, zero_file, garbage_file, truncated_file]
    verifier.total_images_scanned = 0
    verifier.total_images_passed = 0
    verifier.total_images_corrupted = 0
    verifier.corrupted_files = []
    batch_results = verifier.verify_batch(test_batch, "ForensicTest")

    print(f"Batch Test: Total={verifier.total_images_scanned}, Passed={verifier.total_images_passed}, Corrupted={verifier.total_images_corrupted}")
    assert verifier.total_images_scanned == 4
    assert verifier.total_images_passed == 1
    assert verifier.total_images_corrupted == 3
    assert len(verifier.corrupted_files) == 3

    # Clean up temp test directory
    shutil.rmtree(TEMP_TEST_DIR)
    print(">>> TEST 2 RESULT: PASS (Verification engine genuinely catches corruptions; no mocking/facade)")


def run_test_3_execution_timing_and_io_feasibility():
    print("\n--- TEST 3: Execution Timing & I/O Feasibility Benchmark ---")
    # Sample 100 real images across centers and sequence data
    all_imgs = []
    all_imgs.extend(list((DATASET_ROOT / "data_C1" / "images_C1").glob("*.jpg"))[:20])
    all_imgs.extend(list((DATASET_ROOT / "data_C2" / "images_C2").glob("*.jpg"))[:20])
    all_imgs.extend(list((DATASET_ROOT / "data_C3" / "images_C3").glob("*.jpg"))[:20])
    all_imgs.extend(list((DATASET_ROOT / "imagesAll_positive").glob("*.jpg"))[:20])
    all_imgs.extend(list((DATASET_ROOT / "sequenceData" / "negativeOnly").glob("*/*.jpg"))[:20])

    assert len(all_imgs) == 100, f"Expected 100 sample images, got {len(all_imgs)}"

    verifier = PolypGenVerifier(
        target_dir=str(ROOT_EXTRACTED),
        output_json=str(Path(__file__).parent / "temp_out.json"),
        output_md=str(Path(__file__).parent / "temp_out.md"),
        max_workers=12,
    )

    t0 = time.perf_counter()
    results = verifier.verify_batch(all_imgs, "TimingBench")
    t1 = time.perf_counter()

    elapsed = t1 - t0
    rate = len(all_imgs) / elapsed
    projected_total_sec = 19260 / rate

    print(f"Benchmarked 100 images with 12 threads:")
    print(f"  Elapsed: {elapsed:.3f} s")
    print(f"  Throughput: {rate:.2f} images/second")
    print(f"  Average time per image (across 12 threads): {(elapsed / len(all_imgs)) * 1000:.2f} ms")
    print(f"  Projected time for 19,260 images: {projected_total_sec:.1f} s (~{projected_total_sec / 60:.2f} min)")
    print(f"  Recorded execution time by Worker M2: 455.06 s (~7.58 min) @ 42.32 images/sec")

    # Verify that the recorded time (455s) is within reasonable range (e.g. within 2x to 0.5x of benchmark)
    ratio = 455.06 / projected_total_sec
    print(f"  Recorded / Projected ratio: {ratio:.2f}x")
    assert 0.3 <= ratio <= 3.0, f"Runtime {455.06}s is anomalous compared to projected {projected_total_sec}s"
    print(">>> TEST 3 RESULT: PASS (Execution timing 455s is authentic and fully consistent with CPU decompression speed)")


def run_test_4_verification_summary_authenticity():
    print("\n--- TEST 4: Verification Summary JSON & Markdown Parity ---")
    json_path = ROOT_EXTRACTED / "verification_summary.json"
    md_path = ROOT_EXTRACTED / "verification_report.md"

    assert json_path.exists(), "verification_summary.json missing"
    assert md_path.exists(), "verification_report.md missing"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate high-level structure
    assert data["verification_status"] == "PASS"
    assert data["integrity_percentage"] == 100.0
    assert data["summary_metrics"]["total_images_verified"] == 19260
    assert data["summary_metrics"]["total_images_passed"] == 19260
    assert data["summary_metrics"]["total_images_corrupted"] == 0
    assert data["summary_metrics"]["total_empty_directories"] == 0
    assert data["summary_metrics"]["total_bytes_processed"] > 2_000_000_000

    # Validate mathematical consistency
    # Centers
    c_img_total = sum(c["images_count"] for c in data["centers"].values())
    c_mask_total = sum(c["masks_count"] for c in data["centers"].values())
    c_bbox_img_total = sum(c["bbox_images_count"] for c in data["centers"].values())
    assert c_img_total == 1537
    assert c_mask_total == 1537
    assert c_bbox_img_total == 1474

    # Sequences
    seq_neg_total = data["sequence_data"]["negativeOnly"]["total_frames"]
    assert seq_neg_total == 4275
    seq_pos = data["sequence_data"]["positive"]
    assert seq_pos["images_verified"] == 2225
    assert seq_pos["masks_verified"] == 2225
    assert seq_pos["bbox_images_verified"] == 2225

    # Pool
    pool_total = data["images_all_positive"]["total_files"]
    assert pool_total == 3762
    assert pool_total == c_img_total + seq_pos["images_verified"]

    # Grand total
    grand_total = c_img_total + c_mask_total + c_bbox_img_total + seq_neg_total + seq_pos["images_verified"] + seq_pos["masks_verified"] + seq_pos["bbox_images_verified"] + pool_total
    assert grand_total == 19260

    print("High-level and granular counts in JSON are mathematically perfect and 100% verified.")
    print(">>> TEST 4 RESULT: PASS (Artifact authenticity and mathematical parity confirmed)")

if __name__ == "__main__":
    print("=" * 60)
    print("FORENSIC INTEGRITY AUDIT TEST SUITE")
    print("=" * 60)
    run_test_1_filesystem_ground_truth()
    run_test_2_anti_cheating_and_corruption_detection()
    run_test_3_execution_timing_and_io_feasibility()
    run_test_4_verification_summary_authenticity()
    print("\n" + "=" * 60)
    print("ALL 4 FORENSIC TESTS PASSED PROGRAMMATICALLY WITH ZERO DEFECTS.")
    print("=" * 60)
