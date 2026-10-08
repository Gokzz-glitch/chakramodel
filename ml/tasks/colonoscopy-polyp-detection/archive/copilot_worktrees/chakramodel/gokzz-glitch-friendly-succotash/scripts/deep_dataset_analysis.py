"""Read-only duplicate, corruption, and leakage analysis for local polyp data."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image, UnidentifiedImageError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".avi", ".mp4", ".mov", ".mkv"}


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pixel_hash(path: Path, mask: bool = False) -> tuple[str, tuple[int, int], str]:
    with Image.open(path) as image:
        decoded = image.convert("L" if mask else "RGB")
        digest = hashlib.sha256(decoded.tobytes()).hexdigest()
        return digest, decoded.size, decoded.mode


def is_image_directory(path: Path) -> bool:
    return path.name.lower() in {"image", "images", "mask", "masks"}


def dataset_label(path: Path) -> str:
    lowered = str(path).lower()
    for name in ("pranet_benchmark", "kvasir-seg", "chakramodel-evaluation-datasets",
                 "polypdb-polyp-raw", "endoscene-cvc300-polyp-raw-dataset"):
        if name in lowered:
            return name
    return path.parts[-3] if len(path.parts) >= 3 else path.name


def archive_status(root: Path) -> list[dict]:
    result = []
    for archive in sorted((root / "alldataset").glob("*.zip")):
        record = {"file": str(archive), "bytes": archive.stat().st_size}
        try:
            with zipfile.ZipFile(archive) as handle:
                bad_member = handle.testzip()
                record.update({"valid_zip": True, "bad_member": bad_member})
        except (OSError, zipfile.BadZipFile) as exc:
            record.update({"valid_zip": False, "error": str(exc)})
        result.append(record)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(r"M:\chakramodelpro"))
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            r"M:\chakramodelpro\polyp-detection-research\results\metrics"
            r"\deep_dataset_analysis.json"
        ),
    )
    args = parser.parse_args()
    raw = args.root / "polyp-detection-research" / "data" / "raw"
    records: list[dict] = []
    errors: list[dict] = []
    by_byte_hash: defaultdict[str, list[str]] = defaultdict(list)
    by_pixel_hash: defaultdict[str, list[str]] = defaultdict(list)
    pair_records: list[dict] = []

    candidate_dirs = [
        path for path in raw.rglob("*") if path.is_dir() and is_image_directory(path)
    ]
    for directory in sorted(candidate_dirs):
        is_mask_dir = directory.name.lower() in {"mask", "masks"}
        files = sorted(
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS
        )
        for path in files:
            record = {
                "dataset": dataset_label(directory),
                "kind": "mask" if is_mask_dir else "image",
                "path": str(path),
                "bytes": path.stat().st_size,
            }
            try:
                record["byte_sha256"] = file_hash(path)
                pixel, size, mode = pixel_hash(path, mask=is_mask_dir)
                record.update({"pixel_sha256": pixel, "width": size[0], "height": size[1], "mode": mode})
                by_byte_hash[record["byte_sha256"]].append(str(path))
                by_pixel_hash[record["pixel_sha256"]].append(str(path))
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                errors.append(record)
            records.append(record)

        image_by_stem = {
            path.stem.lower(): path for path in files
        }
        if is_mask_dir:
            image_dir = directory.parent / ("image" if (directory.parent / "image").is_dir() else "images")
            image_files = {
                path.stem.lower(): path for path in image_dir.iterdir()
                if path.is_file() and path.suffix.lower() in IMAGE_EXTS
            } if image_dir.is_dir() else {}
            for stem, mask in image_by_stem.items():
                image = image_files.get(stem)
                if image is None:
                    pair_records.append({"mask": str(mask), "status": "missing_image"})
                else:
                    pair_records.append({"image": str(image), "mask": str(mask), "status": "paired"})

    def groups(mapping: defaultdict[str, list[str]]) -> list[list[str]]:
        return [paths for paths in mapping.values() if len(paths) > 1]

    split_names = {
        "train": "TrainDataset",
        "test": "TestDataset",
    }
    cross_split: list[dict] = []
    for digest, paths in by_byte_hash.items():
        splits = {split for split, name in split_names.items() if any(name in path for path in paths)}
        if len(splits) > 1:
            cross_split.append({"sha256": digest, "paths": paths, "splits": sorted(splits)})

    report = {
        "root": str(args.root),
        "raw_root": str(raw),
        "summary": {
            "files_scanned": len(records),
            "read_errors": len(errors),
            "paired_records": sum(item["status"] == "paired" for item in pair_records),
            "unpaired_masks": sum(item["status"] == "missing_image" for item in pair_records),
            "duplicate_byte_groups": len(groups(by_byte_hash)),
            "duplicate_decoded_pixel_groups": len(groups(by_pixel_hash)),
            "cross_split_byte_duplicates": len(cross_split),
        },
        "archives": archive_status(args.root),
        "errors": errors,
        "duplicate_byte_groups": groups(by_byte_hash),
        "duplicate_decoded_pixel_groups": groups(by_pixel_hash),
        "cross_split_byte_duplicates": cross_split,
        "records": records,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({**report["summary"], "report": str(args.report)}, indent=2))
    return 1 if errors or cross_split else 0


if __name__ == "__main__":
    raise SystemExit(main())
