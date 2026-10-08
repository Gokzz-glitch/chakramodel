"""
Adversarial Empirical Stress-Test Suite for Criteria A & B
Target Directories Verification and Auto-Fix
Author: challenger_m1_1_g15
Target under test: scripts/backup_sync.py

This test harness stress-tests:
1. Single-byte corruption in the middle of files (same size, altered SHA-256).
2. Size-truncated corruption (different size).
3. Multiple corrupted files in subdirectories.
4. Deleted files in target directories.
5. Read-only corrupted target file behavior under Windows filesystem semantics.
6. --dry-run (reporting without modifications) vs. live execution (--verify-and-sync).
7. Genuine SHA-256 cryptographic verification against standard test vectors.
8. Atomic temp file (.tmp_autofix) cleanup and leakage guarantees.
9. Directory and file extension exclusion enforcement.
"""

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, List

import pytest

# Ensure scripts directory is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from backup_sync import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_EXTS,
    atomic_write_replace,
    classify_target,
    main,
    stream_sha256,
    verify_and_sync_all_targets,
    verify_and_sync_target,
)


# ============================================================================
# Test 1: Single-Byte Middle-of-File Corruption (Same Size, Altered SHA-256)
# ============================================================================

class TestSingleByteCorruption:
    """Stress-test single-byte corruption where file size is exactly conserved."""

    def test_single_byte_middle_corruption_auto_fixed(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        # Create a 1.5 MB binary payload so it crosses the 1MB chunk boundary
        size_bytes = 1_500_000
        mid_point = size_bytes // 2
        payload = bytearray(os.urandom(size_bytes))
        
        src_file = source_dir / "large_model.bin"
        src_file.write_bytes(payload)
        src_sha = hashlib.sha256(payload).hexdigest()

        # Initial synchronization
        res_init = verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
        )
        assert res_init["files_missing_fixed"] == 1
        
        tgt_file = target_dir / "large_model.bin"
        assert tgt_file.exists()
        assert stream_sha256(tgt_file) == src_sha

        # Adversarial corruption: mutate exactly 1 byte in the middle
        corrupted_payload = bytearray(payload)
        corrupted_payload[mid_point] ^= 0xFF  # Invert all bits of the middle byte
        tgt_file.write_bytes(corrupted_payload)

        # Assertions before auto-fix
        assert tgt_file.stat().st_size == src_file.stat().st_size, "Sizes must be identical!"
        corrupt_sha = hashlib.sha256(corrupted_payload).hexdigest()
        assert stream_sha256(tgt_file) == corrupt_sha
        assert corrupt_sha != src_sha, "SHA-256 must differ!"

        # Dry run test: must detect corruption but NOT modify target file
        dry_stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
            dry_run=True,
        )
        assert dry_stats["files_corrupted_fixed"] == 1
        assert stream_sha256(tgt_file) == corrupt_sha, "Dry run must NOT modify target file!"

        # Live run test: must repair the file
        live_stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
            dry_run=False,
        )
        assert live_stats["files_corrupted_fixed"] == 1
        assert tgt_file.stat().st_size == size_bytes
        repaired_sha = stream_sha256(tgt_file)
        assert repaired_sha == src_sha, "Live run must restore exact SHA-256!"
        assert tgt_file.read_bytes() == bytes(payload), "Restored content must match byte-for-byte!"


# ============================================================================
# Test 2: Size-Truncated and Size-Expanded Corruption
# ============================================================================

class TestSizeMismatchCorruption:
    """Stress-test fast-path size mismatch detection and auto-fix."""

    def test_truncated_corruption(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        full_content = b"CHAKRAMODEL_WEIGHTS_DATA_BLOCK_" * 1000  # 31,000 bytes
        src_file = source_dir / "weights.bin"
        src_file.write_bytes(full_content)

        # Pre-seed target with truncated version (e.g. 500 bytes)
        tgt_file = target_dir / "weights.bin"
        tgt_file.write_bytes(full_content[:500])

        stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
            dry_run=False,
        )
        assert stats["files_corrupted_fixed"] == 1
        assert tgt_file.stat().st_size == len(full_content)
        assert tgt_file.read_bytes() == full_content

    def test_zero_byte_target_corruption(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        src_file = source_dir / "zero_target.dat"
        src_file.write_bytes(b"Non-empty source data")

        tgt_file = target_dir / "zero_target.dat"
        tgt_file.write_bytes(b"")  # 0 bytes

        stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
            dry_run=False,
        )
        assert stats["files_corrupted_fixed"] == 1
        assert tgt_file.read_bytes() == b"Non-empty source data"

    def test_zero_byte_source_with_corrupt_target(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        src_file = source_dir / "empty.dat"
        src_file.write_bytes(b"")  # Genuine 0-byte file

        tgt_file = target_dir / "empty.dat"
        tgt_file.write_bytes(b"Stray bytes")

        stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
            dry_run=False,
        )
        assert stats["files_corrupted_fixed"] == 1
        assert tgt_file.stat().st_size == 0


# ============================================================================
# Test 3: Multiple Corrupted and Missing Files in Deep Nested Subdirectories
# ============================================================================

class TestSubdirectoryComplexTree:
    """Stress-test deep hierarchies with mixed missing and corrupted files."""

    def test_multi_level_mixed_failures(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        # Build deep directory hierarchy
        files = {
            "level1/file1.txt": b"Level 1 content",
            "level1/level2/file2.bin": b"\xAA\xBB\xCC\xDD" * 200,
            "level1/level2/level3/file3.json": b'{"status": "valid", "val": 42}',
            "level1/level2/level3/level4/file4.dat": b"Deep nested leaf node",
            "root_file.md": b"# Root Markdown",
        }

        for rel_path, data in files.items():
            p = source_dir / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

        # Initial populate
        verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
        )

        # Inject adversarial damages:
        # 1. Delete level1/file1.txt (missing)
        (target_dir / "level1" / "file1.txt").unlink()

        # 2. Corrupt level1/level2/file2.bin (same size byte flip)
        bin_path = target_dir / "level1" / "level2" / "file2.bin"
        bad_bin = bytearray(files["level1/level2/file2.bin"])
        bad_bin[100] ^= 0x55
        bin_path.write_bytes(bad_bin)

        # 3. Truncate level1/level2/level3/file3.json (size corruption)
        (target_dir / "level1" / "level2" / "level3" / "file3.json").write_bytes(b'{"status":')

        # 4. Delete level1/level2/level3/level4/file4.dat (missing)
        (target_dir / "level1" / "level2" / "level3" / "level4" / "file4.dat").unlink()

        # 5. Leave root_file.md intact (verified OK)

        # Execute live sync
        stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
            dry_run=False,
        )

        assert stats["files_checked"] == 5
        assert stats["files_verified_ok"] == 1  # root_file.md
        assert stats["files_missing_fixed"] == 2  # file1 and file4
        assert stats["files_corrupted_fixed"] == 2  # file2 and file3
        assert len(stats["errors"]) == 0

        # Verify all files match source byte-for-byte
        for rel_path, expected_data in files.items():
            tgt = target_dir / rel_path
            assert tgt.exists(), f"Target file missing: {rel_path}"
            assert tgt.read_bytes() == expected_data, f"Data mismatch in {rel_path}"
            assert stream_sha256(tgt) == stream_sha256(source_dir / rel_path)


# ============================================================================
# Test 4: Deleted Files in Target Directory
# ============================================================================

class TestDeletedFilesAutoFix:
    """Stress-test detection and restoration of deleted files at multiple levels."""

    def test_deleted_files_restored_byte_for_byte(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        files = {
            "root_delete.txt": b"Root deleted file payload",
            "nested/dir1/delete_nested.bin": b"\xDE\xAD\xBE\xEF" * 1024,
            "nested/dir2/intact.txt": b"Should remain untouched",
        }

        for rel, data in files.items():
            p = source_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

        # Initial sync
        verify_and_sync_target(source_dir, target_dir, set(), set(), dry_run=False)

        # Delete two files in target
        (target_dir / "root_delete.txt").unlink()
        (target_dir / "nested" / "dir1" / "delete_nested.bin").unlink()

        assert not (target_dir / "root_delete.txt").exists()
        assert not (target_dir / "nested" / "dir1" / "delete_nested.bin").exists()

        # Dry run: detects missing without restoring
        dry_stats = verify_and_sync_target(source_dir, target_dir, set(), set(), dry_run=True)
        assert dry_stats["files_missing_fixed"] == 2
        assert not (target_dir / "root_delete.txt").exists()
        assert not (target_dir / "nested" / "dir1" / "delete_nested.bin").exists()

        # Live run: restores both missing files
        live_stats = verify_and_sync_target(source_dir, target_dir, set(), set(), dry_run=False)
        assert live_stats["files_missing_fixed"] == 2
        assert (target_dir / "root_delete.txt").exists()
        assert (target_dir / "nested" / "dir1" / "delete_nested.bin").exists()
        assert (target_dir / "root_delete.txt").read_bytes() == files["root_delete.txt"]
        assert (target_dir / "nested" / "dir1" / "delete_nested.bin").read_bytes() == files["nested/dir1/delete_nested.bin"]
        assert stream_sha256(target_dir / "root_delete.txt") == stream_sha256(source_dir / "root_delete.txt")


# ============================================================================
# Test 5: Read-Only Corrupted Target File (Adversarial Edge Case)
# ============================================================================

class TestReadOnlyTargetFile:
    """
    Stress-test behavior when a corrupted file on the target directory
    has the READ-ONLY attribute (e.g. stat.S_IREAD / Windows attrib +R).
    Investigates whether os.replace() raises PermissionError and how backup_sync behaves.
    """

    def test_read_only_corrupted_target_file_fails_without_chmod(self, tmp_path):
        """
        Empirical finding: On Windows, os.replace() fails with [WinError 5] Access is denied
        when the target file is read-only. This test confirms the failure mode.
        """
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        src_file = source_dir / "readonly_test.txt"
        src_content = "AUTHENTIC_SOURCE_CONTENT_V1"
        src_file.write_text(src_content, encoding="utf-8")

        tgt_file = target_dir / "readonly_test.txt"
        tgt_content = "CORRUPTED_TARGET_CONTENT_V1"  # Same length
        tgt_file.write_text(tgt_content, encoding="utf-8")

        # Set read-only attribute on target file
        os.chmod(tgt_file, stat.S_IREAD)

        try:
            # Run verification and sync
            stats = verify_and_sync_target(
                source_root=source_dir,
                target_path=target_dir,
                exclude_dirs=set(),
                exclude_exts=set(),
                dry_run=False,
            )

            # With remediation in atomic_write_replace (chmod S_IWRITE + retry loop),
            # read-only target file is successfully auto-fixed without error
            assert len(stats["errors"]) == 0, f"Expected 0 errors, got: {stats['errors']}"
            assert stats["files_corrupted_fixed"] == 1
            # Target file is restored with authentic source content
            assert tgt_file.read_text(encoding="utf-8") == src_content
            assert stream_sha256(tgt_file) == stream_sha256(src_file)

            # Check that temp file was cleaned up
            tmp_files = list(target_dir.glob("*.tmp_autofix*"))
            assert len(tmp_files) == 0, f"Temporary files were leaked during read-only auto-fix: {tmp_files}"

        finally:
            # Clean up read-only flag so tmp_path can be removed cleanly
            try:
                os.chmod(tgt_file, stat.S_IWRITE)
            except OSError:
                pass


# ============================================================================
# Test 5: Genuine SHA-256 Implementation Verification
# ============================================================================

class TestGenuineSHA256:
    """Verify stream_sha256 computes true NIST FIPS 180-4 SHA-256 digests."""

    def test_sha256_known_vectors(self, tmp_path):
        # NIST Test Vector 1: Empty string -> e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
        empty_file = tmp_path / "empty.txt"
        empty_file.write_bytes(b"")
        assert stream_sha256(empty_file) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        # NIST Test Vector 2: "abc" -> ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
        abc_file = tmp_path / "abc.txt"
        abc_file.write_bytes(b"abc")
        assert stream_sha256(abc_file) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    def test_sha256_streaming_chunk_boundaries(self, tmp_path):
        """Test multi-chunk streaming at boundary sizes: exactly 1MB, 1MB-1, 1MB+1, 2.5MB."""
        chunk_size = 1024 * 1024  # 1MB
        test_sizes = [
            chunk_size - 1,
            chunk_size,
            chunk_size + 1,
            int(chunk_size * 2.5),
        ]

        for sz in test_sizes:
            data = os.urandom(sz)
            f = tmp_path / f"test_{sz}.bin"
            f.write_bytes(data)

            expected_sha = hashlib.sha256(data).hexdigest()
            actual_sha = stream_sha256(f, chunk_size=chunk_size)
            assert actual_sha == expected_sha, f"SHA-256 streaming failed at size {sz}"


# ============================================================================
# Test 6: Temp File (.tmp_autofix) Atomicity and Cleanup Guarantee
# ============================================================================

class TestTempFileCleanup:
    """Verify .tmp_autofix temporary files are never leaked."""

    def test_no_tmp_residue_after_successful_replace(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        (source_dir / "clean_test.txt").write_text("Clean atomicity", encoding="utf-8")

        verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(),
            exclude_exts=set(),
            dry_run=False,
        )

        # Inspect target directory for any .tmp_autofix residue
        all_target_files = [f.name for f in target_dir.rglob("*")]
        tmp_files = [f for f in all_target_files if ".tmp_autofix" in f]
        assert len(tmp_files) == 0, f"Leaked temporary files detected: {tmp_files}"

    def test_tmp_cleanup_on_simulated_checksum_failure(self, tmp_path, monkeypatch):
        """If checksum verification fails during atomic copy, tmp file must be deleted."""
        src = tmp_path / "src.dat"
        tgt = tmp_path / "tgt.dat"
        src.write_bytes(b"ORIGINAL_DATA")

        # Monkeypatch stream_sha256 to return different hash for tmp file to simulate corruption during write
        real_stream_sha = stream_sha256

        def mock_stream_sha(path, chunk_size=DEFAULT_CHUNK_SIZE):
            if ".tmp_autofix" in str(path):
                return "BAD_CHECKSUM_DURING_TRANSFER"
            return real_stream_sha(path, chunk_size)

        monkeypatch.setattr("backup_sync.stream_sha256", mock_stream_sha)

        with pytest.raises(ValueError, match="SHA-256 mismatch during atomic copy"):
            atomic_write_replace(src, tgt, dry_run=False)

        # Verify no .tmp_autofix file remains in target directory
        remaining = list(tmp_path.glob("*.tmp_autofix*"))
        assert len(remaining) == 0, f"Temp file was leaked on failure: {remaining}"
        assert not tgt.exists()


# ============================================================================
# Test 7: Exclusion Rules Strict Enforcement
# ============================================================================

class TestExclusionRules:
    """Verify default exclusions and CLI flags."""

    def test_default_exclusions_strict(self, tmp_path):
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        # Regular file to be synced
        (source_dir / "valid_code.py").write_text("print('hello')", encoding="utf-8")

        # Default excluded directory trees
        for ex_dir in [".venv", "__pycache__", ".pytest_cache", ".agents", ".claude", ".bmad-loop", "_bmad-output", ".git"]:
            d = source_dir / ex_dir / "subdir"
            d.mkdir(parents=True)
            (d / "secret.txt").write_text("Should not be copied", encoding="utf-8")

        # Default excluded extensions
        (source_dir / "module.pyc").write_bytes(b"\x00" * 32)
        (source_dir / "script.pyo").write_bytes(b"\x00" * 32)
        (source_dir / "temp.tmp").write_bytes(b"\x00" * 32)

        stats = verify_and_sync_target(
            source_root=source_dir,
            target_path=target_dir,
            exclude_dirs=set(DEFAULT_EXCLUDE_DIRS),
            exclude_exts=set(DEFAULT_EXCLUDE_EXTS),
            dry_run=False,
        )

        assert stats["files_missing_fixed"] == 1  # Only valid_code.py
        assert (target_dir / "valid_code.py").exists()

        # Ensure NONE of the excluded files/directories exist in target
        for ex_dir in [".venv", "__pycache__", ".pytest_cache", ".agents", ".claude", ".bmad-loop", "_bmad-output", ".git"]:
            assert not (target_dir / ex_dir).exists(), f"Excluded dir {ex_dir} was copied!"

        assert not (target_dir / "module.pyc").exists()
        assert not (target_dir / "script.pyo").exists()
        assert not (target_dir / "temp.tmp").exists()


# ============================================================================
# Test 8: CLI Integration Tests (--dry-run vs. --verify-and-sync)
# ============================================================================

class TestCLIExecution:
    """Subprocess CLI execution tests for --dry-run and live synchronization."""

    def test_cli_dry_run_vs_live(self, tmp_path):
        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        source_dir = tmp_path / "cli_source"
        target_dir = tmp_path / "cli_target"
        state_file = tmp_path / "state.json"
        log_file = tmp_path / "sync.log"
        source_dir.mkdir()
        target_dir.mkdir()

        # Create source files
        (source_dir / "app.py").write_text("print('v1.0')", encoding="utf-8")
        (source_dir / "data.csv").write_text("a,b,c\n1,2,3\n", encoding="utf-8")

        # Create corrupted target file
        (target_dir / "app.py").write_text("print('corrupt')", encoding="utf-8")

        # 1. CLI Execution with --dry-run and --verify-and-sync
        cmd_dry = [
            sys.executable,
            str(script_path),
            "--source-dir", str(source_dir),
            "--target-dirs", str(target_dir),
            "--downloads-dirs", str(tmp_path / "empty_dl"),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
            "--verify-and-sync",
            "--dry-run",
        ]
        res_dry = subprocess.run(cmd_dry, capture_output=True, text=True)
        assert res_dry.returncode == 0, f"Dry-run failed: {res_dry.stderr}"
        assert "[DRY-RUN]" in res_dry.stdout or "[DRY-RUN]" in log_file.read_text(encoding="utf-8")

        # Verify disk was UNTOUCHED
        assert (target_dir / "app.py").read_text(encoding="utf-8") == "print('corrupt')"
        assert not (target_dir / "data.csv").exists()

        # 2. CLI Execution with live --verify-and-sync
        cmd_live = [
            sys.executable,
            str(script_path),
            "--source-dir", str(source_dir),
            "--target-dirs", str(target_dir),
            "--downloads-dirs", str(tmp_path / "empty_dl"),
            "--state-file", str(state_file),
            "--log-file", str(log_file),
            "--verify-and-sync",
        ]
        res_live = subprocess.run(cmd_live, capture_output=True, text=True)
        assert res_live.returncode == 0, f"Live sync failed: {res_live.stderr}"

        # Verify disk was UPDATED
        assert (target_dir / "app.py").read_text(encoding="utf-8") == "print('v1.0')"
        assert (target_dir / "data.csv").exists()
        assert (target_dir / "data.csv").read_text(encoding="utf-8") == "a,b,c\n1,2,3\n"
