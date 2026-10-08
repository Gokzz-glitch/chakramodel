"""Create a deduplicated, thresholded PolypDB candidate snapshot.

This is a candidate dataset, not an assertion of official provenance. It keeps
the source tree untouched and groups frames by filename prefix before the final
frame number to reduce sequence leakage between train and validation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image


FRAME_RE = re.compile(r"^(.*)_\d+$")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def group_key(stem: str) -> str:
    match = FRAME_RE.match(stem)
    return match.group(1) if match else stem


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(
            r"M:\chakramodelpro\polyp-detection-research\data\raw"
            r"\polypdb-polyp-raw\PolypDB\PolypDB\PolypDB_modality_wise"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(r"M:\chakramodelpro\kaggle_ready_polypdb_candidate_v1"),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {args.output}")

    candidates: dict[str, tuple[Path, Path, str]] = {}
    duplicate_image_groups: defaultdict[str, list[str]] = defaultdict(list)
    missing_masks = []
    for image in sorted((args.source).rglob("*")):
        if not image.is_file() or image.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        if image.parent.name.lower() != "images":
            continue
        mask = image.parent.parent / "masks" / f"{image.stem}.png"
        if not mask.is_file():
            mask = image.parent.parent / "masks" / f"{image.stem}{image.suffix}"
        if not mask.is_file():
            missing_masks.append({"image": str(image), "expected_mask": str(mask)})
            continue
        image_hash = digest(image)
        duplicate_image_groups[image_hash].append(str(image))
        # The modality-wise hierarchy is canonical; the hash makes repeated
        # modality/center exports collapse to one sample.
        candidates.setdefault(image_hash, (image, mask, image_hash))

    rows = []
    for image, mask, image_hash in candidates.values():
        with Image.open(image) as source_image, Image.open(mask) as source_mask:
            rgb = source_image.convert("RGB")
            binary = source_mask.convert("L").point(lambda value: 255 if value > 127 else 0)
            if rgb.size != binary.size:
                missing_masks.append(
                    {"image": str(image), "mask": str(mask), "error": "dimension_mismatch"}
                )
                continue
            key = group_key(image.stem)
            bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 10
            split = "test" if bucket == 0 else ("val" if bucket == 1 else "train")
            name = f"{image_hash[:16]}_{image.stem}"
            image_out = args.output / split / "images" / f"{name}.jpg"
            mask_out = args.output / split / "masks" / f"{name}.png"
            image_out.parent.mkdir(parents=True, exist_ok=True)
            mask_out.parent.mkdir(parents=True, exist_ok=True)
            rgb.save(image_out, quality=95)
            binary.save(mask_out)
            rows.append(
                {
                    "split": split,
                    "image": str(image_out.relative_to(args.output)).replace("\\", "/"),
                    "mask": str(mask_out.relative_to(args.output)).replace("\\", "/"),
                    "source_image": str(image),
                    "source_mask": str(mask),
                    "source_image_sha256": image_hash,
                    "group_key": key,
                }
            )

    with (args.output / "manifest.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "source": str(args.source),
        "output": str(args.output),
        "source_unique_pairs": len(candidates),
        "source_duplicate_image_groups": sum(len(v) > 1 for v in duplicate_image_groups.values()),
        "source_duplicate_files_removed": sum(
            len(v) - 1 for v in duplicate_image_groups.values() if len(v) > 1
        ),
        "output_pairs": len(rows),
        "split_counts": {
            split: sum(row["split"] == split for row in rows)
            for split in ("train", "val", "test")
        },
        "missing_or_invalid": missing_masks,
        "mask_policy": "threshold source grayscale masks at >127 to binary 0/255",
        "provenance_status": "CANDIDATE_ONLY_NOT_OFFICIALLY_VERIFIED",
    }
    (args.output / "curation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (args.output / "README.txt").write_text(
        "PolypDB candidate snapshot\n"
        "==========================\n"
        "Deduplicated by image SHA-256 and thresholded to binary masks.\n"
        "This is not an official provenance verification. Review source license,\n"
        "patient/sequence grouping, and annotation quality before publication.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 1 if missing_masks else 0


if __name__ == "__main__":
    raise SystemExit(main())
