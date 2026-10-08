"""
Comprehensive Acceptance Test Suite for ChakraModel Backup Sync, Recovery, and Scheduling
Tests all 5 Acceptance Criteria:
- Test A: Corruption Auto-Fix (SHA-256 detection and atomic restoration)
- Test B: Deletion Auto-Fix (Missing file detection and restoration)
- Test C: Downloads Mock Weights Recovery (Privacy filtering, mock weights recovery, stub protection)
- Test D: Standalone Execution (CLI execution with exit code 0)
- Test E: Task Scheduler Verification (XML schema validation, time window enforcement, daily guard)
"""

import datetime
import io
import json
import os
import pickle
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

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
    is_within_scheduled_window,
    main,
    scan_and_recover_downloads,
    stream_sha256,
    validate_archive_integrity,
    verify_and_sync_all_targets,
    verify_and_sync_target,
)


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def create_mock_weight_zip(dest_path: Path) -> None:
    """Create a minimal valid PyTorch state_dict zip archive."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    mock_state = {
        "decode_head.bias": ("tensor_mock", [1, 2, 3]),
        "backbone.weight": ("tensor_mock", [4, 5, 6]),
    }
    pkl_bytes = pickle.dumps(mock_state, protocol=2)

    with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("archive/data.pkl", pkl_bytes)
        z.writestr("archive/byteorder", b"little")
        z.writestr("archive/.format_version", b"3")
        z.writestr("archive/data/0", b"\x00" * 64)
        z.writestr("archive/data/1", b"\x00" * 64)


# ---------------------------------------------------------------------------
# Test A: Corruption Auto-Fix
# ---------------------------------------------------------------------------

class TestCorruptionAutoFix:
    """
    Test A: Programmatic test demonstrating that modifying a file in a backup
    directory causes the script to detect corruption via SHA-256 hash mismatch
    and restore it from source.
    """

    def test_corruption_detected_and_restored(self, tmp_path):
        source_dir = tmp_path / "source"
        backup_dir = tmp_path / "backup"
        source_dir.mkdir()
        backup_dir.mkdir()

        # Create authentic source files
        src_code = source_dir / "src" / "model.py"
        src_code.parent.mkdir(parents=True)
        original_content = "def forward(x):\n    return x * 2\n"
        src_code.write_text(original_content, encoding="utf-8")

        src_config = source_dir / "configs" / "train.yaml"
        src_config.parent.mkdir(parents=True)
        src_config.write_text("epochs: 50\nlr: 0.001\n", encoding="utf-8")

        # Initial sync to populate backup
        verify_and_sync_target(
            source_root=source_dir,
            target_path=backup_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
        )

        tgt_code = backup_dir / "src" / "model.py"
        assert tgt_code.exists()
        assert stream_sha256(tgt_code) == stream_sha256(src_code)

        # Corrupt the target file: same size or different content to trigger SHA-256 mismatch
        corrupted_content = "def forward(x):\n    return x * 9\n"  # Exactly same length!
        assert len(corrupted_content) == len(original_content)
        tgt_code.write_text(corrupted_content, encoding="utf-8")

        # Confirm target is corrupted before sync
        src_hash_before = stream_sha256(src_code)
        tgt_hash_before = stream_sha256(tgt_code)
        assert src_hash_before != tgt_hash_before, "Target should have differing hash before auto-fix"

        # Run verification and auto-fix
        stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=backup_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
        )

        # Assert corruption was detected and repaired
        assert stats["files_corrupted_fixed"] >= 1
        assert tgt_code.read_text(encoding="utf-8") == original_content
        assert stream_sha256(tgt_code) == src_hash_before


# ---------------------------------------------------------------------------
# Test B: Deletion Auto-Fix
# ---------------------------------------------------------------------------

class TestDeletionAutoFix:
    """
    Test B: Programmatic test demonstrating that deleting a file in a backup
    directory causes the script to detect missing file and restore it from source.
    """

    def test_missing_file_detected_and_restored(self, tmp_path):
        source_dir = tmp_path / "source"
        backup_dir = tmp_path / "backup"
        source_dir.mkdir()
        backup_dir.mkdir()

        # Create source files
        file1 = source_dir / "weights" / "checkpoint.pth"
        file1.parent.mkdir(parents=True)
        file1.write_bytes(b"\x01\x02\x03\x04" * 100)

        file2 = source_dir / "docs" / "README.md"
        file2.parent.mkdir(parents=True)
        file2.write_text("# ChakraModel Documentation\n", encoding="utf-8")

        # Initial sync
        verify_and_sync_target(
            source_root=source_dir,
            target_path=backup_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
        )

        tgt_file1 = backup_dir / "weights" / "checkpoint.pth"
        tgt_file2 = backup_dir / "docs" / "README.md"
        assert tgt_file1.exists()
        assert tgt_file2.exists()

        # Delete file1 on target
        tgt_file1.unlink()
        assert not tgt_file1.exists()

        # Run auto-fix
        stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=backup_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
        )

        # Verify file1 was restored from source
        assert stats["files_missing_fixed"] >= 1
        assert tgt_file1.exists()
        assert tgt_file1.read_bytes() == file1.read_bytes()
        assert stream_sha256(tgt_file1) == stream_sha256(file1)


# ---------------------------------------------------------------------------
# Test C: Downloads Mock Weights Recovery & Privacy Filter
# ---------------------------------------------------------------------------

class TestDownloadsRecovery:
    """
    Test C: Programmatic test demonstrating that a mock weights zip placed in
    a mock Downloads directory is correctly identified and recovered into
    weights/ in the model root, while personal files are blocked and 49-byte stubs
    do not overwrite valid files.
    """

    def test_mock_weights_recovery_and_privacy_filter(self, tmp_path):
        mock_downloads = tmp_path / "Downloads"
        mock_downloads.mkdir()
        model_root = tmp_path / "chakramodel"
        model_root.mkdir()
        ledger_file = tmp_path / "logs" / "ledger.json"

        # 1. Create valid mock weights zip in downloads
        mock_zip = mock_downloads / "mock_weights.zip"
        create_mock_weight_zip(mock_zip)
        assert validate_archive_integrity(mock_zip)[0] is True

        # 2. Create personal files in downloads (must be quarantined/denied)
        personal_resume = mock_downloads / "Gokul_Resume_2026.pdf"
        personal_resume.write_text("Personal Resume Details", encoding="utf-8")

        personal_passport = mock_downloads / "Passport_Scan_Copy.pdf"
        personal_passport.write_text("Passport Copy", encoding="utf-8")

        personal_leads = mock_downloads / "corporate_leads.csv"
        personal_leads.write_text("name,email,company\nJohn,john@corp.com,ACME\n", encoding="utf-8")

        # 3. Create a 49-byte stub zip in downloads and a healthy file in model_root
        stub_zip = mock_downloads / "model_output.zip"
        stub_zip.write_bytes(b"PK\x05\x06" + b"\x00" * 45)  # 49 bytes stub
        assert stub_zip.stat().st_size == 49

        existing_valid = model_root / "results" / "archives" / "model_output.zip"
        existing_valid.parent.mkdir(parents=True, exist_ok=True)
        existing_valid_content = b"GENUINE_ARCHIVE_DATA_PAYLOAD_VALID" * 10
        existing_valid.write_bytes(existing_valid_content)

        # 4. Run recovery scan
        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_downloads],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        # Verification 1: Mock weights zip recovered into weights/
        recovered_weights = model_root / "weights" / "mock_weights.zip"
        assert recovered_weights.exists(), "mock_weights.zip was not recovered into weights/"
        assert validate_archive_integrity(recovered_weights)[0] is True
        assert stream_sha256(recovered_weights) == stream_sha256(mock_zip)

        # Verification 2: Privacy deny-filter permanently blocked personal files
        assert not (model_root / "docs" / "pdfs" / "Gokul_Resume_2026.pdf").exists()
        assert not (model_root / "docs" / "pdfs" / "Passport_Scan_Copy.pdf").exists()
        assert not (model_root / "results" / "recovered" / "corporate_leads.csv").exists()
        assert stats["privacy_denied"] >= 3

        # Verification 3: 49-byte stub was blocked from overwriting valid destination
        assert existing_valid.read_bytes() == existing_valid_content, "Healthy archive was overwritten by stub!"
        assert stats["blocked_stubs"] >= 1


# ---------------------------------------------------------------------------
# Test D: Standalone Execution
# ---------------------------------------------------------------------------

class TestStandaloneExecution:
    """
    Test D: Test verifying scripts/backup_sync.py can be executed standalone
    without errors (exit code 0).
    """

    def test_standalone_cli_execution(self, tmp_path):
        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        assert script_path.exists(), f"Script missing at {script_path}"

        test_source = tmp_path / "source"
        test_target = tmp_path / "target"
        test_source.mkdir()
        test_target.mkdir()

        # Add a dummy file
        (test_source / "hello.txt").write_text("Hello ChakraModel", encoding="utf-8")

        state_file = tmp_path / "state.json"
        log_file = tmp_path / "sync.log"

        # Execute backup_sync.py as standalone process
        cmd = [
            sys.executable,
            str(script_path),
            "--source-dir", str(test_source),
            "--target-dirs", str(test_target),
            "--downloads-dirs", str(tmp_path / "empty_downloads"),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
            "--all",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"Process failed with stderr: {result.stderr}\nstdout: {result.stdout}"

        # Verify target received the file
        assert (test_target / "hello.txt").exists()
        assert (test_target / "hello.txt").read_text(encoding="utf-8") == "Hello ChakraModel"

        # Verify state file was updated
        assert state_file.exists()
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        assert state.get("last_status") == "SUCCESS"


# ---------------------------------------------------------------------------
# Test E: Task Scheduler Verification & Startup Mode
# ---------------------------------------------------------------------------

class TestTaskSchedulerVerification:
    """
    Test E: Test verifying the XML task definition contains <LogonTrigger>,
    <Delay>PT6M</Delay>, and testing --startup-task time window enforcement.
    """

    def test_xml_task_definition(self):
        xml_path = PROJECT_ROOT / "scripts" / "task_scheduler_config.xml"
        assert xml_path.exists(), f"XML file missing at {xml_path}"

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Namespace handling
        ns = {"ns": "http://schemas.microsoft.com/windows/2004/02/mit/task"}

        logon_trigger = root.find(".//ns:LogonTrigger", ns)
        assert logon_trigger is not None, "XML must define <LogonTrigger>"

        delay_elem = logon_trigger.find("ns:Delay", ns)
        assert delay_elem is not None, "LogonTrigger must contain <Delay>"
        assert delay_elem.text == "PT6M", f"Delay must be 'PT6M', got '{delay_elem.text}'"

        # Check battery settings
        disallow_batt = root.find(".//ns:DisallowStartIfOnBatteries", ns)
        assert disallow_batt is not None and disallow_batt.text.lower() == "false"

        stop_batt = root.find(".//ns:StopIfGoingOnBatteries", ns)
        assert stop_batt is not None and stop_batt.text.lower() == "false"

        # Check action command
        arguments = root.find(".//ns:Arguments", ns)
        assert arguments is not None
        assert "--startup-task" in arguments.text

    def test_time_window_enforcement_logic(self):
        # 1. Test simulated time outside window
        time_early = datetime.time(4, 30, 0)
        in_win, _ = is_within_scheduled_window("06:00", "11:00", current_time=time_early)
        assert in_win is False

        time_late = datetime.time(14, 0, 0)
        in_win, _ = is_within_scheduled_window("06:00", "11:00", current_time=time_late)
        assert in_win is False

        # 2. Test simulated time inside window
        time_inside = datetime.time(8, 0, 0)
        in_win, _ = is_within_scheduled_window("06:00", "11:00", current_time=time_inside)
        assert in_win is True

    def test_startup_task_clean_exit_outside_window(self, tmp_path):
        """When outside the time window, --startup-task exits 0 without running sync."""
        state_file = tmp_path / "state.json"
        log_file = tmp_path / "sync.log"

        # Set window that cannot match current time (e.g. 01:00 to 01:01 AM)
        exit_code = main([
            "--startup-task",
            "--window-start", "01:00",
            "--window-end", "01:01",
            "--state-file", str(state_file),
            "--log-file", str(log_file),
            "--source-dir", str(tmp_path / "src"),
        ])
        assert exit_code == 0
        # Should not have recorded SUCCESS since it skipped
        assert not state_file.exists() or json.load(open(state_file)).get("last_status") != "SUCCESS"

    def test_daily_execution_guard(self, tmp_path):
        """Second run on same day should skip and return clean 0."""
        state_file = tmp_path / "state.json"
        log_file = tmp_path / "sync.log"
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        # Run 1: Inside window (00:00 to 23:59 covers any current time)
        exit_code_1 = main([
            "--startup-task",
            "--window-start", "00:00",
            "--window-end", "23:59",
            "--source-dir", str(source_dir),
            "--target-dirs", str(target_dir),
            "--downloads-dirs", str(tmp_path / "empty_dl"),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
        ])
        assert exit_code_1 == 0
        assert state_file.exists()
        with open(state_file, "r") as f:
            state = json.load(f)
        assert state.get("last_status") == "SUCCESS"

        # Run 2: Immediately run again on same day without --force
        exit_code_2 = main([
            "--startup-task",
            "--window-start", "00:00",
            "--window-end", "23:59",
            "--source-dir", str(source_dir),
            "--target-dirs", str(target_dir),
            "--downloads-dirs", str(tmp_path / "empty_dl"),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
        ])
        assert exit_code_2 == 0  # Clean skip!

        # Run 3: Run with --force -> should re-execute
        exit_code_3 = main([
            "--startup-task",
            "--force",
            "--source-dir", str(source_dir),
            "--target-dirs", str(target_dir),
            "--downloads-dirs", str(tmp_path / "empty_dl"),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
        ])
        assert exit_code_3 == 0


# ---------------------------------------------------------------------------
# Additional Role Safety Gate Tests
# ---------------------------------------------------------------------------

class TestTargetRoleGates:
    """Verify safety gates for audit deliverables and sibling projects."""

    def test_audit_workspace_protected(self, tmp_path):
        source_dir = tmp_path / "chakramodel"
        audit_dir = tmp_path / "chakramodel_audit"
        source_dir.mkdir()
        audit_dir.mkdir()

        (source_dir / "big_dataset.bin").write_bytes(b"\x00" * 1024)
        audit_report = audit_dir / "FULL_AUDIT_REPORT.md"
        audit_report.write_text("# Audit Report Content", encoding="utf-8")

        stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=audit_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
        )

        assert stats["role"] == "AUDIT_WORKSPACE"
        # Audit report is intact and dataset was not copied into audit workspace
        assert audit_report.read_text(encoding="utf-8") == "# Audit Report Content"
        assert not (audit_dir / "big_dataset.bin").exists()

    def test_sibling_project_protected(self, tmp_path):
        source_dir = tmp_path / "chakramodel"
        sibling_dir = tmp_path / "chakramodelpro"
        source_dir.mkdir()
        sibling_dir.mkdir()

        (source_dir / "repo_file.py").write_text("code", encoding="utf-8")
        pro_file = sibling_dir / "chakra-sync.ps1"
        pro_file.write_text("# Pro sync script", encoding="utf-8")

        stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=sibling_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
        )

        assert stats["role"] == "SIBLING_PROJECT"
        assert pro_file.exists()
        assert not (sibling_dir / "repo_file.py").exists()

    def test_cloud_container_target_resolution(self, tmp_path):
        container_dir = tmp_path / "chakramodel & pro (16-9-26_)"
        role, resolved_path = classify_target(container_dir)
        assert role == "CLOUD_CONTAINER"
        assert resolved_path == container_dir / "chakramodel"


# ---------------------------------------------------------------------------
# Additional Edge Case & Resilience Tests
# ---------------------------------------------------------------------------

class TestEdgeCasesAndResilience:
    """Tests for size pre-check, atomic replacement, archive corruption, and exclusions."""

    def test_fast_path_size_mismatch_precheck(self, tmp_path):
        """Size mismatch should trigger auto-fix without relying only on hash match."""
        src_dir = tmp_path / "src"
        tgt_dir = tmp_path / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        f_src = src_dir / "file.bin"
        f_src.write_bytes(b"A" * 1000)

        f_tgt = tgt_dir / "file.bin"
        f_tgt.write_bytes(b"A" * 500)  # Size mismatch (500 != 1000)

        stats = verify_and_sync_target(
            source_root=src_dir,
            target_path=tgt_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
        )
        assert stats["files_corrupted_fixed"] == 1
        assert f_tgt.stat().st_size == 1000
        assert f_tgt.read_bytes() == f_src.read_bytes()

    def test_default_exclusions_respected(self, tmp_path):
        """Default exclusions (.venv, __pycache__, .git, .agents) should be ignored."""
        src_dir = tmp_path / "src"
        tgt_dir = tmp_path / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        # Included file
        (src_dir / "main.py").write_text("print('hello')", encoding="utf-8")

        # Excluded directories
        venv_dir = src_dir / ".venv" / "Lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "site.py").write_text("# venv code", encoding="utf-8")

        git_dir = src_dir / ".git" / "objects"
        git_dir.mkdir(parents=True)
        (git_dir / "pack.pack").write_bytes(b"\x00" * 100)

        agents_dir = src_dir / ".agents" / "worker"
        agents_dir.mkdir(parents=True)
        (agents_dir / "notes.md").write_text("agent notes", encoding="utf-8")

        pycache_dir = src_dir / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "main.cpython-311.pyc").write_bytes(b"\x00" * 50)

        from backup_sync import DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_EXTS

        stats = verify_and_sync_target(
            source_root=src_dir,
            target_path=tgt_dir,
            exclude_dirs=set(DEFAULT_EXCLUDE_DIRS),
            exclude_exts=set(DEFAULT_EXCLUDE_EXTS),
        )

        assert (tgt_dir / "main.py").exists()
        assert not (tgt_dir / ".venv").exists()
        assert not (tgt_dir / ".git").exists()
        assert not (tgt_dir / ".agents").exists()
        assert not (tgt_dir / "__pycache__").exists()
        assert stats["files_missing_fixed"] == 1

    def test_corrupted_archive_rejection_in_downloads(self, tmp_path):
        """Corrupted zip archives in downloads should be skipped and logged."""
        downloads_dir = tmp_path / "downloads"
        model_root = tmp_path / "model"
        downloads_dir.mkdir()
        model_root.mkdir()

        # Create a damaged zip file (not valid zip)
        bad_zip = downloads_dir / "chakra_damaged_weights.zip"
        bad_zip.write_bytes(b"PK\x03\x04" + b"CORRUPTED_GARBAGE_PAYLOAD")

        stats = scan_and_recover_downloads(
            downloads_dirs=[downloads_dir],
            model_root=model_root,
            ledger_file=tmp_path / "ledger.json",
        )

        assert stats["skipped_corrupt"] >= 1
        assert not (model_root / "weights" / "chakra_damaged_weights.zip").exists()


# ---------------------------------------------------------------------------
# Test F: Regression Tests for Remediation Hardening (Reviewer 2 / Challengers)
# ---------------------------------------------------------------------------

class TestRemediationRegression:
    """
    Regression test suite verifying remediations from Reviewer 2, Challenger 1, and Challenger 2:
    - Read-only target overwrite and auto-fix with chmod S_IWRITE and retry loop.
    - Expanded privacy filter blocking sensitive keywords even inside subdirectories.
    - Unconditional stub archive rejection (< 100 bytes) without existing destination.
    - State recording and exit code 1 on active target sync error.
    """

    def test_read_only_target_overwrite_succeeds(self, tmp_path):
        """Target marked stat.S_IREAD is successfully updated and restored."""
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        src_file = source_dir / "protected_model.bin"
        src_data = b"AUTHENTIC_CHECKPOINT_DATA_PROTECTED_V1" * 10
        src_file.write_bytes(src_data)

        # Initial sync to create target file
        stats_init = verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
            dry_run=False,
        )
        assert stats_init["files_missing_fixed"] == 1

        tgt_file = target_dir / "protected_model.bin"
        assert tgt_file.exists()

        # Corrupt target file and mark as read-only
        corrupted_data = b"CORRUPTED_CHECKPOINT_DATA_PROTECTED_XX" * 10
        tgt_file.write_bytes(corrupted_data)
        os.chmod(tgt_file, stat.S_IREAD)

        try:
            # Execute auto-fix: should clear read-only and overwrite atomically
            stats_fix = verify_and_sync_target(
                source_root=source_dir,
                target_path=target_dir,
                exclude_dirs=set(),
                exclude_exts=set(),
                dry_run=False,
            )

            assert len(stats_fix["errors"]) == 0, f"Expected 0 errors, got: {stats_fix['errors']}"
            assert stats_fix["files_corrupted_fixed"] == 1
            assert tgt_file.read_bytes() == src_data
            assert stream_sha256(tgt_file) == stream_sha256(src_file)

            # Confirm temporary files were cleaned up
            tmp_files = list(target_dir.glob("*.tmp_autofix*"))
            assert len(tmp_files) == 0, f"Temporary files leaked: {tmp_files}"
        finally:
            try:
                os.chmod(tgt_file, stat.S_IWRITE)
            except OSError:
                pass

    def test_privacy_filter_blocks_expanded_keywords(self, tmp_path):
        """Tax_Return.pdf, kvasir_mess_fees.pdf, Salary_Slip.pdf, Bank_Statement.pdf are blocked even inside weights/."""
        mock_downloads = tmp_path / "Downloads"
        weights_subfolder = mock_downloads / "weights"
        weights_subfolder.mkdir(parents=True)
        model_root = tmp_path / "chakramodel"
        model_root.mkdir()
        ledger_file = tmp_path / "logs" / "ledger.json"

        sensitive_files = [
            "Tax_Return.pdf",
            "kvasir_mess_fees.pdf",
            "Salary_Slip.pdf",
            "Bank_Statement.pdf",
        ]

        for fname in sensitive_files:
            p = weights_subfolder / fname
            p.write_text(f"SENSITIVE CONFIDENTIAL CONTENT: {fname}", encoding="utf-8")

        # Also place a genuine mock weights file to confirm valid assets are still recovered
        mock_zip = mock_downloads / "mock_weights.zip"
        create_mock_weight_zip(mock_zip)

        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_downloads],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        assert stats["privacy_denied"] >= 4
        assert stats["recovered"] >= 1

        # Verify none of the sensitive files leaked into model_root
        for fname in sensitive_files:
            assert not (model_root / "docs" / "pdfs" / fname).exists(), f"Privacy leak detected: {fname} copied to docs/pdfs!"
            assert not (model_root / "results" / "recovered" / fname).exists()
            assert not (model_root / "recovered" / fname).exists()

    def test_stub_archive_rejected_without_existing_dest(self, tmp_path):
        """49-byte stub archive is rejected even when destination file does not exist yet."""
        mock_downloads = tmp_path / "Downloads"
        mock_downloads.mkdir()
        model_root = tmp_path / "chakramodel"
        model_root.mkdir()
        ledger_file = tmp_path / "logs" / "ledger.json"

        dest_expected = model_root / "results" / "archives" / "chakra_empty_stub.zip"
        assert not dest_expected.exists(), "Precondition: destination file must not exist yet"

        stub_file = mock_downloads / "chakra_empty_stub.zip"
        stub_file.write_bytes(b"PK\x05\x06" + b"\x00" * 45)  # 49 bytes stub zip
        assert stub_file.stat().st_size == 49

        stats = scan_and_recover_downloads(
            downloads_dirs=[mock_downloads],
            model_root=model_root,
            ledger_file=ledger_file,
            dry_run=False,
        )

        assert stats["blocked_stubs"] == 1
        assert stats["recovered"] == 0
        assert not dest_expected.exists(), "Stub archive was written to non-existing destination!"

        # Inspect ledger for BLOCKED_STUB action
        with open(ledger_file, "r", encoding="utf-8") as f:
            entries = json.load(f)
        blocked_entries = [e for e in entries if e.get("action") == "BLOCKED_STUB"]
        assert len(blocked_entries) == 1

    def test_sync_error_records_failure_in_state(self, tmp_path, monkeypatch):
        """Active target sync failure marks status FAILED in state file and returns exit code 1."""
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        state_file = tmp_path / "logs" / "backup_sync_state.json"
        source_dir.mkdir()
        target_dir.mkdir()

        (source_dir / "file.txt").write_text("content", encoding="utf-8")

        # Simulate an active target sync error (e.g. permission or I/O failure in verify_and_sync_target)
        import backup_sync

        def mock_verify_and_sync_target(*args, **kwargs):
            return {
                "target_path": str(target_dir),
                "effective_target": str(target_dir),
                "role": "LOCAL_MIRROR",
                "status": "FAILED",
                "files_checked": 1,
                "files_verified_ok": 0,
                "files_missing_fixed": 0,
                "files_corrupted_fixed": 0,
                "errors": ["Simulated active target disk failure: Access Denied"],
            }

        monkeypatch.setattr(backup_sync, "verify_and_sync_target", mock_verify_and_sync_target)

        exit_code = main([
            "--source-dir", str(source_dir),
            "--target-dirs", str(target_dir),
            "--state-file", str(state_file),
            "--verify-and-sync",
            "--force",
        ])

        assert exit_code == 1, "main() must return exit code 1 when active target sync fails"

        # Check state file persisted status FAILED
        assert state_file.exists()
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        assert state["last_status"] == "FAILED", f"State should record FAILED, got {state['last_status']}"
