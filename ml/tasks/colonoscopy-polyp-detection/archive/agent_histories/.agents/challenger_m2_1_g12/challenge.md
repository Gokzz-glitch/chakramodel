# Adversarial Challenge Report: Baseline Flaw Detection Suite (M2.1)

**Agent**: `challenger_m2_1_g12`  
**Date**: 2026-09-10  
**Target**: `tests/adversarial/` (14 automated flaw detection test scripts and master test runner)  
**Verdict**: **CONFIRMED** (Baseline flaw exposure verified 14/14; minor test harness edge cases surfaced)

---

## Challenge Summary

**Overall risk assessment**: **LOW**  
The 14 adversarial test scripts in `tests/adversarial/` deterministically and accurately detect all 14 baseline flaws when executed against the current repository state. Every single test script exits with **code 1** individually, and the master runner `run_all_adversarial_tests.py` exits with **code 0** reporting **14/14 flaws detected**.

Adversarial stress-testing of harness edge cases revealed 3 specific boundary behaviors regarding nonexistent target files in Flaws 09, 11, and 13. None of these invalidate baseline flaw detection, but they provide valuable actionable hardening recommendations for Phase 2/3 remediation verification.

---

## Empirical Verification Matrix (Baseline Run)

| Test Script | Flaw Target | Baseline Exit Code | Flaw Marker Present | Execution Time |
|---|---|:---:|:---:|:---:|
| `test_flaw_01_no_skip_connections.py` | No skip connections in decoder (16x16 px finest detail) | **1** | `[FAIL] FLAW 01 DETECTED` | 0.10s |
| `test_flaw_02_dead_imagenet_head.py` | Dead ImageNet head (1.025M dead parameters) | **1** | `[FAIL] FLAW 02 DETECTED` | 0.09s |
| `test_flaw_03_dead_code.py` | 75 lines uninstantiated dead code (BasicConv2d, RFB, RA) | **1** | `[FAIL] FLAW 03 DETECTED` | 0.10s |
| `test_flaw_04_oom_fallback.py` | `self.to('cpu')` device mutation in `forward()` OOM handler | **1** | `[FAIL] FLAW 04 DETECTED` | 0.08s |
| `test_flaw_05_tta_enabled_by_default.py` | TTA enabled by default (3x latency, conflated metrics) | **1** | `[FAIL] FLAW 05 DETECTED` | 0.10s |
| `test_flaw_06_unguarded_torch_load.py` | 31 unguarded `torch.load()` calls lacking `weights_only=True` | **1** | `[FAIL] FLAW 06 DETECTED` | 0.29s |
| `test_flaw_07_strict_false_state_dict.py` | Unchecked `strict=False` in `load_state_dict()` (silent 0/312 keys) | **1** | `[FAIL] FLAW 07 DETECTED` | 0.09s |
| `test_flaw_08_conformal_formula_sign.py` | Sign-flipped conformal scoring formula in inference vs calibration | **1** | `[FAIL] FLAW 08 DETECTED` | 0.08s |
| `test_flaw_09_mc_dropout_collapse.py` | MC-Dropout variance collapse (~2.85e-15 FP roundoff noise) | **1** | `[FAIL] FLAW 09 DETECTED` | 0.11s |
| `test_flaw_10_contradictory_calibration_qhat.py` | Contradictory calibration q_hat files (71,183x discrepancy) | **1** | `[FAIL] FLAW 10 DETECTED` | 0.10s |
| `test_flaw_11_unpinned_dependencies.py` | 26 unpinned floating `>=` dependencies in requirements manifests | **1** | `[FAIL] FLAW 11 DETECTED` | 0.10s |
| `test_flaw_12_ci_lacking_src_coverage.py` | CI workflow never lints or runs unit tests covering `src/` | **1** | `[FAIL] FLAW 12 DETECTED` | 0.18s |
| `test_flaw_13_unrecoverable_training_batches.py` | Unrecoverable training batch count (2376 tracked vs 330 expected) | **1** | `[FAIL] FLAW 13 DETECTED` | 4.24s |
| `test_flaw_14_headline_metric_artifact_absence.py` | Headline metric 0.7304 has no producing artifact (prose-only) | **1** | `[FAIL] FLAW 14 DETECTED` | 0.08s |
| **`run_all_adversarial_tests.py`** | **Master Runner (all 14 tests in sequence)** | **0** | **14 / 14 Flaws Detected** | **5.75s** |

---

## Adversarial Stress-Test Challenges

### [Medium] Challenge 1: Flaw 11 Inadvertently Passes with Exit 0 When Target File Is Missing

- **Assumption challenged**: Invoking `test_flaw_11_unpinned_dependencies.py` with an invalid or missing target file will fail cleanly with exit code 2.
- **Attack scenario**:
  ```powershell
  python tests/adversarial/test_flaw_11_unpinned_dependencies.py --target-file nonexistent.txt
  ```
  In `test_flaw_11_unpinned_dependencies.py`:
  ```python
  def check_flaw_11(req_files: list[Path]) -> int:
      for rf in req_files:
          if not rf.exists():
              print(f"  [WARN] File not found: {rf}")
              continue
          v = check_requirements_file(rf)
          all_violations.extend(v)
      if all_violations:
          return 1
      else:
          print("\n[PASS] Flaw 11 Resolved: All dependencies are strictly pinned...")
          return 0
  ```
  The missing file is skipped with a warning. Because `all_violations` is empty, the function declares `[PASS] Flaw 11 Resolved` and exits with **code 0**.
- **Blast radius**: If a CI runner or remediation script misconfigures the path to `requirements.txt`, the test will silently report that all dependencies are strictly pinned, masking unpinned dependencies.
- **Mitigation**: Add an existence check at the start of `check_flaw_11`: if none of `req_files` exist (or any explicitly requested target file is missing), print `[ERROR]` and return exit code 2.

---

### [Low] Challenge 2: Flaw 09 Conflates Missing Target File with Detected Flaw (Exit 1 vs Exit 2)

- **Assumption challenged**: Missing source files should cause configuration exit code 2.
- **Attack scenario**:
  ```powershell
  python tests/adversarial/test_flaw_09_mc_dropout_collapse.py --target-file nonexistent.py
  ```
  In `test_flaw_09_mc_dropout_collapse.py`:
  ```python
  def check_source_enable_mc_dropout(source_file: Path) -> bool:
      if not source_file.exists():
          return False
  ...
  elif source_file is not None:
      if not proper_dropout_code:
          flaw_detected = True
  ```
  When `source_file` is nonexistent, `check_source_enable_mc_dropout` returns `False`. The script interprets `proper_dropout_code == False` as flaw detected and exits with code 1 instead of configuration error code 2.
- **Blast radius**: A broken path or deleted `run_all_combos.py` will falsely report that MC-Dropout variance collapse is detected, rather than failing on missing file.
- **Mitigation**: Verify `source_file.exists()` before auditing AST, and return exit code 2 if the user explicitly provided a path that does not exist.

---

### [Low] Challenge 3: Flaw 13 CLI Target Routing Uses File Extension Heuristics

- **Assumption challenged**: `--target-file` cleanly accepts any arbitrary target.
- **Attack scenario**:
  ```powershell
  python tests/adversarial/test_flaw_13_unrecoverable_training_batches.py --target-file custom_weights.bin
  ```
  Because `custom_weights.bin` does not end in `.pth` or `.pt`, lines 110-114 assign `custom_weights.bin` to `doc_path` and fall back to `DEFAULT_CHECKPOINT` for the checkpoint.
- **Blast radius**: If weights are stored with alternative extensions, the test audits the default checkpoint instead of the specified file.
- **Mitigation**: Prefer explicit flags `--checkpoint-file` and `--doc-file` over overloaded `--target-file`.

---

## Stress Test Results Summary

| Stress Vector | Experiment Conducted | Expected Behavior | Actual Empirical Result | Status |
|---|---|---|---|:---:|
| **Baseline 14 Flaws** | Execute 14 scripts individually | Exit 1 for each script | All 14 scripts exited with code 1 | **PASS** |
| **Master Runner** | Execute `run_all_adversarial_tests.py` | Exit 0, 14/14 detected | Exited 0; reported 14/14 flaws detected (5.75s) | **PASS** |
| **Invalid CLI Flag** | Pass `--invalid-stress-arg-xyz` | Exit 2, print usage to stderr | All 14 scripts exited with code 2 | **PASS** |
| **CWD Independence** | Execute from `.agents/challenger_m2_1_g12` | Same results as repo root | All 14 scripts exited with code 1; runner exited 0 | **PASS** |
| **Output Consistency** | Regex audit of headers & fail tags | Unified format across suite | 14/14 scripts match header and `[FAIL]` format | **PASS** |
| **Missing Target File** | Pass `--target-file nonexistent.xyz` | Exit 2 for each script | 11/14 exited 2; Flaw 09 exited 1; Flaw 11 exited 0; Flaw 13 exited 1 | **Documented in Challenges** |

---

## Unchallenged Areas

1. **Remediation implementation**: Challenger is review-only. No fixes were applied to `src/`, `weights/`, or documentation in this milestone.
2. **Adversarial test script modification**: Test scripts in `tests/adversarial/` were not modified. The three edge-case challenges are documented above for future hardening by implementers.
