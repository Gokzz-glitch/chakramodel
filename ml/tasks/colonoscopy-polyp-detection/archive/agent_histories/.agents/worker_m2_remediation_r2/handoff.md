# Forensic Audit Remediation Handoff Report: Milestone 2 Hardening

**Agent:** `worker_m2_remediation_r2`  
**Working Directory:** `M:\chakramodel\.agents\worker_m2_remediation_r2`  
**Parent Caller:** `ba6ae91c-9868-4822-93f7-a3b0985f6f8d` (`orchestrator_gen12` / parent)  
**Date:** 2026-09-10  

---

## 1. Observation

### 1.1 Source Directory Immutability
- Commands executed:
  ```powershell
  git restore --staged src/
  git restore src/
  git diff HEAD -- src/
  git status --porcelain src/
  ```
- Result: Completely empty output (0 bytes). Both working tree and staging area for `src/` are 100% clean and identical to baseline `HEAD`.

### 1.2 Initial State of Adversarial Scripts on CLI Isolation
- Prior to remediation, running `python .agents/reviewer_m2_1_g12/test_cli_isolation.py` failed with:
  ```text
  Auditing test_flaw_06_unguarded_torch_load.py:
    [PASS] --help returned 0
    [PASS] Non-existent file correctly returned 2
    [FAIL] Malformed syntax expected returncode 2, got 0

  Testing Flaw 07 isolated mock:
    Flawed 07: exit 1 (expected 1), Patched 07: exit 1 (expected 0)
  OVERALL RESULT: FAIL
  ```
- Additionally, Reviewer 1 identified vulnerabilities in:
  - `tests/adversarial/test_flaw_04_oom_fallback.py`: Lines 44-48 appended `(sub.lineno, "tensor.to('cpu')")` to `dangerous_calls` even when `is_self_call` was False, causing false positives on legitimate tensor transfers like `x.to('cpu')`.
  - `tests/adversarial/test_flaw_05_tta_enabled_by_default.py`: Lines 54-58 inspected only positional `item.args.args` and `item.args.defaults`, completely missing keyword-only arguments in `item.args.kwonlyargs` and `item.args.kw_defaults` (e.g. `def __init__(self, *, use_tta: bool = False):`).
  - `tests/adversarial/test_flaw_06_unguarded_torch_load.py`: Lines 44-46 contained only a `pass` for direct imports (`from torch import load`), allowing unguarded calls to bypass detection. In addition, `check_file` caught syntax exceptions and returned `[]`, exiting 0 on malformed `--target-file` inputs instead of exit code 2.
  - `tests/adversarial/test_flaw_07_strict_false_state_dict.py`: Lines 55-66 performed an un-scoped global AST walk for `if 'missing' in ...: raise`, allowing an unrelated check in another function to mask an unguarded `strict=False` in `load_state_dict`.

### 1.3 Post-Remediation Verification Results
- Master runner: `python tests/adversarial/run_all_adversarial_tests.py`
  - Output: `>>> ALL 14 ADVERSARIAL FLAWS SUCCESSFULLY EXPOSED ON CURRENT CODEBASE (14/14 Exit 1)!`
  - Exit code: `0`
- Patched verification: `python .agents/worker_m2_adversarial/verify_patched_exit0.py`
  - Output: `All 14 scripts correctly exit 0 when provided patched inputs!`
  - Exit code: `0`
- Reviewer CLI isolation: `python .agents/reviewer_m2_1_g12/test_cli_isolation.py`
  - Output: `OVERALL RESULT: PASS`
  - Exit code: `0`
- Edge-cases harness: `python .agents/worker_m2_remediation_r2/test_edge_cases.py`
  - Output:
    ```text
    === Testing Flaws 04, 05, 06, 07 Specific Edge Cases ===
    Flaw 04 tensor .to('cpu'): exit 0 (expected 0)
    Flaw 04 self.to('cpu'): exit 1 (expected 1)
    Flaw 05 kwonly use_tta=False: exit 0 (expected 0)
    Flaw 05 kwonly use_tta=True: exit 1 (expected 1)
    Flaw 06 direct import unsafe: exit 1 (expected 1)
    Flaw 06 direct import safe: exit 0 (expected 0)
    Flaw 06 malformed syntax: exit 2 (expected 2)
    Flaw 07 unrelated function bypass attempt: exit 1 (expected 1)
    Flaw 07 properly scoped guard: exit 0 (expected 0)
    ALL EDGE CASES RESULT: PASS
    ```
  - Exit code: `0`
- Source cleanliness check:
  ```powershell
  git diff HEAD -- src/
  git status --porcelain src/
  ```
  Returns exactly 0 bytes.

---

## 2. Logic Chain

1. **Premise 1 (Integrity & Immutability)**: The Forensic Auditor vetoed Milestone 2 due to modified files in `src/`. Restoring `src/` via `git restore` and confirming with `git diff HEAD -- src/` guarantees the primary codebase remains strictly immutable during the audit phase.
2. **Premise 2 (Flaw 04 AST Precision)**: By restricting `dangerous_calls.append` to `if is_self_call:`, tensor operations such as `logits.to('cpu')` or `x.to('cpu')` are not registered as device mutations. When `self.to('cpu')` or `self.to(device='cpu')` is called inside `forward()`, `is_self_call` is True and the violation is registered.
3. **Premise 3 (Flaw 05 Keyword-Only Handling)**: In Python 3 AST, keyword-only parameters are stored in `item.args.kwonlyargs` with default AST nodes in `item.args.kw_defaults`. Pairing `kwonlyargs` with `kw_defaults` allows the detector to correctly recognize `def __init__(self, *, use_tta: bool = False):` without breaking positional default extraction.
4. **Premise 4 (Flaw 06 Direct Import & Error Handling)**:
   - Scanning `ast.ImportFrom` for `node.module == "torch"` (or starting with `torch.`) where `alias.name == "load"` maps aliases to `torch_load_funcs`. Any subsequent `Call` where `node.func.id in torch_load_funcs` is identified as `torch.load` and checked for `weights_only=True`.
   - When `--target-file` is specified, `ast.parse` is executed within an explicit `try-except` block; syntax errors return exit code 2 immediately, ensuring invalid inputs are rejected deterministically.
5. **Premise 5 (Flaw 07 Function-Scoped Mismatch Check)**:
   - Using `ScopeTracker(ast.NodeVisitor)` records the enclosing `ast.FunctionDef` / `ast.AsyncFunctionDef` for each `load_state_dict` call.
   - For calls specifying `strict=False`, validation searches exclusively within `call_info["scope"]`. Unrelated checks in other functions (e.g. `check_filename`) cannot satisfy the guard requirement for `load_state_dict`.
   - Local guards are detected by inspecting `ast.If` conditions for target variable identifiers (e.g., `m`, `u`, `missing`, `unexpected`) or keywords, coupled with an `ast.Raise` or `ast.Assert` in the branch body.

---

## 3. Caveats

- **No caveats**: All 4 target test scripts have been hardened and verified against both baseline flawed code and remediated/patched code.
- `git diff HEAD -- src/` returns 0 bytes. All modifications are confined strictly to `tests/adversarial/` and `.agents/worker_m2_remediation_r2/`.

---

## 4. Conclusion

The Milestone 2 Forensic Auditor veto has been completely remediated:
1. `src/` is 100% clean and identical to `HEAD` (0 bytes diff).
2. All 4 requested AST edge-cases in `tests/adversarial/` (Flaws 04, 05, 06, 07) have been hardened against false positives, false negatives, and CLI error conditions.
3. The entire 14-test adversarial suite achieves 100% detection (14/14 Exit 1) on the baseline repository and 100% pass (14/14 Exit 0) on patched inputs.
4. All CLI isolation and edge-case tests pass with exit code 0.

---

## 5. Verification Method

To independently verify these results:

1. **Verify Source Tree Cleanliness**:
   ```powershell
   git diff HEAD -- src/
   git status --porcelain src/
   ```
   *Expected*: Exactly 0 bytes output.

2. **Verify 14/14 Flaws Detected on Baseline**:
   ```powershell
   python tests/adversarial/run_all_adversarial_tests.py
   ```
   *Expected*: Exit code 0, reporting 14 / 14 flaws detected (Exit 1).

3. **Verify 14/14 Tests Pass on Patched Code**:
   ```powershell
   python .agents/worker_m2_adversarial/verify_patched_exit0.py
   ```
   *Expected*: Exit code 0, reporting all 14 scripts exit 0 on patched inputs.

4. **Verify Reviewer CLI Isolation**:
   ```powershell
   python .agents/reviewer_m2_1_g12/test_cli_isolation.py
   ```
   *Expected*: Exit code 0, `OVERALL RESULT: PASS`.

5. **Verify Specific AST Edge Cases**:
   ```powershell
   python .agents/worker_m2_remediation_r2/test_edge_cases.py
   ```
   *Expected*: Exit code 0, `ALL EDGE CASES RESULT: PASS`.
