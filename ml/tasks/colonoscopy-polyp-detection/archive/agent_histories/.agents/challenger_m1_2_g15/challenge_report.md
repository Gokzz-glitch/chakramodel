# Empirical Challenge & Adversarial Stress Report

**Agent:** `challenger_m1_2_g15`  
**Parent:** `orchestrator_gen15` (`e9d0dc6b-8d4f-4c1a-924e-6152f16b1473`)  
**Scope:** Acceptance Criteria C, D, & E (Downloads Recovery, Standalone Execution, Scheduled Sync & Task Scheduler)  
**Date:** 2026-09-16  

---

## Challenge Summary

**Overall risk assessment:** **MEDIUM-HIGH**  
While the core architecture meets Acceptance Criteria C, D, and E under scoped unit-testing and standard execution paths, empirical stress-testing surfaced three critical vulnerabilities, false-positive test artifacts, and operational hazards:

1. **Privacy Deny-Filter Delimiter Gap (Vulnerability - HIGH):** `PERSONAL_DENY_REGEX` uses `mess\s*fees`, matching only spaces or direct concatenation. Filenames with underscores (e.g. `kvasir_mess_fees.pdf`) bypass the filter and are classified as recoverable repository deliverables (`PDF_DOC`), directly violating privacy guarantees.
2. **False-Positive Test Artifact & Unindexed Stub Behavior (Bug/Test Flaw - MEDIUM):** `model_output.zip` does not contain any ChakraModel indicator keyword. In real environments (`C:\Users\imgk3\Downloads\model_output.zip`), `is_chakramodel_asset()` evaluates to `False` and skips it as `unrelated_ignored`. The worker's acceptance test only passed because the test method name contained `weights`, polluting pytest's temporary folder path (`path_lower`). Furthermore, if a 49-byte stub archive does match an indicator but the destination does not yet exist, stub protection does not trigger and the empty file is written to the repository.
3. **Full Run I/O Saturation & Cloud Mount Freeze (Operational Hazard - HIGH):** Running `backup_sync.py --all --dry-run` on the default live environment attempts to walk 65,362 files (55 GB) and compute streaming SHA-256 digests of all size-matched files across both local drives (`M:`, `D:`) and cloud mounts (`I:` on Google Drive). For a single 13 GB archive (`CVC_ClinicVideoDB_Kaggle.zip`), this requires reading 26 GB from disk. Daily scheduled startup runs via Task Scheduler will saturate disk and network I/O, risking timeout termination under `<ExecutionTimeLimit>PT2H</ExecutionTimeLimit>`.

---

## Challenges & Confirmed Vulnerabilities

### [High] Challenge 1: Privacy Deny-Filter Underscore Delimiter Bypass

- **Assumption challenged:** The Tier 1 privacy deny-filter blocks 100% of sensitive documents including fee receipts, resumes, and personal documents even when combined with ChakraModel indicators.
- **Attack scenario:** A user downloads a college hostel mess fee receipt named `kvasir_mess_fees.pdf` into `Downloads`.
  - In `backup_sync.py` line 344:
    ```python
    PERSONAL_DENY_REGEX = re.compile(
        r"(passport|resume|profile\.pdf$|lor[-_]nit|receipt|payment|booking|"
        r"mess\s*fees|bill|\.ics$|leads?|corporate_leads|researcher_leads|"
        ...
    )
    ```
  - Because `\s` only matches whitespace (` `, `\t`, `\n`) and not `_` or `-`, `PERSONAL_DENY_REGEX.search("kvasir_mess_fees.pdf")` returns `None` (`is_personal_or_denied == False`).
  - Next, `is_chakramodel_asset("kvasir_mess_fees.pdf")` detects `"kvasir"`, returning `True`.
  - `classify_download_file()` returns `('CHAKRAMODEL_ASSET', 'PDF_DOC', WindowsPath('M:/chakramodel/docs/pdfs/kvasir_mess_fees.pdf'))`.
- **Blast radius:** Personal financial/student documents containing sensitive personal identity or fee structures are copied straight into the public/shared project repository under `docs/pdfs/`.
- **Empirical verification:** Verified via `test_empirical_vulnerability_mess_fees_regex_gap` in `tests/test_challenger_m1_2_empirical.py`.
- **Mitigation:** Update regex from `mess\s*fees` to `mess[\s_\-]*fees` or generic `(fee|fees|mess)` deny tokens.

---

### [Medium] Challenge 2: Test Artifact Poisoning & Stub Protection Gap

- **Assumption challenged:** `model_output.zip` placed in Downloads is protected by 49-byte stub logic, preventing corrupt stub archives from overwriting valid deliverables.
- **Attack scenario:**
  1. *Test Pollution:* In `test_backup_sync.py`, worker_m2_g15 wrote:
     ```python
     def test_mock_weights_recovery_and_privacy_filter(self, tmp_path):
         ...
         stub_zip = mock_downloads / "model_output.zip"
     ```
     `is_chakramodel_asset()` checks `any(ind in name_lower or ind in path_lower for ind in CHAKRA_INDICATORS)`. Pytest created the temporary folder named `.../test_mock_weights_recovery_and_privacy_filter0/`. Because `"weights"` was in the test method name, `path_lower` contained `"weights"`, causing `is_chakramodel_asset()` to return `True` by accident.
  2. *Real World Behavior:* In `C:\Users\imgk3\Downloads\model_output.zip`, `is_chakramodel_asset()` returns `False`. The file is ignored under `unrelated_ignored` without ever reaching `blocked_stubs`.
  3. *Missing Destination Gap:* In `recover_file()`, line 511 checks:
     ```python
     if dest_file.exists():
         dest_size = dest_file.stat().st_size
         if src_size < 100 and dest_size >= 100:
             return "BLOCKED_STUB_OVERWRITE"
     ```
     If `dest_file` does NOT already exist in `model_root`, stub protection does not execute. A 49-byte empty zip archive (e.g. `chakra_model_output.zip`) will be written directly into `results/archives/`.
- **Blast radius:** False sense of test validity in worker test suite; potential ingestion of empty stub files when destination is fresh.
- **Empirical verification:** Verified via `test_empirical_finding_model_output_zip_without_indicator` in `tests/test_challenger_m1_2_empirical.py`.
- **Mitigation:**
  - Add `"model_output"` to `CHAKRA_INDICATORS` or check `name_lower` strictly rather than parent `path_lower`.
  - Add unconditional stub rejection: `if is_archive and src_size < 100: return "BLOCKED_STUB"`.

---

### [High] Challenge 3: Streaming SHA-256 I/O Saturation on Large Production Targets

- **Assumption challenged:** `python backup_sync.py --all --dry-run` and daily scheduled startup tasks complete quickly and safely without system degradation.
- **Attack scenario:**
  - The repository `M:\chakramodel` contains 65,362 files totaling 54.95 GB, including large video datasets and weight checkpoints:
    * `CVC_ClinicVideoDB_Kaggle.zip`: 13.0 GB
    * `video_testing\polyp\videos with polyps-20260804T054937Z-1-001.zip`: 1.99 GB
    * `data\datasets_archive\colon_cancer_dataset.zip`: 1.43 GB
    * Checkpoints (`.pth`): 1.18 GB each
  - In `verify_and_sync_target()`, lines 280-281:
    ```python
    src_hash = stream_sha256(src_file, chunk_size=chunk_size)
    tgt_hash = stream_sha256(tgt_file, chunk_size=chunk_size)
    ```
  - Unlike `recover_file()` (which has `if dry_run and src_size > 500 * 1024 * 1024: is_ident = True`), `verify_and_sync_target()` computes SHA-256 on EVERY file whose size matches, even in `--dry-run` mode.
  - When executed, `PID 14424` read 21.4 GB in 3.5 minutes (~38 MB/s disk transfer) on the first 13 GB archive alone.
  - Target 2 is `I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel` on Google Drive. Streaming 55 GB over Google Drive across the network would take 1 to 3 hours, freezing cloud syncing and tripping the Task Scheduler 2-hour timeout (`<ExecutionTimeLimit>PT2H</ExecutionTimeLimit>`).
- **Blast radius:** Startup tasks scheduled 6 minutes after boot consume 100% disk read bandwidth and saturate network streaming, degrading user system responsiveness.
- **Empirical verification:** Background task `task-56` was monitored reading >21 GB across `M:` and `D:` before manual termination to prevent disk pegging.
- **Mitigation:**
  - Add size-matched dry-run bypass to `verify_and_sync_target()`: `if dry_run: stats["files_verified_ok"] += 1; continue`.
  - For files > 100 MB on cloud mounts, match on mtime + size before triggering full streaming SHA-256.

---

## Stress Test Results

Test harness: `M:\chakramodel\tests\test_challenger_m1_2_empirical.py` (17 tests executed)

| Scenario | Expected Behavior | Actual Behavior | Verdict |
|---|---|---|---|
| **Weights Recovery with Integrity** | `mock_weights.zip` with `.pth`/`.pt` validated via CRC testzip() and recovered to `weights/` | Verified archive integrity, recovered to `weights/mock_weights.zip`, SHA-256 matched | **PASS** |
| **Corrupted Zip (Truncated)** | Truncated zip rejected, skipped, logged in ledger | `validate_archive_integrity()` returned False, 0 bytes written to destination, ledger entry added | **PASS** |
| **Corrupted Zip (Bad CRC)** | Zip with corrupted member payload rejected via `testzip()` | Caught by `testzip()`, skipped, ledger recorded `SKIPPED_CORRUPT_ARCHIVE` | **PASS** |
| **49-Byte Stub (Existing File)** | Stub blocked from overwriting healthy archive | Overwrite blocked, healthy archive unchanged, recorded `BLOCKED_STUB_OVERWRITE` | **PASS** |
| **49-Byte Stub (Missing Keyword)** | Verify `model_output.zip` behavior in clean path | `is_chakramodel_asset` returned False; ignored as unrelated; confirmed test false-positive artifact | **PASS (Finding)** |
| **Privacy Filter (Standard Files)** | 100% denial of passports, resumes, leads, receipts, exes | 16/16 personal files blocked (`privacy_denied=16`), 0 recovered | **PASS** |
| **Privacy Filter (Disguised Names)** | Block disguised files (`chakra_passport.pdf`, `polyp_resume.pdf`) | 5/5 disguised personal files blocked by Tier 1 deny patterns | **PASS** |
| **Privacy Filter (Regex Gap)** | Test `kvasir_mess_fees.pdf` with underscore | Bypassed `mess\s*fees` regex; classified as `CHAKRAMODEL_ASSET`; leaked to `docs/pdfs/` | **FAIL (Vulnerability Confirmed)** |
| **Raw Checkpoints Recovery** | Standalone `.pth`/`.pt` files in downloads recovered | `yolov8n_polyp_best.pt` -> `weights/yolo/`, `chakra_transformer_best.pth` -> `weights/checkpoints/` | **PASS** |
| **Standalone CLI (Isolated)** | `backup_sync.py --all --dry-run` executes with code 0 | Exited code 0, state recorded SUCCESS | **PASS** |
| **Standalone CLI (--help)** | Help output with usage and all flags | Exited code 0, complete parameter documentation | **PASS** |
| **Standalone CLI (Invalid Args)** | Invalid arguments return non-zero exit code | Argparse returned exit code 2 on unknown flags | **PASS** |
| **Task Scheduler XML Schema** | Valid XML with `LogonTrigger`, `Delay PT6M`, `InteractiveToken`, battery settings | Full XML schema validated via `xml.etree.ElementTree` | **PASS** |
| **Time Window Boundary Oracle** | Exhaustive check of 06:00 to 11:00 AM window | 10/10 boundary timestamps evaluated accurately | **PASS** |
| **Startup Task Outside Window** | `--startup-task` outside 06:00-11:00 exits code 0 | Clean exit code 0 returned, sync skipped | **PASS** |
| **Daily Execution Guard (Duplicate)** | Second run on same day skipped with code 0 | Skipped duplicate run, clean exit 0 | **PASS** |
| **Daily Guard (Retry on Failure)** | Run after previous FAILED run executes retry | Did not skip, re-executed sync and updated state to SUCCESS | **PASS** |
| **Daily Guard (--force Override)** | `--force` overrides time window and duplicate guard | Ignored off-window time and previous run; forced sync execution | **PASS** |

---

## Captured Execution Logs

### 1. Pytest Empirical Challenger Test Execution
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\imgk3\AppData\Local\Programs\Python\Python311\python.exe
cachedir: .pytest_cache
rootdir: M:\chakramodel
plugins: anyio-4.14.2
collecting ... collected 17 items

tests/test_challenger_m1_2_empirical.py::TestDownloadsRecoveryEmpirical::test_valid_weights_recovery_with_integrity PASSED [  5%]
tests/test_challenger_m1_2_empirical.py::TestDownloadsRecoveryEmpirical::test_corrupted_zip_safe_rejection PASSED [ 11%]
tests/test_challenger_m1_2_empirical.py::TestDownloadsRecoveryEmpirical::test_49_byte_stub_protection_with_indicator_over_existing_target PASSED [ 17%]
tests/test_challenger_m1_2_empirical.py::TestDownloadsRecoveryEmpirical::test_empirical_finding_model_output_zip_without_indicator PASSED [ 23%]
tests/test_challenger_m1_2_empirical.py::TestDownloadsRecoveryEmpirical::test_personal_files_privacy_filter_stress PASSED [ 29%]
tests/test_challenger_m1_2_empirical.py::TestDownloadsRecoveryEmpirical::test_adversarial_disguised_personal_files_stress PASSED [ 35%]
tests/test_challenger_m1_2_empirical.py::TestDownloadsRecoveryEmpirical::test_empirical_vulnerability_mess_fees_regex_gap PASSED [ 41%]
tests/test_challenger_m1_2_empirical.py::TestDownloadsRecoveryEmpirical::test_raw_pth_and_pt_standalone_recovery PASSED [ 47%]
tests/test_challenger_m1_2_empirical.py::TestStandaloneExecutionEmpirical::test_standalone_cli_dry_run_isolated PASSED [ 52%]
tests/test_challenger_m1_2_empirical.py::TestStandaloneExecutionEmpirical::test_cli_help_flag PASSED [ 58%]
tests/test_challenger_m1_2_empirical.py::TestStandaloneExecutionEmpirical::test_cli_invalid_arguments_returns_error PASSED [ 64%]
tests/test_challenger_m1_2_empirical.py::TestScheduledSyncAndTaskSchedulerEmpirical::test_task_scheduler_xml_schema_conformance PASSED [ 70%]
tests/test_challenger_m1_2_empirical.py::TestScheduledSyncAndTaskSchedulerEmpirical::test_time_window_boundary_oracle PASSED [ 76%]
tests/test_challenger_m1_2_empirical.py::TestScheduledSyncAndTaskSchedulerEmpirical::test_startup_task_cli_clean_exit_0_outside_window PASSED [ 82%]
tests/test_challenger_m1_2_empirical.py::TestScheduledSyncAndTaskSchedulerEmpirical::test_daily_execution_guard_duplicate_skip PASSED [ 88%]
tests/test_challenger_m1_2_empirical.py::TestScheduledSyncAndTaskSchedulerEmpirical::test_daily_guard_retries_on_previous_failure PASSED [ 94%]
tests/test_challenger_m1_2_empirical.py::TestScheduledSyncAndTaskSchedulerEmpirical::test_startup_task_force_flag_overrides_window_and_guard PASSED [100%]

============================= 17 passed in 1.32s ==============================
```

### 2. Standalone Startup Task Window Check (Verbatim Live CLI)
```
[2026-09-16 04:49:26] [INFO] [backup_sync] ============================================================
[2026-09-16 04:49:26] [INFO] [backup_sync] ChakraModel Backup Synchronization & Recovery System Initialized
[2026-09-16 04:49:26] [INFO] [backup_sync] Source Directory: M:\chakramodel
[2026-09-16 04:49:26] [INFO] [backup_sync] Outside scheduled window (06:00-11:00), skipping. Current time: 04:49:26.
[2026-09-16 04:49:26] [INFO] [backup_sync] Clean exit code 0 returned for scheduled task outside active window.
Exit Code: 0
```

### 3. Task Scheduler XML Direct Validation
```
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT6M</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>python.exe</Command>
      <Arguments>M:\chakramodel\scripts\backup_sync.py --startup-task</Arguments>
      <WorkingDirectory>M:\chakramodel</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
```

---

## Unchallenged Areas

- **Actual Task Registration in Windows Task Scheduler:** The Task Scheduler XML and PowerShell script were validated programmatically; full system-level registration (`schtasks /Create`) was not committed directly to `C:\Windows\System32\Tasks` to avoid modifying host OS registry/services without interactive Administrator elevation prompt.
