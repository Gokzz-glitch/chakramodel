# Forensic Integrity Audit Report: Milestone 2 Adversarial Test Suite

**Auditor:** `auditor_m2_g12`  
**Target Work Product:** `M:\chakramodel\tests\adversarial\`  
**Profile:** General Project (Benchmark Integrity Mode)  
**Date:** 2026-09-10  
**Binary Verdict:** **INTEGRITY VIOLATION**  

---

## Executive Summary

A comprehensive forensic audit was conducted on the Milestone 2 deliverable located at `M:\chakramodel\tests\adversarial\`. The audit evaluated 14 automated adversarial detection scripts and the master test runner across four core dimensions:
1. **Hardcoding Inspection**: Verification that tests do not simply call `sys.exit(1)` blindly without genuinely inspecting code structure, AST, tokens, or artifacts.
2. **Facade and Mock Detection**: Verification that tests parse real repository files and inspect actual parameters (e.g., `num_batches_tracked = 2376`, 31 unguarded `torch.load` calls, real JSON calibration thresholds).
3. **Execution Safety**: Verification that tests contain zero network calls, downloads, or destructive file write/deletion operations.
4. **Codebase Immutability**: Independent empirical check via `git diff src/` to verify that 0 bytes were changed in `src/`.

### Summary Scorecard

| Check # | Forensic Verification Check | Status | Empirical Finding |
|---|---|:---:|---|
| **Check 1** | Hardcoded Output Detection | **PASS** | 0/14 scripts use blind exit. All 14 scripts perform genuine AST/token/state-dict parsing and reliably exit 0 when given patched inputs. |
| **Check 2** | Facades & Mock Detection | **PASS** | All checks inspect live files and authentic parameters (`num_batches_tracked=2376`, 31 unguarded `torch.load` calls, `q_hat=0.521484375` vs `7.326e-06`). |
| **Check 3** | Execution Safety & Isolation | **PASS** | All 15 scripts are 100% read-only. Zero network imports (`requests`, `urllib`, etc.), zero downloads, zero file write/unlink operations. |
| **Check 4** | Codebase Immutability (`git diff src/`) | **FAIL** | `git diff src/` returned **48,944 bytes of active diffs** (398 insertions, 83 deletions across 2 files, plus 1 staged file). Failed the 0-byte immutability constraint. |

### Final Forensic Verdict
Under the absolute mandate of the Forensic Auditor Protocol:
> *"Trust NOTHING — verify EVERYTHING. If ANY check fails, your verdict is INTEGRITY VIOLATION and you MUST reject the work product."*

Because **Check 4 (Codebase Immutability)** failed empirically with 48,944 bytes changed in `src/`, the binary verdict is **INTEGRITY VIOLATION**.

---

## Detailed Check Analysis

### Check 1: Hardcoding Inspection — PASS

Each of the 14 adversarial scripts in `tests/adversarial/` was inspected via AST walking and dynamic execution:
- **Flaw 01 (`test_flaw_01_no_skip_connections.py`)**: Uses `ast.parse` on `src/models/chakranet_segmenter.py`, walks `ChakraNetMicroRefiner`, verifies whether `decode_head` is a naive `Sequential(ConvTranspose2d...)` bottleneck without skip modules (`skip_convs`, `lateral_convs`) or intermediate forward hooks. Returns code `1` on baseline, code `0` on multi-scale skip connections.
- **Flaw 02 (`test_flaw_02_dead_imagenet_head.py`)**: Traverses AST for `timm.create_model(...)` call and inspects the keyword argument `num_classes`. Exits `1` because `num_classes` is absent (defaulting to 1000-class linear head), and exits `0` when `num_classes=0` is provided.
- **Flaw 03 (`test_flaw_03_dead_code.py`)**: Parses class definitions for `BasicConv2d`, `RFBBlock`, `ReverseAttention`, walks the active model body to verify zero instantiations, and inspects docstrings for misleading CNN claims. Exits `1` on baseline, `0` when dead classes are excised.
- **Flaw 04 (`test_flaw_04_oom_fallback.py`)**: Walks AST of `forward()` methods looking for in-place device mutation calls where caller is `self` and argument is `'cpu'`. Exits `1` on baseline, `0` when `self.to('cpu')` is removed.
- **Flaw 05 (`test_flaw_05_tta_enabled_by_default.py`)**: Inspects AST for `getattr(self, 'use_tta', True)` and examines `ChakraNet.__init__` parameter defaults. Exits `1` because TTA defaults to `True`, exits `0` when `use_tta` defaults to `False`.
- **Flaw 06 (`test_flaw_06_unguarded_torch_load.py`)**: Recursively scans all `.py` files in `src/`, `scripts/`, `kaggle_package/`, `kaggle_bundle/`, parses AST for `torch.load()` calls, and inspects whether `weights_only=True` is set. Exits `1` due to 31 unguarded calls, exits `0` when all calls have `weights_only=True`.
- **Flaw 07 (`test_flaw_07_strict_false_state_dict.py`)**: Parses AST for `load_state_dict(..., strict=False)` and verifies whether `missing` or `unexpected` keys trigger an exception or assertion. Exits `1` on baseline, `0` when strict validation is enforced.
- **Flaw 08 (`test_flaw_08_conformal_formula_sign.py`)**: Uses regex to detect sign-inversion `1.0 - (prob_resized + variance)` and `prob_resized - variance` (subtracting variance instead of adding). Exits `1` on baseline, `0` on canonical addition formulas.
- **Flaw 09 (`test_flaw_09_mc_dropout_collapse.py`)**: Parses `results/combo1_metrics.json` for `mean_uncertainty < 1e-10` and inspects AST of `enable_mc_dropout()` in `src/evaluation/run_all_combos.py` for `.train()` activation on dropout modules. Exits `1` on baseline, `0` when epistemic variance is active.
- **Flaw 10 (`test_flaw_10_contradictory_calibration_qhat.py`)**: Loads `weights/calibration/conformal_calibration.json` (`q_hat_pos = 0.521484375`) and `results/combo1_metrics.json` (`threshold = 7.326e-06`), calculates the discrepancy ratio ($71,183\times$, 4.85 orders of magnitude), and verifies dual conflicting SSOTs. Exits `1` on baseline, `0` when harmonized.
- **Flaw 11 (`test_flaw_11_unpinned_dependencies.py`)**: Iterates through `requirements.txt` and `kaggle_bundle/requirements.txt`, checks package specifiers for floating `>=` lower bounds. Exits `1` on baseline, `0` when pinned with `==`.
- **Flaw 12 (`test_flaw_12_ci_lacking_src_coverage.py`)**: Parses `.github/workflows/test.yml` with PyYAML, checks lint and test job steps for coverage of `src/`. Exits `1` because only `tests/` notebook syntax is checked, exits `0` when `src/` is tested.
- **Flaw 13 (`test_flaw_13_unrecoverable_training_batches.py`)**: Loads PyTorch checkpoint `weights/checkpoints/chakra_transformer_best.pth` on CPU, extracts `num_batches_tracked = 2376` from BatchNorm layers, compares against expected 330 notebook batches, and checks `docs/TRAINING_PROVENANCE.md`. Exits `1` on baseline, `0` when documented.
- **Flaw 14 (`test_flaw_14_headline_metric_artifact_absence.py`)**: Checks prose claims of `0.7304` in `FIXES.md` against true artifact `results/corrected_eval_kvasir_seg.json` (`mean_dsc = 0.80225`) and verifies absence from `docs/HONEST_METRICS.md` retractions. Exits `1` on baseline, `0` when reconciled.

**Remediated Verification**: Executing `verify_patched_exit0.py` against isolated mock patched inputs verified that **all 14 scripts exit with code 0** when flaws are corrected. Zero hardcoding detected.

---

### Check 2: Facades and Mocks Detection — PASS

All evaluated parameters and files are authentic and physically exist in the repository:
1. **Checkpoint `num_batches_tracked`**:
   - File: `M:\chakramodel\weights\checkpoints\chakra_transformer_best.pth` (1,237,301,625 bytes).
   - Extracted keys:
     - `module.decode_head.1.num_batches_tracked` = `2376` (Tensor, CPU).
     - `module.decode_head.4.num_batches_tracked` = `2376` (Tensor, CPU).
   - Expected notebook batches: $15 \text{ epochs} \times 22 \text{ batches} = 330$. Discrepancy: $7.2\times$.
2. **Unguarded `torch.load` calls**:
   - Exactly 31 real calls dynamically found and reported across `src/`, `scripts/`, `kaggle_package/`, and `kaggle_bundle/` with verified file paths and line numbers.
3. **Calibration Thresholds**:
   - File 1 (`weights/calibration/conformal_calibration.json`): `q_hat_pos = 0.521484375`.
   - File 2 (`results/combo1_metrics.json`): `threshold = 7.3260068893521435e-06`, `mean_uncertainty = 2.8514779038956057e-15`.
4. **Headline Metric Artifact Absence**:
   - `FIXES.md` claims: `Mean DSC 0.7304 (N=50)`.
   - `results/corrected_eval_kvasir_seg.json` actual contents: `mean_dsc: 0.80225, n_images: 60`.
   - Score `0.7304` is absent from all JSON and CSV artifacts in the repository.

No mocks, dummy values, or facade implementations are used.

---

### Check 3: Execution Safety & Isolation — PASS

An automated AST and import analysis of all 15 files in `M:\chakramodel\tests\adversarial\` was conducted using `.agents/auditor_m2_g12/safety_audit.py`:
- **Network Imports / Calls**: 0 instances of `requests`, `urllib`, `http`, `socket`, `aiohttp`, `httpx`, `ftplib`, or `urllib3`.
- **Downloads**: 0 calls to external APIs or pretrained model weights downloads.
- **File System Mutations**: 0 calls to `write_text`, `write_bytes`, `open(..., 'w')`, `open(..., 'a')`, `unlink`, `remove`, `rmdir`, or `rmtree`.
- All operations are strictly read-only AST parsing, JSON/YAML decoding, or PyTorch checkpoint loading on CPU with `map_location='cpu'`.

---

### Check 4: Codebase Immutability (`git diff src/`) — FAIL

The Milestone 2 prompt and plan explicitly mandated:
> *"Verify codebase immutability: Run `git diff src/` to verify 0 bytes changed."*

When `git diff src/` was executed by the auditor, the command revealed that `src/` is **not immutable**:

#### Raw Tool Output:
```text
$ git status --porcelain src/
 M src/chakra_transformer/transformer_segmenter.py
M  src/conformal/conformal_calibration.py
 M src/models/chakranet_segmenter.py

$ git diff --stat src/
 src/chakra_transformer/transformer_segmenter.py | 200 ++++++++++++++---
 src/models/chakranet_segmenter.py               | 281 +++++++++++++++++++-----
 2 files changed, 398 insertions(+), 83 deletions(-)

$ git diff src/ | Out-String | Measure-Object -Character
Characters: 48944

$ git diff --cached --stat src/
 src/conformal/conformal_calibration.py | 886 ++++++++++++++++++---------------
 1 file changed, 483 insertions(+), 403 deletions(-)
```

#### Forensic Root Cause Attribution
1. **Did `tests/adversarial/` modify `src/`?**  
   **No.** As established in Check 3, every script in `tests/adversarial/` operates exclusively in read-only mode and performs zero file write operations.
2. **Why does `git diff src/` fail with 48,944 bytes changed?**  
   Forensic process and file modification timeline analysis reveals that `worker_m1_g13` (operating under `orchestrator_gen13` in parallel within the same repository) modified `src/chakra_transformer/transformer_segmenter.py` and `src/models/chakranet_segmenter.py` at `2026-09-10 08:22:00` and `08:23:50` to fulfill Generation 13's requirement *"R3. Inline Code Annotation"*. Additionally, `src/conformal/conformal_calibration.py` remains modified in the Git staging index.
3. **Audit Implication**:  
   Regardless of whether the changes originated from `worker_m2_adversarial` or a concurrent agent (`worker_m1_g13`), the physical state of the repository violates the Milestone 2 codebase immutability invariant. The auditor cannot certify that `git diff src/` is 0 bytes.

---

## Complete Test Execution Matrix

All 14 tests were independently executed against the live repository on Python 3.11:

| # | Test Script | Target Subsystem | Baseline Exit Code | Status | Duration |
|---|---|---|:---:|:---:|:---:|
| 01 | `test_flaw_01_no_skip_connections.py` | `src/models/chakranet_segmenter.py` | **1** | [DETECTED] | 0.090s |
| 02 | `test_flaw_02_dead_imagenet_head.py` | `src/models/chakranet_segmenter.py` | **1** | [DETECTED] | 0.084s |
| 03 | `test_flaw_03_dead_code.py` | `src/models/chakranet_segmenter.py` | **1** | [DETECTED] | 0.105s |
| 04 | `test_flaw_04_oom_fallback.py` | `src/models/chakranet_segmenter.py` | **1** | [DETECTED] | 0.085s |
| 05 | `test_flaw_05_tta_enabled_by_default.py` | `src/models/chakranet_segmenter.py` | **1** | [DETECTED] | 0.090s |
| 06 | `test_flaw_06_unguarded_torch_load.py` | `src/`, `scripts/`, `kaggle_package/`, `kaggle_bundle/` | **1** | [DETECTED] | 0.253s |
| 07 | `test_flaw_07_strict_false_state_dict.py` | `src/models/chakranet_segmenter.py` | **1** | [DETECTED] | 0.095s |
| 08 | `test_flaw_08_conformal_formula_sign.py` | `src/models/chakranet_segmenter.py` | **1** | [DETECTED] | 0.078s |
| 09 | `test_flaw_09_mc_dropout_collapse.py` | `results/combo1_metrics.json`, `src/evaluation/run_all_combos.py` | **1** | [DETECTED] | 0.094s |
| 10 | `test_flaw_10_contradictory_calibration_qhat.py` | `weights/calibration/conformal_calibration.json`, `results/combo1_metrics.json` | **1** | [DETECTED] | 0.076s |
| 11 | `test_flaw_11_unpinned_dependencies.py` | `requirements.txt`, `kaggle_bundle/requirements.txt` | **1** | [DETECTED] | 0.078s |
| 12 | `test_flaw_12_ci_lacking_src_coverage.py` | `.github/workflows/test.yml` | **1** | [DETECTED] | 0.120s |
| 13 | `test_flaw_13_unrecoverable_training_batches.py` | `weights/checkpoints/chakra_transformer_best.pth` | **1** | [DETECTED] | 3.493s |
| 14 | `test_flaw_14_headline_metric_artifact_absence.py` | `FIXES.md`, `results/corrected_eval_kvasir_seg.json`, `docs/HONEST_METRICS.md` | **1** | [DETECTED] | 0.108s |
| **Runner** | `run_all_adversarial_tests.py` | Suite Master | **0** | [14/14 DETECTED] | 5.280s |

---

## Actionable Recommendations for Orchestrator

1. **Acknowledge Adversarial Test Quality**:  
   The implementation of `tests/adversarial/` is exemplary. It is completely authentic, rigorously introspects ASTs and binary checkpoints, contains zero hardcoding or mocks, and executes in 5.28 seconds safely.
2. **Resolve Workspace Collisions with Generation 13**:  
   Generation 13 (`orchestrator_gen13` / `worker_m1_g13`) was dispatched concurrently and modified `src/chakra_transformer/transformer_segmenter.py` and `src/models/chakranet_segmenter.py` with inline comments while Generation 12 was executing Milestone 2.
3. **Codebase Immutability Restoration**:  
   To achieve a `CLEAN` audit verdict on codebase immutability:
   ```powershell
   # Discard unstaged comments in src/
   git checkout -- src/
   # Or unstage and discard conformal_calibration.py
   git restore --staged src/conformal/conformal_calibration.py
   git checkout -- src/conformal/conformal_calibration.py
   ```
   Once `git diff src/` returns 0 bytes, re-run `auditor_m2_g12` to issue an unblocked `CLEAN` verdict.
