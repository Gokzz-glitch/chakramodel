#!/usr/bin/env python3
"""
Prepare PraNet Benchmark Data — Single Source of Truth
======================================================

This script takes the official PraNet benchmark data (downloaded from the Google Drive
link published in the PraNet paper) and:

1. Validates every image and mask (opens, checks shape, checks for corruption)
2. Binarizes all masks (threshold=127) to fix JPEG compression artifacts
3. Checks for empty masks, dimension mismatches, tiny polyps
4. Generates TSV manifests for the exact PraNet benchmark splits
5. Produces a comprehensive cleaning report

PraNet Benchmark Protocol:
  Train: 1450 images (900 Kvasir-SEG + 550 CVC-ClinicDB)
  Test:  5 datasets — Kvasir(100), CVC-ClinicDB(62), CVC-ColonDB(380),
                       ETIS-LaribPolypDB(196), CVC-300(60)

Usage:
    python scripts/prepare_pranet_benchmark.py [--data-dir DATA_DIR] [--output-dir OUTPUT_DIR]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

# ─── Configuration ──────────────────────────────────────────────────────────

EXPECTED_COUNTS = {
    # Training sets
    "TrainDataset": {"total": 1450},
    # Test sets
    "CVC-300": {"images": 60, "masks": 60},
    "CVC-ClinicDB": {"images": 62, "masks": 62},
    "CVC-ColonDB": {"images": 380, "masks": 380},
    "ETIS-LaribPolypDB": {"images": 196, "masks": 196},
    "Kvasir": {"images": 100, "masks": 100},
}

MASK_THRESHOLD = 127  # Binarization threshold for JPEG-compressed masks


def validate_image(path: Path) -> dict:
    """Validate a single image file. Returns a report dict."""
    report = {"path": str(path), "valid": False, "error": None}
    try:
        with Image.open(path) as img:
            img.verify()  # Check file integrity
        # Re-open after verify (verify closes the image)
        with Image.open(path) as img:
            img.load()  # Force full decode
            report["width"] = img.width
            report["height"] = img.height
            report["mode"] = img.mode
            report["format"] = img.format
            report["valid"] = True
    except Exception as e:
        report["error"] = str(e)
    return report


def validate_mask(path: Path) -> dict:
    """Validate a single mask file and compute statistics."""
    report = {"path": str(path), "valid": False, "error": None}
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            img.load()
            report["width"] = img.width
            report["height"] = img.height
            report["mode"] = img.mode
            report["format"] = img.format

            # Convert to grayscale numpy array
            mask_arr = np.array(img.convert("L"))
            unique_vals = np.unique(mask_arr)
            report["unique_values"] = len(unique_vals)
            report["unique_values_list"] = unique_vals.tolist()[:20]  # Cap for readability
            report["is_binary"] = set(unique_vals.tolist()).issubset({0, 255})

            # Binarize and compute polyp ratio
            binary = (mask_arr >= MASK_THRESHOLD).astype(np.uint8) * 255
            polyp_pixels = np.sum(binary > 0)
            total_pixels = binary.size
            report["polyp_ratio"] = float(polyp_pixels / total_pixels) if total_pixels > 0 else 0.0
            report["is_empty"] = polyp_pixels == 0
            report["is_tiny"] = report["polyp_ratio"] < 0.005  # < 0.5% of image

            report["valid"] = True
    except Exception as e:
        report["error"] = str(e)
    return report


def binarize_mask(src_path: Path, dst_path: Path, threshold: int = MASK_THRESHOLD) -> bool:
    """Binarize a mask and save to dst_path. Returns True if mask was non-binary."""
    try:
        with Image.open(src_path) as img:
            mask_arr = np.array(img.convert("L"))
            unique_vals = set(np.unique(mask_arr).tolist())

            was_non_binary = not unique_vals.issubset({0, 255})

            # Apply threshold
            binary = ((mask_arr >= threshold).astype(np.uint8)) * 255

            # Save as PNG (lossless)
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(binary, mode="L").save(dst_path, format="PNG")

            return was_non_binary
    except Exception as e:
        print(f"  ERROR binarizing {src_path}: {e}")
        return False


def process_dataset(
    name: str,
    image_dir: Path,
    mask_dir: Path,
    cleaned_mask_dir: Path,
    expected_count: int,
) -> dict:
    """Process a single dataset: validate images, validate+binarize masks, report."""
    report = {
        "name": name,
        "image_dir": str(image_dir),
        "mask_dir": str(mask_dir),
        "expected_count": expected_count,
        "status": "UNKNOWN",
    }

    # Find all images
    img_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    images = sorted([
        f for f in image_dir.iterdir()
        if f.is_file() and f.suffix.lower() in img_extensions
    ])
    masks = sorted([
        f for f in mask_dir.iterdir()
        if f.is_file() and f.suffix.lower() in img_extensions
    ])

    report["image_count"] = len(images)
    report["mask_count"] = len(masks)

    # Check counts
    if len(images) != expected_count:
        report["status"] = f"IMAGE_COUNT_MISMATCH(expected={expected_count}, got={len(images)})"
        print(f"  ⚠ {name}: Expected {expected_count} images, found {len(images)}")
    if len(masks) != expected_count:
        report["status"] = f"MASK_COUNT_MISMATCH(expected={expected_count}, got={len(masks)})"
        print(f"  ⚠ {name}: Expected {expected_count} masks, found {len(masks)}")

    # Build image-mask pairs by filename stem
    image_stems = {f.stem: f for f in images}
    mask_stems = {f.stem: f for f in masks}
    common_stems = sorted(set(image_stems.keys()) & set(mask_stems.keys()))

    report["paired_count"] = len(common_stems)
    report["unpaired_images"] = sorted(set(image_stems.keys()) - set(mask_stems.keys()))
    report["unpaired_masks"] = sorted(set(mask_stems.keys()) - set(image_stems.keys()))

    if report["unpaired_images"]:
        print(f"  ⚠ {name}: {len(report['unpaired_images'])} images without masks")
    if report["unpaired_masks"]:
        print(f"  ⚠ {name}: {len(report['unpaired_masks'])} masks without images")

    # Validate each pair
    corrupt_images = []
    corrupt_masks = []
    dimension_mismatches = []
    empty_masks = []
    tiny_polyps = []
    non_binary_fixed = 0
    polyp_ratios = []
    valid_pairs = []

    for i, stem in enumerate(common_stems):
        img_path = image_stems[stem]
        mask_path = mask_stems[stem]

        # Progress
        if (i + 1) % 50 == 0 or i == 0:
            print(f"    Validating {name}: {i + 1}/{len(common_stems)}")

        # Validate image
        img_report = validate_image(img_path)
        if not img_report["valid"]:
            corrupt_images.append({"file": stem, "error": img_report["error"]})
            continue

        # Validate mask
        mask_report = validate_mask(mask_path)
        if not mask_report["valid"]:
            corrupt_masks.append({"file": stem, "error": mask_report["error"]})
            continue

        # Check dimension match
        if img_report["width"] != mask_report["width"] or img_report["height"] != mask_report["height"]:
            dimension_mismatches.append({
                "file": stem,
                "image_size": f"{img_report['width']}x{img_report['height']}",
                "mask_size": f"{mask_report['width']}x{mask_report['height']}",
            })
            continue

        # Binarize mask
        cleaned_path = cleaned_mask_dir / f"{stem}.png"
        was_non_binary = binarize_mask(mask_path, cleaned_path)
        if was_non_binary:
            non_binary_fixed += 1

        # Track stats
        if mask_report["is_empty"]:
            empty_masks.append(stem)
        if mask_report["is_tiny"] and not mask_report["is_empty"]:
            tiny_polyps.append({"file": stem, "polyp_ratio": mask_report["polyp_ratio"]})
        polyp_ratios.append(mask_report["polyp_ratio"])

        # Record valid pair (use cleaned mask path)
        valid_pairs.append((str(img_path), str(cleaned_path)))

    report["corrupt_images"] = corrupt_images
    report["corrupt_masks"] = corrupt_masks
    report["dimension_mismatches"] = dimension_mismatches
    report["empty_masks"] = empty_masks
    report["tiny_polyps"] = tiny_polyps
    report["non_binary_fixed"] = non_binary_fixed
    report["valid_pairs"] = len(valid_pairs)
    report["pairs_list"] = valid_pairs  # For manifest generation

    if polyp_ratios:
        report["mask_statistics"] = {
            "mean_polyp_ratio": round(float(np.mean(polyp_ratios)), 6),
            "median_polyp_ratio": round(float(np.median(polyp_ratios)), 6),
            "min_polyp_ratio": round(float(np.min(polyp_ratios)), 6),
            "max_polyp_ratio": round(float(np.max(polyp_ratios)), 6),
            "empty_mask_count": len(empty_masks),
            "tiny_polyp_count": len(tiny_polyps),
        }

    # Set final status
    if not corrupt_images and not corrupt_masks and not dimension_mismatches and len(valid_pairs) == expected_count:
        report["status"] = "PERFECT"
    elif not corrupt_images and not corrupt_masks and not dimension_mismatches:
        report["status"] = f"VALID_BUT_COUNT_DIFFERS(expected={expected_count}, valid={len(valid_pairs)})"
    else:
        issues = []
        if corrupt_images:
            issues.append(f"{len(corrupt_images)} corrupt images")
        if corrupt_masks:
            issues.append(f"{len(corrupt_masks)} corrupt masks")
        if dimension_mismatches:
            issues.append(f"{len(dimension_mismatches)} dim mismatches")
        report["status"] = f"ISSUES({', '.join(issues)})"

    # Don't save pairs_list to JSON (too large)
    report_for_json = {k: v for k, v in report.items() if k != "pairs_list"}
    return report, valid_pairs, report_for_json


def write_manifest(pairs: list, output_path: Path, data_root: Path):
    """Write a TSV manifest file with relative paths."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("image\tmask\n")
        for img_path, mask_path in pairs:
            # Write relative to data_root for portability
            img_rel = os.path.relpath(img_path, data_root)
            mask_rel = os.path.relpath(mask_path, data_root)
            f.write(f"{img_rel}\t{mask_rel}\n")
    print(f"  ✓ Manifest: {output_path} ({len(pairs)} pairs)")


def main():
    parser = argparse.ArgumentParser(description="Prepare PraNet benchmark data")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/raw/pranet_benchmark",
        help="Path to extracted PraNet benchmark data",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed",
        help="Output directory for cleaned data and manifests",
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=".",
        help="Project root directory",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    data_dir = (project_root / args.data_dir).resolve()
    output_dir = (project_root / args.output_dir).resolve()
    manifest_dir = output_dir / "manifests"
    cleaned_mask_dir = output_dir / "cleaned_masks"
    report_dir = project_root / "results" / "metrics"

    print("=" * 70)
    print("  PraNet Benchmark Data Preparation")
    print("=" * 70)
    print(f"  Data source:  {data_dir}")
    print(f"  Output dir:   {output_dir}")
    print(f"  Project root: {project_root}")
    print()

    # Verify structure
    train_dir = data_dir / "TrainDataset"
    test_dir = data_dir / "TestDataset"

    if not train_dir.exists() or not test_dir.exists():
        print(f"ERROR: Expected TrainDataset and TestDataset in {data_dir}")
        sys.exit(1)

    all_reports = []
    all_manifests = {}
    start_time = time.time()

    # ─── Process Training Data ──────────────────────────────────────────────

    print("\n" + "─" * 70)
    print("  TRAINING DATA (1450 images)")
    print("─" * 70)

    train_img_dir = train_dir / "image"
    train_mask_dir = train_dir / "masks"
    train_clean_dir = cleaned_mask_dir / "TrainDataset"

    report, pairs, report_json = process_dataset(
        "TrainDataset", train_img_dir, train_mask_dir, train_clean_dir, 1450
    )
    all_reports.append(report_json)

    # Write train manifest
    write_manifest(pairs, manifest_dir / "train_pranet.tsv", project_root)
    all_manifests["train_pranet"] = len(pairs)

    print(f"\n  Train: {report_json['status']}")
    print(f"    Valid pairs: {report_json['valid_pairs']}/{report_json['expected_count']}")
    print(f"    Non-binary masks fixed: {report_json['non_binary_fixed']}")
    if report_json.get("mask_statistics"):
        ms = report_json["mask_statistics"]
        print(f"    Polyp ratio: mean={ms['mean_polyp_ratio']:.4f}, "
              f"median={ms['median_polyp_ratio']:.4f}, "
              f"range=[{ms['min_polyp_ratio']:.4f}, {ms['max_polyp_ratio']:.4f}]")

    # ─── Process Test Datasets ──────────────────────────────────────────────

    test_sets = [
        ("CVC-300", 60),
        ("CVC-ClinicDB", 62),
        ("CVC-ColonDB", 380),
        ("ETIS-LaribPolypDB", 196),
        ("Kvasir", 100),
    ]

    for ds_name, expected in test_sets:
        print(f"\n{'─' * 70}")
        print(f"  TEST: {ds_name} ({expected} images)")
        print("─" * 70)

        ds_dir = test_dir / ds_name
        ds_img_dir = ds_dir / "images"
        ds_mask_dir = ds_dir / "masks"
        ds_clean_dir = cleaned_mask_dir / ds_name

        report, pairs, report_json = process_dataset(
            ds_name, ds_img_dir, ds_mask_dir, ds_clean_dir, expected
        )
        all_reports.append(report_json)

        manifest_name = f"test_{ds_name.lower().replace('-', '_')}.tsv"
        write_manifest(pairs, manifest_dir / manifest_name, project_root)
        all_manifests[f"test_{ds_name}"] = len(pairs)

        print(f"\n  {ds_name}: {report_json['status']}")
        print(f"    Valid pairs: {report_json['valid_pairs']}/{report_json['expected_count']}")
        print(f"    Non-binary masks fixed: {report_json['non_binary_fixed']}")
        if report_json.get("mask_statistics"):
            ms = report_json["mask_statistics"]
            print(f"    Polyp ratio: mean={ms['mean_polyp_ratio']:.4f}, "
                  f"median={ms['median_polyp_ratio']:.4f}, "
                  f"range=[{ms['min_polyp_ratio']:.4f}, {ms['max_polyp_ratio']:.4f}]")

    # ─── Summary ────────────────────────────────────────────────────────────

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    total_valid = sum(r["valid_pairs"] for r in all_reports)
    total_expected = sum(r["expected_count"] for r in all_reports)
    total_corrupt_img = sum(len(r["corrupt_images"]) for r in all_reports)
    total_corrupt_mask = sum(len(r["corrupt_masks"]) for r in all_reports)
    total_dim_mismatch = sum(len(r["dimension_mismatches"]) for r in all_reports)
    total_non_binary = sum(r["non_binary_fixed"] for r in all_reports)

    print(f"  Total valid pairs:    {total_valid}/{total_expected}")
    print(f"  Corrupt images:       {total_corrupt_img}")
    print(f"  Corrupt masks:        {total_corrupt_mask}")
    print(f"  Dimension mismatches: {total_dim_mismatch}")
    print(f"  Non-binary masks fixed: {total_non_binary}")
    print(f"  Time elapsed:         {elapsed:.1f}s")

    for name, count in all_manifests.items():
        print(f"  Manifest {name}: {count} pairs")

    # Overall status
    all_perfect = all(r["status"] == "PERFECT" for r in all_reports)
    if all_perfect:
        print("\n  ✅ ALL DATASETS PERFECT — Ready for training!")
    else:
        print("\n  ⚠ Some issues found:")
        for r in all_reports:
            if r["status"] != "PERFECT":
                print(f"    - {r['name']}: {r['status']}")

    # ─── Save Full Report ───────────────────────────────────────────────────

    timestamp = datetime.now(timezone.utc).isoformat()
    full_report = {
        "timestamp": timestamp,
        "benchmark_source": "PraNet Google Drive (official)",
        "benchmark_protocol": "PraNet (1450 train, 5 test sets)",
        "data_root": str(data_dir),
        "output_dir": str(output_dir),
        "elapsed_seconds": round(elapsed, 1),
        "summary": {
            "total_valid_pairs": total_valid,
            "total_expected": total_expected,
            "corrupt_images": total_corrupt_img,
            "corrupt_masks": total_corrupt_mask,
            "dimension_mismatches": total_dim_mismatch,
            "non_binary_masks_fixed": total_non_binary,
            "all_perfect": all_perfect,
        },
        "manifests": all_manifests,
        "dataset_reports": all_reports,
    }

    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"pranet_benchmark_cleaning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, default=str)
    print(f"\n  Report saved: {report_path}")

    return 0 if all_perfect else 1


if __name__ == "__main__":
    main()
