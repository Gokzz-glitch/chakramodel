## 2026-09-10T02:44:27Z

Implement the 14 automated adversarial detection scripts in M:\chakramodel\tests\adversarial\ and a master runner M:\chakramodel\tests\adversarial\run_all_adversarial_tests.py.

REQUIREMENTS:
1. Directory: Create directory M:\chakramodel\tests\adversarial\ if it does not exist.
2. 14 Test Scripts:
   - tests/adversarial/test_flaw_01_no_skip_connections.py
   - tests/adversarial/test_flaw_02_dead_imagenet_head.py
   - tests/adversarial/test_flaw_03_dead_code.py
   - tests/adversarial/test_flaw_04_oom_fallback.py
   - tests/adversarial/test_flaw_05_tta_enabled_by_default.py
   - tests/adversarial/test_flaw_06_unguarded_torch_load.py
   - tests/adversarial/test_flaw_07_strict_false_state_dict.py
   - tests/adversarial/test_flaw_08_conformal_formula_sign.py
   - tests/adversarial/test_flaw_09_mc_dropout_collapse.py
   - tests/adversarial/test_flaw_10_contradictory_calibration_qhat.py
   - tests/adversarial/test_flaw_11_unpinned_dependencies.py
   - tests/adversarial/test_flaw_12_ci_lacking_src_coverage.py
   - tests/adversarial/test_flaw_13_unrecoverable_training_batches.py
   - tests/adversarial/test_flaw_14_headline_metric_artifact_absence.py

3. Script Specifications:
   - Each script must run standalone via `python tests/adversarial/test_flaw_XX_*.py`.
   - By default (no CLI arguments), each script targets the primary codebase M:\chakramodel and MUST EXIT 1 with a clear, descriptive error message exposing the flaw!
   - Each script must accept optional CLI arguments (e.g. `--target-file <path>` or appropriate target path argument), so that when run against an isolated patched copy or patched file, it verifies the fix and EXITS 0!
   - Use AST parsing, regex/code inspection, or runtime checks as designed by the explorers:
     * Consult M:\chakramodel\.agents\explorer_m1_1_g12\analysis.md (Flaws 1-5)
     * Consult M:\chakramodel\.agents\explorer_m1_2_g12\analysis.md and prototype scripts in M:\chakramodel\.agents\explorer_m1_2_g12\ (Flaws 6-10)
     * Consult M:\chakramodel\.agents\explorer_m1_3_g12\analysis.md (Flaws 11-14)
   - Ensure scripts do not perform network calls (we are offline / CODE_ONLY).

4. Master Runner:
   - M:\chakramodel\tests\adversarial\run_all_adversarial_tests.py:
     Executes all 14 tests against the current codebase, captures stdout/stderr and exit codes, verifies all 14 exit with code 1, and prints a structured summary table. Exits 0 if all 14 flaws were successfully detected (all 14 exit 1), or exits 1 if any script failed to expose the flaw.

5. Verification:
   - Run `python tests/adversarial/run_all_adversarial_tests.py` and confirm 14/14 scripts exit 1 (flaws detected).
   - Document the results in M:\chakramodel\.agents\worker_m2_adversarial\handoff.md.

PRIMARY SOURCE CODE FILES IN M:\chakramodel\ (outside tests/adversarial/) MUST REMAIN UNMODIFIED!
