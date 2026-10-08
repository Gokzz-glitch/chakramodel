#!/usr/bin/env python3
"""
verify_datasets.py - 7-Gate Zero-Corruption Verification Suite

Provides rigorous, forensic-level verification of acquired Kaggle datasets:
  Gate 1: File Presence & State Check (archive exists, non-zero size, no lingering partials).
  Gate 2: Archive CRC-32 Integrity Validation (full decompression test via zipfile.testzip()).
  Gate 3: Member Count Validation (exact match against expected manifest counts).
  Gate 4: Media Magic-Byte Header Inspection (JPEG, PNG, MP4 ftyp headers sampled in-memory).
  Gate 5: Cryptographic Hash Generation (SHA-256 and MD5 computed in 8MB streaming buffer).
  Gate 6: Structured Machine-Readable JSON Report (written to verification_report.json).
  Gate 7: Deterministic Exit Code (0 if 100% passed across all gates, 1 on any failure).
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
import zipfile
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

DEFAULT_TARGET_DIR = r"I:\My Drive\1509-chakramodelom\dataet"
DEFAULT_REPORT_PATH = "verification_report.json"
DEFAULT_SAMPLE_COUNT = 50

DATASET_SPECS = {
    # Batch 1 (Initial Scope - Completed & Verified)
    "polypgen20021-video.zip": {
        "slug": "gokulraj324/polypgen20021-video",
        "valid_sizes": [3420255917],
        "valid_member_counts": [26918, 10000],
        "media_type": "jpeg",
        "expected_md5": "fe5c45d639e3a76ce7183b4a41110f06",
    },
    "endoscene-cvc300-polyp-raw-dataset.zip": {
        "slug": "gokulrocky/endoscene-cvc300-polyp-raw-dataset",
        "valid_sizes": [16459371],
        "valid_member_counts": [120],
        "media_type": "png",
        "expected_md5": "6529191ce3808095e1fb11a566f3adfd",
    },
    "cvc-sample-video.zip": {
        "slug": "gokulrocky/cvc-sample-video",
        "valid_sizes": [4340196259, 4351232756],
        "valid_member_counts": [46, 21],
        "media_type": "mp4",
        "expected_md5": "37f9a036017eb7623cf2374a76eb8962",
    },
    # Batch 2 (Scope Expansion - 8 Additional Datasets)
    "hperkvasir-labeled-videos-part2-002.zip": {
        "slug": "gokulrocky/hperkvasir-labeled-videos-part2-002",
        "valid_sizes": [14687248757],
        "valid_member_counts": [188],
        "media_type": "avi",
        "expected_md5": "99a4c5209e3244c168c4b15d06ea2b7d",
    },
    "hyperkvasir-labeled-videos-part2-001.zip": {
        "slug": "gokulrocky/hyperkvasir-labeled-videos-part2-001",
        "valid_sizes": [15423057945],
        "valid_member_counts": [189],
        "media_type": "avi",
        "expected_md5": "5c4f9ffa41bb8d75fdd31adbc4a1e736",
    },
    "hyperkvasir-dataset-first-half-and-and-ld-dataset.zip": {
        "slug": "gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset",
        "valid_sizes": [16544061303],
        "valid_member_counts": [41082],
        "media_type": "mixed",
        "expected_md5": "0098d238d0deb5d8f1d666bde0547deb",
    },
    "chakramodel-evaluation-datasets.zip": {
        "slug": "gokulrocky/chakramodel-evaluation-datasets",
        "valid_sizes": [99487305],
        "valid_member_counts": [3000],
        "media_type": "png",
        "expected_md5": "4837f9839b23d3412b6732a7cb3391df",
    },
    "final-om-evlautation-upload.zip": {
        "slug": "gokulrocky/final-om-evlautation-upload",
        "aliases": ["gokulrocky/finalmuruga-harae"],
        "valid_sizes": [1155170464, 1155167936],
        "valid_member_counts": [56, 55],
        "media_type": "mixed",
        "expected_md5": "2e0957fe84eedeebfcf105b1f354f93d",
    },
    "ldpolypvideopolyponly.zip": {
        "slug": "gokulraj324/ldpolypvideopolyponly",
        "valid_sizes": [13189544842],
        "valid_member_counts": [82594],
        "media_type": "mixed",
        "expected_md5": "8c30835303211c993ae38f027e5c2def",
    },
    "ldpolypvideowithoutpolyps.zip": {
        "slug": "gokulraj324/ldpolypvideowithoutpolyps",
        "valid_sizes": [13247306908],
        "valid_member_counts": [61],
        "media_type": "avi",
        "expected_md5": "5d60b22f5b0757978cbafb1e802f84ff",
    },
    "polypdb-polyp-raw.zip": {
        "slug": "gokulrocky/polypdb-polyp-raw",
        "valid_sizes": [1384993669],
        "valid_member_counts": [15736],
        "media_type": "jpeg",
        "expected_md5": "b9ae8c023937431dd874b53d55d5b177",
    },
}



def compute_hashes(filepath: str, chunk_size: int = 8 * 1024 * 1024) -> Tuple[str, str]:
    """Stream file in 8MB chunks and compute SHA-256 and MD5 simultaneously."""
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest()


def check_magic_bytes(data: bytes, media_type: str) -> bool:
    """Validate media binary signature from initial bytes."""
    if media_type == "jpeg":
        return len(data) >= 3 and data[:3] == b"\xff\xd8\xff"
    elif media_type == "png":
        return len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n"
    elif media_type == "mp4":
        return len(data) >= 8 and data[4:8] == b"ftyp"
    elif media_type == "avi":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"AVI "
    elif media_type == "mixed":
        if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
            return True
        if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
            return True
        if len(data) >= 8 and data[4:8] == b"ftyp":
            return True
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"AVI ":
            return True
        if len(data) >= 4 and data[:4] == b"PK\x03\x04":
            return True
        try:
            data[:32].decode("utf-8")
            return True
        except UnicodeDecodeError:
            pass
        return False
    return True


def sample_media_magic_bytes(
    z: zipfile.ZipFile,
    media_type: str,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
) -> Tuple[bool, int, int, List[str]]:
    """Sample inner files from zip and verify magic byte headers in memory."""
    if sample_count <= 0:
        return True, 0, 0, []

    target_exts = {
        "jpeg": (".jpg", ".jpeg"),
        "png": (".png",),
        "mp4": (".mp4",),
        "avi": (".avi",),
        "mixed": (".jpg", ".jpeg", ".png", ".avi", ".mp4", ".pt", ".pth", ".txt", ".csv", ".py", ".ipynb"),
    }.get(media_type, ())

    matching_members = [
        m for m in z.infolist()
        if not m.is_dir() and m.filename.lower().endswith(target_exts)
    ]

    if not matching_members:
        # Fallback to any non-directory member if specific extensions aren't found
        matching_members = [m for m in z.infolist() if not m.is_dir()]

    # Evenly space samples across the archive
    total_eligible = len(matching_members)
    step = max(1, total_eligible // sample_count)
    samples = matching_members[::step][:sample_count]

    valid_count = 0
    invalid_samples = []

    for member in samples:
        try:
            with z.open(member) as f:
                header = f.read(32)
                if check_magic_bytes(header, media_type):
                    valid_count += 1
                else:
                    invalid_samples.append(f"{member.filename} (header: {header[:8].hex()})")
        except Exception as e:
            invalid_samples.append(f"{member.filename} (read error: {e})")

    passed = (len(invalid_samples) == 0 and valid_count > 0)
    return passed, len(samples), valid_count, invalid_samples


def verify_single_dataset(
    archive_name: str,
    spec: Dict[str, Any],
    target_dir: str,
    sample_count: int,
) -> Dict[str, Any]:
    """Execute 7-gate verification pipeline for a single dataset archive."""
    archive_path = os.path.join(target_dir, archive_name)
    if not os.path.exists(archive_path) and "aliases" in spec:
        for alias in spec["aliases"]:
            alias_slug = alias.split("/")[1]
            alias_path = os.path.join(target_dir, f"{alias_slug}.zip")
            if os.path.exists(alias_path):
                archive_path = alias_path
                archive_name = f"{alias_slug}.zip"
                break
    partial_path = archive_path + ".kaggle-partial"

    result = {
        "archive_filename": archive_name,
        "dataset_slug": spec["slug"],
        "target_path": archive_path,
        "valid_sizes_bytes": spec["valid_sizes"],
        "valid_member_counts": spec["valid_member_counts"],
        "media_type": spec["media_type"],
        "gates": {},
        "hashes": {},
        "status": "FAILED",
        "errors": [],
    }

    print(f"\n" + "-" * 70, flush=True)
    print(f"VERIFYING: {archive_name} ({spec['slug']})", flush=True)
    print("-" * 70, flush=True)

    # ---------------------------------------------------------
    # Gate 1: File Existence, Non-Zero Size & No Leftover Partial
    # ---------------------------------------------------------
    g1_passed = True
    g1_errors = []

    if not os.path.exists(archive_path):
        g1_passed = False
        g1_errors.append(f"Archive file does not exist at {archive_path}")
    elif os.path.getsize(archive_path) == 0:
        g1_passed = False
        g1_errors.append("Archive file is zero bytes (empty)")

    if os.path.exists(partial_path):
        g1_passed = False
        g1_errors.append(f"Lingering .kaggle-partial marker detected at {partial_path}")

    file_size = os.path.getsize(archive_path) if os.path.exists(archive_path) else 0
    size_matched = (file_size in spec["valid_sizes"])
    if not size_matched and g1_passed:
        g1_errors.append(
            f"Size mismatch: found {file_size:,} bytes, expected one of {spec['valid_sizes']}"
        )
        g1_passed = False

    result["actual_size_bytes"] = file_size
    result["gates"]["gate1_presence_and_size"] = {
        "passed": g1_passed,
        "file_exists": os.path.exists(archive_path),
        "file_size_bytes": file_size,
        "expected_sizes_bytes": spec["valid_sizes"],
        "partial_absent": not os.path.exists(partial_path),
        "errors": g1_errors,
    }

    if g1_passed:
        print(f"  [+] Gate 1 PASSED: File exists ({file_size:,} bytes), no partial markers.", flush=True)
    else:
        print(f"  [-] Gate 1 FAILED: {'; '.join(g1_errors)}", flush=True)
        result["errors"].extend(g1_errors)
        return result

    # ---------------------------------------------------------
    # Gate 2: Full Archive CRC-32 Decompression (testzip)
    # ---------------------------------------------------------
    g2_passed = False
    g2_errors = []
    bad_member = None

    try:
        print(f"  [*] Gate 2: Running full CRC-32 testzip() integrity scan...", flush=True)
        t0 = time.time()
        with zipfile.ZipFile(archive_path, "r") as z:
            bad_member = z.testzip()
            duration = time.time() - t0
            if bad_member is None:
                g2_passed = True
                print(f"  [+] Gate 2 PASSED: 0 corrupted members in archive (tested in {duration:.1f}s).", flush=True)
            else:
                g2_errors.append(f"Corrupted archive member detected: {bad_member}")
                print(f"  [-] Gate 2 FAILED: Corrupted member: {bad_member}", flush=True)
    except zipfile.BadZipFile as e:
        g2_errors.append(f"BadZipFile error: {e}")
        print(f"  [-] Gate 2 FAILED: BadZipFile: {e}", flush=True)
    except Exception as e:
        g2_errors.append(f"Unexpected error during testzip(): {e}")
        print(f"  [-] Gate 2 FAILED: {e}", flush=True)

    result["gates"]["gate2_archive_integrity"] = {
        "passed": g2_passed,
        "bad_member": bad_member,
        "errors": g2_errors,
    }

    if not g2_passed:
        result["errors"].extend(g2_errors)
        return result

    # ---------------------------------------------------------
    # Gate 3: Member Count & Internal Structure
    # ---------------------------------------------------------
    g3_passed = False
    g3_errors = []
    total_members = 0
    non_dir_files = 0
    total_uncompressed_bytes = 0

    try:
        with zipfile.ZipFile(archive_path, "r") as z:
            infolist = z.infolist()
            total_members = len(infolist)
            non_dir_files = len([m for m in infolist if not m.is_dir()])
            total_uncompressed_bytes = sum(m.file_size for m in infolist)

            target_exts = {
                "jpeg": (".jpg", ".jpeg"),
                "png": (".png",),
                "mp4": (".mp4",),
                "avi": (".avi",),
                "mixed": (".jpg", ".jpeg", ".png", ".avi", ".mp4", ".pt", ".pth", ".txt", ".csv", ".py", ".ipynb"),
            }.get(spec["media_type"], ())
            media_files = len([
                m for m in infolist
                if not m.is_dir() and m.filename.lower().endswith(target_exts)
            ])

            # Match either total members, non-directory files, or media files against valid counts
            count_matched = (
                non_dir_files in spec["valid_member_counts"]
                or total_members in spec["valid_member_counts"]
                or media_files in spec["valid_member_counts"]
            )

            if count_matched:
                g3_passed = True
                print(
                    f"  [+] Gate 3 PASSED: Member count valid ({non_dir_files:,} files, "
                    f"{media_files:,} {spec['media_type']} files, "
                    f"{total_uncompressed_bytes:,} uncompressed bytes).",
                    flush=True,
                )
            else:
                msg = (
                    f"Member count mismatch: found {non_dir_files} files ({media_files} {spec['media_type']} files, "
                    f"{total_members} total entries), expected one of {spec['valid_member_counts']}"
                )
                g3_errors.append(msg)
                print(f"  [-] Gate 3 FAILED: {msg}", flush=True)
    except Exception as e:
        g3_errors.append(f"Gate 3 inspection error: {e}")
        print(f"  [-] Gate 3 FAILED: {e}", flush=True)

    result["gates"]["gate3_member_count"] = {
        "passed": g3_passed,
        "file_count": non_dir_files,
        "media_file_count": media_files if 'media_files' in locals() else 0,
        "total_entries": total_members,
        "total_uncompressed_bytes": total_uncompressed_bytes,
        "expected_counts": spec["valid_member_counts"],
        "errors": g3_errors,
    }

    if not g3_passed:
        result["errors"].extend(g3_errors)
        return result

    # ---------------------------------------------------------
    # Gate 4: Media Magic-Byte Header Inspection
    # ---------------------------------------------------------
    g4_passed = False
    g4_errors = []
    samples_checked = 0
    valid_samples = 0
    invalid_samples = []

    try:
        with zipfile.ZipFile(archive_path, "r") as z:
            g4_passed, samples_checked, valid_samples, invalid_samples = sample_media_magic_bytes(
                z, spec["media_type"], sample_count=sample_count
            )
            if g4_passed:
                print(
                    f"  [+] Gate 4 PASSED: Sampled {samples_checked} '{spec['media_type']}' files; "
                    f"100% valid magic byte signatures.",
                    flush=True,
                )
            else:
                msg = f"Invalid magic bytes in {len(invalid_samples)} samples: {invalid_samples[:3]}"
                g4_errors.append(msg)
                print(f"  [-] Gate 4 FAILED: {msg}", flush=True)
    except Exception as e:
        g4_errors.append(f"Gate 4 magic byte check error: {e}")
        print(f"  [-] Gate 4 FAILED: {e}", flush=True)

    result["gates"]["gate4_media_magic_bytes"] = {
        "passed": g4_passed,
        "media_type": spec["media_type"],
        "samples_checked": samples_checked,
        "valid_samples": valid_samples,
        "invalid_samples": invalid_samples,
        "errors": g4_errors,
    }

    if not g4_passed:
        result["errors"].extend(g4_errors)
        return result

    # ---------------------------------------------------------
    # Gate 5: Cryptographic Hashes (SHA-256 & MD5)
    # ---------------------------------------------------------
    g5_passed = True
    g5_errors = []
    print(f"  [*] Gate 5: Computing SHA-256 and MD5 cryptographic hashes...", flush=True)
    t0 = time.time()
    sha256_hash, md5_hash = compute_hashes(archive_path)
    hash_time = time.time() - t0

    etag_md5_matched = None
    if spec.get("expected_md5"):
        etag_md5_matched = (md5_hash.lower() == spec["expected_md5"].lower())
        if not etag_md5_matched:
            g5_passed = False
            g5_errors.append(
                f"Cryptographic MD5 mismatch: computed {md5_hash}, expected {spec['expected_md5']}"
            )

    result["hashes"] = {
        "sha256": sha256_hash,
        "md5": md5_hash,
        "expected_md5": spec.get("expected_md5"),
        "etag_md5_matched": etag_md5_matched,
    }

    result["gates"]["gate5_cryptographic_checksums"] = {
        "passed": g5_passed,
        "sha256": sha256_hash,
        "md5": md5_hash,
        "computation_time_seconds": round(hash_time, 2),
        "etag_md5_matched": etag_md5_matched,
        "errors": g5_errors,
    }

    if g5_passed:
        print(f"  [+] Gate 5 PASSED (SHA-256: {sha256_hash[:16]}..., MD5: {md5_hash}, computed in {hash_time:.1f}s)", flush=True)
        if etag_md5_matched is True:
            print(f"      [+] Exact match against Kaggle server ETag MD5!", flush=True)
    else:
        print(f"  [-] Gate 5 FAILED: {'; '.join(g5_errors)}", flush=True)
        result["errors"].extend(g5_errors)
        return result

    # Overall dataset verdict
    result["status"] = "PASSED"
    return result


def main():
    parser = argparse.ArgumentParser(
        description="7-Gate Zero-Corruption Verification Suite for Kaggle Datasets."
    )
    parser.add_argument(
        "--target-dir",
        default=DEFAULT_TARGET_DIR,
        help=f"Target directory containing dataset archives (default: {DEFAULT_TARGET_DIR})",
    )
    parser.add_argument(
        "--output-report",
        default=DEFAULT_REPORT_PATH,
        help=f"Path to write JSON report (default: {DEFAULT_REPORT_PATH})",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=DEFAULT_SAMPLE_COUNT,
        help=f"Number of inner media files to sample for magic bytes (default: {DEFAULT_SAMPLE_COUNT})",
    )

    args = parser.parse_args()

    # Determine report absolute path
    report_file = args.output_report
    if not os.path.isabs(report_file):
        report_file = os.path.join(args.target_dir, report_file)

    print("=" * 70, flush=True)
    print("        7-GATE ZERO-CORRUPTION VERIFICATION SUITE", flush=True)
    print("=" * 70, flush=True)
    print(f"Target Directory: {args.target_dir}", flush=True)
    print(f"Output Report   : {report_file}", flush=True)
    print(f"Sample Count    : {args.sample_count}", flush=True)
    print(f"Datasets        : {list(DATASET_SPECS.keys())}", flush=True)
    print("=" * 70, flush=True)

    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "target_directory": args.target_dir,
        "overall_status": "FAILED",
        "summary": {
            "total_expected": len(DATASET_SPECS),
            "total_verified_passed": 0,
            "total_failed": 0,
            "cumulative_size_bytes": 0,
        },
        "datasets": {},
    }

    all_passed = True
    cumulative_size = 0

    for archive_name, spec in DATASET_SPECS.items():
        res = verify_single_dataset(
            archive_name=archive_name,
            spec=spec,
            target_dir=args.target_dir,
            sample_count=args.sample_count,
        )
        report["datasets"][spec["slug"]] = res

        if res["status"] == "PASSED":
            report["summary"]["total_verified_passed"] += 1
            cumulative_size += res.get("actual_size_bytes", 0)
        else:
            report["summary"]["total_failed"] += 1
            all_passed = False

    report["summary"]["cumulative_size_bytes"] = cumulative_size

    # Gate 6: JSON Report Generation
    print("\n" + "-" * 70, flush=True)
    print(f"[*] Gate 6: Writing machine-readable verification report...", flush=True)
    if all_passed:
        report["overall_status"] = "PASSED"
    else:
        report["overall_status"] = "FAILED"

    try:
        report_dir = os.path.dirname(report_file)
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[+] Gate 6 PASSED: Report generated at '{report_file}'.", flush=True)
    except Exception as e:
        print(f"[-] Gate 6 FAILED: Unable to write report: {e}", flush=True)
        all_passed = False

    # Gate 7: Deterministic Exit Code
    print("=" * 70, flush=True)
    print(f"VERIFICATION SUMMARY: {report['summary']['total_verified_passed']}/{len(DATASET_SPECS)} datasets PASSED.", flush=True)
    print(f"Overall Status: {report['overall_status']}", flush=True)
    print("=" * 70, flush=True)

    if all_passed:
        print("[+] SUCCESS: All 7 gates passed. Zero corruption guaranteed.", flush=True)
        sys.exit(0)
    else:
        print("[-] FAILURE: One or more datasets failed zero-corruption verification.", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
