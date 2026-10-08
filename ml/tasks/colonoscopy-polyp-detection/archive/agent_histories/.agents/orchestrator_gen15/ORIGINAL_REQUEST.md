# Original User Request

## 2026-09-15T23:05:56Z

Verify that multiple backup directories exactly match the contents of `M:\chakramodel`, ensuring zero tolerance for missed or corrupted files, and create a scheduled daily sync mechanism.

Working directory: M:\chakramodel
Integrity mode: development

## Requirements

### R1. Target Directories Verification and Auto-Fix
Verify the following directories against `M:\chakramodel`:
- `D:\15-0926chakramodel versioncontrol\chakramodel`
- `I:\My Drive\chakramodel & pro (16-9-26_)`
- `M:\chakramodel_audit`
- `M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909`
- `M:\chakramodelpro`

Verification must use cryptographic hashing (e.g., SHA-256) for zero tolerance to corruption. Any missing or corrupted files in the target backup directories must be automatically copied/overwritten from `M:\chakramodel` to fix them immediately.

### R2. Recovering Files from Downloads
Scan the user's local `Downloads` (e.g. `C:\Users\imgk3\Downloads`) and `J:\My Drive\downloads` directories for scattered Chakramodel-related files (e.g., model weight zips). Recover these files one by one and integrate them back into the proper locations in `M:\chakramodel`.

### R3. Scheduled Daily Sync
Write a Python script that performs this synchronization and verification. Configure it to run daily on Windows startup between 6 AM and 11 AM, executing exactly 6 minutes after the laptop boots up.

## Acceptance Criteria

### Verification and Auto-Fix
- [ ] A programmatic test demonstrates that modifying a file in a backup directory causes the script to detect the corruption via hash mismatch and restore it from `M:\chakramodel`.
- [ ] Deleting a file in a backup directory results in the script automatically copying it back from `M:\chakramodel`.

### Downloads Recovery
- [ ] A programmatic test demonstrates that a mock weights zip placed in `Downloads` is correctly identified and recovered into `M:\chakramodel`.

### Scheduled Sync
- [ ] The Python sync script can be executed standalone without errors.
- [ ] A Windows Task Scheduler configuration (e.g., XML or PowerShell setup script) is generated that triggers the Python script at startup/logon, restricted to the 6 AM - 11 AM time window, with a 6-minute execution delay.

### Rules & Workflow
- Maintain plan.md, progress.md, and BRIEFING.md in M:\chakramodel\.agents\orchestrator_gen15\.
- Do not write source code yourself; orchestrate specialist subagents (explorers, workers, reviewers, challengers).
- Ensure zero tolerance for corruption using cryptographic hashing (SHA-256).
- When all milestones are verified with passing tests, send your victory report to Sentinel via send_message.
