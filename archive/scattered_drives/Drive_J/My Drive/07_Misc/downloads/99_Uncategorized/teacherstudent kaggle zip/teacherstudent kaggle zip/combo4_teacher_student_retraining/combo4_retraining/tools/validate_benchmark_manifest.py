"""Validate the fixed benchmark manifest and reject group leakage.

Manifest format: one JSON object per line with image_id, image_path, mask_path
(empty for negatives), group_id, dataset_id, split, and label_status.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

REQUIRED = {"image_id", "image_path", "mask_path", "group_id", "dataset_id", "split", "label_status"}
SPLITS = {"train", "val", "test", "negative_pool"}


def validate(path):
    rows = []
    seen = set()
    errors = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON ({exc})")
            continue
        missing = REQUIRED - row.keys()
        if missing:
            errors.append(f"line {line_number}: missing {sorted(missing)}")
        if row.get("image_id") in seen:
            errors.append(f"line {line_number}: duplicate image_id {row.get('image_id')}")
        seen.add(row.get("image_id"))
        if row.get("split") not in SPLITS:
            errors.append(f"line {line_number}: invalid split {row.get('split')}")
        if row.get("split") in {"train", "val", "test"} and not row.get("mask_path"):
            errors.append(f"line {line_number}: positive split requires mask_path")
        rows.append(row)

    groups = defaultdict(set)
    for row in rows:
        groups[row.get("group_id")].add(row.get("split"))
    for group, splits in groups.items():
        if len(splits - {"negative_pool"}) > 1:
            errors.append(f"group {group} appears in multiple splits: {sorted(splits)}")

    if errors:
        raise ValueError("\n".join(errors))
    counts = defaultdict(int)
    for row in rows:
        counts[row["split"]] += 1
    return len(rows), dict(counts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    count, splits = validate(args.manifest)
    print(json.dumps({"valid": True, "rows": count, "splits": splits}, indent=2))


if __name__ == "__main__":
    main()
