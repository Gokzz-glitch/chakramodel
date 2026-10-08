"""
Independent Forensic Verification & Stress-Testing Script
Authored by: auditor_m1_g15
Sole purpose: Empirically verify all claims and edge cases of backup_sync.py
"""

import datetime
import hashlib
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# Add scripts directory
PROJECT_ROOT = Path(r"M:\chakramodel")
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from backup_sync import (
    DEFAULT_CHUNK_SIZE,
    SyncStateManager,
    atomic_write_replace,
    classify_download_file,
    classify_target,
    is_personal_or_denied,
    is_within_scheduled_window,
    parse_time_str,
    recover_file,
    scan_and_recover_downloads,
    stream_sha256,
    validate_archive_integrity,
    verify_and_sync_target,
)


def run_audit_suite():
    print("=== STARTING INDEPENDENT AUDIT SUITE ===")
    results = {}

    # Test 1: Single-bit corruption detection and restoration
    print("\n--- Test 1: Single-bit corruption detection and restoration ---")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        src_dir = tmp_p / "src"
        tgt_dir = tmp_p / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        test_data = b"FORENSIC_INTEGRITY_CHECK_PAYLOAD_CHUNK_1234567890" * 50
        src_file = src_dir / "secure_data.bin"
        src_file.write_bytes(test_data)
        src_hash = hashlib.sha256(test_data).hexdigest()

        # Initial sync
        stats1 = verify_and_sync_target(src_dir, tgt_dir, set(), set())
        tgt_file = tgt_dir / "secure_data.bin"
        assert tgt_file.exists()
        assert stream_sha256(tgt_file) == src_hash

        # Corrupt exactly 1 byte (flip lowest bit of byte 10)
        corrupted_data = bytearray(test_data)
        corrupted_data[10] ^= 0x01
        tgt_file.write_bytes(bytes(corrupted_data))
        assert len(corrupted_data) == len(test_data), "Length must remain identical to force SHA-256 check"
        assert stream_sha256(tgt_file) != src_hash

        # Run verify and sync
        stats2 = verify_and_sync_target(src_dir, tgt_dir, set(), set())
        assert stats2["files_corrupted_fixed"] == 1
        assert tgt_file.read_bytes() == test_data
        assert stream_sha256(tgt_file) == src_hash
        print("PASS: Single-bit corruption with identical size detected and restored via SHA-256!")
        results["single_bit_corruption"] = "PASS"

    # Test 2: Deletion and Size-mismatch restoration
    print("\n--- Test 2: Deletion and Size-mismatch auto-fix ---")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        src_dir = tmp_p / "src"
        tgt_dir = tmp_p / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        (src_dir / "f1.txt").write_text("Hello World" * 10)
        (src_dir / "f2.txt").write_text("ChakraModel" * 20)
        verify_and_sync_target(src_dir, tgt_dir, set(), set())

        # Delete f1 on target
        (tgt_dir / "f1.txt").unlink()
        # Truncate f2 on target
        (tgt_dir / "f2.txt").write_text("ChakraModel")

        stats = verify_and_sync_target(src_dir, tgt_dir, set(), set())
        assert stats["files_missing_fixed"] == 1
        assert stats["files_corrupted_fixed"] == 1
        assert (tgt_dir / "f1.txt").read_text() == "Hello World" * 10
        assert (tgt_dir / "f2.txt").read_text() == "ChakraModel" * 20
        print("PASS: Deletion and size mismatch successfully auto-fixed!")
        results["deletion_and_size_mismatch"] = "PASS"

    # Test 3: Exhaustive Privacy Deny-Filter check
    print("\n--- Test 3: Exhaustive Privacy Deny-Filter check ---")
    denied_candidates = [
        "passport_scan.pdf",
        "Gokul_Passport_2026.pdf",
        "resume_2026.pdf",
        "CV_Profile.pdf",
        "profile.pdf",
        "lor-nit.pdf",
        "lor_nit_recommendation.pdf",
        "payment_receipt_102.pdf",
        "mess fees slip.pdf",
        "messfees_receipt.png",
        "electricity_bill.pdf",
        "schedule_calendar.ics",
        "corporate_leads.csv",
        "researcher_leads.csv",
        "sales_leads_q3.csv",
        "russia_moscow_contacts.csv",
        "priority_1_outreach.csv",
        "priority_2_dataset.csv",
        "installer.exe",
        "setup.msi",
        "batch_script.bat",
        "eclipse_ide.zip",
        "acer care center.exe",
        "chatgpt installer.exe",
        "chromesetup.exe",
        "desktop.ini",
        "screenshot_error.png",
        "opus_keyword_analysis.txt",
    ]
    all_denied = True
    for name in denied_candidates:
        p = Path(f"C:/Users/imgk3/Downloads/{name}")
        if not is_personal_or_denied(p):
            print(f"FAIL: Pattern not denied: {name}")
            all_denied = False
    assert all_denied, "Some privacy-sensitive files leaked through the filter!"
    print(f"PASS: All {len(denied_candidates)} privacy-sensitive files correctly blocked!")
    results["privacy_deny_filter"] = "PASS"

    # Test 4: Genuine ChakraModel indicator identification
    print("\n--- Test 4: ChakraModel indicator identification ---")
    allowed_candidates = [
        "mock_weights.zip",
        "om-krish-4-6 (2).ipynb",
        "om-finalkaggle-upload.zip",
        "polyp_dataset_cvc.zip",
        "combo2_best.pth",
        "pranet_kvasir_best.pth",
        "yolo26n.pt",
        "best.pt",
        "chakramodel_om_4.zip",
        "claudev7_eval.ipynb",
    ]
    all_allowed = True
    for name in allowed_candidates:
        p = Path(f"C:/Users/imgk3/Downloads/{name}")
        status, cat, dest = classify_download_file(p, PROJECT_ROOT)
        if status != "CHAKRAMODEL_ASSET":
            print(f"FAIL: Chakra asset rejected: {name} (status={status})")
            all_allowed = False
    assert all_allowed, "Some valid ChakraModel assets were rejected!"
    print(f"PASS: All {len(allowed_candidates)} ChakraModel assets correctly identified and classified!")
    results["chakramodel_asset_classification"] = "PASS"

    # Test 5: 49-Byte Stub Protection & Corrupt Zip Handling
    print("\n--- Test 5: 49-byte stub protection and corrupt zip rejection ---")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        dl_dir = tmp_p / "dl"
        model_p = tmp_p / "model"
        dl_dir.mkdir()
        model_p.mkdir()

        # Destination has a valid 500-byte archive
        dest_archive = model_p / "results" / "archives" / "dataset.zip"
        dest_archive.parent.mkdir(parents=True)
        valid_payload = b"VALID_ZIP_ARCHIVE_DATA_PAYLOAD" * 20
        dest_archive.write_bytes(valid_payload)

        # Downloads has 49-byte stub
        stub_file = dl_dir / "dataset.zip"
        stub_file.write_bytes(b"PK\x05\x06" + b"\x00" * 45)
        assert stub_file.stat().st_size == 49

        ledger = []
        act = recover_file(stub_file, dest_archive, "RESULTS_ARCHIVE", ledger)
        assert act == "BLOCKED_STUB_OVERWRITE"
        assert dest_archive.read_bytes() == valid_payload, "Destination was overwritten by stub!"

        # Downloads has a corrupted 200-byte zip
        corrupt_zip = dl_dir / "corrupt_weights.zip"
        corrupt_zip.write_bytes(b"PK\x03\x04" + b"BAD_CRC_DATA" * 15)
        dest_weights = model_p / "weights" / "corrupt_weights.zip"
        act2 = recover_file(corrupt_zip, dest_weights, "WEIGHTS_ARCHIVE", ledger)
        assert act2 == "SKIPPED_CORRUPT_ARCHIVE"
        assert not dest_weights.exists()
        print("PASS: 49-byte stub blocked and corrupt zip skipped!")
        results["stub_protection_and_corrupt_zip"] = "PASS"

    # Test 6: Time window boundary conditions
    print("\n--- Test 6: Time window boundary conditions ---")
    # 05:59:59 -> Outside
    assert is_within_scheduled_window("06:00", "11:00", current_time=datetime.time(5, 59, 59))[0] is False
    # 06:00:00 -> Inside
    assert is_within_scheduled_window("06:00", "11:00", current_time=datetime.time(6, 0, 0))[0] is True
    # 10:59:59 -> Inside
    assert is_within_scheduled_window("06:00", "11:00", current_time=datetime.time(10, 59, 59))[0] is True
    # 11:00:00 -> Inside
    assert is_within_scheduled_window("06:00", "11:00", current_time=datetime.time(11, 0, 0))[0] is True
    # 11:00:01 -> Outside
    assert is_within_scheduled_window("06:00", "11:00", current_time=datetime.time(11, 0, 1))[0] is False
    # 23:59:59 -> Outside
    assert is_within_scheduled_window("06:00", "11:00", current_time=datetime.time(23, 59, 59))[0] is False
    print("PASS: Time window boundary conditions verified strictly!")
    results["time_window_boundaries"] = "PASS"

    # Test 7: Atomic Write Replace SHA-256 verification
    print("\n--- Test 7: Atomic Write Replace SHA-256 verification ---")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        src = tmp_p / "src.dat"
        tgt = tmp_p / "tgt.dat"
        src.write_bytes(b"PAYLOAD_ATOMIC_REPLACE" * 100)

        ok = atomic_write_replace(src, tgt)
        assert ok is True
        assert tgt.exists()
        assert tgt.read_bytes() == src.read_bytes()
        assert stream_sha256(tgt) == stream_sha256(src)

        # Check that no temporary files remain in tgt directory
        tmp_files = list(tmp_p.glob("*.tmp_autofix*"))
        assert len(tmp_files) == 0, f"Temporary files leaked: {tmp_files}"
        print("PASS: Atomic write replace verified with zero temp leakage!")
        results["atomic_write_replace"] = "PASS"

    print("\n=== INDEPENDENT AUDIT SUITE COMPLETED SUCCESSFULLY ===")
    for k, v in results.items():
        print(f"  - {k}: {v}")
    return results


if __name__ == "__main__":
    run_audit_suite()
