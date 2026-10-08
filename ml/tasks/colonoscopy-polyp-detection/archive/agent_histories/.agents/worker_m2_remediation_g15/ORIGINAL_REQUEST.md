## 2026-09-15T23:30:25Z

You are worker_m2_remediation_g15.
Your working directory is M:\chakramodel\.agents\worker_m2_remediation_g15\
Your parent is orchestrator_gen15 (e9d0dc6b-8d4f-4c1a-924e-6152f16b1473).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mission:
Apply targeted hardening and remediation to `M:\chakramodel\scripts\backup_sync.py` and add regression tests to `M:\chakramodel\tests\test_backup_sync.py` based on the synthesized findings from Reviewer 2, Challenger 1, and Challenger 2:

Inputs to read:
- `M:\chakramodel\.agents\reviewer_m1_2_g15\review.md` (Findings 1 to 4)
- `M:\chakramodel\.agents\challenger_m1_1_g15\challenge_report.md` (Read-only target finding)
- `M:\chakramodel\.agents\challenger_m1_2_g15\challenge_report.md` (Privacy delimiter, stub, and dry-run findings)

Remediation Tasks in `M:\chakramodel\scripts\backup_sync.py`:
1. **Windows Read-Only Target Overwrite**:
   In `atomic_write_replace(src_path, tgt_path, ...)`:
   Before calling `os.replace(temp_path, tgt_path)`:
   If `tgt_path.exists()`:
   ```python
   try:
       os.chmod(tgt_path, stat.S_IWRITE)
   except OSError:
       pass
   ```
   Add a retry loop (3 attempts with 0.1s, 0.2s backoff) catching `PermissionError` / `OSError` (handling transient WinError 5 / WinError 32). Also clean up `temp_path` on final failure.

2. **Sync Error Recording & Daily Guard Suppression Fix**:
   In `main()` and wherever results are aggregated:
   If any active target (`LOCAL_MIRROR` or `CLOUD_CONTAINER`) has `status == "FAILED"` or `len(res.get("errors", [])) > 0`:
   Set `success = False`.
   Ensure `status = "SUCCESS" if success else "FAILED"`.
   Ensure `state_manager.record_run(status=status, ...)` records `"FAILED"` on error, and `main()` exits with code 1.
   (Note: if `--startup-task` is outside the 6:00-11:00 AM window, it exits 0 before syncing as designed).

3. **Privacy Filter Hardening & Path Matching Refinement**:
   - Expand `PERSONAL_DENY_REGEX` to cover all sensitive personal/financial keywords:
     `r"(passport|resume|curriculum[\s_\-]*vitae|\bcv\b|tax|itr|bank|statement|salary|payslip|pay[\s_\-]*slip|medical|prescription|aadhaar|pan|ssn|license|id[\s_\-]*card|voter|offer[\s_\-]*letter|appraisal|contract|confidential|private|secret|budget|lor[\-_]nit|receipt|payment|booking|mess[\s_\-]*fees?|bill|\.ics$|leads?|corporate_leads|researcher_leads|russia_moscow|priority_\d+.*\.csv$|\.(exe|msi|bat)$|eclipse|acer\s*care|chatgpt\s*installer|chromesetup|desktop\.ini$|screenshot|opus_keyword)"`
   - In `is_chakramodel_asset(filepath)`:
     Match `CHAKRA_INDICATORS` on `name_lower` (filename itself). If checking parent folder, only match if the parent directory is explicitly a known repository subtree (e.g. `CHAKRAMODEL_OM_4` or `chakramodel`), NOT just because a generic word like "weights" or "data" is in the path.
   - In `resolve_recovery_destination`: ensure generic non-model files (.pdf, .csv) require a ChakraModel indicator in their filename to prevent non-ChakraModel files from being copied.

4. **Stub Archive Handling Hardening**:
   - Unconditional stub rejection: If a file is an archive (`.zip`, `.tar.gz`) and `src_size < 100`, reject it immediately as `BLOCKED_STUB` (or `BLOCKED_STUB_OVERWRITE` if dest exists), even if destination does not exist yet.
   - Ensure `"model_output"` is included in indicator keywords.

5. **Dry-Run I/O Optimization**:
   In `verify_and_sync_target()`:
   If `dry_run` is True and `src_stat.st_size == tgt_stat.st_size`:
   Do not read gigabytes of data for full SHA-256 in dry-run mode if size matches (e.g. count as verified in dry-run, or only hash if `--force-hash`).

6. **Regression Tests in `tests/test_backup_sync.py`**:
   Add test methods to verify:
   - `test_read_only_target_overwrite_succeeds`: target marked `stat.S_IREAD` is successfully updated and restored.
   - `test_privacy_filter_blocks_expanded_keywords`: `Tax_Return.pdf`, `kvasir_mess_fees.pdf`, `Salary_Slip.pdf`, `Bank_Statement.pdf` are blocked even inside a folder named `weights`.
   - `test_stub_archive_rejected_without_existing_dest`: 49-byte stub archive is rejected even when destination file does not exist yet.
   - `test_sync_error_records_failure_in_state`: active target sync failure marks status `FAILED` in state file and returns exit code 1.

Execute all test suites:
- `pytest -v M:\chakramodel\tests\test_backup_sync.py`
- `pytest -v M:\chakramodel\tests\test_adversarial_criteria_ab.py`
- `pytest -v M:\chakramodel\tests\test_challenger_m1_2_empirical.py`
Ensure 100% tests pass! Document your work in `M:\chakramodel\.agents\worker_m2_remediation_g15\handoff.md`. When complete, send a message to orchestrator parent.
