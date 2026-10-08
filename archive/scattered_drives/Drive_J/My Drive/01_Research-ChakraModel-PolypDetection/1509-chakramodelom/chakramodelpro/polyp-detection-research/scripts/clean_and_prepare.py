#!/usr/bin/env python3
"""
Data Cleaning & Standardization Pipeline for Polyp Segmentation
================================================================
Cleans, standardizes, and prepares all image-mask datasets for training.

Key operations:
  1. Binarize masks (threshold at 127) to fix JPEG compression artifacts
  2. Verify image-mask spatial alignment
  3. Normalize all masks to PNG format (lossless)
  4. Generate standardized train/val/test manifests (TSV format)
  5. Detect and log anomalies (all-black masks, tiny polyps, etc.)
  6. Compute and save dataset statistics

Usage:
  python scripts/clean_and_prepare.py --data-root data/raw --output-dir data/processed
"""

import argparse
import csv
import hashlib
import json
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np


# ================================================
# Dataset Registry: maps dataset name to its
# internal directory structure conventions
# ================================================
DATASET_REGISTRY = {
    "Kvasir-SEG": {
        "images_subdir": "images",
        "masks_subdir": "masks",
        "image_ext": ".jpg",
        "mask_ext": ".jpg",  # JPEG masks (needs binarization!)
        "expected_count": 1000,
        "role": "primary_train",
        "source": "Simula Research Laboratory",
        "needs_binarization": True,
    },
    "cvc-clinicdb": {
        "images_subdir": "images",
        "masks_subdir": "masks",
        "image_ext": ".jpg",
        "mask_ext": ".png",
        "expected_count": 612,
        "role": "primary_train",
        "source": "CVC Barcelona / chakramodel-evaluation-datasets",
        "needs_binarization": True,  # safety: binarize all masks
    },
    "etis-larib": {
        "images_subdir": "images",
        "masks_subdir": "masks",
        "image_ext": ".jpg",
        "mask_ext": ".png",
        "expected_count": 196,
        "role": "external_test",
        "source": "CVC / MICCAI challenge / chakramodel-evaluation-datasets",
        "needs_binarization": True,
    },
    "CVC-300": {
        "images_subdir": "images",
        "masks_subdir": "masks",
        "image_ext": ".png",
        "mask_ext": ".png",
        "expected_count": 60,
        "role": "external_test",
        "source": "CVC Barcelona / EndoScene",
        "needs_binarization": True,
    },
}


def find_dataset_dir(data_root, dataset_name):
    """
    Search for a dataset directory under data_root.
    Handles nested extraction paths (e.g., extraction creates
    chakramodel-evaluation-datasets/cvc-clinicdb/images/).
    """
    data_root = Path(data_root)
    candidates = []

    # Direct match
    direct = data_root / dataset_name
    if direct.is_dir():
        candidates.append(direct)

    # Search recursively (up to 3 levels deep)
    for level1 in data_root.iterdir():
        if not level1.is_dir():
            continue
        check = level1 / dataset_name
        if check.is_dir():
            candidates.append(check)
        for level2 in level1.iterdir():
            if not level2.is_dir():
                continue
            check = level2 / dataset_name
            if check.is_dir():
                candidates.append(check)

    # Return best candidate (prefer shorter path = less nesting)
    if candidates:
        return min(candidates, key=lambda p: len(str(p)))
    return None


def discover_pairs(dataset_dir, registry_entry):
    """
    Discover image-mask pairs in a dataset directory.
    Returns list of (image_path, mask_path) tuples.
    """
    dataset_dir = Path(dataset_dir)
    img_subdir = registry_entry["images_subdir"]
    mask_subdir = registry_entry["masks_subdir"]

    img_dir = dataset_dir / img_subdir
    mask_dir = dataset_dir / mask_subdir

    if not img_dir.is_dir():
        return [], f"Images directory not found: {img_dir}"
    if not mask_dir.is_dir():
        return [], f"Masks directory not found: {mask_dir}"

    pairs = []
    unmatched = []

    img_files = sorted([f for f in img_dir.iterdir() if f.is_file()])
    for img_f in img_files:
        # Try to find matching mask by stem (ignoring extension)
        mask_candidates = [
            mask_dir / (img_f.stem + ext)
            for ext in [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"]
        ]
        mask_f = None
        for mc in mask_candidates:
            if mc.is_file():
                mask_f = mc
                break
        if mask_f:
            pairs.append((str(img_f), str(mask_f)))
        else:
            unmatched.append(str(img_f))

    if unmatched:
        return pairs, f"WARNING: {len(unmatched)} images without masks"
    return pairs, None


def binarize_mask(mask_path, threshold=127):
    """
    Load a mask and binarize it.
    Returns (binary_mask_uint8, stats_dict).
    """
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return None, {"error": "DECODE_FAILED"}

    original_unique = len(np.unique(mask))
    binary = (mask > threshold).astype(np.uint8) * 255
    binary_unique = len(np.unique(binary))

    # Statistics about the mask
    polyp_pixels = np.sum(binary > 0)
    total_pixels = binary.shape[0] * binary.shape[1]
    polyp_ratio = polyp_pixels / total_pixels if total_pixels > 0 else 0

    stats = {
        "original_unique_values": original_unique,
        "is_originally_binary": original_unique <= 2,
        "polyp_pixel_ratio": round(polyp_ratio, 6),
        "polyp_pixels": int(polyp_pixels),
        "total_pixels": int(total_pixels),
        "is_empty_mask": polyp_pixels == 0,
        "is_tiny_polyp": 0 < polyp_ratio < 0.005,  # less than 0.5% of image
    }

    return binary, stats


def validate_pair(img_path, mask_path):
    """
    Validate that an image-mask pair is spatially consistent.
    Returns (is_valid, error_message).
    """
    img = cv2.imread(str(img_path))
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

    if img is None:
        return False, "IMAGE_DECODE_FAILED"
    if mask is None:
        return False, "MASK_DECODE_FAILED"

    img_h, img_w = img.shape[:2]
    mask_h, mask_w = mask.shape[:2]

    if img_h != mask_h or img_w != mask_w:
        return False, f"DIM_MISMATCH(img={img_w}x{img_h}, mask={mask_w}x{mask_h})"

    return True, None


def clean_dataset(dataset_name, dataset_dir, registry_entry, output_dir, binarize=True):
    """
    Clean and validate a single dataset.
    - Discovers pairs
    - Validates each pair
    - Binarizes masks
    - Saves cleaned masks as PNG to output_dir
    - Returns cleaning report
    """
    print(f"\n{'='*60}")
    print(f"  CLEANING: {dataset_name}")
    print(f"  Source: {dataset_dir}")
    print(f"{'='*60}")

    report = {
        "dataset_name": dataset_name,
        "source_dir": str(dataset_dir),
        "role": registry_entry["role"],
        "expected_count": registry_entry["expected_count"],
        "actual_pairs": 0,
        "valid_pairs": 0,
        "corrupt_images": [],
        "corrupt_masks": [],
        "dimension_mismatches": [],
        "empty_masks": [],
        "tiny_polyps": [],
        "non_binary_masks_fixed": 0,
        "mask_binarization_applied": binarize,
        "cleaning_status": "UNKNOWN",
    }

    # Discover pairs
    pairs, warn = discover_pairs(dataset_dir, registry_entry)
    report["actual_pairs"] = len(pairs)

    if warn:
        print(f"  {warn}")
        report["warnings"] = [warn]

    if not pairs:
        report["cleaning_status"] = "EMPTY"
        print(f"  [X] No pairs found!")
        return report

    print(f"  Found {len(pairs)} image-mask pairs")

    # Prepare output directory for cleaned masks
    clean_mask_dir = Path(output_dir) / "cleaned_masks" / dataset_name
    clean_mask_dir.mkdir(parents=True, exist_ok=True)

    valid = 0
    mask_stats_list = []

    for i, (img_path, mask_path) in enumerate(pairs):
        if (i + 1) % 100 == 0 or i == 0:
            print(f"  Processing {i+1}/{len(pairs)}...", end='\r')

        # Validate pair
        is_valid, error = validate_pair(img_path, mask_path)
        if not is_valid:
            if "IMAGE" in error:
                report["corrupt_images"].append({"path": img_path, "error": error})
            elif "MASK" in error:
                report["corrupt_masks"].append({"path": mask_path, "error": error})
            elif "DIM" in error:
                report["dimension_mismatches"].append({
                    "image": img_path,
                    "mask": mask_path,
                    "error": error,
                })
            continue

        # Binarize mask
        if binarize:
            binary_mask, stats = binarize_mask(mask_path)
            if binary_mask is None:
                report["corrupt_masks"].append({
                    "path": mask_path,
                    "error": stats.get("error", "UNKNOWN"),
                })
                continue

            mask_stats_list.append(stats)

            if not stats["is_originally_binary"]:
                report["non_binary_masks_fixed"] += 1

            if stats["is_empty_mask"]:
                report["empty_masks"].append(img_path)

            if stats["is_tiny_polyp"]:
                report["tiny_polyps"].append({
                    "image": img_path,
                    "polyp_ratio": stats["polyp_pixel_ratio"],
                })

            # Save cleaned binary mask as PNG (lossless)
            mask_filename = Path(mask_path).stem + ".png"
            clean_path = clean_mask_dir / mask_filename
            cv2.imwrite(str(clean_path), binary_mask)

        valid += 1

    print(f"  Processing {len(pairs)}/{len(pairs)}... done")

    report["valid_pairs"] = valid

    # Aggregate mask statistics
    if mask_stats_list:
        ratios = [s["polyp_pixel_ratio"] for s in mask_stats_list]
        report["mask_statistics"] = {
            "mean_polyp_ratio": round(float(np.mean(ratios)), 6),
            "median_polyp_ratio": round(float(np.median(ratios)), 6),
            "min_polyp_ratio": round(float(np.min(ratios)), 6),
            "max_polyp_ratio": round(float(np.max(ratios)), 6),
            "empty_mask_count": len(report["empty_masks"]),
            "tiny_polyp_count": len(report["tiny_polyps"]),
            "non_binary_fixed": report["non_binary_masks_fixed"],
        }

    # Status determination
    if valid == len(pairs) and valid == registry_entry["expected_count"]:
        report["cleaning_status"] = "PERFECT"
    elif valid == len(pairs):
        if valid != registry_entry["expected_count"]:
            report["cleaning_status"] = f"COUNT_MISMATCH(expected={registry_entry['expected_count']}, got={valid})"
        else:
            report["cleaning_status"] = "CLEAN"
    else:
        report["cleaning_status"] = f"ISSUES({len(pairs) - valid} bad pairs)"

    # Print summary
    print(f"\n  SUMMARY:")
    print(f"  Expected:          {registry_entry['expected_count']}")
    print(f"  Found pairs:       {len(pairs)}")
    print(f"  Valid pairs:       {valid}")
    print(f"  Corrupt images:    {len(report['corrupt_images'])}")
    print(f"  Corrupt masks:     {len(report['corrupt_masks'])}")
    print(f"  Dim mismatches:    {len(report['dimension_mismatches'])}")
    print(f"  Empty masks:       {len(report['empty_masks'])}")
    print(f"  Tiny polyps:       {len(report['tiny_polyps'])}")
    print(f"  Non-binary fixed:  {report['non_binary_masks_fixed']}")
    print(f"  Clean masks saved: {clean_mask_dir}")
    print(f"  Status:            {report['cleaning_status']}")

    return report


def build_pranet_splits(data_root, output_dir, seed=42):
    """
    Build the standard PraNet benchmark split:
      Train: 900 Kvasir-SEG + 550 CVC-ClinicDB = 1,450
      Test:
        - 100 Kvasir-SEG
        - 62 CVC-ClinicDB
        - 196 ETIS-LaribPolypDB
        - 380 CVC-ColonDB (if available)
        - 60 CVC-300

    Writes TSV manifests: image_relpath<TAB>mask_relpath
    """
    data_root = Path(data_root)
    output_dir = Path(output_dir) / "manifests"
    output_dir.mkdir(parents=True, exist_ok=True)

    random.seed(seed)
    manifests = {}
    split_report = {"seed": seed, "splits": {}}

    # --- Kvasir-SEG split (900 train / 100 test) ---
    kvasir_dir = find_dataset_dir(data_root, "Kvasir-SEG")
    if kvasir_dir:
        pairs, _ = discover_pairs(kvasir_dir, DATASET_REGISTRY["Kvasir-SEG"])
        random.shuffle(pairs)
        train_count = int(len(pairs) * 0.9)  # 900
        kvasir_train = pairs[:train_count]
        kvasir_test = pairs[train_count:]

        split_report["splits"]["kvasir_train"] = len(kvasir_train)
        split_report["splits"]["kvasir_test"] = len(kvasir_test)
        print(f"  Kvasir-SEG: {len(kvasir_train)} train / {len(kvasir_test)} test")
    else:
        kvasir_train, kvasir_test = [], []
        print("  [!] Kvasir-SEG not found!")

    # --- CVC-ClinicDB split (550 train / 62 test) ---
    clinicdb_dir = find_dataset_dir(data_root, "cvc-clinicdb")
    if clinicdb_dir:
        pairs, _ = discover_pairs(clinicdb_dir, DATASET_REGISTRY["cvc-clinicdb"])
        random.shuffle(pairs)
        train_count = int(len(pairs) * 0.9)  # ~550
        clinicdb_train = pairs[:train_count]
        clinicdb_test = pairs[train_count:]

        split_report["splits"]["clinicdb_train"] = len(clinicdb_train)
        split_report["splits"]["clinicdb_test"] = len(clinicdb_test)
        print(f"  CVC-ClinicDB: {len(clinicdb_train)} train / {len(clinicdb_test)} test")
    else:
        clinicdb_train, clinicdb_test = [], []
        print("  [!] CVC-ClinicDB not found!")

    # --- ETIS-Larib (all test) ---
    etis_dir = find_dataset_dir(data_root, "etis-larib")
    if etis_dir:
        etis_test, _ = discover_pairs(etis_dir, DATASET_REGISTRY["etis-larib"])
        split_report["splits"]["etis_test"] = len(etis_test)
        print(f"  ETIS-Larib: {len(etis_test)} test (all)")
    else:
        etis_test = []
        print("  [!] ETIS-Larib not found")

    # --- CVC-300 (all test) ---
    cvc300_dir = find_dataset_dir(data_root, "CVC-300")
    if cvc300_dir:
        cvc300_test, _ = discover_pairs(cvc300_dir, DATASET_REGISTRY["CVC-300"])
        split_report["splits"]["cvc300_test"] = len(cvc300_test)
        print(f"  CVC-300: {len(cvc300_test)} test (all)")
    else:
        cvc300_test = []
        print("  [!] CVC-300 not found")

    # --- Combined train manifest ---
    combined_train = kvasir_train + clinicdb_train
    total_train = len(combined_train)
    split_report["splits"]["combined_train"] = total_train
    print(f"\n  COMBINED TRAIN: {total_train}")

    # Write manifests
    def write_manifest(path, pairs):
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(["image_path", "mask_path"])
            for img, mask in pairs:
                writer.writerow([img, mask])
        return len(pairs)

    manifests["train_combined"] = write_manifest(
        output_dir / "train_combined.tsv", combined_train)
    manifests["train_kvasir"] = write_manifest(
        output_dir / "train_kvasir.tsv", kvasir_train)
    manifests["test_kvasir"] = write_manifest(
        output_dir / "test_kvasir.tsv", kvasir_test)

    if clinicdb_train:
        manifests["train_clinicdb"] = write_manifest(
            output_dir / "train_clinicdb.tsv", clinicdb_train)
        manifests["test_clinicdb"] = write_manifest(
            output_dir / "test_clinicdb.tsv", clinicdb_test)

    if etis_test:
        manifests["test_etis"] = write_manifest(
            output_dir / "test_etis.tsv", etis_test)

    if cvc300_test:
        manifests["test_cvc300"] = write_manifest(
            output_dir / "test_cvc300.tsv", cvc300_test)

    # Leakage check: ensure no overlap between train and test filenames
    print("\n  LEAKAGE CHECK:")
    train_stems = {Path(p[0]).stem for p in combined_train}
    for name, test_pairs in [("kvasir", kvasir_test), ("clinicdb", clinicdb_test),
                              ("etis", etis_test), ("cvc300", cvc300_test)]:
        test_stems = {Path(p[0]).stem for p in test_pairs}
        overlap = train_stems & test_stems
        if overlap:
            print(f"  [!!] LEAKAGE in {name}: {len(overlap)} overlapping filenames!")
            split_report[f"leakage_{name}"] = list(overlap)[:10]
        else:
            print(f"  [OK] {name}: 0 overlapping filenames")

    split_report["manifests"] = manifests
    return split_report


def main():
    parser = argparse.ArgumentParser(
        description="Clean and prepare polyp segmentation datasets"
    )
    parser.add_argument("--data-root", required=True,
                        help="Root directory containing raw datasets")
    parser.add_argument("--output-dir", default="data/processed",
                        help="Output directory for cleaned data and manifests")
    parser.add_argument("--skip-cleaning", action="store_true",
                        help="Skip mask binarization, only build manifests")
    parser.add_argument("--skip-splits", action="store_true",
                        help="Skip manifest generation")

    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_reports = []

    # Phase 1: Clean each dataset
    if not args.skip_cleaning:
        print("\n" + "=" * 60)
        print("  PHASE 1: DATASET CLEANING & BINARIZATION")
        print("=" * 60)

        for ds_name, registry in DATASET_REGISTRY.items():
            ds_dir = find_dataset_dir(args.data_root, ds_name)
            if ds_dir:
                report = clean_dataset(
                    ds_name, ds_dir, registry,
                    args.output_dir, binarize=True
                )
                all_reports.append(report)
            else:
                print(f"\n  [!] Dataset '{ds_name}' not found under {args.data_root}")
                all_reports.append({
                    "dataset_name": ds_name,
                    "cleaning_status": "NOT_FOUND",
                })

    # Phase 2: Build PraNet-standard splits
    if not args.skip_splits:
        print("\n" + "=" * 60)
        print("  PHASE 2: BUILDING PRANET BENCHMARK SPLITS")
        print("=" * 60)

        split_report = build_pranet_splits(args.data_root, args.output_dir)
    else:
        split_report = None

    # Save combined report
    final_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_root": str(args.data_root),
        "output_dir": str(args.output_dir),
        "cleaning_reports": all_reports,
        "split_report": split_report,
    }

    report_path = Path("results") / "metrics" / f"cleaning_report_{timestamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(final_report, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  ALL DONE")
    print(f"  Report saved to: {report_path}")
    print(f"{'='*60}")

    # Print final status table
    print("\n  DATASET STATUS:")
    for r in all_reports:
        status = r.get("cleaning_status", "UNKNOWN")
        name = r.get("dataset_name", "?")
        valid = r.get("valid_pairs", "?")
        expected = r.get("expected_count", "?")
        print(f"    {name:<25} {status:<30} ({valid}/{expected})")

    if split_report:
        print("\n  SPLIT SUMMARY:")
        for k, v in split_report.get("splits", {}).items():
            print(f"    {k:<25} {v} images")


if __name__ == "__main__":
    main()
