# Plan — Orchestrator Gen15
# Project: ChakraModel Backup Synchronization, Recovery & Daily Scheduling

## Architecture Overview
The system provides zero-tolerance backup synchronization and recovery for `M:\chakramodel`:
1. **Target Backup Directories Verification & Auto-Fix**:
   - Compares 5 target directories:
     * `D:\15-0926chakramodel versioncontrol\chakramodel`
     * `I:\My Drive\chakramodel & pro (16-9-26_)`
     * `M:\chakramodel_audit`
     * `M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909`
     * `M:\chakramodelpro`
   - Uses cryptographic hashing (SHA-256 with 64KB/1MB chunking) for zero-tolerance corruption detection.
   - Automatically copies missing files and overwrites corrupted files from `M:\chakramodel` to target backup directories immediately.
2. **Downloads Recovery Engine**:
   - Scans `C:\Users\imgk3\Downloads` and `J:\My Drive\downloads` for Chakramodel-related files (e.g. `*.zip`, `*.pth`, `*.pt`, `*.ipynb`, `*.csv`).
   - Identifies candidate files and recovers them into designated locations in `M:\chakramodel`.
3. **Scheduled Daily Sync Engine**:
   - Executable standalone Python script `scripts/backup_sync.py`.
   - Windows Task Scheduler XML and setup script (`scripts/setup_task_scheduler.ps1`) executing on startup/logon with a 6-minute delay (`PT6M`) restricted to the 6 AM - 11 AM time window.

---

## Milestones Decomposition
| # | Milestone | Scope | Dependencies | Status |
|---|-----------|-------|--------------|--------|
| 1 | M1: System Exploration & Design | Audit target paths, downloads directories, Task Scheduler capabilities, and define detailed technical specifications | None | IN_PROGRESS |
| 2 | M2: Core Implementation | Implement `scripts/backup_sync.py`, CLI flags, Task Scheduler XML/PowerShell scripts | M1 | PENDING |
| 3 | M3: Adversarial Verification & Acceptance Tests | Create programmatic tests in `tests/test_backup_sync.py` verifying corruption fix, deletion restore, mock weights zip recovery, standalone execution, and scheduler config | M2 | PENDING |
| 4 | M4: Forensic Integrity Audit & Sentinel Delivery | Independent integrity audit (zero mock/facade implementations) and delivery of victory report to Sentinel | M3 | PENDING |

---

## Interface Contracts & File Layout
### Files to Create:
- `scripts/backup_sync.py`: Main standalone Python script supporting:
  * `--verify-and-sync`: verifies all 5 targets against `M:\chakramodel`, auto-restores missing/corrupted files using SHA-256.
  * `--recover-downloads`: scans `Downloads` and `J:\My Drive\downloads`, extracts/recovers Chakramodel files.
  * `--check-time-window`: checks if current time is between 6 AM and 11 AM (if run as startup task).
  * `--all`: runs full workflow (time check if startup, sync targets, recover downloads).
- `scripts/setup_task_scheduler.ps1`: PowerShell script to register the Windows Scheduled Task using `Register-ScheduledTask` or `schtasks.exe`.
- `scripts/task_scheduler_config.xml`: Windows Task Scheduler task XML with logon/boot trigger, 6-minute delay, and time window constraints.
- `tests/test_backup_sync.py`: Unit and E2E adversarial test suite covering all Acceptance Criteria.

---

## Verification Criteria
- [ ] Modifying a file in a backup directory causes hash mismatch detection and auto-restoration from `M:\chakramodel`.
- [ ] Deleting a file in a backup directory causes missing file detection and auto-copy from `M:\chakramodel`.
- [ ] Mock weights zip placed in Downloads is correctly detected and recovered into `M:\chakramodel`.
- [ ] Python sync script executes standalone with zero errors (exit code 0).
- [ ] Windows Task Scheduler configuration triggers script on startup/logon with 6-minute delay restricted to 6 AM - 11 AM.
- [ ] Forensic Auditor validates authentic implementation with zero hardcoding or evasion.
