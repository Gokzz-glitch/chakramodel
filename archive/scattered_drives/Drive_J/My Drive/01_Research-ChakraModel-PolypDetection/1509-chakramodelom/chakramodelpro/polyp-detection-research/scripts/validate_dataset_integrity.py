#!/usr/bin/env python3
"""
Dataset Integrity Validator for Colonoscopy Polyp Segmentation
==============================================================
Validates every image and mask file for:
  1. File existence and non-zero size
  2. Image decodability (not corrupted)
  3. Correct dimensions (H, W match between image and mask)
  4. Correct number of channels (3 for images, 1 or 3 for masks)
  5. Mask value range (binary: only 0 and 255, or continuous 0-255)
  6. Image-mask filename pairing correctness
  7. Duplicate detection (identical files via hash)
  8. Format validation (JPEG/PNG magic bytes)
  9. Resolution statistics and outlier detection

Usage:
  python scripts/validate_dataset_integrity.py --data-dir data/raw/Kvasir-SEG
  python scripts/validate_dataset_integrity.py --data-dir data/raw --all-datasets
  python scripts/validate_dataset_integrity.py --data-dir data/raw/Kvasir-SEG --fix  # removes corrupt files
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np


# ----------------------------------------─────────────
# Magic byte signatures for format validation
# ----------------------------------------─────────────
JPEG_MAGIC = b'\xff\xd8\xff'
PNG_MAGIC = b'\x89PNG'
BMP_MAGIC = b'BM'
TIFF_LE_MAGIC = b'II'
TIFF_BE_MAGIC = b'MM'


def check_magic_bytes(filepath):
    """Check if file has valid image magic bytes."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
        if len(header) < 3:
            return False, "FILE_TOO_SMALL"
        if header[:3] == JPEG_MAGIC:
            return True, "JPEG"
        if header[:4] == PNG_MAGIC:
            return True, "PNG"
        if header[:2] == BMP_MAGIC:
            return True, "BMP"
        if header[:2] in (TIFF_LE_MAGIC, TIFF_BE_MAGIC):
            return True, "TIFF"
        return False, f"UNKNOWN_FORMAT(0x{header[:4].hex()})"
    except Exception as e:
        return False, f"READ_ERROR({e})"


def compute_file_hash(filepath, algorithm='md5'):
    """Compute hash of a file for duplicate detection."""
    h = hashlib.new(algorithm)
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def validate_single_image(filepath, is_mask=False):
    """
    Validate a single image file. Returns a dict with validation results.
    """
    result = {
        "path": str(filepath),
        "exists": False,
        "size_bytes": 0,
        "magic_valid": False,
        "magic_format": "",
        "decodable": False,
        "height": 0,
        "width": 0,
        "channels": 0,
        "dtype": "",
        "min_val": 0,
        "max_val": 0,
        "unique_values": 0,
        "is_binary_mask": None,
        "errors": [],
        "warnings": [],
    }

    # Gate 1: Existence and size
    if not os.path.isfile(filepath):
        result["errors"].append("FILE_NOT_FOUND")
        return result
    result["exists"] = True

    fsize = os.path.getsize(filepath)
    result["size_bytes"] = fsize
    if fsize == 0:
        result["errors"].append("ZERO_SIZE_FILE")
        return result

    # Gate 2: Magic bytes
    valid_magic, fmt = check_magic_bytes(filepath)
    result["magic_valid"] = valid_magic
    result["magic_format"] = fmt
    if not valid_magic:
        result["errors"].append(f"INVALID_MAGIC_BYTES({fmt})")

    # Gate 3: Decodability
    try:
        if is_mask:
            img = cv2.imread(str(filepath), cv2.IMREAD_GRAYSCALE)
        else:
            img = cv2.imread(str(filepath), cv2.IMREAD_COLOR)
    except Exception as e:
        result["errors"].append(f"CV2_EXCEPTION({e})")
        return result

    if img is None:
        result["errors"].append("CV2_DECODE_FAILED")
        return result

    result["decodable"] = True
    result["height"] = img.shape[0]
    result["width"] = img.shape[1]
    result["channels"] = img.shape[2] if len(img.shape) == 3 else 1
    result["dtype"] = str(img.dtype)
    result["min_val"] = int(img.min())
    result["max_val"] = int(img.max())

    # Gate 4: Value range checks
    if is_mask:
        unique = np.unique(img)
        result["unique_values"] = len(unique)
        # Check if it's a proper binary mask
        if set(unique.tolist()).issubset({0, 255}):
            result["is_binary_mask"] = True
        elif set(unique.tolist()).issubset({0, 1}):
            result["is_binary_mask"] = True
            result["warnings"].append("MASK_USES_0_1_INSTEAD_OF_0_255")
        else:
            result["is_binary_mask"] = False
            if len(unique) <= 10:
                result["warnings"].append(f"MASK_NOT_BINARY(unique={unique.tolist()})")
            else:
                result["warnings"].append(f"MASK_CONTINUOUS_VALUES(n_unique={len(unique)}, min={img.min()}, max={img.max()})")
    else:
        # Color image checks
        if result["channels"] != 3:
            result["warnings"].append(f"IMAGE_NOT_3CH(channels={result['channels']})")
        if result["max_val"] == 0:
            result["errors"].append("ALL_BLACK_IMAGE")
        elif result["max_val"] == result["min_val"]:
            result["errors"].append(f"CONSTANT_VALUE_IMAGE(val={result['max_val']})")

    # Gate 5: Dimension sanity
    if result["height"] < 16 or result["width"] < 16:
        result["errors"].append(f"TOO_SMALL({result['width']}x{result['height']})")
    if result["height"] > 4096 or result["width"] > 4096:
        result["warnings"].append(f"VERY_LARGE({result['width']}x{result['height']})")

    return result


def discover_dataset_structure(data_dir):
    """
    Auto-discover image-mask pairs in a dataset directory.
    Supports common layouts:
      - images/ + masks/
      - Original/ + Ground Truth/
      - train/images/ + train/masks/
      - Flat directory with naming conventions
    Returns list of (image_path, mask_path) tuples and the detected layout.
    """
    data_dir = Path(data_dir)
    pairs = []
    layout = "unknown"

    # Pattern 1: images/ + masks/
    img_dir = data_dir / "images"
    mask_dir = data_dir / "masks"
    if img_dir.is_dir() and mask_dir.is_dir():
        layout = "images_masks"
        img_files = sorted([f for f in img_dir.iterdir() if f.is_file()])
        for img_f in img_files:
            # Try exact name match first
            mask_candidates = [
                mask_dir / img_f.name,
                mask_dir / (img_f.stem + ".png"),
                mask_dir / (img_f.stem + ".jpg"),
                mask_dir / (img_f.stem + ".bmp"),
                mask_dir / (img_f.stem + ".tif"),
            ]
            mask_f = None
            for mc in mask_candidates:
                if mc.is_file():
                    mask_f = mc
                    break
            pairs.append((str(img_f), str(mask_f) if mask_f else None))
        return pairs, layout

    # Pattern 2: Original/ + Ground Truth/
    img_dir = data_dir / "Original"
    mask_dir = data_dir / "Ground Truth"
    if img_dir.is_dir() and mask_dir.is_dir():
        layout = "original_groundtruth"
        img_files = sorted([f for f in img_dir.iterdir() if f.is_file()])
        for img_f in img_files:
            mask_candidates = [
                mask_dir / img_f.name,
                mask_dir / (img_f.stem + ".png"),
                mask_dir / (img_f.stem + ".bmp"),
                mask_dir / (img_f.stem + ".tif"),
            ]
            mask_f = None
            for mc in mask_candidates:
                if mc.is_file():
                    mask_f = mc
                    break
            pairs.append((str(img_f), str(mask_f) if mask_f else None))
        return pairs, layout

    # Pattern 3: Subdirectories with images and masks inside
    for subdir in sorted(data_dir.iterdir()):
        if subdir.is_dir():
            sub_pairs, sub_layout = discover_dataset_structure(subdir)
            if sub_pairs:
                pairs.extend(sub_pairs)
                layout = f"nested({subdir.name}/{sub_layout})"

    if not pairs:
        # Pattern 4: All image files in flat directory (no masks)
        img_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
        all_files = sorted([f for f in data_dir.iterdir()
                           if f.is_file() and f.suffix.lower() in img_exts])
        if all_files:
            layout = "flat_images_only"
            pairs = [(str(f), None) for f in all_files]

    return pairs, layout


def validate_dataset(data_dir, compute_hashes=True):
    """
    Full validation of a dataset directory.
    Returns comprehensive report dict.
    """
    data_dir = Path(data_dir)
    dataset_name = data_dir.name
    print(f"\n{'='*70}")
    print(f"  VALIDATING DATASET: {dataset_name}")
    print(f"  Path: {data_dir}")
    print(f"{'='*70}")

    report = {
        "dataset_name": dataset_name,
        "dataset_path": str(data_dir),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "layout": "",
        "total_pairs": 0,
        "valid_pairs": 0,
        "corrupt_images": [],
        "corrupt_masks": [],
        "missing_masks": [],
        "dimension_mismatches": [],
        "duplicate_images": [],
        "duplicate_masks": [],
        "resolution_stats": {},
        "mask_stats": {},
        "all_errors": [],
        "all_warnings": [],
        "overall_status": "UNKNOWN",
    }

    # Discover pairs
    pairs, layout = discover_dataset_structure(data_dir)
    report["layout"] = layout
    report["total_pairs"] = len(pairs)

    if not pairs:
        report["overall_status"] = "EMPTY_DATASET"
        report["all_errors"].append("No image-mask pairs found")
        print(f"  [X] NO PAIRS FOUND (layout: {layout})")
        return report

    print(f"  Layout: {layout}")
    print(f"  Total pairs found: {len(pairs)}")

    # Validate each pair
    image_results = []
    mask_results = []
    image_hashes = defaultdict(list)
    mask_hashes = defaultdict(list)
    resolutions = []
    valid_count = 0
    has_masks = any(m is not None for _, m in pairs)

    for i, (img_path, mask_path) in enumerate(pairs):
        if (i + 1) % 100 == 0 or i == 0:
            print(f"  Checking pair {i+1}/{len(pairs)}...", end='\r')

        # Validate image
        img_result = validate_single_image(img_path, is_mask=False)
        image_results.append(img_result)

        if img_result["errors"]:
            report["corrupt_images"].append({
                "path": img_path,
                "errors": img_result["errors"]
            })
            report["all_errors"].extend(
                [f"IMAGE:{img_path}:{e}" for e in img_result["errors"]]
            )

        if img_result["warnings"]:
            report["all_warnings"].extend(
                [f"IMAGE:{img_path}:{w}" for w in img_result["warnings"]]
            )

        # Validate mask
        if mask_path is None:
            report["missing_masks"].append(img_path)
        else:
            mask_result = validate_single_image(mask_path, is_mask=True)
            mask_results.append(mask_result)

            if mask_result["errors"]:
                report["corrupt_masks"].append({
                    "path": mask_path,
                    "errors": mask_result["errors"]
                })
                report["all_errors"].extend(
                    [f"MASK:{mask_path}:{e}" for e in mask_result["errors"]]
                )

            if mask_result["warnings"]:
                report["all_warnings"].extend(
                    [f"MASK:{mask_path}:{w}" for w in mask_result["warnings"]]
                )

            # Dimension match check
            if img_result["decodable"] and mask_result["decodable"]:
                if (img_result["height"] != mask_result["height"] or
                        img_result["width"] != mask_result["width"]):
                    mismatch = {
                        "image": img_path,
                        "mask": mask_path,
                        "image_dims": f"{img_result['width']}x{img_result['height']}",
                        "mask_dims": f"{mask_result['width']}x{mask_result['height']}",
                    }
                    report["dimension_mismatches"].append(mismatch)
                    report["all_errors"].append(
                        f"DIM_MISMATCH:{img_path}:"
                        f"img={img_result['width']}x{img_result['height']} "
                        f"mask={mask_result['width']}x{mask_result['height']}"
                    )
                else:
                    # Both valid and matching
                    if not mask_result["errors"]:
                        valid_count += 1
                        resolutions.append((img_result["width"], img_result["height"]))

        # Hash computation for duplicate detection
        if compute_hashes and img_result["decodable"]:
            h = compute_file_hash(img_path)
            if h:
                image_hashes[h].append(img_path)

        if compute_hashes and mask_path and mask_results and mask_results[-1]["decodable"]:
            h = compute_file_hash(mask_path)
            if h:
                mask_hashes[h].append(mask_path)

    print(f"  Checking pair {len(pairs)}/{len(pairs)}... done")

    report["valid_pairs"] = valid_count

    # Duplicate detection
    for h, paths in image_hashes.items():
        if len(paths) > 1:
            report["duplicate_images"].append(paths)
    for h, paths in mask_hashes.items():
        if len(paths) > 1:
            report["duplicate_masks"].append(paths)

    # Resolution statistics
    if resolutions:
        widths = [r[0] for r in resolutions]
        heights = [r[1] for r in resolutions]
        unique_res = list(set(resolutions))
        report["resolution_stats"] = {
            "min_width": min(widths),
            "max_width": max(widths),
            "min_height": min(heights),
            "max_height": max(heights),
            "mean_width": round(np.mean(widths), 1),
            "mean_height": round(np.mean(heights), 1),
            "unique_resolutions": len(unique_res),
            "most_common": str(max(set(resolutions), key=resolutions.count)) if resolutions else "N/A",
            "resolution_distribution": {
                f"{w}x{h}": resolutions.count((w, h))
                for w, h in sorted(unique_res, key=lambda x: resolutions.count(x), reverse=True)[:20]
            }
        }

    # Mask statistics
    if mask_results:
        binary_count = sum(1 for m in mask_results if m.get("is_binary_mask") is True)
        non_binary_count = sum(1 for m in mask_results if m.get("is_binary_mask") is False)
        report["mask_stats"] = {
            "total_masks": len(mask_results),
            "binary_masks": binary_count,
            "non_binary_masks": non_binary_count,
            "decodable_masks": sum(1 for m in mask_results if m["decodable"]),
        }

    # Overall status
    if report["corrupt_images"] or report["corrupt_masks"] or report["dimension_mismatches"]:
        report["overall_status"] = "ISSUES_FOUND"
    elif report["missing_masks"] and has_masks:
        report["overall_status"] = "MISSING_MASKS"
    elif valid_count == len(pairs):
        report["overall_status"] = "CLEAN"
    else:
        report["overall_status"] = "PARTIAL"

    # Print summary
    print(f"\n  ----------------------------------------")
    print(f"  SUMMARY for {dataset_name}:")
    print(f"  ----------------------------------------")
    print(f"  Total pairs:          {len(pairs)}")
    print(f"  Valid pairs:          {valid_count}")
    print(f"  Corrupt images:       {len(report['corrupt_images'])}")
    print(f"  Corrupt masks:        {len(report['corrupt_masks'])}")
    print(f"  Missing masks:        {len(report['missing_masks'])}")
    print(f"  Dimension mismatches: {len(report['dimension_mismatches'])}")
    print(f"  Duplicate images:     {len(report['duplicate_images'])} groups")
    print(f"  Duplicate masks:      {len(report['duplicate_masks'])} groups")
    if report["resolution_stats"]:
        rs = report["resolution_stats"]
        print(f"  Resolution range:     {rs['min_width']}x{rs['min_height']} — {rs['max_width']}x{rs['max_height']}")
        print(f"  Unique resolutions:   {rs['unique_resolutions']}")
    if report["mask_stats"]:
        ms = report["mask_stats"]
        print(f"  Binary masks:         {ms['binary_masks']}/{ms['total_masks']}")
        print(f"  Non-binary masks:     {ms['non_binary_masks']}")
    print(f"  Overall status:       {report['overall_status']}")

    if report["corrupt_images"]:
        print(f"\n  [!]  CORRUPT IMAGES:")
        for ci in report["corrupt_images"][:20]:
            print(f"      {ci['path']}: {ci['errors']}")
        if len(report["corrupt_images"]) > 20:
            print(f"      ... and {len(report['corrupt_images'])-20} more")

    if report["corrupt_masks"]:
        print(f"\n  [!]  CORRUPT MASKS:")
        for cm in report["corrupt_masks"][:20]:
            print(f"      {cm['path']}: {cm['errors']}")
        if len(report["corrupt_masks"]) > 20:
            print(f"      ... and {len(report['corrupt_masks'])-20} more")

    if report["dimension_mismatches"]:
        print(f"\n  [!]  DIMENSION MISMATCHES:")
        for dm in report["dimension_mismatches"][:10]:
            print(f"      {dm['image']}: img={dm['image_dims']} mask={dm['mask_dims']}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Validate dataset integrity for polyp segmentation"
    )
    parser.add_argument("--data-dir", required=True,
                        help="Path to dataset directory (or parent for --all-datasets)")
    parser.add_argument("--all-datasets", action="store_true",
                        help="Validate all subdirectories as separate datasets")
    parser.add_argument("--output", default=None,
                        help="Path to save JSON report (default: auto-generated)")
    parser.add_argument("--no-hashes", action="store_true",
                        help="Skip hash computation for duplicates (faster)")
    parser.add_argument("--fix", action="store_true",
                        help="Remove corrupt files (DANGEROUS - moves to .corrupt/)")

    args = parser.parse_args()
    data_dir = Path(args.data_dir)

    if not data_dir.is_dir():
        print(f"ERROR: {data_dir} is not a directory")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path("results") / "metrics" / f"dataset_integrity_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run validation
    start_time = time.time()
    all_reports = []

    if args.all_datasets:
        # Validate each subdirectory as a separate dataset
        subdirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])
        print(f"Found {len(subdirs)} subdirectories to validate")
        for subdir in subdirs:
            report = validate_dataset(subdir, compute_hashes=not args.no_hashes)
            all_reports.append(report)
    else:
        report = validate_dataset(data_dir, compute_hashes=not args.no_hashes)
        all_reports.append(report)

    elapsed = time.time() - start_time

    # Build final report
    final_report = {
        "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        "validation_duration_seconds": round(elapsed, 2),
        "total_datasets": len(all_reports),
        "datasets_clean": sum(1 for r in all_reports if r["overall_status"] == "CLEAN"),
        "datasets_with_issues": sum(1 for r in all_reports if r["overall_status"] != "CLEAN"),
        "total_errors": sum(len(r["all_errors"]) for r in all_reports),
        "total_warnings": sum(len(r["all_warnings"]) for r in all_reports),
        "datasets": all_reports,
    }

    # Save report
    with open(output_path, 'w') as f:
        json.dump(final_report, f, indent=2)
    print(f"\n{'='*70}")
    print(f"  VALIDATION COMPLETE")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Report saved to: {output_path}")
    print(f"  Clean datasets: {final_report['datasets_clean']}/{final_report['total_datasets']}")
    print(f"  Total errors: {final_report['total_errors']}")
    print(f"  Total warnings: {final_report['total_warnings']}")
    print(f"{'='*70}")

    # Handle --fix mode
    if args.fix and final_report["total_errors"] > 0:
        print("\n  [FIX] FIX MODE: Moving corrupt files to .corrupt/ directory...")
        for report in all_reports:
            corrupt_dir = Path(report["dataset_path"]) / ".corrupt"
            for ci in report["corrupt_images"]:
                p = Path(ci["path"])
                if p.exists():
                    corrupt_dir.mkdir(parents=True, exist_ok=True)
                    dest = corrupt_dir / p.name
                    print(f"    Moving {p} → {dest}")
                    p.rename(dest)
            for cm in report["corrupt_masks"]:
                p = Path(cm["path"])
                if p.exists():
                    corrupt_dir.mkdir(parents=True, exist_ok=True)
                    dest = corrupt_dir / p.name
                    print(f"    Moving {p} → {dest}")
                    p.rename(dest)

    # Exit code
    sys.exit(0 if final_report["total_errors"] == 0 else 1)


if __name__ == "__main__":
    main()
