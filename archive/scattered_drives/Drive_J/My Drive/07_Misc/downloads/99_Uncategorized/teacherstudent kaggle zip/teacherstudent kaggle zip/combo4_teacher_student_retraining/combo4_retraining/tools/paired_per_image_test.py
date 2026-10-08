"""Paired per-image comparison for matching polyp-segmentation runs.

Usage:
  python tools/paired_per_image_test.py \
    --candidate path/to/vit/per_image.json \
    --baseline path/to/xattn/per_image.json \
    --split test_etis \
    --bootstrap 4000

The loader accepts either the run-level ``per_image.json`` format or RUN_E's
``eval_per_image.json`` format. It reports paired mean Dice difference and a
cluster-aware option when a ``sequence``/``video``/``case`` field is present.
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np


def load_records(path, split):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if split in data and isinstance(data[split], list):
            data = data[split]
        elif "images" in data and isinstance(data["images"], list):
            data = data["images"]
        else:
            data = data.get("records", [])
    if not isinstance(data, list):
        raise ValueError(f"Unsupported JSON structure: {path}")
    records = []
    for item in data:
        if not isinstance(item, dict):
            continue
        image = item.get("image") or item.get("path") or item.get("filename")
        dice = item.get("dice")
        if dice is None:
            dice = item.get("Dice") or item.get("mdice")
        if image is None or dice is None:
            continue
        try:
            records.append((str(image).replace("\\", "/"), float(dice), item))
        except (TypeError, ValueError):
            continue
    if not records:
        raise ValueError(f"No image/dice records found in {path} for split {split!r}")
    return records


def bootstrap(values, samples, seed):
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    draws = rng.integers(0, len(values), size=(samples, len(values)))
    means = values[draws].mean(axis=1)
    return float(np.mean(values)), tuple(np.quantile(means, [0.025, 0.975]))


def sequence_key(item, image):
    for key in ("sequence", "video", "case", "patient", "procedure", "lesion"):
        if item.get(key) is not None:
            return str(item[key])
    parts = image.split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--split", default="test_etis")
    parser.add_argument("--bootstrap", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cluster-bootstrap", action="store_true")
    args = parser.parse_args()

    candidate = load_records(args.candidate, args.split)
    baseline = load_records(args.baseline, args.split)
    left = {image: (dice, item) for image, dice, item in candidate}
    right = {image: (dice, item) for image, dice, item in baseline}
    common = sorted(set(left) & set(right))
    if not common:
        raise ValueError("The two files have no matching image keys")

    differences = np.asarray([left[k][0] - right[k][0] for k in common], dtype=float)
    mean, ci = bootstrap(differences, args.bootstrap, args.seed)
    wins = int(np.sum(differences > 0))
    losses = int(np.sum(differences < 0))
    ties = len(differences) - wins - losses
    print(f"split={args.split} matched={len(common)} unmatched_candidate={len(left)-len(common)} unmatched_baseline={len(right)-len(common)}")
    print(f"paired_mean_dice_difference={mean:.6f} bootstrap_95ci=[{ci[0]:.6f}, {ci[1]:.6f}]")
    print(f"wins={wins} losses={losses} ties={ties}")

    if args.cluster_bootstrap:
        clusters = defaultdict(list)
        for image, diff in zip(common, differences):
            clusters[sequence_key(left[image][1], image)].append(diff)
        cluster_values = np.asarray([np.mean(values) for values in clusters.values()])
        cmean, cci = bootstrap(cluster_values, args.bootstrap, args.seed)
        print(f"clusters={len(cluster_values)} cluster_mean_difference={cmean:.6f} cluster_bootstrap_95ci=[{cci[0]:.6f}, {cci[1]:.6f}]")


if __name__ == "__main__":
    main()
