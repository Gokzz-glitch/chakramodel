# Comprehensive Review Report: Automated Adversarial Detection Scripts (Flaws 08–14 & Master Runner)

**Reviewer:** `reviewer_m2_2_g12` (Roles: reviewer, critic)  
**Date:** 2026-09-10  
**Working Directory:** `M:\chakramodel\.agents\reviewer_m2_2_g12`  
**Parent Orchestrator:** `orchestrator_gen12` (`ba6ae91c-9868-4822-93f7-a3b0985f6f8d`)  
**Scope of Review:**
- `tests/adversarial/test_flaw_08_conformal_formula_sign.py`
- `tests/adversarial/test_flaw_09_mc_dropout_collapse.py`
- `tests/adversarial/test_flaw_10_contradictory_calibration_qhat.py`
- `tests/adversarial/test_flaw_11_unpinned_dependencies.py`
- `tests/adversarial/test_flaw_12_ci_lacking_src_coverage.py`
- `tests/adversarial/test_flaw_13_unrecoverable_training_batches.py`
- `tests/adversarial/test_flaw_14_headline_metric_artifact_absence.py`
- `tests/adversarial/run_all_adversarial_tests.py`

---

## 1. Review Summary

**Verdict: APPROVE**

The automated adversarial detection scripts for Flaws 08 through 14 and the master test runner (`run_all_adversarial_tests.py`) are rigorously designed, scientifically sound, and fully verified. Every script:
1. Deterministically detects its targeted defect on the baseline codebase and exits with code `1`.
2. Cleanly passes with exit code `0` when evaluated against isolated remediated inputs via `--target-file` (or script-specific CLI parameters).
3. Emits clear, actionable diagnostic explanations detailing mathematical, architectural, and clinical hazards.
4. Uses genuine inspection mechanisms (AST walking, PyTorch tensor deserialization, regex parsing, JSON artifact analysis, and YAML step validation) without any hardcoded cheats or dummy facades.
5. Preserves complete immutability of primary application source code (`src/`), ensuring no fixes have been prematurely or inappropriately injected into the production codebase.
6. Master runner accurately executes and summarizes all 14 tests in ~5.1–6.4s, reporting 14/14 `[DETECTED]` and exiting with status `0`.

---

## 2. Detailed Technical Assessment by Script

### Flaw 08: `test_flaw_08_conformal_formula_sign.py`
- **Target Inspected:** `src/models/chakranet_segmenter.py` (lines 504–505 and 628–629).
- **Core Defect:** In `chakranet_segmenter.py`, the inference scoring formula calculates:
  ```python
  score_pos = 1.0 - (prob_resized + variance)
  score_neg = prob_resized - variance
  ```
  This subtracts variance from confidence instead of adding it, producing a $\Delta S = 2v$ inversion relative to canonical calibration non-conformity $(1 - p) + v$.
- **Detection Mechanism:** Employs regex pattern matching distinguishing buggy subtraction patterns (`1.0 - (prob + variance)` and `score_neg = prob - variance`) from canonical addition patterns (`(1.0 - prob) + variance` and `score_neg = prob + variance`).
- **Baseline Execution:** Exits `1` (`[FAIL] FLAW 08 DETECTED`).
- **Remediated Execution:** Exits `0` when `--target-file` contains canonical addition formulas.
- **Code Quality:** Excellent. Robust regex with whitespace and identifier tolerance.

### Flaw 09: `test_flaw_09_mc_dropout_collapse.py`
- **Target Inspected:** `results/combo1_metrics.json` and `src/evaluation/run_all_combos.py`.
- **Core Defect:** Calling `model.eval()` sets `training = False` on all modules. Method `enable_mc_dropout()` only toggles `self.mc_dropout = True` without recursively calling `self.drop.train()`. In eval mode, PyTorch's `Dropout2d` acts as an identity function. All MC stochastic passes are identical, resulting in an empirical variance of $2.85\times 10^{-15}$ (pure hardware floating-point noise).
- **Detection Mechanism:** Hybrid audit:
  1. JSON check for collapsed `mean_uncertainty < 1e-10`.
  2. AST inspection of `enable_mc_dropout()` in `run_all_combos.py` verifying whether `.train()` or `.apply()` is invoked on dropout layers.
- **Baseline Execution:** Exits `1` (`[FAIL] FLAW 09 DETECTED`).
- **Remediated Execution:** Exits `0` on patched JSON (`mean_uncertainty = 0.042`) or patched Python AST via `--target-file`.
- **Code Quality:** Robust dual-mode CLI accepting either `--target-file` (auto-detecting `.json` vs `.py`) or explicit `--metrics-file` and `--source-file`.

### Flaw 10: `test_flaw_10_contradictory_calibration_qhat.py`
- **Target Inspected:** `weights/calibration/conformal_calibration.json` vs `results/combo1_metrics.json`.
- **Core Defect:** Two conflicting calibration records exist:
  - File 1 (`weights/calibration/conformal_calibration.json`): $q_{\text{hat\_pos}} = 0.521484375$ (~0.52).
  - File 2 (`results/combo1_metrics.json`): $\text{threshold} = 7.326006889\times 10^{-6}$ (~7.33e-06).
  The discrepancy is $71,183\times$ (4.85 orders of magnitude). File 2 was derived from collapsed MC-Dropout variance, while deployed inference weights distribute File 1.
- **Detection Mechanism:** Parses both JSONs, extracts thresholds, computes magnitude ratio and logarithmic order difference (`orders_diff > 3.0`), and checks for explicit reconciliation tags (`DEPRECATED` or `SUPERSEDED`) in `conformal_status`.
- **Baseline Execution:** Exits `1` (`[FAIL] FLAW 10 DETECTED`, reporting 71182.62x / 4.85 orders of magnitude discrepancy).
- **Remediated Execution:** Exits `0` when `--target-file` or `--metrics-file` contains reconciled `conformal_status`.
- **Code Quality:** Mathematically exact, avoids arbitrary hardcoded threshold comparisons by using logarithmic scale difference.

### Flaw 11: `test_flaw_11_unpinned_dependencies.py`
- **Target Inspected:** `requirements.txt` and `kaggle_bundle/requirements.txt`.
- **Core Defect:** Manifests specify floating lower bounds (e.g. `timm>=0.9.0`, `torch>=2.0.0`, `numpy>=1.23.0`). This permits silent installation of breaking upstream versions (e.g. NumPy 2.x ABI breakage, timm 1.0.x ViT output tensor shape changes from 3D `(B, 577, 1024)` to 4D/pooled).
- **Detection Mechanism:** Line-by-line parsing of requirement specifications, identifying `>=` bounds lacking `==`, as well as completely unpinned packages.
- **Baseline Execution:** Exits `1` (`[FAIL] FLAW 11 DETECTED: 26 unpinned floating dependencies detected`).
- **Remediated Execution:** Exits `0` when given a pinned requirements manifest with exact `==` versions.
- **Code Quality:** Robust comment stripping and operator parsing; accepts `--target-file` or `--req-file`.

### Flaw 12: `test_flaw_12_ci_lacking_src_coverage.py`
- **Target Inspected:** `.github/workflows/test.yml`.
- **Core Defect:** CI workflow `lint` job runs `flake8 tests/` exclusively, omitting `src/`. CI `test` job executes only `python tests/test_notebooks_adversarial.py` (a notebook JSON validator). Application source code in `src/` is never linted or unit-tested in CI.
- **Detection Mechanism:** Safely parses YAML workflow structure:
  1. Audits `lint` job steps for `flake8` or `ruff` targeting directory `src`.
  2. Audits `test` job steps for `pytest` or unit test scripts targeting application logic.
- **Baseline Execution:** Exits `1` (`[FAIL] FLAW 12 DETECTED: CI workflow lacks coverage for application source code`).
- **Remediated Execution:** Exits `0` when audited against a workflow containing `flake8 src/ tests/` and `pytest tests/`.
- **Code Quality:** Clean structure leveraging `pyyaml`, resilient against step reordering.

### Flaw 13: `test_flaw_13_unrecoverable_training_batches.py`
- **Target Inspected:** `weights/checkpoints/chakra_transformer_best.pth` and `docs/TRAINING_PROVENANCE.md`.
- **Core Defect:** Checkpoint state dict contains `num_batches_tracked = 2376` in its decoder BatchNorm layers. However, the committed notebook `Combo6_ChakraTransformer.ipynb` defines a 15-epoch, 22-step training regime (330 steps total). The checkpoint received $7.2\times$ more optimizer updates from an undocumented multi-GPU DDP run, rendering training data composition unrecoverable and invalidating zero-shot generalization claims.
- **Detection Mechanism:** Loads checkpoint state dict on CPU using `torch.load(..., map_location='cpu')`, extracts `num_batches_tracked`, verifies whether `tracked_batches > 2 * EXPECTED_NOTEBOOK_BATCHES` (2376 vs 330), and verifies existence of `docs/TRAINING_PROVENANCE.md` containing disclosures for `2376` and `zero-shot`.
- **Baseline Execution:** Exits `1` (`[FAIL] FLAW 13 DETECTED: Missing training data provenance disclosure at TRAINING_PROVENANCE.md`).
- **Remediated Execution:** Exits `0` when `--target-file` points to a valid provenance disclosure or clean 330-batch checkpoint.
- **Code Quality:** High performance PyTorch CPU loading (~3.5s for 1.2 GB checkpoint); handles both tensor and scalar forms of `num_batches_tracked`.

### Flaw 14: `test_flaw_14_headline_metric_artifact_absence.py`
- **Target Inspected:** `FIXES.md`, `results/corrected_eval_kvasir_seg.json`, and `docs/HONEST_METRICS.md`.
- **Core Defect:** `FIXES.md` Section 5 asserts a "Genuine Measured Evaluation" of Mean DSC 0.7304 on N=50 images, citing `corrected_eval_kvasir_seg.json`. However, that JSON artifact actually contains Mean DSC 0.80225 on N=60 images, and `docs/HONEST_METRICS.md` omitted 0.7304 from its table of retracted metrics.
- **Detection Mechanism:**
  1. Checks if `FIXES.md` asserts "0.7304".
  2. Compares against `mean_dsc` in `results/corrected_eval_kvasir_seg.json` (0.80225 vs 0.7304).
  3. Checks if `docs/HONEST_METRICS.md` explicitly retracts 0.7304.
- **Baseline Execution:** Exits `1` (`[FAIL] FLAW 14 DETECTED: Headline metric 0.7304 is unsubstantiated by empirical artifacts`).
- **Remediated Execution:** Exits `0` when `--target-file` points to a corrected document (or `--honest-metrics` includes the retraction).
- **Code Quality:** Thorough cross-artifact verification preventing ghost metrics.

---

### Master Runner: `run_all_adversarial_tests.py`
- **Design & Logic:**
  - Defines data structure for all 14 flaw tests with script paths and expected return codes (`1`).
  - Executes each test in an isolated subprocess via `sys.executable`.
  - Captures stdout/stderr and extracts concise diagnostic failure lines.
  - Generates a cleanly formatted summary table with script name, exit code, detection status, and per-test execution timing.
  - Enforces the master invariant: exits `0` if and only if all 14 tests exit `1`. If any test passes (exit 0) or encounters an unhandled crash/error (exit 2 or -1), the runner exits `1`.
- **Empirical Baseline Run:**
  - Total flaws tested: 14.
  - Flaws detected: 14 / 14 (all exited `1`).
  - Total elapsed time: ~5.14–6.41 seconds.
  - Runner exit code: `0` (Success: all 14 baseline flaws detected).

---

## 3. Active Integrity Review

- **Hardcoded test results or expected outputs in source code**: NONE. All tests perform live AST walking, regex analysis, JSON parsing, YAML structural checking, or PyTorch tensor state dictionary inspection.
- **Dummy or facade implementations**: NONE. Checks accurately interrogate the specific mathematical and software structures where defects reside.
- **Shortcuts bypassing intended tasks**: NONE.
- **Fabricated verification outputs or logs**: NONE. All outputs were independently generated and verified via live execution.
- **Self-certifying work without genuine independent verification**: NONE. Tested with external isolated mock inputs in temporary directories.
- **Primary source file modifications**: Confirmed 0 modifications to production logic in `src/`. (Non-semantic docstrings added by an independent parallel worker `worker_m1_g13` do not alter code logic or mask defects).

---

## 4. Findings

### Minor Observation (Informational / Non-Blocking)
- In `test_flaw_13_unrecoverable_training_batches.py`, loading the 1.2 GB PyTorch checkpoint on CPU takes ~3.5 to 4.5 seconds. While acceptable for a 14-test suite that completes in under 7 seconds, downstream CI environments with constrained memory or slow I/O should ensure adequate RAM (> 2 GB) is allocated.

---

## 5. Verified Claims

1. `test_flaw_08_conformal_formula_sign.py` exits 1 on current codebase and exits 0 on canonical patched formula $\rightarrow$ **VERIFIED (PASS)**.
2. `test_flaw_09_mc_dropout_collapse.py` exits 1 on current codebase and exits 0 on patched uncertainty JSON or AST $\rightarrow$ **VERIFIED (PASS)**.
3. `test_flaw_10_contradictory_calibration_qhat.py` exits 1 on current codebase and exits 0 on reconciled conformal status $\rightarrow$ **VERIFIED (PASS)**.
4. `test_flaw_11_unpinned_dependencies.py` exits 1 on current codebase and exits 0 on pinned requirements $\rightarrow$ **VERIFIED (PASS)**.
5. `test_flaw_12_ci_lacking_src_coverage.py` exits 1 on current codebase and exits 0 on comprehensive workflow $\rightarrow$ **VERIFIED (PASS)**.
6. `test_flaw_13_unrecoverable_training_batches.py` exits 1 on current codebase and exits 0 on documented provenance $\rightarrow$ **VERIFIED (PASS)**.
7. `test_flaw_14_headline_metric_artifact_absence.py` exits 1 on current codebase and exits 0 on retracted/aligned metrics $\rightarrow$ **VERIFIED (PASS)**.
8. `run_all_adversarial_tests.py` runs all 14 tests, displays comprehensive summary table, and exits 0 when all 14 exit 1 $\rightarrow$ **VERIFIED (PASS)**.
9. All 14 defects remain active in `src/` and no shortcuts/bypasses exist $\rightarrow$ **VERIFIED (PASS)**.

---

## 6. Coverage Gaps & Unverified Items

- None. All 7 targeted scripts and the master runner were fully tested across baseline and remediated configurations.
