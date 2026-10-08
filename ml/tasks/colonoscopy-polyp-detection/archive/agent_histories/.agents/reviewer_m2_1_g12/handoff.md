# Handoff Report: Review of Adversarial Detection Scripts (Flaws 01-07)

**Agent:** `reviewer_m2_1_g12`  
**Working Directory:** `M:\chakramodel\.agents\reviewer_m2_1_g12`  
**Parent Orchestrator:** `orchestrator_gen12` (`ba6ae91c-9868-4822-93f7-a3b0985f6f8d`)  
**Verdict:** **FAIL / REQUEST_CHANGES**  

---

## 1. Observation

Direct tool observations across the repository and test suite:

1. **Baseline Flaw Detection (Exit 1)**:
   Running each script directly against the baseline repository exited 1 with descriptive diagnostics:
   - `python tests/adversarial/test_flaw_01_no_skip_connections.py` -> Exit 1. Diagnosed: `ChakraNetMicroRefiner decoder has NO skip connections`.
   - `python tests/adversarial/test_flaw_02_dead_imagenet_head.py` -> Exit 1. Diagnosed: `timm.create_model call found at line: 198`, `num_classes: None`.
   - `python tests/adversarial/test_flaw_03_dead_code.py` -> Exit 1. Diagnosed: `3 dead classes found (lines 39, 67, 136)`.
   - `python tests/adversarial/test_flaw_04_oom_fallback.py` -> Exit 1. Diagnosed: `self.to('cpu') found in forward() OOM fallback at line 322`.
   - `python tests/adversarial/test_flaw_05_tta_enabled_by_default.py` -> Exit 1. Diagnosed: `getattr(self, 'use_tta', True) at lines 438, 564`.
   - `python tests/adversarial/test_flaw_06_unguarded_torch_load.py` -> Exit 1. Diagnosed: `31 unguarded torch.load() calls found without weights_only=True`.
   - `python tests/adversarial/test_flaw_07_strict_false_state_dict.py` -> Exit 1. Diagnosed: `load_state_dict() uses strict=False without raising on key mismatch at line 380`.

2. **AST Parsing Accuracy & Edge Cases Observed**:
   - In `test_flaw_04_oom_fallback.py` lines 44-48:
     ```python
     is_self_call = isinstance(sub.func.value, ast.Name) and sub.func.value.id == "self"
     if len(sub.args) >= 1:
         first_arg = sub.args[0]
         if isinstance(first_arg, ast.Constant) and first_arg.value == "cpu":
             dangerous_calls.append((sub.lineno, "self.to('cpu')" if is_self_call else "tensor.to('cpu')"))
     ```
     Tested with `return x.to('cpu')` inside a `forward()` function -> Exited `1` with `[FAIL] FLAW 04 DETECTED`.
   - In `test_flaw_06_unguarded_torch_load.py` lines 44-46:
     ```python
     elif isinstance(node.func, ast.Name) and node.func.id == "load":
         # Check if torch.load was directly imported
         pass
     ```
     Tested with `from torch import load; sd = load('model.pth')` -> Exited `0` with `[PASS] Flaw 06 Resolved`.
   - In `test_flaw_06_unguarded_torch_load.py` lines 33-36:
     ```python
     try:
         tree = ast.parse(content, filename=str(file_path))
     except Exception:
         return violations
     ```
     Tested with syntax error file -> Exited `0` with `[PASS] Flaw 06 Resolved` instead of returning exit `2`.
   - In `test_flaw_07_strict_false_state_dict.py` lines 55-66:
     `has_raise_on_mismatch` scans entire AST unconditionally. Tested with unrelated function `if 'missing' in filename: raise ValueError()` alongside unguarded `model.load_state_dict(sd, strict=False)` -> Exited `0` with `[PASS] Flaw 07 Resolved`.
   - In `test_flaw_05_tta_enabled_by_default.py` lines 54-58:
     Only checks `item.args.args` and `item.args.defaults`. Tested with keyword-only argument `def __init__(self, *, use_tta: bool = False):` -> Exited `1` with `[FAIL] FLAW 05 DETECTED`.

3. **Source Code Modifications Observed**:
   Executing git status (`git.exe status --porcelain src/`) yielded:
   ```text
    M src/chakra_transformer/transformer_segmenter.py
   M  src/conformal/conformal_calibration.py
    M src/models/chakranet_segmenter.py
   ```
   Primary source files in `src/` are modified relative to `HEAD`.

---

## 2. Logic Chain

1. **Premise**: Adversarial detection scripts serve as the automated ground truth quality gate for Milestone 3 remediations.
2. **Observation 1 & 2**: While all scripts detect the flawed baseline on the unmodified code, several scripts contain flawed AST logic:
   - Flaw 04 contains a confirmed false positive: remediated code moving tensors to CPU will fail gating.
   - Flaw 06 contains a confirmed false negative: unpickling vulnerabilities imported via `from torch import load` pass gating.
   - Flaw 07 contains a confirmed false negative: global un-scoped matching permits unguarded `strict=False` in modules with unrelated `missing` checks.
   - Flaw 05 contains a false positive for keyword-only parameters.
3. **Observation 3**: Primary source files in `src/` are currently modified in the workspace, violating the explicit verification constraint.
4. **Deduction**: Approving flawed quality gates would directly break legitimate remediations in Milestone 3 and permit security vulnerabilities to remain undetected.
5. **Conclusion**: The detection suite requires changes before approval.

---

## 3. Caveats

- **Scope**: Review was focused specifically on Flaws 01 through 07 in accordance with the user instructions. Flaws 08 through 14 were audited by peer reviewers.
- **Source Attribution**: The modifications in `src/` (`chakranet_segmenter.py` and `transformer_segmenter.py`) were made by parallel agent `worker_m1_g13` (documenting architecture and layer parameters) rather than `worker_m2_adversarial`. Nonetheless, workspace consistency requires tracking.
- **Integrity**: No evidence of deliberate fraud, hardcoded facades, or fabricated outputs was found; the issues are algorithmic AST parsing bugs.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES (FAIL)**

Actionable fixes required by the test author (`worker_m2_adversarial`):
1. **Flaw 04**: Fix `test_flaw_04_oom_fallback.py` to only append to `dangerous_calls` if `is_self_call is True`.
2. **Flaw 06**: Fix `test_flaw_06_unguarded_torch_load.py` to catch direct imports `from torch import load` and return exit `2` if a file provided via `--target-file` cannot be parsed.
3. **Flaw 07**: Fix `test_flaw_07_strict_false_state_dict.py` to scope mismatch validation to the specific function or block containing the `load_state_dict` call.
4. **Flaw 05**: Fix `test_flaw_05_tta_enabled_by_default.py` to also inspect `item.args.kwonlyargs` and `item.args.kw_defaults`.

---

## 5. Verification Method

To independently reproduce this review and verify the findings:

1. **Verify Baseline Detections (Exit 1)**:
   ```powershell
   python tests/adversarial/test_flaw_01_no_skip_connections.py
   python tests/adversarial/test_flaw_02_dead_imagenet_head.py
   python tests/adversarial/test_flaw_03_dead_code.py
   python tests/adversarial/test_flaw_04_oom_fallback.py
   python tests/adversarial/test_flaw_05_tta_enabled_by_default.py
   python tests/adversarial/test_flaw_06_unguarded_torch_load.py
   python tests/adversarial/test_flaw_07_strict_false_state_dict.py
   ```

2. **Run the Reviewer's Automated Stress-Test Suite**:
   ```powershell
   python .agents/reviewer_m2_1_g12/test_cli_isolation.py
   ```
   *Expected output*: Highlights the exact failure modes documented in this report.

3. **Verify Git Modifications in `src/`**:
   ```powershell
   & "C:\Users\imgk3\AppData\Local\GitHubDesktop\app-3.6.3\resources\app\git\cmd\git.exe" status --porcelain src/
   ```
