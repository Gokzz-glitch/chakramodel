"""Create a deterministic train/validation split from a TSV manifest."""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows or set(rows[0]) != {"image", "mask"}:
        raise ValueError(f"Manifest must contain image and mask columns: {path}")
    return rows


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "mask"], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--train-output", type=Path, required=True)
    parser.add_argument("--val-output", type=Path, required=True)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not 0 < args.val_fraction < 1:
        raise ValueError("--val-fraction must be between 0 and 1")

    rows = read_manifest(args.input)
    rng = random.Random(args.seed)
    indices = list(range(len(rows)))
    rng.shuffle(indices)
    val_count = max(1, round(len(rows) * args.val_fraction))
    val_indices = set(indices[:val_count])
    train_rows = [row for i, row in enumerate(rows) if i not in val_indices]
    val_rows = [row for i, row in enumerate(rows) if i in val_indices]

    write_manifest(args.train_output, train_rows)
    write_manifest(args.val_output, val_rows)
    print(
        f"Created {len(train_rows)} training rows and {len(val_rows)} validation rows "
        f"from {len(rows)} rows (seed={args.seed})."
    )


if __name__ == "__main__":
    main()
