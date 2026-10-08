"""
Comprehensive Empirical Adversarial Execution Runner
Executes all stress tests for Acceptance Criteria A & B and outputs detailed telemetry.
"""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add scripts to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from backup_sync import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_EXTS,
    atomic_write_replace,
    main,
    stream_sha256,
    verify_and_sync_target,
)

def log_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def main_runner():
    log_header("ChakraModel Empirical Adversarial Test Harness - Criteria A & B")
    print(f"System: Python {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

    results = {}

    # ------------------------------------------------------------------------
    # Scenario 1: Single-Byte Middle-of-File Corruption
    # ------------------------------------------------------------------------
    log_header("SCENARIO 1: Single-Byte Mid-File Corruption (Same Size, Altered SHA-256)")
    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "src"
        tgt_dir = Path(td) / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        size = 1_200_000
        mid = size // 2
        payload = bytearray(os.urandom(size))
        (src_dir / "model.bin").write_bytes(payload)
        src_sha = hashlib.sha256(payload).hexdigest()

        # Initial populate
        verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=False)
        tgt_file = tgt_dir / "model.bin"

        # Corrupt 1 byte in middle
        corrupt_payload = bytearray(payload)
        corrupt_payload[mid] ^= 0xFF
        tgt_file.write_bytes(corrupt_payload)
        corrupt_sha = hashlib.sha256(corrupt_payload).hexdigest()

        print(f"Original SHA-256:  {src_sha}")
        print(f"Corrupted SHA-256: {corrupt_sha}")
        print(f"File Size (Bytes): {size} (Preserved Exactly)")

        # Test Dry-Run
        dry_stats = verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=True)
        print(f"Dry-Run Stats: CorruptedDetected={dry_stats['files_corrupted_fixed']}")
        assert stream_sha256(tgt_file) == corrupt_sha, "Dry run must NOT alter disk"

        # Test Live Sync
        live_stats = verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=False)
        repaired_sha = stream_sha256(tgt_file)
        print(f"Live-Run Stats: CorruptedFixed={live_stats['files_corrupted_fixed']}")
        print(f"Repaired SHA-256:  {repaired_sha}")
        assert repaired_sha == src_sha, "Repaired SHA must match source exactly"
        assert tgt_file.read_bytes() == bytes(payload), "Payload must match byte-for-byte"
        results["Scenario 1 (Single-Byte Mid Corruption)"] = "PASS"

    # ------------------------------------------------------------------------
    # Scenario 2: Size-Truncated and Zero-Byte Corruption
    # ------------------------------------------------------------------------
    log_header("SCENARIO 2: Size-Truncated & Zero-Byte Corruption")
    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "src"
        tgt_dir = Path(td) / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        (src_dir / "file_trunc.dat").write_bytes(b"A" * 50_000)
        (tgt_dir / "file_trunc.dat").write_bytes(b"A" * 12_000)  # Truncated

        (src_dir / "file_zero.dat").write_bytes(b"Data in source")
        (tgt_dir / "file_zero.dat").write_bytes(b"")  # 0 bytes

        stats = verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=False)
        print(f"Sync Stats: CorruptedFixed={stats['files_corrupted_fixed']}")
        assert (tgt_dir / "file_trunc.dat").stat().st_size == 50_000
        assert (tgt_dir / "file_zero.dat").read_bytes() == b"Data in source"
        results["Scenario 2 (Size Mismatch Fast-Path)"] = "PASS"

    # ------------------------------------------------------------------------
    # Scenario 3: Multiple Corrupted Files in Subdirectories
    # ------------------------------------------------------------------------
    log_header("SCENARIO 3: Multiple Corrupted Files Across Deep Directory Trees")
    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "src"
        tgt_dir = Path(td) / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        tree = {
            "a/b/c/file1.txt": b"Leaf file 1",
            "a/b/file2.bin": b"Binary file 2" * 50,
            "a/file3.json": b'{"key": "value"}',
            "clean.txt": b"Intact content",
        }
        for rel, d in tree.items():
            p = src_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(d)

        verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=False)

        # Corrupt file1, file2, file3
        (tgt_dir / "a/b/c/file1.txt").write_bytes(b"Corrupted Leaf")
        (tgt_dir / "a/b/file2.bin").write_bytes(b"Truncated")
        (tgt_dir / "a/file3.json").write_bytes(b'{"key": "wrong"}')

        stats = verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=False)
        print(f"Deep Tree Stats: Checked={stats['files_checked']}, VerifiedOK={stats['files_verified_ok']}, CorruptedFixed={stats['files_corrupted_fixed']}")
        assert stats["files_verified_ok"] == 1
        assert stats["files_corrupted_fixed"] == 3
        for rel, d in tree.items():
            assert (tgt_dir / rel).read_bytes() == d
        results["Scenario 3 (Subdirectory Tree Corruption)"] = "PASS"

    # ------------------------------------------------------------------------
    # Scenario 4: Deleted Files in Target
    # ------------------------------------------------------------------------
    log_header("SCENARIO 4: Deleted Files in Target Directories")
    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "src"
        tgt_dir = Path(td) / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        (src_dir / "file_del1.txt").write_text("Deleted root file", encoding="utf-8")
        nested_src = src_dir / "sub" / "file_del2.bin"
        nested_src.parent.mkdir(parents=True, exist_ok=True)
        nested_src.write_bytes(b"\x12\x34\x56\x78" * 500)

        # Initial sync
        verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=False)
        (tgt_dir / "file_del1.txt").unlink()
        (tgt_dir / "sub" / "file_del2.bin").unlink()

        dry_stats = verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=True)
        print(f"Dry-Run Deleted Detection: MissingFixed={dry_stats['files_missing_fixed']}")
        assert not (tgt_dir / "file_del1.txt").exists()

        live_stats = verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=False)
        print(f"Live-Run Restoration: MissingFixed={live_stats['files_missing_fixed']}")
        assert (tgt_dir / "file_del1.txt").exists()
        assert (tgt_dir / "sub" / "file_del2.bin").exists()
        assert stream_sha256(tgt_dir / "file_del1.txt") == stream_sha256(src_dir / "file_del1.txt")
        results["Scenario 4 (Deleted Files Restoration)"] = "PASS"

    # ------------------------------------------------------------------------
    # Scenario 5: Read-Only Corrupted Target File (Vulnerability Stress-Test)
    # ------------------------------------------------------------------------
    log_header("SCENARIO 5: Read-Only Corrupted Target File (Windows WinError 5)")
    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "src"
        tgt_dir = Path(td) / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        src_file = src_dir / "readonly.txt"
        src_file.write_text("GENUINE_SOURCE_DATA")
        tgt_file = tgt_dir / "readonly.txt"
        tgt_file.write_text("CORRUPTED_READONLY_DATA")

        # Set read-only attribute
        os.chmod(tgt_file, stat.S_IREAD)
        print(f"Set file attribute to READ-ONLY: {tgt_file}")

        stats = verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=False)
        print(f"Sync Results on Read-Only Target:")
        print(f"  Files Corrupted Fixed: {stats['files_corrupted_fixed']}")
        print(f"  Error Count: {len(stats['errors'])}")
        for err in stats["errors"]:
            print(f"  Logged Error: {err}")

        # Check residue
        tmp_files = list(tgt_dir.glob("*.tmp_autofix*"))
        print(f"  Remaining .tmp_autofix files: {tmp_files}")

        # Check disk state
        current_content = tgt_file.read_text()
        print(f"  Target File Content Remaining: {current_content}")

        # Reset permissions for cleanup
        os.chmod(tgt_file, stat.S_IWRITE)

        is_vulnerable = len(stats["errors"]) > 0 and current_content == "CORRUPTED_READONLY_DATA"
        if is_vulnerable:
            print("  [FINDING CONFIRMED] Script failed to repair read-only target file due to Windows os.replace PermissionError.")
            results["Scenario 5 (Read-Only Corrupted Target File)"] = "CONFIRMED_VULNERABILITY_FAILURE"
        else:
            results["Scenario 5 (Read-Only Corrupted Target File)"] = "PASS"

    # ------------------------------------------------------------------------
    # Scenario 6: Genuine SHA-256 Hash Verification
    # ------------------------------------------------------------------------
    log_header("SCENARIO 6: Genuine Cryptographic SHA-256 Engine Verification")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "vector.dat"
        # NIST Test Vector
        p.write_bytes(b"")
        sha_empty = stream_sha256(p)
        assert sha_empty == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        p.write_bytes(b"abc")
        sha_abc = stream_sha256(p)
        assert sha_abc == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

        # Multi-chunk streaming verification
        large_bytes = os.urandom(2_500_000)
        p.write_bytes(large_bytes)
        expected_sha = hashlib.sha256(large_bytes).hexdigest()
        actual_sha = stream_sha256(p)
        assert actual_sha == expected_sha
        print(f"Empty File SHA-256: {sha_empty} (NIST OK)")
        print(f"String 'abc' SHA-256: {sha_abc} (NIST OK)")
        print(f"2.5 MB Stream SHA-256: {actual_sha} == {expected_sha} (OK)")
        results["Scenario 6 (Genuine SHA-256 Verification)"] = "PASS"

    # ------------------------------------------------------------------------
    # Scenario 7: Temp File (.tmp_autofix) Atomicity and Cleanup
    # ------------------------------------------------------------------------
    log_header("SCENARIO 7: Temp File (.tmp_autofix) Atomicity & Cleanup")
    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "src"
        tgt_dir = Path(td) / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        (src_dir / "sample.bin").write_bytes(b"\x55" * 10_000)
        verify_and_sync_target(src_dir, tgt_dir, set(), set(), dry_run=False)

        leaked_files = list(tgt_dir.glob("*.tmp_autofix*"))
        print(f"Leaked temp files after clean sync: {len(leaked_files)}")
        assert len(leaked_files) == 0
        results["Scenario 7 (Temp File Cleanup)"] = "PASS"

    # ------------------------------------------------------------------------
    # Scenario 8: Directory & Extension Exclusions
    # ------------------------------------------------------------------------
    log_header("SCENARIO 8: Exclusion Invariants (.venv, .git, .agents, __pycache__, etc.)")
    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "src"
        tgt_dir = Path(td) / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        (src_dir / "valid.py").write_text("valid = True")
        (src_dir / ".venv" / "pip.exe").parent.mkdir(parents=True)
        (src_dir / ".venv" / "pip.exe").write_bytes(b"\x00" * 100)
        (src_dir / ".git" / "HEAD").parent.mkdir(parents=True)
        (src_dir / ".git" / "HEAD").write_text("ref: refs/heads/main")
        (src_dir / ".agents" / "plan.md").parent.mkdir(parents=True)
        (src_dir / ".agents" / "plan.md").write_text("agent plan")
        (src_dir / "junk.pyc").write_bytes(b"\x00" * 10)

        stats = verify_and_sync_target(
            src_dir, tgt_dir,
            exclude_dirs=set(DEFAULT_EXCLUDE_DIRS),
            exclude_exts=set(DEFAULT_EXCLUDE_EXTS),
            dry_run=False,
        )

        print(f"Exclusion Stats: Checked={stats['files_checked']}, MissingFixed={stats['files_missing_fixed']}")
        assert (tgt_dir / "valid.py").exists()
        assert not (tgt_dir / ".venv").exists()
        assert not (tgt_dir / ".git").exists()
        assert not (tgt_dir / ".agents").exists()
        assert not (tgt_dir / "junk.pyc").exists()
        results["Scenario 8 (Exclusions Enforcement)"] = "PASS"

    # ------------------------------------------------------------------------
    # Scenario 9: CLI End-to-End Subprocess Execution
    # ------------------------------------------------------------------------
    log_header("SCENARIO 9: CLI End-to-End Execution (--dry-run vs. --verify-and-sync)")
    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "src"
        tgt_dir = Path(td) / "tgt"
        src_dir.mkdir()
        tgt_dir.mkdir()

        (src_dir / "code.py").write_text("v1.0")
        (tgt_dir / "code.py").write_text("v0.0_corrupt")

        script_path = PROJECT_ROOT / "scripts" / "backup_sync.py"
        cmd_dry = [
            sys.executable, str(script_path),
            "--source-dir", str(src_dir),
            "--target-dirs", str(tgt_dir),
            "--downloads-dirs", str(Path(td) / "empty_dl"),
            "--state-file", str(Path(td) / "state.json"),
            "--log-file", str(Path(td) / "sync.log"),
            "--verify-and-sync", "--dry-run",
        ]
        res_dry = subprocess.run(cmd_dry, capture_output=True, text=True)
        assert res_dry.returncode == 0
        assert (tgt_dir / "code.py").read_text() == "v0.0_corrupt"
        print("CLI Dry-Run Execution: Verified code.py left unchanged.")

        cmd_live = [
            sys.executable, str(script_path),
            "--source-dir", str(src_dir),
            "--target-dirs", str(tgt_dir),
            "--downloads-dirs", str(Path(td) / "empty_dl"),
            "--state-file", str(Path(td) / "state.json"),
            "--log-file", str(Path(td) / "sync.log"),
            "--verify-and-sync",
        ]
        res_live = subprocess.run(cmd_live, capture_output=True, text=True)
        assert res_live.returncode == 0
        assert (tgt_dir / "code.py").read_text() == "v1.0"
        print("CLI Live Execution: Verified code.py restored to v1.0.")
        results["Scenario 9 (CLI E2E Subprocess)"] = "PASS"

    # ------------------------------------------------------------------------
    # Summary of Harness Results
    # ------------------------------------------------------------------------
    log_header("HARNESS SUMMARY")
    for scen, verdict in results.items():
        print(f"  {scen:<55}: {verdict}")

    return results

if __name__ == "__main__":
    main_runner()
