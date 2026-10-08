# Adversarial Safety, Edge-Case, and Negative Testing Review Report

**Reviewer:** `reviewer_m1_2_g15` (Reviewer & Adversarial Critic)  
**Parent:** `orchestrator_gen15` (`e9d0dc6b-8d4f-4c1a-924e-6152f16b1473`)  
**Target Deliverables:** Produced by `worker_m2_g15`  
- `M:\chakramodel\scripts\backup_sync.py`
- `M:\chakramodel\scripts\task_scheduler_config.xml`
- `M:\chakramodel\scripts\setup_task_scheduler.ps1`
- `M:\chakramodel\tests\test_backup_sync.py`  
**Date:** 2026-09-16T04:56:30Z  

---

## 1. Review Summary

**Verdict: REQUEST_CHANGES**

- **Integrity Assessment:** **PASS** (Zero integrity violations. No hardcoded bypasses, dummy implementations, or fabricated outputs detected. Core logic uses authentic chunked SHA-256 streaming, genuine atomic writes with UUID tempfiles, and real PowerShell cmdlets.)
- **Overall Safety & Quality Assessment:** The deliverables establish an impressive, production-grade foundation with 14 passing acceptance tests. However, adversarial stress-testing identified **two CRITICAL vulnerabilities** and **two MAJOR deficiencies** that must be resolved before production deployment:
  1. **[CRITICAL] Privacy Leak Bypass:** Personal and confidential documents (tax returns, bank statements, salary slips, medical records, aadhaar cards, confidential client lists) in subdirectories such as `weights/`, `chakra/`, or `combo/` bypass the Tier 1 privacy filter and are copied directly into repository folders (`docs/pdfs/`, `results/recovered/`).
  2. **[CRITICAL] Error Swallowing & Daily Guard Suppression:** When target auto-fix fails due to file permission or locking errors, the script swallows the error with `pass`, reports `SUCCESS`, and writes `last_status: SUCCESS` into `backup_sync_state.json`. This causes the daily guard on subsequent morning boots to permanently skip auto-fixing corrupted targets for the rest of the day.
  3. **[MAJOR] Windows Read-Only Target Failure:** `atomic_write_replace` fails with `[WinError 5] Access is denied` when an existing target file in a backup directory is marked Read-Only (`attrib +r`), preventing auto-fix of protected backup files.
  4. **[MAJOR] Absence of Transient Lock Retry Logic:** No retry loop exists for transient file locks (common during Google Drive virtual drive indexing or Windows Defender scans).

---

## 2. Findings

### [Critical] Finding 1: Privacy Leak Bypass on Subdirectories & Generic Indicator Matching

- **What:** Non-denied personal, financial, and confidential documents located inside any folder whose path contains generic indicators (e.g. `weights`, `chakra`, `combo`, `cvc`, `polyp`) are erroneously classified as `CHAKRAMODEL_ASSET` and copied into repository directories (`docs/pdfs/`, `results/recovered/`, `recovered/`).
- **Where:** `M:\chakramodel\scripts\backup_sync.py`:
  - Lines 342-348: `PERSONAL_DENY_REGEX`
  - Lines 351-358: `CHAKRA_INDICATORS`
  - Line 380: `if any(ind in name_lower or ind in path_lower for ind in CHAKRA_INDICATORS): return True`
  - Lines 441-452: `resolve_recovery_destination` (unconstrained `.pdf`, `.csv`, `.xlsx` fallbacks).
- **Why (Root Cause & Proof):**
  1. `is_chakramodel_asset` searches `CHAKRA_INDICATORS` across `path_lower = str(filepath).lower()`.
  2. Because `"weights"` is in `CHAKRA_INDICATORS`, *any* file inside a user folder like `C:\Users\imgk3\Downloads\weights\` or `J:\My Drive\downloads\weights\` has `ind in path_lower == True`.
  3. `PERSONAL_DENY_REGEX` only matches a narrow list (`passport`, `resume`, `bill`, `receipt`, `payment`, `booking`, `leads`). It omits terms like `tax`, `bank`, `statement`, `salary`, `payslip`, `medical`, `aadhaar`, `pan`, `id_card`, `curriculum_vitae`, `confidential`.
  4. Empirical proof executed during review:
     - `C:\Users\imgk3\Downloads\weights\Tax_Return_2025.pdf` -> Classified as `CHAKRAMODEL_ASSET` -> Copied to `M:\chakramodel\docs\pdfs\Tax_Return_2025.pdf`
     - `C:\Users\imgk3\Downloads\weights\Bank_Statement.pdf` -> Classified as `CHAKRAMODEL_ASSET` -> Copied to `M:\chakramodel\docs\pdfs\Bank_Statement.pdf`
     - `J:\My Drive\downloads\weights\Salary_Slip.pdf` -> Classified as `CHAKRAMODEL_ASSET` -> Copied to `M:\chakramodel\docs\pdfs\Salary_Slip.pdf`
     - `C:\Users\imgk3\Downloads\combo\medical_records.pdf` -> Classified as `CHAKRAMODEL_ASSET` -> Copied to `M:\chakramodel\docs\pdfs\medical_records.pdf`
     - `C:\Users\imgk3\Downloads\cvc\Aadhaar_Card.pdf` -> Classified as `CHAKRAMODEL_ASSET` -> Copied to `M:\chakramodel\docs\pdfs\Aadhaar_Card.pdf`
     - `C:\Users\imgk3\Downloads\weights\Confidential_Clients.csv` -> Classified as `CHAKRAMODEL_ASSET` -> Copied to `M:\chakramodel\results\recovered\Confidential_Clients.csv`
- **Suggestion:**
  1. Expand `PERSONAL_DENY_REGEX` to include comprehensive personal, identity, and financial terms:
     `r"(passport|resume|curriculum[\s_-]*vitae|\bcv\b|profile\.pdf$|tax|itr|bank|statement|salary|payslip|pay[\s_-]*slip|medical|prescription|aadhaar|pan|ssn|license|id[\s_-]*card|voter|offer[\s_-]*letter|appraisal|contract|confidential|private|secret|budget|lor[-_]nit|receipt|payment|booking|mess\s*fees|bill|\.ics$|leads?|corporate_leads|researcher_leads|russia_moscow|priority_\d+.*\.csv$|\.(exe|msi|bat)$|eclipse|acer\s*care|chatgpt\s*installer|chromesetup|desktop\.ini$|screenshot|opus_keyword)"`
  2. Do not match generic indicator words like `"weights"` against the whole directory path string in `is_chakramodel_asset`. Require the filename itself to match ChakraModel criteria (or restrict folder matching to known specific repository subpaths).
  3. Constrain `resolve_recovery_destination`: do not recover arbitrary `.pdf` or `.csv` files unless their filename explicitly contains recognized ChakraModel keywords (`"chakra"`, `"polyp"`, `"audit"`, `"cvc"`, `"kvasir"`).

---

### [Critical] Finding 2: Sync Error Swallowing & Daily Guard Suppression

- **What:** When `verify_and_sync_all_targets` encounters errors (e.g. read-only file, locked file, network error), the errors are swallowed in `main()`. The run is reported as `SUCCESS`, returns exit code `0`, and records `last_status: SUCCESS` in `logs/backup_sync_state.json`.
- **Where:** `M:\chakramodel\scripts\backup_sync.py`:
  - Lines 1090-1094:
    ```python
    for res in tgt_results:
        if res.get("status") == "FAILED" or len(res.get("errors", [])) > 0:
            # Non-fatal warnings on unmounted targets, but mark flag if critical
            pass
    ```
  - Line 1112: `status = "SUCCESS" if success else "FAILED"`
- **Why (Root Cause & Proof):**
  Because `success` is never set to `False` when target errors occur, `state_manager.record_run(status="SUCCESS")` is executed. The daily guard (`has_run_successfully_today()`) queries `last_status == "SUCCESS"`. When the user restarts or logs in again later that morning, the startup task checks the guard, sees `SUCCESS`, and skips synchronization! The corrupt or missing backup files are left uncorrected.
  - Empirical proof executed during review:
    Target file `file.txt` failed to sync with `[WinError 5] Access is denied`.
    CLI output: `ChakraModel Backup Sync finished with status: SUCCESS in 0.01s`, `Exit code: 0`.
    State file: `{"last_status": "SUCCESS", "last_metrics": {"targets_results": [{"errors": ["...Access is denied..."]}]}}`.
- **Suggestion:**
  In `main()`, inspect `tgt_results`: if any target that is active (`LOCAL_MIRROR` or `CLOUD_CONTAINER`) has `errors` or `status == "FAILED"`, set `success = False` and record `status = "FAILED"` (or `"PARTIAL_FAILURE"`). Do not return exit code `0` or record `SUCCESS` in the state file if active backup targets failed to auto-fix.

---

### [Major] Finding 3: Windows Read-Only Target Overwrite Failure

- **What:** `atomic_write_replace` fails with `PermissionError: [WinError 5] Access is denied` when replacing an existing file in a target backup directory if that file has the Windows Read-Only attribute set (`attrib +r`).
- **Where:** `M:\chakramodel\scripts\backup_sync.py` lines 105-148 (`atomic_write_replace`).
- **Why (Root Cause & Proof):**
  On Windows, `os.replace` (Win32 `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING`) is rejected with `ERROR_ACCESS_DENIED` if the target destination file has `FILE_ATTRIBUTE_READONLY`. In backup mirrors, files often inherit or are marked with read-only attributes to prevent accidental edits.
  - Empirical proof executed during review:
    Creating `target.txt` with `stat.S_IREAD` and invoking `atomic_write_replace` raised:
    `PermissionError: [WinError 5] Access is denied: '...target.txt.tmp_autofix_...' -> '...target.txt'`.
- **Suggestion:**
  Before calling `os.replace`, remove the read-only attribute if the destination exists:
  ```python
  if tgt_path.exists():
      try:
          os.chmod(tgt_path, stat.S_IWRITE)
      except OSError:
          pass
  ```

---

### [Major] Finding 4: Absence of Retry Logic for Transient File Locks

- **What:** If a target or source file is briefly locked by another process (e.g. Google Drive for Desktop virtual drive syncing, antivirus scanner, or an active process), `atomic_write_replace` immediately raises `PermissionError` without retrying.
- **Where:** `M:\chakramodel\scripts\backup_sync.py` lines 105-148.
- **Why:** Cloud-mounted virtual drive letters (`I:\` and `J:\`) periodically lock files during background upload/metadata sync. Without a simple retry mechanism (e.g., 3 attempts with 200ms exponential backoff), transient locks cause auto-fix failures.
- **Suggestion:**
  Wrap `os.replace` and `shutil.copy2` with a retry helper:
  ```python
  for attempt in range(max_retries):
      try:
          if tgt_path.exists():
              try:
                  os.chmod(tgt_path, stat.S_IWRITE)
              except OSError:
                  pass
          os.replace(tmp_path, tgt_path)
          break
      except PermissionError:
          if attempt == max_retries - 1:
              raise
          time.sleep(0.2 * (2 ** attempt))
  ```

---

### [Minor] Finding 5: Static Temporary Filename Collision in State Manager

- **What:** `SyncStateManager.record_run()` writes temporary JSON to `self.state_file.with_suffix(".tmp")` (`backup_sync_state.tmp`).
- **Where:** `M:\chakramodel\scripts\backup_sync.py` line 813.
- **Why:** If two invocations run at the same time, they collide on `backup_sync_state.tmp`, causing `[WinError 32] The process cannot access the file because it is being used by another process`.
- **Suggestion:**
  Use a unique suffix: `self.state_file.with_name(f"{self.state_file.name}.tmp_{uuid.uuid4().hex[:8]}")`.

---

### [Minor] Finding 6: Inverted / Overnight Time Windows

- **What:** `is_within_scheduled_window` assumes `start_t <= end_t`.
- **Where:** `M:\chakramodel\scripts\backup_sync.py` line 737.
- **Why:** If a user specifies a window spanning midnight (e.g. `--window-start 22:00 --window-end 04:00`), `start_t <= now_t <= end_t` is impossible and always returns `False`.
- **Suggestion:**
  Handle overnight windows:
  ```python
  if start_t <= end_t:
      in_window = start_t <= now_t <= end_t
  else:
      in_window = (now_t >= start_t or now_t <= end_t)
  ```

---

## 3. Verified Claims

| Claim by `worker_m2_g15` | Verification Method | Result | Notes |
|---|---|---|---|
| Acceptance test suite passes (14 tests) | `pytest -v M:\chakramodel\tests\test_backup_sync.py` | **PASS** | 14 passed in 0.36s |
| Time window boundary: 06:00:00 is inside | Synthetic `datetime.time(6, 0, 0)` test | **PASS** | Evaluates to `True` |
| Time window boundary: 11:00:00 is inside | Synthetic `datetime.time(11, 0, 0)` test | **PASS** | Evaluates to `True` |
| Time window boundary: 05:59:59 is outside | Synthetic `datetime.time(5, 59, 59)` test | **PASS** | Evaluates to `False` |
| Time window boundary: 11:00:01 is outside | Synthetic `datetime.time(11, 0, 1)` test | **PASS** | Evaluates to `False` |
| Zero-byte file synchronization | Synthetic 0-byte file test | **PASS** | Synchronized cleanly |
| Zero-byte target corruption auto-fix | Target truncated to 0-bytes | **PASS** | Fast-path size check detected & repaired |
| 50MB file streaming SHA-256 | Synthetic 50MB payload test | **PASS** | Streamed in 0.068s with bounded RAM |
| Deep nesting (12 levels) & special characters | Synthetic nested unicode & symbol paths | **PASS** | Handled cleanly |
| State file corruption recovery | Corrupted/truncated/0-byte JSON | **PASS** | Gracefully resets to `{}` and heals |
| Task Scheduler XML Schema | ElementTree parse of `task_scheduler_config.xml` | **PASS** | `<LogonTrigger>`, `<Delay>PT6M</Delay>`, batteries enabled |
| PowerShell script status | `setup_task_scheduler.ps1 -Status` | **PASS** | Ran without elevation, reported unregistered cleanly |

---

## 4. Adversarial Stress-Test Matrix

| Stress-Test Scenario | Input / Attack Vector | Predicted / Desired Behavior | Observed Actual Behavior | Status |
|---|---|---|---|---|
| **Boundary Time 06:00:00** | Exactly 06:00:00 AM | Inside window (`True`) | Inside window (`True`) | **PASS** |
| **Boundary Time 11:00:00** | Exactly 11:00:00 AM | Inside window (`True`) | Inside window (`True`) | **PASS** |
| **Boundary Time 05:59:59** | 1 sec before window | Outside window (`False`) | Outside window (`False`) | **PASS** |
| **Boundary Time 11:00:01** | 1 sec after window | Outside window (`False`) | Outside window (`False`) | **PASS** |
| **Overnight Time Window** | Window 22:00 to 04:00 at 23:00 | Inside window (`True`) | Outside window (`False`) | **FAIL** (Minor Finding 6) |
| **Read-Only Target File** | Target has `attrib +r` set | Overwrite/Auto-fix succeeds | `[WinError 5] Access is denied` | **FAIL** (Major Finding 3) |
| **Target Sync Error Handling** | Target auto-fix fails with error | Report error, don't record SUCCESS | Swallowed with `pass`, records `SUCCESS` | **FAIL** (Critical Finding 2) |
| **Locked Target File** | Target opened exclusively by another process | Safe error recording & retry | Catches error cleanly, but zero retries | **PARTIAL** (Major Finding 4) |
| **Privacy Filter: Standard** | `Passport.pdf`, `Resume.pdf`, `leads.csv` | Blocked (`DENY_PRIVACY`) | Blocked (`DENY_PRIVACY`) | **PASS** |
| **Privacy Filter: Weights Subfolder** | `weights\Tax_Return_2025.pdf`, `weights\Bank_Statement.pdf` | Blocked / Ignored | **LEAKED** into `docs\pdfs\` | **FAIL** (Critical Finding 1) |
| **Privacy Filter: Identity Docs** | `cvc\Aadhaar_Card.pdf`, `combo\medical_records.pdf` | Blocked / Ignored | **LEAKED** into `docs\pdfs\` | **FAIL** (Critical Finding 1) |
| **Privacy Filter: Confidential Data** | `weights\Confidential_Clients.csv` | Blocked / Ignored | **LEAKED** into `results\recovered\` | **FAIL** (Critical Finding 1) |
| **Concurrent State Writes** | Two processes writing state at same time | Independent safe writes | Collides on static `.tmp` file (`WinError 32`) | **FAIL** (Minor Finding 5) |
| **Corrupted State File** | 0-byte or truncated JSON state | Load fallback `{}` and heal | Fallback `{}` loaded, state heals | **PASS** |
| **Corrupted Ledger File** | Invalid JSON in recovery ledger | Fallback `[]` and heal | Fallback `[]` loaded, ledger heals | **PASS** |

---

## 5. Required Remediations for Approval

Before approving, `worker_m2_g15` (or remediation worker) must address:
1. **Fix Privacy Leak (Finding 1):**
   - Expand `PERSONAL_DENY_REGEX` to cover `tax`, `statement`, `bank`, `salary`, `payslip`, `medical`, `prescription`, `aadhaar`, `pan`, `ssn`, `license`, `id_card`, `curriculum_vitae`, `confidential`, `private`, `secret`, `budget`.
   - In `is_chakramodel_asset`, remove folder-level matching of generic terms like `"weights"`; require the filename itself to indicate a model asset or use strict path prefixes.
   - Restrict `.pdf` and `.csv` catch-all destinations to only files with explicit ChakraModel keyword indicators in their filename.
2. **Fix Error Swallowing & Daily Guard Status (Finding 2):**
   - In `main()`, set `success = False` if any active target results contain errors or failed status. Do not record `SUCCESS` or exit `0` when auto-fix fails.
3. **Fix Windows Read-Only Target Overwrites (Finding 3):**
   - In `atomic_write_replace`, clear `stat.S_IWRITE` on `tgt_path` before calling `os.replace`.
4. **Add Retry Loop for Transient Locks (Finding 4):**
   - Implement a 3-attempt retry loop with backoff in `atomic_write_replace`.
5. **Use Unique Tempfile in State Manager (Finding 5):**
   - Use UUID in temporary filename for `backup_sync_state.json`.
6. **Add Regression Tests:**
   - Add automated test cases in `test_backup_sync.py` verifying read-only target auto-fix, privacy filtering on subdirectories named `weights/`, and non-success status propagation on target errors.
