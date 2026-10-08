#!/usr/bin/env python3
"""
test_oracle_checksums.py - Independent Checksum Verification Oracle

Independently streams dataset archives directly from disk to compute SHA-256 and MD5
hashes and cross-references them against verification_report.json.
"""

import hashlib
import json
import os
import sys
import time

TARGET_DIR = r"I:\My Drive\1509-chakramodelom\dataet"
REPORT_PATH = os.path.join(TARGET_DIR, "verification_report.json")

SAMPLE_FILES = [
    "endoscene-cvc300-polyp-raw-dataset.zip",
    "chakramodel-evaluation-datasets.zip",
    "final-om-evlautation-upload.zip",
    "finalmuruga-harae.zip",
    "polypdb-polyp-raw.zip",
    "polypgen20021-video.zip",
]


def compute_hashes_indep(filepath: str, buffer_size: int = 16 * 1024 * 1024):
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    total_bytes = 0
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(buffer_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest(), total_bytes


def main():
    if not os.path.exists(REPORT_PATH):
        sys.exit(f"Report not found at {REPORT_PATH}")

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    # Map filename -> hashes
    expected_by_filename = {}
    for slug, ds in report["datasets"].items():
        expected_by_filename[ds["archive_filename"]] = ds["hashes"]

    print("=" * 80)
    print("      INDEPENDENT VERIFICATION ORACLE - CHECKSUM VALIDATION")
    print("=" * 80)

    all_passed = True
    results = []

    for filename in SAMPLE_FILES:
        filepath = os.path.join(TARGET_DIR, filename)
        if not os.path.exists(filepath):
            print(f"[!] File not found: {filepath}")
            all_passed = False
            continue

        exp = expected_by_filename.get(filename)
        if not exp and filename == "finalmuruga-harae.zip":
            # Mirror alias for final-om-evlautation-upload.zip
            exp = expected_by_filename.get("final-om-evlautation-upload.zip")

        if not exp:
            print(f"[!] No expected record in report for {filename}")
            all_passed = False
            continue

        print(f"\n[*] Hashing {filename}...")
        t0 = time.time()
        c_sha256, c_md5, size_bytes = compute_hashes_indep(filepath)
        dt = time.time() - t0
        mb_per_sec = (size_bytes / (1024 * 1024)) / dt if dt > 0 else 0

        exp_sha256 = exp["sha256"]
        exp_md5 = exp["md5"]

        sha_match = c_sha256.lower() == exp_sha256.lower()
        md5_match = c_md5.lower() == exp_md5.lower()

        print(f"    Size: {size_bytes:,} bytes | Elapsed: {dt:.2f}s ({mb_per_sec:.1f} MB/s)")
        print(f"    Computed SHA-256: {c_sha256}")
        print(f"    Reported SHA-256: {exp_sha256}")
        print(f"    SHA-256 Match   : {sha_match}")
        print(f"    Computed MD5    : {c_md5}")
        print(f"    Reported MD5    : {exp_md5}")
        print(f"    MD5 Match       : {md5_match}")

        passed = sha_match and md5_match
        if not passed:
            all_passed = False

        results.append({
            "filename": filename,
            "size_bytes": size_bytes,
            "elapsed_s": round(dt, 2),
            "mb_per_sec": round(mb_per_sec, 1),
            "sha256": c_sha256,
            "md5": c_md5,
            "sha_match": sha_match,
            "md5_match": md5_match,
            "passed": passed,
        })

    print("\n" + "=" * 80)
    print("                     ORACLE VERIFICATION SUMMARY")
    print("=" * 80)
    for res in results:
        status_str = "PASSED" if res["passed"] else "FAILED"
        print(f"  [{status_str}] {res['filename']} ({res['size_bytes']:,} bytes) in {res['elapsed_s']}s")

    if all_passed:
        print("\n[+] VERDICT: ALL SAMPLE ARCHIVES MATCH BYTE-FOR-BYTE WITH ZERO CORRUPTION.")
        sys.exit(0)
    else:
        print("\n[-] VERDICT: CHECKSUM MISMATCH DETECTED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
