# Handoff Report: Adversarial Review of Production Sync, Recovery & Scheduling

**Agent:** `reviewer_m1_2_g15` (Reviewer & Adversarial Critic)  
**Recipient:** `orchestrator_gen15` (`e9d0dc6b-8d4f-4c1a-924e-6152f16b1473`)  
**Date:** 2026-09-16T04:57:00Z  
**Handoff Type:** Hard  
**Verdict:** `REQUEST_CHANGES`  

---

## 1. Observation

1. **Acceptance Test Suite Verification:**
   - Command: `pytest -v M:\chakramodel\tests\test_backup_sync.py`
   - Output:
     ```
     ============================= test session starts =============================
     platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
     collected 14 items
     tests/test_backup_sync.py::TestCorruptionAutoFix::test_corruption_detected_and_restored PASSED [  7%]
     tests/test_backup_sync.py::TestDeletionAutoFix::test_missing_file_detected_and_restored PASSED [ 14%]
     tests/test_backup_sync.py::TestDownloadsRecovery::test_mock_weights_recovery_and_privacy_filter PASSED [ 21%]
     tests/test_backup_sync.py::TestStandaloneExecution::test_standalone_cli_execution PASSED [ 28%]
     tests/test_backup_sync.py::TestTaskSchedulerVerification::test_xml_task_definition PASSED [ 35%]
     tests/test_backup_sync.py::TestTaskSchedulerVerification::test_time_window_enforcement_logic PASSED [ 42%]
     tests/test_backup_sync.py::TestTaskSchedulerVerification::test_startup_task_clean_exit_outside_window PASSED [ 50%]
     tests/test_backup_sync.py::TestTaskSchedulerVerification::test_daily_execution_guard PASSED [ 57%]
     tests/test_backup_sync.py::TestTargetRoleGates::test_audit_workspace_protected PASSED [ 64%]
     tests/test_backup_sync.py::TestTargetRoleGates::test_sibling_project_protected PASSED [ 71%]
     tests/test_backup_sync.py::TestTargetRoleGates::test_cloud_container_target_resolution PASSED [ 78%]
     tests/test_backup_sync.py::TestEdgeCasesAndResilience::test_fast_path_size_mismatch_precheck PASSED [ 85%]
     tests/test_backup_sync.py::TestEdgeCasesAndResilience::test_default_exclusions_respected PASSED [ 92%]
     tests/test_backup_sync.py::TestEdgeCasesAndResilience::test_corrupted_archive_rejection_in_downloads PASSED [100%]
     ============================= 14 passed in 0.36s ==============================
     ```

2. **Time Window Boundary Verification:**
   - 06:00:00 -> `True` (inside window)
   - 11:00:00 -> `True` (inside window)
   - 05:59:59 -> `False` (outside window)
   - 11:00:01 -> `False` (outside window)

3. **Privacy Leak Test on Subdirectories (`backup_sync.py:380, 441-452`):**
   - When files are located inside subdirectories matching `CHAKRA_INDICATORS` (e.g. `C:\Users\imgk3\Downloads\weights\` or `J:\My Drive\downloads\weights\` or `C:\Users\imgk3\Downloads\chakra\`):
     * `C:\Users\imgk3\Downloads\weights\Tax_Return_2025.pdf` -> `CHAKRAMODEL_ASSET` -> Destination: `M:\chakramodel\docs\pdfs\Tax_Return_2025.pdf`
     * `C:\Users\imgk3\Downloads\weights\Bank_Statement.pdf` -> `CHAKRAMODEL_ASSET` -> Destination: `M:\chakramodel\docs\pdfs\Bank_Statement.pdf`
     * `J:\My Drive\downloads\weights\Salary_Slip.pdf` -> `CHAKRAMODEL_ASSET` -> Destination: `M:\chakramodel\docs\pdfs\Salary_Slip.pdf`
     * `C:\Users\imgk3\Downloads\combo\medical_records.pdf` -> `CHAKRAMODEL_ASSET` -> Destination: `M:\chakramodel\docs\pdfs\medical_records.pdf`
     * `C:\Users\imgk3\Downloads\cvc\Aadhaar_Card.pdf` -> `CHAKRAMODEL_ASSET` -> Destination: `M:\chakramodel\docs\pdfs\Aadhaar_Card.pdf`
     * `C:\Users\imgk3\Downloads\weights\Confidential_Clients.csv` -> `CHAKRAMODEL_ASSET` -> Destination: `M:\chakramodel\results\recovered\Confidential_Clients.csv`
     Total Leaks Observed: 9 of 10 sensitive files tested.

4. **Error Swallowing and False SUCCESS in Daily Guard (`backup_sync.py:1090-1094, 1112`):**
   - When a target sync fails with an error:
     * Log: `[ERROR] [backup_sync] Error verifying 'file.txt' on '...': [WinError 5] Access is denied`
     * Line 1093: `pass`
     * Final line: `[INFO] [backup_sync] ChakraModel Backup Sync finished with status: SUCCESS in 0.01s`
     * Exit code returned by `main()`: `0`
     * Recorded in `logs/backup_sync_state.json`: `"last_status": "SUCCESS"`
     * Result on subsequent boots: `has_run_successfully_today()` returns `True`, completely suppressing daily auto-fix.

5. **Windows Read-Only Target Overwrite Failure (`backup_sync.py:105-148`):**
   - Target file marked with `stat.S_IREAD` (`attrib +r`).
   - `atomic_write_replace` fails verbatim:
     `PermissionError: [WinError 5] Access is denied: '...target.txt.tmp_autofix_...' -> '...target.txt'`
   - Target remains corrupted because `os.replace` cannot overwrite a read-only file on Windows without clearing `stat.S_IWRITE` first.

6. **State Tempfile Concurrency Collision (`backup_sync.py:813`):**
   - When two processes write state simultaneously, collision on static filename `backup_sync_state.tmp` yields:
     `Failed writing sync state file: [WinError 32] The process cannot access the file because it is being used by another process`

---

## 2. Logic Chain

1. **Integrity & Core Logic (Observation 1):**
   - All 14 tests pass and show authentic implementations of SHA-256 streaming, XML configuration, and PowerShell cmdlets. No shortcuts, dummy methods, or integrity violations were found.

2. **Privacy Vulnerability Logic (Observation 3):**
   - `is_chakramodel_asset` tests `ind in path_lower` where `ind` includes `"weights"`.
   - Any user folder named `weights` (a standard downloads folder) causes `is_chakramodel_asset` to return `True` for all files inside it.
   - `PERSONAL_DENY_REGEX` lacks coverage for `tax`, `statement`, `bank`, `salary`, `payslip`, `medical`, `aadhaar`, `pan`, `id_card`, `curriculum_vitae`, `confidential`.
   - `resolve_recovery_destination` maps any unclassified `.pdf` to `docs/pdfs/` and `.csv` to `results/recovered/`.
   - Therefore, sensitive personal documents inside downloads subfolders are leaked directly into the public repository.

3. **Silent Failure & Daily Guard Suppression Logic (Observation 4):**
   - In `backup_sync.py:1090-1094`, target errors are ignored with `pass`.
   - `success` remains `True`, so `status` is set to `"SUCCESS"`.
   - `SyncStateManager.record_run("SUCCESS", ...)` writes `"last_status": "SUCCESS"`.
   - When the scheduled task executes on next startup, `has_run_successfully_today()` reads `last_status == "SUCCESS"` and skips auto-fix.
   - Therefore, any uncorrected file remains corrupted for the remainder of the day without alert or retry.

4. **Windows Read-Only Overwrite Logic (Observation 5):**
   - In Windows Win32 API, `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING` (invoked by Python `os.replace`) fails with `ERROR_ACCESS_DENIED` if the destination has `FILE_ATTRIBUTE_READONLY`.
   - Backup files frequently have read-only attributes.
   - `atomic_write_replace` does not clear read-only permissions prior to replacing.
   - Therefore, auto-fix fails on read-only targets.

---

## 3. Caveats

- **Google Drive Rate Limits:** Testing used synthetic local directories and simulated cloud paths. Under actual Google Drive for Desktop operation, extreme rate-limiting or network disconnects could trigger transient locks, which reinforces the need for retry logic.
- **Elevation Behavior:** `setup_task_scheduler.ps1` self-elevation launches a separate elevated PowerShell prompt via `Start-Process powershell -Verb RunAs`. In automated non-interactive CI environments, self-elevation triggers a UAC prompt unless run by an already elevated shell.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

While the implementation is architecturally solid and adheres to the project structure, it cannot be approved for production due to two Critical safety/correctness issues and two Major issues:
1. **Critical:** Privacy filter bypass allowing personal financial and identity documents to be copied into the repository.
2. **Critical:** Error swallowing in target sync causing false `SUCCESS` reporting and suppression of subsequent daily runs.
3. **Major:** Read-only target auto-fix failure on Windows (`WinError 5`).
4. **Major:** Lack of retry logic for transient file locks.

A remediation worker must implement the changes detailed in `M:\chakramodel\.agents\reviewer_m1_2_g15\review.md` and add corresponding tests.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Privacy Leak:**
   ```powershell
   python -c "import sys; from pathlib import Path; sys.path.insert(0, r'M:\chakramodel\scripts'); from backup_sync import classify_download_file; print(classify_download_file(Path(r'C:\Users\imgk3\Downloads\weights\Tax_Return_2025.pdf')))"
   ```
   *Actual:* Outputs `('CHAKRAMODEL_ASSET', 'PDF_DOC', WindowsPath('M:/chakramodel/docs/pdfs/Tax_Return_2025.pdf'))`.

2. **Verify Read-Only Overwrite Failure:**
   ```powershell
   python -c "import sys, tempfile, stat, os; from pathlib import Path; sys.path.insert(0, r'M:\chakramodel\scripts'); from backup_sync import atomic_write_replace; d = Path(tempfile.mkdtemp()); s = d/'s.txt'; t = d/'t.txt'; s.write_text('new'); t.write_text('old'); os.chmod(t, stat.S_IREAD); atomic_write_replace(s, t)"
   ```
   *Actual:* Raises `PermissionError: [WinError 5] Access is denied`.

3. **Verify False SUCCESS on Target Sync Failure:**
   ```powershell
   python -c "import sys, tempfile, stat, os, json; from pathlib import Path; sys.path.insert(0, r'M:\chakramodel\scripts'); from backup_sync import main; d = Path(tempfile.mkdtemp()); s = d/'s'; t = d/'t'; s.mkdir(); t.mkdir(); (s/'f.txt').write_text('new'); tf = t/'f.txt'; tf.write_text('old'); os.chmod(tf, stat.S_IREAD); sf = d/'st.json'; main(['--source-dir', str(s), '--target-dirs', str(t), '--state-file', str(sf), '--verify-and-sync']); print('Recorded Status:', json.load(open(sf))['last_status'])"
   ```
   *Actual:* Prints `Recorded Status: SUCCESS` despite `[WinError 5]` failure.
