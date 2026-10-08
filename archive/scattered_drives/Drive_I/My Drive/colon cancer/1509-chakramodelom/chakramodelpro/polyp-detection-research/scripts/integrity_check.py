#!/usr/bin/env python3
"""
integrity_check.py — Full byte-level dataset integrity gate
============================================================

Reads every image and mask referenced by the 7 manifests used in
configs/baseline_unet.yaml.  For each file:

  - Reads complete raw bytes (byte 0 … EOF)
  - Computes SHA-256 over those bytes
  - Records file size
  - Confirms PIL readability and H×W dimensions
  - Checks mask pixel distributions

Cross-split checks (by SHA-256 + file size, NOT filenames):
  - Train vs Val duplicate images
  - Train vs Val duplicate masks
  - Train+Val vs each test set

Failures are collected exhaustively; exit code 1 if ANY gate fails.
Nothing is repaired or skipped silently.

Usage
-----
    python scripts/integrity_check.py [--project-root .]
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

# --- Manifest definitions ----------------------------------------------------
# Exactly the 7 manifests referenced by configs/baseline_unet.yaml
MANIFEST_ROLES = {
    "train":         "data/processed/manifests/train_pranet_train.tsv",
    "val":           "data/processed/manifests/val_pranet.tsv",
    "test_kvasir":   "data/processed/manifests/test_kvasir.tsv",
    "test_clinicdb": "data/processed/manifests/test_cvc_clinicdb.tsv",
    "test_colondb":  "data/processed/manifests/test_cvc_colondb.tsv",
    "test_etis":     "data/processed/manifests/test_etis_laribpolypdb.tsv",
    "test_cvc300":   "data/processed/manifests/test_cvc_300.tsv",
}

# Expected PraNet pair counts
EXPECTED_COUNTS = {
    "train":         1232,
    "val":           218,
    "test_kvasir":   100,
    "test_clinicdb": 62,
    "test_colondb":  380,
    "test_etis":     196,
    "test_cvc300":   60,
}

CHUNK_SIZE = 1 << 22   # 4 MiB read chunks — efficient for large PNGs/JPEGs


# --- Helpers -----------------------------------------------------------------

def sha256_file(path: Path) -> tuple[str, int]:
    """Return (hex-digest, file-size-bytes) by reading the full file."""
    h = hashlib.sha256()
    total = 0
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total


def bytes_equal(path_a: Path, path_b: Path) -> bool:
    """Direct byte-for-byte comparison after a hash collision is found."""
    with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
        while True:
            ca = fa.read(CHUNK_SIZE)
            cb = fb.read(CHUNK_SIZE)
            if ca != cb:
                return False
            if not ca:   # both exhausted simultaneously
                return True


def read_manifest(tsv_path: Path) -> list[tuple[str, str]]:
    """Parse a TSV manifest; returns list of (image_rel, mask_rel) tuples."""
    pairs = []
    with open(tsv_path, encoding="utf-8") as fh:
        header = fh.readline().strip().split("\t")
        # Support both column-name conventions
        if "image" in header:
            img_col, mask_col = header.index("image"), header.index("mask")
        elif "image_path" in header:
            img_col = header.index("image_path")
            mask_col = header.index("mask_path")
        else:
            raise ValueError(f"Unrecognised header in {tsv_path}: {header}")
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            pairs.append((parts[img_col], parts[mask_col]))
    return pairs


def check_image(path: Path) -> dict:
    """Return PIL readability + dimensions for an image file."""
    r: dict = {"path": str(path), "readable": False, "width": None, "height": None, "error": None}
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            img.load()
            r["width"] = img.width
            r["height"] = img.height
            r["mode"] = img.mode
            r["readable"] = True
    except Exception as exc:
        r["error"] = str(exc)
    return r


def check_mask(path: Path) -> dict:
    """Return PIL readability + dimensions + pixel-value stats for a mask."""
    r: dict = {
        "path": str(path), "readable": False,
        "width": None, "height": None, "error": None,
        "unique_values": None, "is_binary": None,
        "polyp_ratio": None, "is_empty": None,
    }
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            img.load()
            r["width"] = img.width
            r["height"] = img.height
            r["mode"] = img.mode
            r["readable"] = True
            arr = np.array(img.convert("L"))
            unique = sorted(set(arr.flatten().tolist()))
            r["unique_values"] = unique[:30]   # cap for JSON size
            r["unique_value_count"] = len(unique)
            r["is_binary"] = set(unique).issubset({0, 255})
            polyp_px = int(np.sum(arr >= 128))
            r["polyp_ratio"] = round(polyp_px / arr.size, 6) if arr.size else 0.0
            r["is_empty"] = polyp_px == 0
    except Exception as exc:
        r["error"] = str(exc)
    return r


# --- Main --------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Byte-level dataset integrity check")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    report_dir = root / "results" / "metrics"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir / f"integrity_report_{timestamp}.json"

    t0 = time.perf_counter()

    failures: list[dict] = []
    warnings: list[dict] = []

    # -- 1. Load + parse all 7 manifests --------------------------------------
    print("=" * 72)
    print("  INTEGRITY CHECK — byte-level SHA-256")
    print("=" * 72)

    split_pairs: dict[str, list[tuple[str, str]]] = {}
    manifest_counts_ok = True

    for role, rel_path in MANIFEST_ROLES.items():
        tsv = root / rel_path
        print(f"\n[1] Manifest: {rel_path}")
        if not tsv.exists():
            msg = f"Manifest file missing: {tsv}"
            print(f"  FAIL  {msg}")
            failures.append({"gate": "manifest_exists", "role": role, "path": str(tsv), "detail": msg})
            manifest_counts_ok = False
            split_pairs[role] = []
            continue
        pairs = read_manifest(tsv)
        split_pairs[role] = pairs
        expected = EXPECTED_COUNTS[role]
        status = "OK" if len(pairs) == expected else "FAIL"
        print(f"  {status}  {role}: {len(pairs)} pairs (expected {expected})")
        if len(pairs) != expected:
            msg = f"{role}: expected {expected} pairs, got {len(pairs)}"
            failures.append({"gate": "manifest_count", "role": role, "path": str(tsv),
                             "expected": expected, "actual": len(pairs), "detail": msg})
            manifest_counts_ok = False

    # -- 2. Hash every file in every manifest ---------------------------------
    print("\n" + "-" * 72)
    print("[2] Hashing all files (SHA-256, full byte read)")
    print("-" * 72)

    # file_hash_cache: abs_path_str → (digest, size)
    file_hash_cache: dict[str, tuple[str, int]] = {}
    # per-split: {role: {"images": {digest: [path]}, "masks": {digest: [path]}}}
    split_digests: dict[str, dict] = {}

    # per-split per-file details for the JSON report
    split_file_details: dict[str, list[dict]] = {}

    total_files_hashed = 0
    total_bytes_read = 0

    for role, pairs in split_pairs.items():
        split_digests[role] = {"images": defaultdict(list), "masks": defaultdict(list)}
        split_file_details[role] = []

        unreadable_images: list[str] = []
        unreadable_masks: list[str] = []
        dim_mismatches: list[dict] = []
        missing_images: list[str] = []
        missing_masks: list[str] = []
        non_binary_masks: list[dict] = []
        empty_masks: list[str] = []
        unpaired: list[dict] = []

        print(f"\n  {role} ({len(pairs)} pairs):")
        for idx, (img_rel, mask_rel) in enumerate(pairs):
            if (idx + 1) % 200 == 0 or idx == 0:
                print(f"    ... {idx + 1}/{len(pairs)}")

            img_path = root / img_rel
            mask_path = root / mask_rel

            pair_detail: dict = {
                "index": idx,
                "image_rel": img_rel,
                "mask_rel": mask_rel,
                "image_exists": img_path.exists(),
                "mask_exists": mask_path.exists(),
            }

            # -- existence
            if not img_path.exists():
                missing_images.append(str(img_path))
                failures.append({
                    "gate": "file_exists", "role": role, "kind": "image",
                    "path": str(img_path), "detail": "Image file not found on disk"
                })
                pair_detail["image_hash"] = None
                pair_detail["image_size"] = None
            else:
                p_str = str(img_path)
                if p_str not in file_hash_cache:
                    dig, sz = sha256_file(img_path)
                    file_hash_cache[p_str] = (dig, sz)
                    total_files_hashed += 1
                    total_bytes_read += sz
                dig, sz = file_hash_cache[p_str]
                pair_detail["image_hash"] = dig
                pair_detail["image_size"] = sz
                split_digests[role]["images"][dig].append(str(img_path))

            if not mask_path.exists():
                missing_masks.append(str(mask_path))
                failures.append({
                    "gate": "file_exists", "role": role, "kind": "mask",
                    "path": str(mask_path), "detail": "Mask file not found on disk"
                })
                pair_detail["mask_hash"] = None
                pair_detail["mask_size"] = None
            else:
                p_str = str(mask_path)
                if p_str not in file_hash_cache:
                    dig, sz = sha256_file(mask_path)
                    file_hash_cache[p_str] = (dig, sz)
                    total_files_hashed += 1
                    total_bytes_read += sz
                dig, sz = file_hash_cache[p_str]
                pair_detail["mask_hash"] = dig
                pair_detail["mask_size"] = sz
                split_digests[role]["masks"][dig].append(str(mask_path))

            # -- PIL readability + dimensions (only if both files exist)
            if img_path.exists() and mask_path.exists():
                img_info = check_image(img_path)
                mask_info = check_mask(mask_path)

                pair_detail["image_readable"] = img_info["readable"]
                pair_detail["mask_readable"] = mask_info["readable"]

                if not img_info["readable"]:
                    unreadable_images.append(str(img_path))
                    failures.append({
                        "gate": "readability", "role": role, "kind": "image",
                        "path": str(img_path), "detail": img_info["error"]
                    })

                if not mask_info["readable"]:
                    unreadable_masks.append(str(mask_path))
                    failures.append({
                        "gate": "readability", "role": role, "kind": "mask",
                        "path": str(mask_path), "detail": mask_info["error"]
                    })

                if img_info["readable"] and mask_info["readable"]:
                    # dimension match
                    iw, ih = img_info["width"], img_info["height"]
                    mw, mh = mask_info["width"], mask_info["height"]
                    pair_detail["image_wh"] = [iw, ih]
                    pair_detail["mask_wh"] = [mw, mh]
                    pair_detail["dimensions_match"] = (iw == mw and ih == mh)

                    if iw != mw or ih != mh:
                        dim_mismatches.append({
                            "image": img_rel, "mask": mask_rel,
                            "image_wh": [iw, ih], "mask_wh": [mw, mh]
                        })
                        failures.append({
                            "gate": "dimension_match", "role": role,
                            "image": img_rel, "mask": mask_rel,
                            "image_wh": [iw, ih], "mask_wh": [mw, mh],
                            "detail": f"Dimension mismatch: image {iw}x{ih} vs mask {mw}x{mh}"
                        })

                    # mask pixel distribution
                    pair_detail["mask_is_binary"] = mask_info["is_binary"]
                    pair_detail["mask_unique_value_count"] = mask_info["unique_value_count"]
                    pair_detail["mask_polyp_ratio"] = mask_info["polyp_ratio"]
                    pair_detail["mask_is_empty"] = mask_info["is_empty"]

                    if not mask_info["is_binary"]:
                        non_binary_masks.append({
                            "mask": mask_rel,
                            "unique_value_count": mask_info["unique_value_count"],
                            "unique_values_sample": mask_info["unique_values"]
                        })
                        failures.append({
                            "gate": "mask_binary", "role": role, "mask": mask_rel,
                            "unique_value_count": mask_info["unique_value_count"],
                            "unique_values_sample": mask_info["unique_values"],
                            "detail": "Mask is not strictly binary {0, 255}"
                        })

                    if mask_info["is_empty"]:
                        empty_masks.append(mask_rel)
                        warnings.append({
                            "gate": "mask_empty", "role": role, "mask": mask_rel,
                            "detail": "Mask has zero polyp pixels"
                        })

            split_file_details[role].append(pair_detail)

        # within-split duplicate images
        intra_dup_images = {d: ps for d, ps in split_digests[role]["images"].items() if len(ps) > 1}
        intra_dup_masks = {d: ps for d, ps in split_digests[role]["masks"].items() if len(ps) > 1}

        for dig, paths in intra_dup_images.items():
            # Confirm with direct byte comparison
            confirmed = bytes_equal(Path(paths[0]), Path(paths[1]))
            failures.append({
                "gate": "intra_split_duplicate_image", "role": role,
                "sha256": dig, "paths": paths, "byte_confirmed": confirmed,
                "detail": f"Duplicate image bytes within {role}"
            })

        for dig, paths in intra_dup_masks.items():
            confirmed = bytes_equal(Path(paths[0]), Path(paths[1]))
            failures.append({
                "gate": "intra_split_duplicate_mask", "role": role,
                "sha256": dig, "paths": paths, "byte_confirmed": confirmed,
                "detail": f"Duplicate mask bytes within {role}"
            })

        status_str = "CLEAN" if not (missing_images or missing_masks or unreadable_images
                                     or unreadable_masks or dim_mismatches or non_binary_masks) else "ISSUES"
        print(f"    {status_str}: missing_imgs={len(missing_images)}, missing_masks={len(missing_masks)}, "
              f"unreadable_imgs={len(unreadable_images)}, unreadable_masks={len(unreadable_masks)}, "
              f"dim_mismatch={len(dim_mismatches)}, non_binary_masks={len(non_binary_masks)}, "
              f"empty_masks={len(empty_masks)}")

    # -- 3. Cross-split duplicate checks (SHA-256 + file-size, confirmed by bytes) --
    print("\n" + "-" * 72)
    print("[3] Cross-split duplicate checks (SHA-256 + direct byte confirmation)")
    print("-" * 72)

    cross_checks = [
        ("train", "val",           "train_vs_val"),
        ("train", "test_kvasir",   "train_vs_test_kvasir"),
        ("train", "test_clinicdb", "train_vs_test_clinicdb"),
        ("train", "test_colondb",  "train_vs_test_colondb"),
        ("train", "test_etis",     "train_vs_test_etis"),
        ("train", "test_cvc300",   "train_vs_test_cvc300"),
        ("val",   "test_kvasir",   "val_vs_test_kvasir"),
        ("val",   "test_clinicdb", "val_vs_test_clinicdb"),
        ("val",   "test_colondb",  "val_vs_test_colondb"),
        ("val",   "test_etis",     "val_vs_test_etis"),
        ("val",   "test_cvc300",   "val_vs_test_cvc300"),
    ]

    cross_results: dict[str, dict] = {}

    for role_a, role_b, label in cross_checks:
        if role_a not in split_digests or role_b not in split_digests:
            continue

        for kind in ("images", "masks"):
            digests_a = split_digests[role_a][kind]
            digests_b = split_digests[role_b][kind]
            overlap_digests = set(digests_a.keys()) & set(digests_b.keys())

            confirmed_dups = []
            for dig in overlap_digests:
                paths_a = digests_a[dig]
                paths_b = digests_b[dig]
                # Confirm with direct byte comparison (first representative from each side)
                confirmed = bytes_equal(Path(paths_a[0]), Path(paths_b[0]))
                if confirmed:
                    # Also compare sizes as second confirmation
                    sz_a = file_hash_cache[paths_a[0]][1]
                    sz_b = file_hash_cache[paths_b[0]][1]
                    confirmed_dups.append({
                        "sha256": dig,
                        "size_bytes_a": sz_a,
                        "size_bytes_b": sz_b,
                        "sizes_match": sz_a == sz_b,
                        "byte_confirmed": True,
                        "paths_in_a": paths_a,
                        "paths_in_b": paths_b,
                    })
                    if role_a in ("train", "val") and role_b in ("test_kvasir", "test_clinicdb",
                                                                  "test_colondb", "test_etis", "test_cvc300"):
                        failures.append({
                            "gate": f"cross_split_duplicate_{kind}",
                            "split_a": role_a, "split_b": role_b,
                            "sha256": dig,
                            "paths_in_a": paths_a,
                            "paths_in_b": paths_b,
                            "detail": f"Exact byte duplicate {kind[:-1]} found in {role_a} and {role_b}"
                        })
                    elif role_a == "train" and role_b == "val":
                        failures.append({
                            "gate": f"train_val_duplicate_{kind}",
                            "sha256": dig,
                            "paths_in_train": paths_a,
                            "paths_in_val": paths_b,
                            "detail": f"Exact byte duplicate {kind[:-1]} found in train and val"
                        })

            key = f"{label}_{kind}"
            cross_results[key] = {
                "role_a": role_a,
                "role_b": role_b,
                "kind": kind,
                "unique_in_a": len(digests_a),
                "unique_in_b": len(digests_b),
                "hash_overlap_count": len(overlap_digests),
                "byte_confirmed_duplicates": len(confirmed_dups),
                "duplicate_groups": confirmed_dups,
            }
            status_str = "CLEAN" if len(confirmed_dups) == 0 else "DUPLICATE"
            print(f"  {status_str}  {label} ({kind}): "
                  f"hash_overlap={len(overlap_digests)}, byte_confirmed={len(confirmed_dups)}")

    # -- 4. Compile summary ----------------------------------------------------
    elapsed = time.perf_counter() - t0
    all_passed = len(failures) == 0

    per_split_summary = {}
    for role, pairs in split_pairs.items():
        details = split_file_details.get(role, [])
        per_split_summary[role] = {
            "manifest_path": str(root / MANIFEST_ROLES[role]),
            "pair_count": len(pairs),
            "expected_count": EXPECTED_COUNTS[role],
            "count_matches_expected": len(pairs) == EXPECTED_COUNTS[role],
            "files_with_any_issue": sum(
                1 for d in details
                if not d.get("image_exists") or not d.get("mask_exists")
                or d.get("image_readable") is False or d.get("mask_readable") is False
                or d.get("dimensions_match") is False or d.get("mask_is_binary") is False
            ),
            "non_binary_mask_count": sum(1 for d in details if d.get("mask_is_binary") is False),
            "empty_mask_count": sum(1 for d in details if d.get("mask_is_empty") is True),
            "unique_image_hashes": len(split_digests.get(role, {}).get("images", {})),
            "unique_mask_hashes": len(split_digests.get(role, {}).get("masks", {})),
        }

    report = {
        "schema_version": "1.0",
        "timestamp_utc": timestamp,
        "project_root": str(root),
        "config_verified": {
            "train_manifest": str(root / MANIFEST_ROLES["train"]),
            "val_manifest": str(root / MANIFEST_ROLES["val"]),
            "uses_train_pranet_train": MANIFEST_ROLES["train"].endswith("train_pranet_train.tsv"),
            "uses_val_pranet": MANIFEST_ROLES["val"].endswith("val_pranet.tsv"),
        },
        "summary": {
            "total_manifests_checked": len(MANIFEST_ROLES),
            "total_pairs_across_all_manifests": sum(len(p) for p in split_pairs.values()),
            "total_unique_files_hashed": total_files_hashed,
            "total_bytes_read": total_bytes_read,
            "total_bytes_read_human": f"{total_bytes_read / (1 << 30):.3f} GiB",
            "elapsed_seconds": round(elapsed, 2),
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "all_gates_passed": all_passed,
            "exit_code": 0 if all_passed else 1,
        },
        "per_split": per_split_summary,
        "cross_split_checks": cross_results,
        "failures": failures,
        "warnings": warnings,
    }

    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    # -- 5. Final verdict ------------------------------------------------------
    print("\n" + "=" * 72)
    print("  FINAL VERDICT")
    print("=" * 72)
    print(f"  Manifests checked   : {len(MANIFEST_ROLES)}")
    print(f"  Total pairs         : {report['summary']['total_pairs_across_all_manifests']}")
    print(f"  Unique files hashed : {total_files_hashed}")
    print(f"  Total bytes read    : {report['summary']['total_bytes_read_human']}")
    print(f"  Elapsed             : {elapsed:.1f}s")
    print(f"  Failures            : {len(failures)}")
    print(f"  Warnings            : {len(warnings)}")
    print(f"  Report              : {report_path}")

    if all_passed:
        print("\n  ✅  ALL INTEGRITY GATES PASSED — exit code 0")
    else:
        print(f"\n  FAIL  {len(failures)} FAILURE(S) — exit code 1")
        print("  First 10 failures:")
        for f in failures[:10]:
            print(f"    [{f['gate']}] {f.get('detail', '')} | path={f.get('path', f.get('image', f.get('mask', '')))}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
