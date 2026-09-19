"""Audit mounted Kaggle datasets before any training.

Usage in Kaggle:
    !python /kaggle/working/chakramodel/data/scripts/audit_kaggle_datasets.py \
        --root /kaggle/input --output /kaggle/working/dataset_audit

The report is descriptive only: it never assumes that a folder named
"labels" contains segmentation masks. Review the JSON/CSV report before
preparing a training split.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

try:
    import cv2
except ImportError as exc:
    raise SystemExit("Install opencv-python before running the audit") from exc


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".avi", ".mp4", ".mov", ".mkv", ".webm", ".mpeg", ".mpg"}
MASK_WORDS = {
    "mask", "masks", "groundtruth", "ground_truth", "segmentation",
    "segmentations", "label", "labels", "annotation", "annotations",
}
GENERIC_DATASET_DIRS = {
    "images", "masks", "labels", "annotations", "annotation", "frames",
    "video", "videos", "data", "gt", "ground_truth", "groundtruth",
}


def sha1(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def audit_dataset(root: Path) -> dict:
    files = [path for path in root.rglob("*") if path.is_file()]
    images = [path for path in files if path.suffix.lower() in IMAGE_EXTS]
    videos = [path for path in files if path.suffix.lower() in VIDEO_EXTS]
    mask_candidates = []
    for path in images:
        relative_parts = path.relative_to(root).parts
        if any(part.lower() in MASK_WORDS for part in relative_parts):
            mask_candidates.append(path)
            continue
        if any(word in path.stem.lower() for word in MASK_WORDS):
            mask_candidates.append(path)
    resolutions = Counter()
    unreadable_images = []
    for path in images:
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None:
            unreadable_images.append(str(path.relative_to(root)))
            continue
        resolutions[f"{image.shape[1]}x{image.shape[0]}"] += 1

    source_images = [path for path in images if path not in set(mask_candidates)]
    stem_counts = Counter(path.stem for path in source_images)
    duplicate_stems = sorted(stem for stem, count in stem_counts.items() if count > 1)
    folders = Counter(str(path.parent.relative_to(root)) for path in files)
    return {
        "dataset": root.name,
        "root": str(root),
        "file_count": len(files),
        "image_count": len(images),
        "video_count": len(videos),
        "mask_candidate_count": len(mask_candidates),
        "unreadable_image_count": len(unreadable_images),
        "duplicate_image_stem_count": len(duplicate_stems),
        "top_resolutions": resolutions.most_common(15),
        "top_folders": folders.most_common(20),
        "sample_images": [str(path.relative_to(root)) for path in images[:10]],
        "sample_masks": [str(path.relative_to(root)) for path in mask_candidates[:10]],
        "sample_videos": [str(path.relative_to(root)) for path in videos[:10]],
        "unreadable_images": unreadable_images[:20],
        "duplicate_image_stems": duplicate_stems[:50],
    }


def collect_dataset_roots(root: Path, dataset_depth: int | None) -> list[Path]:
    candidates = []
    for path in sorted(root.rglob("*")):
        if not path.is_dir():
            continue
        if path.name.lower() in GENERIC_DATASET_DIRS:
            continue
        if any(
            child.is_file() and child.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS
            for child in path.rglob("*")
        ):
            candidates.append(path)

    kept = []
    for candidate in sorted(candidates, key=lambda p: (len(p.parts), str(p))):
        if any(other != candidate and other.is_relative_to(candidate) for other in candidates):
            continue
        kept.append(candidate)

    if dataset_depth is not None:
        kept = [path for path in kept if len(path.relative_to(root).parts) == dataset_depth]
    return sorted(kept, key=lambda p: str(p))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/kaggle/input"))
    parser.add_argument("--dataset-depth", type=int, default=None,
                        help="Optional relative depth to keep under root; defaults to auto-discovery.")
    parser.add_argument("--output", type=Path, default=Path("/kaggle/working/dataset_audit"))
    parser.add_argument("--hash-images", action="store_true",
                        help="Also write SHA-1 hashes for exact duplicate detection")
    args = parser.parse_args()
    if not args.root.is_dir():
        raise FileNotFoundError(f"Dataset root does not exist: {args.root}")

    datasets = collect_dataset_roots(args.root, args.dataset_depth)
    if not datasets:
        depth_hint = f" at depth {args.dataset_depth}" if args.dataset_depth is not None else ""
        raise RuntimeError(f"No dataset directories found{depth_hint} under {args.root}")
    reports = [audit_dataset(dataset) for dataset in datasets]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "dataset", "file_count", "image_count", "video_count",
            "mask_candidate_count", "unreadable_image_count",
            "duplicate_image_stem_count",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: report[field] for field in fields} for report in reports)

    if args.hash_images:
        with (args.output / "image_hashes.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["dataset", "relative_path", "sha1"])
            for dataset in datasets:
                for path in dataset.rglob("*"):
                    if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                        writer.writerow([dataset.name, str(path.relative_to(dataset)), sha1(path)])

    print(json.dumps([
        {
            "dataset": report["dataset"],
            "images": report["image_count"],
            "videos": report["video_count"],
            "mask_candidates": report["mask_candidate_count"],
            "duplicate_stems": report["duplicate_image_stem_count"],
        }
        for report in reports
    ], indent=2))
    print(f"Detailed report: {args.output / 'summary.json'}")


if __name__ == "__main__":
    main()
