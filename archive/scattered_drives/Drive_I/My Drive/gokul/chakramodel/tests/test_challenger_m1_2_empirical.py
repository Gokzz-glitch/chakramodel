"""
Empirical Challenger Test Harness for Acceptance Criteria C, D, & E
Author: challenger_m1_2_g15
Date: 2026-09-16

Tests:
1. Downloads Recovery (Criteria C):
   - Valid mock weights zip containing .pth / .pt files
   - Corrupted zip rejection (both truncated archives and bad CRC32 payloads)
   - 49-byte stub protection against overwriting healthy deliverables
   - Flaw analysis: 49-byte stub without indicator vs with indicator
   - Personal files privacy deny-filter (standard & adversarial disguised names)
   - Vulnerability detection: mess_fees regex gap
   - Raw .pth / .pt standalone checkpoint identification and recovery
2. Standalone Execution (Criteria D):
   - CLI invocation of scripts/backup_sync.py with --all --dry-run
   - CLI --help verification
   - Error code on invalid flags
3. Task Scheduler & Scheduled Sync (Criteria E):
   - XML schema validation (LogonTrigger, PT6M delay, InteractiveToken, battery settings)
   - Time window boundary enforcement (06:00 - 11:00 AM)
   - --startup-task clean exit code 0 when outside window
   - Daily execution guard: skip second run on same calendar day
   - Daily execution guard: retry on previous failure
   - Daily execution guard: --force flag override
"""

import datetime
import io
import json
import os
import pickle
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import List, Optional

import pytest

# Ensure scripts directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from backup_sync import (
    DEFAULT_CHUNK_SIZE,
    SyncStateManager,
    atomic_write_replace,
    classify_download_file,
    classify_target,
    is_personal_or_denied,
    is_chakramodel_asset,
    is_within_scheduled_window,
    main,
    scan_and_recover_downloads,
    stream_sha256,
    validate_archive_integrity,
    verify_and_sync_all_targets,
    verify_and_sync_target,
)


# ===========================================================================
# Fixture Generators & Oracles
# ===========================================================================

def create_valid_mock_weights_zip(dest_path: Path, pth_files: Optional[List[str]] = None) -> Path:
    """Generate a genuine zip archive containing realistic PyTorch state_dicts."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    files_to_pack = pth_files or ["chakra_encoder.pth", "chakra_decoder.pt", "best_weights.pth"]

    mock_state_dict = {
        "model.backbone.layer1.weight": ("mock_tensor", [1.0, 2.0, 3.0]),
        "model.head.bias": ("mock_tensor", [0.5, -0.5]),
        "epoch": 50,
        "best_dice": 0.892,
    }
    raw_bytes = pickle.dumps(mock_state_dict, protocol=4)

    with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for fname in files_to_pack:
            z.writestr(fname, raw_bytes)
        z.writestr("metadata.json", json.dumps({"model": "ChakraModel", "version": "2.0"}))
    return dest_path


def create_corrupted_truncated_zip(dest_path: Path) -> Path:
    """Generate a truncated zip archive (cut off mid-stream)."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\xDE\xAD\xBE\xEF" * 16)
    return dest_path


def create_corrupted_crc_zip(dest_path: Path) -> Path:
    """
    Generate a zip archive with valid directory headers but intentionally
    tampered compressed member payloads, causing CRC32 failure on extraction.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("model_weights.pth", b"ACTUAL_COMPRESSED_PAYLOAD_TENSOR_DATA" * 50)
    raw_data = bytearray(bio.getvalue())

    # Flip bits in the compressed payload area while keeping header and central dir
    payload_idx = raw_data.find(b"ACTUAL_COMPRESSED")
    if payload_idx != -1:
        raw_data[payload_idx] ^= 0xFF
        raw_data[payload_idx + 1] ^= 0xAA
    else:
        raw_data[30] ^= 0xFF

    dest_path.write_bytes(bytes(raw_data))
    return dest_path


def create_stub_49_byte_file(dest_path: Path) -> Path:
    """Create exact 49-byte empty/stub zip archive."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    stub_content = b"PK\x05\x06" + b"\x00" * 45
    dest_path.write_bytes(stub_content)
    assert dest_path.stat().st_size == 49
    return dest_path


# ===========================================================================
# 1. Downloads Recovery & Privacy Filter Stress-Testing (Criteria C)
# ===========================================================================

class TestDownloadsRecoveryEmpirical:
    """Adversarial stress-testing of Downloads recovery, archive checks, and privacy deny-filters."""

    def test_valid_weights_recovery_with_integrity(self, tmp_path):
        """Valid weights archives containing .pth / .pt are verified and recovered into weights/."""
        mock_dl = tmp_path / "Downloads"
        model_root = tmp_path / "chakramodel"
        ledger_file = tmp_path / "logs" / "ledger.json"
        mock_dl.mkdir()
        model_root.mkdir()

        # Place valid mock weights zip
        mock_zip = mock_dl / "mock_weights.zip"
        create_valid_mock_weights_zip(mock_zip, ["chakra_net.pth", "classifier.pt"])

        # Validate archive integrity oracle
        is_valid, err = validate_archive_integrity(mock_zip)
        assert is_valid is True, f"Mock weights zip should be valid: {err}"

        # Execute recovery
        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_dl],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        expected_dest = model_root / "weights" / "mock_weights.zip"
        assert expected_dest.exists(), "Recovered weights zip must exist at destination"
        assert stats["recovered"] == 1
        assert stream_sha256(expected_dest) == stream_sha256(mock_zip)

        # Inspect recovered zip content integrity
        with zipfile.ZipFile(expected_dest, "r") as z:
            assert "chakra_net.pth" in z.namelist()
            assert "classifier.pt" in z.namelist()
            assert z.testzip() is None

    def test_corrupted_zip_safe_rejection(self, tmp_path):
        """Corrupted zips (truncated and CRC errors) must be rejected and never written to repo."""
        mock_dl = tmp_path / "Downloads"
        model_root = tmp_path / "chakramodel"
        ledger_file = tmp_path / "logs" / "ledger.json"
        mock_dl.mkdir()
        model_root.mkdir()

        # 1. Truncated zip
        trunc_zip = mock_dl / "chakra_truncated_weights.zip"
        create_corrupted_truncated_zip(trunc_zip)

        # 2. Corrupted CRC payload zip
        bad_crc_zip = mock_dl / "chakra_bad_crc_weights.zip"
        create_corrupted_crc_zip(bad_crc_zip)

        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_dl],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        assert stats["skipped_corrupt"] == 2, f"Both corrupted archives must be rejected, got {stats}"
        assert not (model_root / "weights" / "chakra_truncated_weights.zip").exists()
        assert not (model_root / "weights" / "chakra_bad_crc_weights.zip").exists()
        assert not (model_root / "weights" / "archive" / "chakra_bad_crc_weights.zip").exists()

        # Verify ledger recorded the corruption
        with open(ledger_file, "r", encoding="utf-8") as f:
            ledger = json.load(f)
        corrupt_entries = [e for e in ledger if e.get("action") == "SKIPPED_CORRUPT_ARCHIVE"]
        assert len(corrupt_entries) == 2

    def test_49_byte_stub_protection_with_indicator_over_existing_target(self, tmp_path):
        """A 49-byte stub zip with chakra indicator in Downloads must NEVER overwrite an existing valid deliverable."""
        mock_dl = tmp_path / "Downloads"
        model_root = tmp_path / "chakramodel"
        ledger_file = tmp_path / "logs" / "ledger.json"
        mock_dl.mkdir()
        model_root.mkdir()

        # Place healthy existing file in model root
        existing_target = model_root / "results" / "archives" / "chakra_model_output.zip"
        existing_target.parent.mkdir(parents=True, exist_ok=True)
        genuine_content = b"HEALTHY_MODEL_OUTPUT_VALUABLE_ARTIFACT" * 20
        existing_target.write_bytes(genuine_content)
        genuine_hash = stream_sha256(existing_target)

        # Place 49-byte stub with chakra indicator in Downloads
        stub_file = mock_dl / "chakra_model_output.zip"
        create_stub_49_byte_file(stub_file)

        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_dl],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        assert stats["blocked_stubs"] >= 1, "49-byte stub should have been blocked"
        assert existing_target.read_bytes() == genuine_content, "Existing file was corrupted/overwritten!"
        assert stream_sha256(existing_target) == genuine_hash

    def test_empirical_finding_model_output_zip_without_indicator(self, tmp_path):
        """
        With remediation, 'model_output' is recognized in CHAKRA_INDICATORS, and
        stub archive protection unconditionally blocks the 49-byte stub zip from being recovered.
        """
        mock_dl = tmp_path / "Downloads"
        model_root = tmp_path / "chakramodel"
        ledger_file = tmp_path / "logs" / "ledger.json"
        mock_dl.mkdir()
        model_root.mkdir()

        stub_file = mock_dl / "model_output.zip"
        create_stub_49_byte_file(stub_file)

        # Direct asset evaluation on clean path: 'model_output' is now an indicator keyword
        is_asset = is_chakramodel_asset(stub_file)
        assert is_asset is True, (
            "model_output.zip with 'model_output' in indicators is recognized as a ChakraModel asset"
        )

        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_dl],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        # Because it's recognized as an asset and is < 100 bytes, stub protection blocks it
        assert stats["unrelated_ignored"] == 0
        assert stats["blocked_stubs"] == 1
        assert stats["recovered"] == 0

    def test_personal_files_privacy_filter_stress(self, tmp_path):
        """Verify strict denial of standard personal, confidential, and credential documents."""
        mock_dl = tmp_path / "Downloads"
        model_root = tmp_path / "chakramodel"
        ledger_file = tmp_path / "logs" / "ledger.json"
        mock_dl.mkdir()
        model_root.mkdir()

        personal_files = [
            "Gokul_Passport_Copy.pdf",
            "passport_photo_scan.jpg",
            "Gokul_K_Resume_2026.pdf",
            "Updated_Resume.docx",
            "candidate_profile.pdf",
            "lor-nit_recommendation_letter.pdf",
            "corporate_leads_all.csv",
            "researcher_leads_q4.csv",
            "russia_moscow_delegation.txt",
            "priority_1_leads_outreach.csv",
            "hotel_booking_receipt.pdf",
            "payment_bill_september.pdf",
            "calendar_event.ics",
            "chatgpt_installer.exe",
            "chromesetup.exe",
            "run_script.bat",
        ]

        for fname in personal_files:
            (mock_dl / fname).write_text(f"CONFIDENTIAL DATA FOR {fname}", encoding="utf-8")

        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_dl],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        assert stats["privacy_denied"] == len(personal_files)
        assert stats["recovered"] == 0

    def test_adversarial_disguised_personal_files_stress(self, tmp_path):
        """Disguised personal files with chakra indicators are still blocked by privacy deny patterns."""
        mock_dl = tmp_path / "Downloads"
        model_root = tmp_path / "chakramodel"
        ledger_file = tmp_path / "logs" / "ledger.json"
        mock_dl.mkdir()
        model_root.mkdir()

        disguised_files = [
            "chakra_passport_scan.pdf",
            "polyp_resume_v2.pdf",
            "yolo_corporate_leads.csv",
            "weights_payment_receipt.pdf",
            "bytetrack_hotel_booking.pdf",
        ]

        for fname in disguised_files:
            (mock_dl / fname).write_text(f"DISGUISED SENSITIVE DATA: {fname}", encoding="utf-8")

        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_dl],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        assert stats["privacy_denied"] == len(disguised_files)
        assert stats["recovered"] == 0

    def test_empirical_vulnerability_mess_fees_regex_gap(self):
        """
        With remediation, PERSONAL_DENY_REGEX matches 'mess[\\s_\\-]*fees?', correctly catching
        'kvasir_mess_fees.pdf' and denying it under Tier 1 privacy filter.
        """
        # 1. 'mess fees' (with space) matches regex
        assert is_personal_or_denied(Path("kvasir_mess fees.pdf")) is True

        # 2. 'mess_fees' (with underscore) matches regex with remediation
        assert is_personal_or_denied(Path("kvasir_mess_fees.pdf")) is True, (
            "Remediation confirmed: mess_fees with underscore is caught by PERSONAL_DENY_REGEX"
        )

        # 3. And because it matches privacy deny filter, it is classified as DENY_PRIVACY
        cls_type, cat, dest = classify_download_file(Path("kvasir_mess_fees.pdf"))
        assert cls_type == "DENY_PRIVACY", "Private mess fees document blocked by privacy filter"
        assert dest is None

    def test_raw_pth_and_pt_standalone_recovery(self, tmp_path):
        """Standalone raw checkpoints (.pth / .pt) in downloads are properly categorized and recovered."""
        mock_dl = tmp_path / "Downloads"
        model_root = tmp_path / "chakramodel"
        ledger_file = tmp_path / "logs" / "ledger.json"
        mock_dl.mkdir()
        model_root.mkdir()

        # Place raw checkpoints
        (mock_dl / "yolov8n_polyp_best.pt").write_bytes(b"YOLO_CHECKPOINT_DATA")
        (mock_dl / "chakra_transformer_best.pth").write_bytes(b"TRANSFORMER_CHECKPOINT_DATA")

        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_dl],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        yolo_dest = model_root / "weights" / "yolo" / "yolov8n_polyp_best.pt"
        ckpt_dest = model_root / "weights" / "checkpoints" / "chakra_transformer_best.pth"

        assert yolo_dest.exists(), "YOLO checkpoint should be recovered to weights/yolo/"
        assert ckpt_dest.exists(), "Model checkpoint should be recovered to weights/checkpoints/"
        assert stats["recovered"] == 2


# ===========================================================================
# 2. Standalone Execution Stress-Testing (Criteria D)
# ===========================================================================

class TestStandaloneExecutionEmpirical:
    """Stress-testing standalone process execution, CLI interface, and error handling."""

    def test_standalone_cli_dry_run_isolated(self, tmp_path):
        """CLI execution of python backup_sync.py --all --dry-run completes with exit code 0."""
        src_dir = tmp_path / "source"
        tgt_dir = tmp_path / "target"
        dl_dir = tmp_path / "downloads"
        src_dir.mkdir()
        tgt_dir.mkdir()
        dl_dir.mkdir()

        # Populate sample files in source
        (src_dir / "test.py").write_text("print('test')", encoding="utf-8")
        (src_dir / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")

        state_file = tmp_path / "state.json"
        log_file = tmp_path / "sync.log"

        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--source-dir", str(src_dir),
            "--target-dirs", str(tgt_dir),
            "--downloads-dirs", str(dl_dir),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
            "--all",
            "--dry-run",
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0, f"Failed with code {proc.returncode}.\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        assert "ChakraModel Backup Sync finished with status: SUCCESS" in proc.stdout

    def test_cli_help_flag(self):
        """python backup_sync.py --help must display usage and exit code 0."""
        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        proc = subprocess.run([sys.executable, str(script_path), "--help"], capture_output=True, text=True)
        assert proc.returncode == 0
        assert "usage: backup_sync.py" in proc.stdout.lower()
        assert "--startup-task" in proc.stdout
        assert "--recover-downloads" in proc.stdout
        assert "--verify-and-sync" in proc.stdout

    def test_cli_invalid_arguments_returns_error(self):
        """Supplying invalid CLI arguments must cleanly return non-zero exit code (code 2 for argparse)."""
        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        proc = subprocess.run([sys.executable, str(script_path), "--non-existent-option"], capture_output=True, text=True)
        assert proc.returncode != 0


# ===========================================================================
# 3. Scheduled Sync & Task Scheduler Stress-Testing (Criteria E)
# ===========================================================================

class TestScheduledSyncAndTaskSchedulerEmpirical:
    """Stress-testing Task Scheduler XML configuration, time window enforcement, and daily guards."""

    def test_task_scheduler_xml_schema_conformance(self):
        """Validate task_scheduler_config.xml conformance against MS Task Scheduler schema."""
        xml_path = PROJECT_ROOT / "scripts" / "task_scheduler_config.xml"
        assert xml_path.exists(), f"Configuration missing: {xml_path}"

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Namespace
        ns = {"ns": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        assert root.tag == "{http://schemas.microsoft.com/windows/2004/02/mit/task}Task"
        assert root.attrib.get("version") == "1.4"

        # 1. Trigger: LogonTrigger with Delay PT6M
        logon = root.find(".//ns:LogonTrigger", ns)
        assert logon is not None, "<LogonTrigger> element missing"
        enabled = logon.find("ns:Enabled", ns)
        assert enabled is not None and enabled.text.lower() == "true"
        delay = logon.find("ns:Delay", ns)
        assert delay is not None and delay.text == "PT6M", f"Expected Delay PT6M, got {delay.text if delay else None}"

        # 2. Principals: InteractiveToken & LeastPrivilege
        logon_type = root.find(".//ns:LogonType", ns)
        assert logon_type is not None and logon_type.text == "InteractiveToken"
        run_level = root.find(".//ns:RunLevel", ns)
        assert run_level is not None and run_level.text == "LeastPrivilege"

        # 3. Settings: Battery run enabled (DisallowStartIfOnBatteries = false)
        disallow_batt = root.find(".//ns:DisallowStartIfOnBatteries", ns)
        assert disallow_batt is not None and disallow_batt.text.lower() == "false"
        stop_batt = root.find(".//ns:StopIfGoingOnBatteries", ns)
        assert stop_batt is not None and stop_batt.text.lower() == "false"

        # 4. Action Command
        cmd_elem = root.find(".//ns:Command", ns)
        assert cmd_elem is not None and "python" in cmd_elem.text.lower()
        args_elem = root.find(".//ns:Arguments", ns)
        assert args_elem is not None and "--startup-task" in args_elem.text

    def test_time_window_boundary_oracle(self):
        """Exhaustive boundary testing of 06:00 to 11:00 time window."""
        window_start = "06:00"
        window_end = "11:00"

        # Boundary checks
        cases = [
            (datetime.time(5, 59, 59), False, "Just before start"),
            (datetime.time(6, 0, 0), True, "Exact start"),
            (datetime.time(6, 0, 1), True, "Just after start"),
            (datetime.time(8, 30, 0), True, "Mid-morning window"),
            (datetime.time(10, 59, 59), True, "Just before end"),
            (datetime.time(11, 0, 0), True, "Exact end"),
            (datetime.time(11, 0, 1), False, "Just after end"),
            (datetime.time(14, 0, 0), False, "Afternoon"),
            (datetime.time(23, 59, 59), False, "Night"),
            (datetime.time(0, 0, 0), False, "Midnight"),
        ]

        for test_time, expected_result, desc in cases:
            in_win, msg = is_within_scheduled_window(window_start, window_end, current_time=test_time)
            assert in_win == expected_result, f"Failed for {desc}: time={test_time}, expected {expected_result}, got {in_win} ({msg})"

    def test_startup_task_cli_clean_exit_0_outside_window(self, tmp_path):
        """When executed outside 06:00-11:00 window, --startup-task exits cleanly with code 0 without running sync."""
        state_file = tmp_path / "state.json"
        log_file = tmp_path / "sync.log"

        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        # Force a window that cannot match current execution time (e.g. 02:00 to 02:01)
        cmd = [
            sys.executable,
            str(script_path),
            "--startup-task",
            "--window-start", "02:00",
            "--window-end", "02:01",
            "--state-file", str(state_file),
            "--log-file", str(log_file),
            "--source-dir", str(tmp_path / "nonexistent_source"),
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0, f"Must exit with code 0 outside window, got {proc.returncode}"
        assert "Outside scheduled window" in proc.stdout
        assert "Clean exit code 0 returned" in proc.stdout
        assert not state_file.exists() or json.load(open(state_file)).get("last_status") != "SUCCESS"

    def test_daily_execution_guard_duplicate_skip(self, tmp_path):
        """Second run on same calendar day must be skipped with exit code 0 to save resources."""
        state_file = tmp_path / "state.json"
        log_file = tmp_path / "sync.log"
        src_dir = tmp_path / "source"
        tgt_dir = tmp_path / "target"
        dl_dir = tmp_path / "downloads"
        src_dir.mkdir()
        tgt_dir.mkdir()
        dl_dir.mkdir()

        (src_dir / "sample.txt").write_text("sample", encoding="utf-8")

        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        base_cmd = [
            sys.executable,
            str(script_path),
            "--startup-task",
            "--window-start", "00:00",
            "--window-end", "23:59",
            "--source-dir", str(src_dir),
            "--target-dirs", str(tgt_dir),
            "--downloads-dirs", str(dl_dir),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
        ]

        # First run: Should execute and succeed
        p1 = subprocess.run(base_cmd, capture_output=True, text=True)
        assert p1.returncode == 0
        assert (tgt_dir / "sample.txt").exists()

        with open(state_file, "r") as f:
            st1 = json.load(f)
        assert st1.get("last_status") == "SUCCESS"
        first_run_ts = st1.get("last_run_timestamp")

        # Second run: Should detect existing run today and skip with code 0
        p2 = subprocess.run(base_cmd, capture_output=True, text=True)
        assert p2.returncode == 0
        assert "Daily sync already completed successfully today" in p2.stdout
        assert "Skipping duplicate startup run" in p2.stdout

        # State file must not have been overwritten with a new execution
        with open(state_file, "r") as f:
            st2 = json.load(f)
        assert st2.get("last_run_timestamp") == first_run_ts

    def test_daily_guard_retries_on_previous_failure(self, tmp_path):
        """If an earlier run on the same day recorded FAILED, the next startup run must NOT skip; it must retry."""
        state_file = tmp_path / "state.json"
        log_file = tmp_path / "sync.log"
        src_dir = tmp_path / "source"
        tgt_dir = tmp_path / "target"
        dl_dir = tmp_path / "downloads"
        src_dir.mkdir()
        tgt_dir.mkdir()
        dl_dir.mkdir()

        today_iso = datetime.date.today().isoformat()
        state_data = {
            "last_run_timestamp": f"{today_iso}T06:15:00",
            "last_run_date": today_iso,
            "last_status": "FAILED",
            "last_trigger_mode": "startup_task",
            "history": [],
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f)

        (src_dir / "repaired.txt").write_text("data", encoding="utf-8")

        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--startup-task",
            "--window-start", "00:00",
            "--window-end", "23:59",
            "--source-dir", str(src_dir),
            "--target-dirs", str(tgt_dir),
            "--downloads-dirs", str(dl_dir),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0
        assert "Skipping duplicate startup run" not in proc.stdout
        assert "ChakraModel Backup Sync finished with status: SUCCESS" in proc.stdout

        with open(state_file, "r") as f:
            st = json.load(f)
        assert st.get("last_status") == "SUCCESS"

    def test_startup_task_force_flag_overrides_window_and_guard(self, tmp_path):
        """--force flag overrides both the time window restriction and the daily duplicate guard."""
        state_file = tmp_path / "state.json"
        log_file = tmp_path / "sync.log"
        src_dir = tmp_path / "source"
        tgt_dir = tmp_path / "target"
        dl_dir = tmp_path / "downloads"
        src_dir.mkdir()
        tgt_dir.mkdir()
        dl_dir.mkdir()

        today_iso = datetime.date.today().isoformat()
        state_data = {
            "last_run_timestamp": f"{today_iso}T06:30:00",
            "last_run_date": today_iso,
            "last_status": "SUCCESS",
            "last_trigger_mode": "startup_task",
            "history": [],
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f)

        (src_dir / "forced_sync.txt").write_text("force", encoding="utf-8")

        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--startup-task",
            "--force",
            "--window-start", "01:00",
            "--window-end", "01:01",
            "--source-dir", str(src_dir),
            "--target-dirs", str(tgt_dir),
            "--downloads-dirs", str(dl_dir),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0
        assert (tgt_dir / "forced_sync.txt").exists(), "Forced sync should have copied file"
        assert "Outside scheduled window" not in proc.stdout
        assert "Skipping duplicate startup run" not in proc.stdout
