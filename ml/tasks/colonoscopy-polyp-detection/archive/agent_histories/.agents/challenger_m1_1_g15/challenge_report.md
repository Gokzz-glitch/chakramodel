# Empirical Adversarial Challenge Report: Criteria A & B (Target Directories Verification and Auto-Fix)

**Challenger Agent:** `challenger_m1_1_g15`  
**Target Script:** `scripts/backup_sync.py`  
**Parent:** `orchestrator_gen15` (`e9d0dc6b-8d4f-4c1a-924e-6152f16b1473`)  
**Date:** 2026-09-15T23:26:00Z (Local: 2026-09-16 04:56:00)  
**Execution Environment:** Windows 11 (win32), Python 3.11.9  

---

## 1. Executive Challenge Summary

**Overall Risk Assessment:** **MEDIUM**

The target verification and auto-fix engine in `scripts/backup_sync.py` demonstrates high mathematical and cryptographic rigor for standard file operations:
- **Genuine SHA-256 Hashing:** Accurately streams digests with chunked 1MB buffering matching NIST test vectors and `hashlib.sha256` byte-for-byte across all buffer boundaries.
- **Fast-Path Size Pre-Check:** Instantly identifies truncated or expanded corrupted files in $O(1)$ time.
- **Single-Byte Mid-File Corruption:** Correctly detects bit flips that conserve exact file length and auto-restores the payload from source.
- **Multi-Subdirectory Tree Traversal:** Successfully traverses deep hierarchies, restoring mixed missing and corrupted files while preserving intact files.
- **Dry-Run vs. Live Separation:** `--dry-run` accurately detects and logs discrepancies without mutating target disk contents; live execution repairs targets byte-for-byte.
- **Temp File Atomicity:** `.tmp_autofix_<uuid>` staging files are strictly cleaned up both upon successful replacement and upon unhandled exceptions.
- **Directory and Extension Exclusions:** Excluded directories (`.venv`, `.git`, `.agents`, `__pycache__`, etc.) and extensions (`.pyc`, `.pyo`, `.tmp`) are completely isolated.

**CRITICAL FINDING / EDGE CASE VULNERABILITY:**  
When a corrupted file on the target directory carries the **READ-ONLY attribute** (`FILE_ATTRIBUTE_READONLY` / `stat.S_IREAD`), Windows semantics cause `os.replace(tmp_path, tgt_path)` to fail with `PermissionError: [WinError 5] Access is denied`. `backup_sync.py` catches this as a non-fatal error, leaving the target file corrupted on disk and un-repaired.

---

## 2. Adversarial Challenges

### [Medium] Challenge 1: Windows Read-Only Target File Blocks Atomic Auto-Fix Replacement

- **Assumption Challenged:**  
  `atomic_write_replace()` assumes `os.replace(tmp_path, tgt_path)` is universally permissible on Windows filesystems if the parent directory is writable.
- **Attack Scenario:**  
  A backup directory contains files marked read-only by automated backup archives, version control, or user security attributes (`attrib +R` or `os.chmod(f, stat.S_IREAD)`). If bit corruption occurs in this file, `verify_and_sync_target` detects the hash mismatch and invokes `atomic_write_replace()`. On Windows, `os.replace` internally maps to `MoveFileEx(..., MOVEFILE_REPLACE_EXISTING)`. If the destination file exists and is read-only, Windows aborts with `[WinError 5] Access is denied`.
- **Blast Radius:**  
  Corrupted target files marked read-only cannot be repaired by `--verify-and-sync`. The script logs an error and skips the file, leaving the backup replica permanently desynchronized and corrupted.
- **Empirical Evidence:**  
  ```
  Error verifying 'readonly.txt' on 'C:\...\tgt': [WinError 5] Access is denied: 'C:\...\readonly.txt.tmp_autofix_4fd93b67' -> 'C:\...\readonly.txt'
  Target File Content Remaining: CORRUPTED_READONLY_DATA
  Files Corrupted Fixed: 0
  Remaining .tmp_autofix files: [] (temp file cleaned up, but repair failed)
  ```
- **Mitigation:**  
  In `scripts/backup_sync.py::atomic_write_replace()`, immediately prior to `os.replace(tmp_path, tgt_path)`, clear the read-only attribute if the target exists:
  ```python
  if tgt_path.exists():
      try:
          os.chmod(tgt_path, stat.S_IWRITE)
      except OSError:
          pass
  os.replace(tmp_path, tgt_path)
  ```

---

## 3. Stress Test Results & Matrix

All tests were executed against `scripts/backup_sync.py` using automated test harness `tests/test_adversarial_criteria_ab.py` (pytest) and `tests/run_adversarial_harness.py`.

| # | Stress Scenario | Expected Behavior | Observed Behavior | Verdict |
|---|-----------------|-------------------|-------------------|---------|
| **1** | **Single-byte corruption in middle of large file (> 1MB)** | Detects SHA-256 mismatch with identical file length; `--dry-run` leaves disk untouched; live run repairs byte-for-byte. | Original SHA: `07c4a52a...`, Corrupted SHA: `ee20520b...`. Dry-run reported 1 corrupted. Live-run restored exact SHA `07c4a52a...`. | **PASS** |
| **2** | **Size-truncated corruption (50KB -> 12KB)** | Fast-path pre-check flags size discrepancy without requiring full hashing; auto-fixed to full length. | Detected size mismatch; target restored to exactly 50,000 bytes with matching data. | **PASS** |
| **3** | **Zero-byte target corruption (source has data, target is 0B)** | Fast-path detects 0B vs non-empty; restored to source content. | Target 0-byte file replaced with authentic source bytes. | **PASS** |
| **4** | **Zero-byte source with corrupted target (target has data)** | Target detected as corrupted; target replaced with 0-byte file. | Target size reduced to 0 bytes matching source. | **PASS** |
| **5** | **Subdirectory tree corruption (4 levels deep, mixed damages)** | Traverses nested dirs; repairs corrupted leaf files while skipping intact files. | Checked=4, VerifiedOK=1, CorruptedFixed=3. All nested files matched source SHA-256. | **PASS** |
| **6** | **Deleted target files (root & nested subdirs)** | Missing target files detected; `--dry-run` reports without modifying; live run restores missing files. | Dry-run reported MissingFixed=2 without creating files. Live-run created files with matching SHA-256. | **PASS** |
| **7** | **Read-only corrupted target file (`stat.S_IREAD`)** | Script should clear read-only flag and restore file. | `os.replace` raised `[WinError 5] Access is denied`. Error recorded; target remained corrupted. | **CONFIRMED FINDING / EDGE CASE VULNERABILITY** |
| **8** | **Genuine SHA-256 test vectors & buffer boundaries** | Matches NIST test vectors (empty, "abc") and `hashlib.sha256` at 1MB-1, 1MB, 1MB+1, 2.5MB. | Empty: `e3b0c442...`, 'abc': `ba7816bf...`, 2.5MB stream matched `hashlib.sha256` exactly. | **PASS** |
| **9** | **Temp file (.tmp_autofix) atomicity & leak prevention** | No `.tmp_autofix` files left on disk after clean run or simulated copy failure. | Leaked temp files: 0. On simulated checksum failure, temp file was cleanly unlinked. | **PASS** |
| **10**| **Default exclusions (.venv, .git, .agents, __pycache__, .pyc)** | None of the excluded directory trees or file extensions are copied to target. | Checked=1, MissingFixed=1 (only valid source file). No excluded items copied. | **PASS** |
| **11**| **CLI end-to-end execution (`--dry-run` vs `--verify-and-sync`)** | Subprocess CLI commands return code 0; dry-run preserves corrupted state; live sync repairs target. | Dry-run left `code.py` as `v0.0_corrupt`. Live sync updated `code.py` to `v1.0`. Exit codes 0. | **PASS** |

---

## 4. Captured Execution Logs

### Pytest Execution Log (`pytest -v tests/test_adversarial_criteria_ab.py`)
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\imgk3\AppData\Local\Programs\Python\Python311\python.exe
cachedir: .pytest_cache
rootdir: M:\chakramodel
plugins: anyio-4.14.2
collecting ... collected 13 items

tests/test_adversarial_criteria_ab.py::TestSingleByteCorruption::test_single_byte_middle_corruption_auto_fixed PASSED [  7%]
tests/test_adversarial_criteria_ab.py::TestSizeMismatchCorruption::test_truncated_corruption PASSED [ 15%]
tests/test_adversarial_criteria_ab.py::TestSizeMismatchCorruption::test_zero_byte_target_corruption PASSED [ 23%]
tests/test_adversarial_criteria_ab.py::TestSizeMismatchCorruption::test_zero_byte_source_with_corrupt_target PASSED [ 30%]
tests/test_adversarial_criteria_ab.py::TestSubdirectoryComplexTree::test_multi_level_mixed_failures PASSED [ 38%]
tests/test_adversarial_criteria_ab.py::TestDeletedFilesAutoFix::test_deleted_files_restored_byte_for_byte PASSED [ 46%]
tests/test_adversarial_criteria_ab.py::TestReadOnlyTargetFile::test_read_only_corrupted_target_file_fails_without_chmod PASSED [ 53%]
tests/test_adversarial_criteria_ab.py::TestGenuineSHA256::test_sha256_known_vectors PASSED [ 61%]
tests/test_adversarial_criteria_ab.py::TestGenuineSHA256::test_sha256_streaming_chunk_boundaries PASSED [ 69%]
tests/test_adversarial_criteria_ab.py::TestTempFileCleanup::test_no_tmp_residue_after_successful_replace PASSED [ 76%]
tests/test_adversarial_criteria_ab.py::TestTempFileCleanup::test_tmp_cleanup_on_simulated_checksum_failure PASSED [ 84%]
tests/test_adversarial_criteria_ab.py::TestExclusionRules::test_default_exclusions_strict PASSED [ 92%]
tests/test_adversarial_criteria_ab.py::TestCLIExecution::test_cli_dry_run_vs_live PASSED [100%]

============================= 13 passed in 0.78s ==============================
```

### Combined Suite (`pytest -v tests/test_backup_sync.py tests/test_adversarial_criteria_ab.py`)
```
============================= 27 passed in 1.08s ==============================
```

---

## 5. Unchallenged Areas

1. **Virtual Google Drive Letter Locking:**  
   Virtual drives (`I:\`, `J:\`) mounted via Google Drive for Desktop may experience transient handle locks during cloud synchronization uploads. Testing local NTFS mock directories accurately verifies Windows API semantics, but Google Drive client background synchronization was not subjected to concurrent upload contention.
2. **Network Interruption During 10GB+ Transfers:**  
   Streaming SHA-256 and atomic temporary writes operate with bounded memory ($< 25$ MB RAM). However, physical network partition testing during a multi-gigabyte atomic file write was simulated via software monkeypatching rather than physical NIC disconnection.

---

## 6. Final Empirical Verdict

- **Core Criteria A & B Requirements:** **PASS**  
  Modifying a file in a backup directory causes the script to detect corruption via hash mismatch and restore it from source byte-for-byte. Deleting a file causes the script to detect the missing file and restore it from source.
- **Production Hardening Recommendation:**  
  Implement the single-line `os.chmod(tgt_path, stat.S_IWRITE)` defense in `atomic_write_replace()` to guarantee auto-fix resilience against read-only Windows target files.
