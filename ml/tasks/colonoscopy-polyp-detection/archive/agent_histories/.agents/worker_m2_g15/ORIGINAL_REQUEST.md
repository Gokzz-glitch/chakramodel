## 2026-09-16T04:45:02Z

You are worker_m2_g15.
Your working directory is M:\chakramodel\.agents\worker_m2_g15\
Your parent is orchestrator_gen15 (e9d0dc6b-8d4f-4c1a-924e-6152f16b1473).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mission:
Implement the complete, production-grade Synchronization, Recovery, and Scheduling system for ChakraModel according to the authoritative requirements and the findings of Explorers 1, 2, and 3.

Inputs to read first:
- `M:\chakramodel\.agents\explorer_m1_1_g15\handoff.md` and `analysis.md` (Target Directories & SHA-256 Architecture)
- `M:\chakramodel\.agents\explorer_m1_2_g15\handoff.md` and `analysis.md` (Downloads Recovery Architecture)
- `M:\chakramodel\.agents\explorer_m1_3_g15\handoff.md` and `analysis.md` (Task Scheduler & Startup Trigger Architecture)
- Prototypes in `M:\chakramodel\.agents\explorer_m1_3_g15\`:
  * `proposed_task_scheduler_config.xml`
  * `proposed_setup_task_scheduler.ps1`
  * `proposed_backup_sync_cli.py`

Deliverables to produce:
1. `M:\chakramodel\scripts\backup_sync.py`:
   - Standalone executable Python script.
   - Requirement 1: Verification and Auto-Fix
     * Targets to verify against `M:\chakramodel`:
       `D:\15-0926chakramodel versioncontrol\chakramodel`
       `I:\My Drive\chakramodel & pro (16-9-26_)`
       `M:\chakramodel_audit`
       `M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909`
       `M:\chakramodelpro`
     * Target directory handling per Explorer 1: note that `I:\My Drive\chakramodel & pro (16-9-26_)` contains child `chakramodel`, and `D:\15-0926chakramodel versioncontrol\chakramodel` has an accidental nested folder. Support syncing to target mirror directories cleanly.
     * Zero-tolerance SHA-256 chunked streaming (e.g. 1MB buffer) for high throughput without memory bloat.
     * Pre-check file size mismatch ($O(1)$) before hashing.
     * Auto-fix: if target file is missing, copy from source; if target file is corrupted (hash mismatch), overwrite from source.
     * Atomic write replacement: write to `.tmp_autofix`, verify hash, then atomic rename.
     * Default exclusions: `.venv`, `__pycache__`, `.pytest_cache`, `.agents`, `.claude` (configurable via CLI flags `--include-venv`, `--include-git`, etc.).
   - Requirement 2: Recovering Files from Downloads
     * Scans `C:\Users\imgk3\Downloads` and `J:\My Drive\downloads`.
     * Identifies Chakramodel files (weights, zips, checkpoints, evaluation notebooks, provenance notebooks).
     * Strictly enforces privacy deny-filter (passports, resumes, leads) from Explorer 2.
     * Protects against 49-byte stub overwrites and checks zip archive integrity via `testzip()`.
     * Recovers identified files into appropriate destinations in `M:\chakramodel` (`weights/`, `notebooks/provenance/`, `notebooks/evaluation/`, etc.).
     * Handles mock weights zip testing cleanly.
   - Requirement 3: Scheduled Daily Sync
     * `--startup-task`: checks if current local time is between 6 AM and 11 AM (`06:00 <= now <= 11:00`). If outside window, logs skip reason and cleanly exits with code 0.
     * Daily execution guard: state file (`logs/backup_sync_state.json`) prevents redundant duplicate runs on same day if already succeeded, while allowing retries if failed or if `--force` is given.
     * CLI argument parsing:
       `--all` (default if no args): runs verification & sync and downloads recovery.
       `--verify-and-sync`: sync target directories.
       `--recover-downloads`: run downloads recovery.
       `--startup-task`: startup mode with time window check and daily guard.
       `--check-window`: utility to check time window.
       `--dry-run`: report changes without touching disk.
       `--source-dir`: specify source (defaults to M:\chakramodel).
       `--target-dirs`: specify target directories (defaults to 5 targets).
       `--downloads-dirs`: specify download locations to scan.

2. `M:\chakramodel\scripts\task_scheduler_config.xml`:
   - Production Windows Task Scheduler XML.
   - Trigger: `<LogonTrigger><Delay>PT6M</Delay></LogonTrigger>`.
   - Action: `python.exe M:\chakramodel\scripts\backup_sync.py --startup-task`.
   - Security: `LeastPrivilege` interactive user token.
   - Battery: `DisallowStartIfOnBatteries = false`, `StopIfGoingOnBatteries = false`.

3. `M:\chakramodel\scripts\setup_task_scheduler.ps1`:
   - PowerShell setup script with `-Register`, `-Unregister`, `-Status`, `-TestRun` operations.
   - Handles self-elevation if run as non-admin, validates XML syntax, registers task `ChakraModelDailySync`.

4. Comprehensive Acceptance Test Suite `M:\chakramodel\tests\test_backup_sync.py`:
   - Must cover all 4 Acceptance Criteria from ORIGINAL_REQUEST:
     * Test A (Corruption Auto-Fix): Programmatic test demonstrating that modifying a file in a backup directory causes the script to detect corruption via SHA-256 hash mismatch and restore it from source.
     * Test B (Deletion Auto-Fix): Programmatic test demonstrating that deleting a file in a backup directory causes the script to detect missing file and restore it from source.
     * Test C (Downloads Mock Weights Recovery): Programmatic test demonstrating that a mock weights zip placed in a mock Downloads directory is correctly identified and recovered into `weights/` in the model root.
     * Test D (Standalone Execution): Test verifying `scripts/backup_sync.py` can be executed standalone without errors (exit code 0).
     * Test E (Task Scheduler Verification): Test verifying the XML task definition contains `<LogonTrigger>`, `<Delay>PT6M</Delay>`, and testing `--startup-task` time window enforcement (exit 0 outside window, normal execution inside window).
   - Run the test suite via `pytest M:\chakramodel\tests\test_backup_sync.py` and ensure 100% tests pass!

Output:
Update your progress.md regularly. Write a detailed handoff report in `M:\chakramodel\.agents\worker_m2_g15\handoff.md` showing all files created, tests executed, commands run, and test outputs. When complete, send a message to orchestrator parent.
