"""Inspect and prepare leakage-safe image/mask segmentation datasets.

The split unit is a group (normally the source-video or source-folder), never
an individual frame. Matching is recursive and uses the image stem, while
duplicate stems are rejected instead of silently pairing the wrong mask.

Example:
  python data/scripts/prepare_segmentation_manifest.py \
    --images /kaggle/input/polypgen/images \
    --masks /kaggle/input/polypgen/masks \
    --output /kaggle/working/polypgen_prepared \
    --materialize
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

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def group_for(path: Path, root: Path, pattern: str | None) -> str:
    relative = path.relative_to(root)
    if pattern:
        match = re.search(pattern, path.stem)
        if not match:
            raise ValueError(f"Group pattern did not match: {path}")
        return match.group(1) if match.groups() else match.group(0)
    # The first directory below images/ is usually the video or case folder.
    return relative.parts[0] if len(relative.parts) > 1 else path.parent.name


def stable_split(group: str, train: float, val: float) -> str:
    value = int(hashlib.sha1(group.encode("utf-8")).hexdigest()[:8], 16) / 2**32
    if value < train:
        return "train"
    if value < train + val:
        return "val"
    return "test"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--masks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group-regex", help="Regex applied to each image stem; group 1 is used.")
    parser.add_argument("--train", type=float, default=.7)
    parser.add_argument("--val", type=float, default=.15)
    parser.add_argument("--materialize", action="store_true",
                        help="Copy paired files into output/images|masks/<split>.")
    args = parser.parse_args()
    if not args.images.is_dir() or not args.masks.is_dir():
        raise FileNotFoundError("--images and --masks must be existing directories")
    if args.train <= 0 or args.val < 0 or args.train + args.val >= 1:
        raise ValueError("Require train > 0, val >= 0, and train + val < 1")

    mask_index: dict[str, list[Path]] = defaultdict(list)
    for path in files(args.masks):
        mask_index[path.stem].append(path)
    rows: list[dict[str, str]] = []
    seen_stems: set[str] = set()
    unmatched = []
    ambiguous = []
    for image in files(args.images):
        if image.stem in seen_stems:
            raise ValueError(f"Duplicate image stem; use --group-regex or rename files: {image.stem}")
        seen_stems.add(image.stem)
        candidates = mask_index.get(image.stem, [])
        if not candidates:
            unmatched.append(str(image))
            continue
        if len(candidates) > 1:
            ambiguous.append((str(image), [str(p) for p in candidates]))
            continue
        group = group_for(image, args.images, args.group_regex)
        rows.append({
            "image": str(image.resolve()),
            "mask": str(candidates[0].resolve()),
            "group": group,
            "split": stable_split(group, args.train, args.val),
        })
    if ambiguous:
        raise ValueError(f"Ambiguous masks for {len(ambiguous)} images; first: {ambiguous[0]}")
    if not rows:
        raise RuntimeError("No image-mask pairs found")

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "mask", "group", "split"])
        writer.writeheader()
        writer.writerows(rows)
    counts = {split: sum(row["split"] == split for row in rows)
              for split in ("train", "val", "test")}
    groups = {split: len({row["group"] for row in rows if row["split"] == split})
              for split in counts}
    summary = {"pairs": len(rows), "unmatched_images": len(unmatched),
               "image_groups": len({row["group"] for row in rows}),
               "pairs_by_split": counts, "groups_by_split": groups}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (args.output / "unmatched_images.txt").write_text("\n".join(unmatched), encoding="utf-8")

    if args.materialize:
        for row in rows:
            split = row["split"]
            name = f"{row['group']}__{Path(row['image']).name}"
            image_out = args.output / "images" / split / name
            mask_out = args.output / "masks" / split / f"{Path(name).stem}.png"
            image_out.parent.mkdir(parents=True, exist_ok=True)
            mask_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(row["image"], image_out)
            shutil.copy2(row["mask"], mask_out)

    print(json.dumps(summary, indent=2))
    if unmatched:
        print(f"WARNING: {len(unmatched)} images had no matching mask; they were excluded.")
    print(f"Manifest written to {args.output / 'manifest.csv'}")


if __name__ == "__main__":
    main()
