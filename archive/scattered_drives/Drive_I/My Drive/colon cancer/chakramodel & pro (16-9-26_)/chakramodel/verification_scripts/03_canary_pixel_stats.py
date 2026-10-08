#!/usr/bin/env python3
"""
Measure pixel statistics of the planted canary and placeholder files.

Verifies Paper 1 sec 3.2 -- currently second-hand from [V] sec 8 and [D] sec 4:

  CANARY_*.png (data/cvc-300/images/)   claimed: 448x448x3, min 0, max 254,
                                        mean 126.72, std 73.60, 255 unique,
                                        603,684 bytes each
  synth_*.png  (data/etis-larib/images/) claimed: 256x256x3, min 100, max 150,
                                        mean 105.66, std 9.42, 21 unique,
                                        ~107 KB each

This distinction is what Paper 1 sec 4.3 rests on: uniform noise triggered the
tripwire (Dice 1.33e-09), a smooth gradient did not (Dice 0.9759).

Run from the repository root:
    .\.venv\Scripts\python.exe verification_scripts\03_canary_pixel_stats.py

Writes: verification_results/canary_stats.json
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
OUTDIR = REPO / "verification_results"
OUTDIR.mkdir(exist_ok=True)

GROUPS = {
    "canary_cvc300":        (REPO / "data" / "cvc-300" / "images", "CANARY_*.png"),
    "canary_cvc300_masks":  (REPO / "data" / "cvc-300" / "masks", "CANARY_*.png"),
    "canary_cvc300_nested": (REPO / "data" / "cvc-300" / "images" / "images", "CANARY_*.png"),
    "synth_etis":           (REPO / "data" / "etis-larib" / "images", "synth_*.png"),
    "canary_etis_nested":   (REPO / "data" / "etis-larib" / "images" / "images", "CANARY_*.png"),
}

report = {}

for label, (d, pattern) in GROUPS.items():
    entry = {"dir": str(d), "pattern": pattern, "exists": d.is_dir(), "files": []}
    if not d.is_dir():
        report[label] = entry
        print(f"{label:<22} DIR MISSING  {d}")
        continue

    files = sorted(d.glob(pattern))
    entry["n_files"] = len(files)
    print(f"\n{label}  ({len(files)} files)  {d}")
    print("-" * 78)

    for p in files:
        arr = np.asarray(Image.open(p))
        size = p.stat().st_size
        rec = {
            "name": p.name,
            "bytes": size,
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
            "min": int(arr.min()),
            "max": int(arr.max()),
            "mean": round(float(arr.mean()), 4),
            "std": round(float(arr.std()), 4),
            "n_unique": int(np.unique(arr).size),
        }
        entry["files"].append(rec)
        print(f"  {p.name:<34} {size:>9,}B  {str(rec['shape']):<16} "
              f"min={rec['min']:>3} max={rec['max']:>3} "
              f"mean={rec['mean']:>8.2f} std={rec['std']:>7.2f} "
              f"uniq={rec['n_unique']:>4}")

    if entry["files"]:
        sizes = {f["bytes"] for f in entry["files"]}
        entry["all_same_size"] = len(sizes) == 1
        entry["size_set"] = sorted(sizes)
        entry["aggregate"] = {
            "mean_of_means": round(
                float(np.mean([f["mean"] for f in entry["files"]])), 4),
            "mean_of_stds": round(
                float(np.mean([f["std"] for f in entry["files"]])), 4),
            "unique_counts": sorted({f["n_unique"] for f in entry["files"]}),
            "shapes": sorted({tuple(f["shape"]) for f in entry["files"]}),
        }
        print(f"  -> all identical size: {entry['all_same_size']}  "
              f"sizes={entry['size_set']}")
        print(f"  -> mean of means={entry['aggregate']['mean_of_means']}  "
              f"mean of stds={entry['aggregate']['mean_of_stds']}  "
              f"unique counts={entry['aggregate']['unique_counts']}")

    report[label] = entry

out = OUTDIR / "canary_stats.json"
out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

print("\n" + "=" * 78)
print("Compare against the claims Paper 1 sec 3.2 currently carries as V2:")
print("  CANARY_*: 448x448x3, min 0, max 254, mean 126.72, std 73.60,")
print("            255 unique values, 603,684 bytes (448*448*3 = 602,112 raw)")
print("  synth_*:  256x256x3, min 100, max 150, mean 105.66, std 9.42,")
print("            21 unique values, ~107 KB")
print("If a measured value differs, report the measured value. Do not adjust")
print("the measurement to match the paper.")
print("=" * 78)
print(f"\nWrote {out}")
