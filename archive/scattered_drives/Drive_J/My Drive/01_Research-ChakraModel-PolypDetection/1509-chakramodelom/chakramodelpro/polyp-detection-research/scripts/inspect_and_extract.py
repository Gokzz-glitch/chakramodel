#!/usr/bin/env python3
"""
Dataset Extractor & Inspector for Polyp Segmentation Research
=============================================================
Inspects zip archives from Kaggle WITHOUT full extraction first,
then selectively extracts image-mask datasets needed for experiments.

Usage:
  # Inspect all zips (list contents, detect structure)
  python scripts/inspect_and_extract.py --mode inspect --source-dir "I:\My Drive\1509-chakramodelom\dataet"

  # Extract specific datasets for experiments
  python scripts/inspect_and_extract.py --mode extract --source-dir "I:\My Drive\1509-chakramodelom\dataet" --target-dir data/raw
"""

import argparse
import json
import os
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def inspect_zip_structure(zip_path, max_list=50):
    """
    Inspect a zip archive and return its internal structure analysis.
    Does NOT extract anything — reads only the central directory.
    """
    result = {
        "archive": str(zip_path),
        "archive_name": Path(zip_path).stem,
        "size_bytes": os.path.getsize(zip_path),
        "is_valid_zip": False,
        "total_entries": 0,
        "total_uncompressed_bytes": 0,
        "top_level_dirs": [],
        "file_extensions": {},
        "image_mask_structure": "unknown",
        "has_images_dir": False,
        "has_masks_dir": False,
        "has_original_dir": False,
        "has_groundtruth_dir": False,
        "sample_paths": [],
        "errors": [],
    }

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            result["is_valid_zip"] = True
            entries = zf.namelist()
            result["total_entries"] = len(entries)
            result["total_uncompressed_bytes"] = sum(
                info.file_size for info in zf.infolist()
            )

            # Analyze directory structure
            top_dirs = set()
            ext_counter = Counter()
            dir_names = set()

            for entry in entries:
                parts = entry.replace('\\', '/').split('/')
                if len(parts) > 1:
                    top_dirs.add(parts[0])
                if len(parts) > 1:
                    for p in parts[:-1]:
                        dir_names.add(p.lower())
                if not entry.endswith('/'):
                    ext = Path(entry).suffix.lower()
                    ext_counter[ext] += 1

            result["top_level_dirs"] = sorted(top_dirs)
            result["file_extensions"] = dict(ext_counter.most_common(20))
            result["sample_paths"] = entries[:max_list]

            # Detect image-mask structure
            lower_dirs = {d.lower() for d in dir_names}
            result["has_images_dir"] = "images" in lower_dirs
            result["has_masks_dir"] = "masks" in lower_dirs
            result["has_original_dir"] = "original" in lower_dirs
            result["has_groundtruth_dir"] = (
                "ground truth" in lower_dirs or
                "groundtruth" in lower_dirs or
                "ground_truth" in lower_dirs or
                "gt" in lower_dirs
            )

            # Classify structure
            if result["has_images_dir"] and result["has_masks_dir"]:
                result["image_mask_structure"] = "standard_images_masks"
            elif result["has_original_dir"] and result["has_groundtruth_dir"]:
                result["image_mask_structure"] = "original_groundtruth"
            elif any(ext in ext_counter for ext in ['.avi', '.mp4', '.mkv', '.mov']):
                result["image_mask_structure"] = "video_only"
            elif any(ext in ext_counter for ext in ['.pt', '.pth', '.onnx', '.bin']):
                result["image_mask_structure"] = "model_weights"
            elif ext_counter.get('.jpg', 0) + ext_counter.get('.jpeg', 0) + ext_counter.get('.png', 0) > 0:
                # Check if there are paired directories
                img_count = ext_counter.get('.jpg', 0) + ext_counter.get('.jpeg', 0) + ext_counter.get('.png', 0)
                result["image_mask_structure"] = f"flat_images({img_count})"
            else:
                result["image_mask_structure"] = "other"

    except zipfile.BadZipFile as e:
        result["errors"].append(f"BAD_ZIP: {e}")
    except Exception as e:
        result["errors"].append(f"ERROR: {e}")

    return result


def inspect_all_zips(source_dir):
    """Inspect all zip files in a directory."""
    source_dir = Path(source_dir)
    zips = sorted(source_dir.glob("*.zip"))

    print(f"\nFound {len(zips)} zip archives in {source_dir}")
    print("=" * 80)

    all_results = []
    for i, zp in enumerate(zips, 1):
        print(f"\n[{i}/{len(zips)}] Inspecting: {zp.name}")
        print(f"  Size: {zp.stat().st_size / 1e6:.1f} MB")

        result = inspect_zip_structure(zp)
        all_results.append(result)

        print(f"  Valid zip: {result['is_valid_zip']}")
        print(f"  Total entries: {result['total_entries']}")
        print(f"  Uncompressed: {result['total_uncompressed_bytes'] / 1e6:.1f} MB")
        print(f"  Top-level dirs: {result['top_level_dirs'][:10]}")
        print(f"  File extensions: {result['file_extensions']}")
        print(f"  Structure type: {result['image_mask_structure']}")
        if result['has_images_dir']:
            print(f"  Has images/ dir: YES")
        if result['has_masks_dir']:
            print(f"  Has masks/ dir: YES")
        if result['has_original_dir']:
            print(f"  Has Original/ dir: YES")
        if result['has_groundtruth_dir']:
            print(f"  Has Ground Truth/ dir: YES")
        if result['errors']:
            print(f"  ERRORS: {result['errors']}")

        # Print sample paths
        print(f"  Sample paths (first 15):")
        for sp in result['sample_paths'][:15]:
            print(f"    {sp}")

    return all_results


def extract_dataset(zip_path, target_dir, dataset_name=None):
    """Extract a zip archive to target directory."""
    zip_path = Path(zip_path)
    target_dir = Path(target_dir)

    if dataset_name is None:
        dataset_name = zip_path.stem

    extract_to = target_dir / dataset_name
    extract_to.mkdir(parents=True, exist_ok=True)

    print(f"\nExtracting {zip_path.name} -> {extract_to}")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        total = len(zf.namelist())
        for i, member in enumerate(zf.namelist(), 1):
            if i % 500 == 0 or i == 1:
                print(f"  Extracting {i}/{total}...", end='\r')
            zf.extract(member, extract_to)
        print(f"  Extracted {total}/{total} files to {extract_to}")

    return str(extract_to)


def main():
    parser = argparse.ArgumentParser(
        description="Inspect and extract polyp segmentation datasets"
    )
    parser.add_argument("--mode", choices=["inspect", "extract", "both"],
                        default="inspect",
                        help="inspect: analyze zip contents; extract: extract to target")
    parser.add_argument("--source-dir", required=True,
                        help="Directory containing zip archives")
    parser.add_argument("--target-dir", default="data/raw",
                        help="Target directory for extraction")
    parser.add_argument("--datasets", nargs="+", default=None,
                        help="Specific zip filenames to extract (without .zip)")
    parser.add_argument("--output", default=None,
                        help="Path to save inspection report JSON")

    args = parser.parse_args()

    if args.mode in ("inspect", "both"):
        results = inspect_all_zips(args.source_dir)

        # Save report
        if args.output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path("results") / "metrics" / f"zip_inspection_{timestamp}.json"
        else:
            output_path = Path(args.output)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_dir": str(args.source_dir),
                "total_archives": len(results),
                "archives": results,
            }, f, indent=2)
        print(f"\nInspection report saved to: {output_path}")

        # Print classification summary
        print("\n" + "=" * 80)
        print("DATASET CLASSIFICATION SUMMARY")
        print("=" * 80)
        for r in results:
            status = "IMAGE-MASK" if "images_masks" in r["image_mask_structure"] or "groundtruth" in r["image_mask_structure"] else r["image_mask_structure"].upper()
            print(f"  {r['archive_name']:<55} {status}")

    if args.mode in ("extract", "both"):
        source_dir = Path(args.source_dir)
        target_dir = Path(args.target_dir)

        if args.datasets:
            zips_to_extract = [source_dir / f"{d}.zip" for d in args.datasets]
        else:
            # Default: extract only the image-mask datasets needed
            default_datasets = [
                "endoscene-cvc300-polyp-raw-dataset",
                "polypdb-polyp-raw",
                "chakramodel-evaluation-datasets",
            ]
            zips_to_extract = [source_dir / f"{d}.zip" for d in default_datasets]

        for zp in zips_to_extract:
            if zp.exists():
                extract_dataset(zp, target_dir)
            else:
                print(f"WARNING: {zp} not found, skipping")


if __name__ == "__main__":
    main()
