# Comprehensive Adversarial Review Report: Flaws 01-07 Detection Suite

**Reviewer:** `reviewer_m2_1_g12`  
**Date:** 2026-09-10  
**Target Repository:** `M:\chakramodel`  
**Target Scope:** `tests/adversarial/test_flaw_01_no_skip_connections.py` through `tests/adversarial/test_flaw_07_strict_false_state_dict.py`  
**Parent Orchestrator:** `orchestrator_gen12` (`ba6ae91c-9868-4822-93f7-a3b0985f6f8d`)  

---

## 1. Review Summary

**Verdict**: **FAIL / REQUEST_CHANGES**

### Executive Summary
The automated adversarial detection suite authored in `tests/adversarial/` successfully achieves its baseline goal of running against the current repository and exiting `1` on all 7 assigned flaws (Flaws 01 through 07). The scripts exhibit good structure, informative diagnostic outputs, and utilize AST parsing rather than fragile textual regex matching.

However, rigorous adversarial stress-testing and boundary analysis uncovered **critical false-positive and false-negative vulnerabilities** in several detection scripts that will severely impede downstream remediation (Milestone 3) and compromise security verification:
1. **Flaw 04 (False Positive)**: Any benign tensor `.to('cpu')` operation inside `forward()` triggers a false detection of in-place module mutation, exiting `1` on valid remediated code.
2. **Flaw 06 (False Negative)**: Direct imports `from torch import load` bypass audit completely due to an unhandled `pass` statement, exiting `0` on unguarded loads. Furthermore, syntax errors in `--target-file` silently exit `0` rather than `2`.
3. **Flaw 07 (False Negative)**: Mismatch handling is audited globally across the entire AST without function scoping, meaning an unrelated `if 'missing' in ...: raise` anywhere in the file causes flawed `strict=False` calls to falsely pass with exit `0`.
4. **Flaw 05 (False Positive)**: Keyword-only argument defaults (`def __init__(self, *, use_tta: bool = False)`) are ignored in AST inspection, causing valid remediated classes to exit `1`.
5. **Codebase Workspace State**: Three files in `src/` (`src/models/chakranet_segmenter.py`, `src/chakra_transformer/transformer_segmenter.py`, `src/conformal/conformal_calibration.py`) are modified relative to `HEAD`, violating the requirement that primary source files remain 100% unmodified.

---

## 2. Review Findings by Dimension

### Finding 1 [Critical / Major] — False Positive on Legitimate Tensor Transfers in Flaw 04
- **What**: `tests/adversarial/test_flaw_04_oom_fallback.py` treats any tensor `.to('cpu')` call in `forward()` as an in-place module mutation `self.to('cpu')`.
- **Where**: `tests/adversarial/test_flaw_04_oom_fallback.py`, lines 44-48, 56.
- **Why**:
  ```python
  is_self_call = isinstance(sub.func.value, ast.Name) and sub.func.value.id == "self"
  if len(sub.args) >= 1:
      first_arg = sub.args[0]
      if isinstance(first_arg, ast.Constant) and first_arg.value == "cpu":
          dangerous_calls.append((sub.lineno, "self.to('cpu')" if is_self_call else "tensor.to('cpu')"))
  ```
  Both `self.to('cpu')` and `tensor.to('cpu')` are appended to `dangerous_calls`. The failure condition `if dangerous_calls or text_has_self_to_cpu:` then triggers `[FAIL] FLAW 04 DETECTED` on normal tensor operations like `return x.to('cpu')`.
- **Proof of Vulnerability**:
  Running `test_flaw_04_oom_fallback.py` against:
  ```python
  class M(nn.Module):
      def forward(self, x):
          return x.to('cpu')
  ```
  Exits `1` with: `Scanned forward() methods for self.to('cpu') calls: [(3, "tensor.to('cpu')")]`.
- **Suggested Remediation**:
  Only append to `dangerous_calls` if `is_self_call is True`.

---

### Finding 2 [Major] — False Negative and Inconsistent Exit Code in Flaw 06
- **What**: `tests/adversarial/test_flaw_06_unguarded_torch_load.py` misses direct imports of `load` and silently exits `0` on syntax errors.
- **Where**: `tests/adversarial/test_flaw_06_unguarded_torch_load.py`, lines 33-36, 44-46.
- **Why**:
  ```python
  elif isinstance(node.func, ast.Name) and node.func.id == "load":
      # Check if torch.load was directly imported
      pass
  ```
  The direct import branch contains only a comment and `pass`. An unsafe file with `from torch import load; sd = load("weights.pth")` returns `0` (passes audit).
  Additionally, when `ast.parse` fails on a malformed file passed via `--target-file`, `check_file` catches `Exception` and returns an empty list of violations. The script outputs `[PASS] Flaw 06 Resolved` with exit `0` instead of exit `2`.
- **Proof of Vulnerability**:
  Running against `from torch import load; sd = load('m.pth')` exits `0` (`[PASS] Flaw 06 Resolved`).
  Running against syntax error `def invalid ::: ((` exits `0` (`[PASS] Flaw 06 Resolved`).
- **Suggested Remediation**:
  1. Implement direct import detection for `from torch import load`.
  2. In `check_flaw_06`, if `--target-file` fails `ast.parse`, return exit code `2`.

---

### Finding 3 [Major] — False Negative via Global AST Un-scoped Mismatch Check in Flaw 07
- **What**: `tests/adversarial/test_flaw_07_strict_false_state_dict.py` checks for exception handling globally rather than within the function calling `load_state_dict`.
- **Where**: `tests/adversarial/test_flaw_07_strict_false_state_dict.py`, lines 55-66, 72.
- **Why**:
  ```python
  has_raise_on_mismatch = False
  for node in ast.walk(tree):
      if isinstance(node, ast.If):
          test_str = ast.unparse(node.test)
          if "missing" in test_str or "unexpected" in test_str:
              for stmt in node.body:
                  if isinstance(stmt, ast.Raise):
                      has_raise_on_mismatch = True
  ```
  `has_raise_on_mismatch` is set to `True` for the entire file if any function contains `if 'missing' in ...: raise`. Any unguarded `model.load_state_dict(sd, strict=False)` in a separate function or class in that same file then passes verification.
- **Proof of Vulnerability**:
  A file containing an unrelated data check `if 'missing' in filename: raise ValueError()` alongside an unguarded `self.net.load_state_dict(sd, strict=False)` passes with exit `0`.
- **Suggested Remediation**:
  Scope the mismatch check to the enclosing function or method where `load_state_dict()` is called.

---

### Finding 4 [Minor] — False Positive on Keyword-Only Arguments in Flaw 05
- **What**: `tests/adversarial/test_flaw_05_tta_enabled_by_default.py` fails to recognize `use_tta=False` defined as a keyword-only argument.
- **Where**: `tests/adversarial/test_flaw_05_tta_enabled_by_default.py`, lines 54-58.
- **Why**:
  The script inspects `item.args.args` and `item.args.defaults`. In Python 3, keyword-only arguments reside in `item.args.kwonlyargs` and `item.args.kw_defaults`.
- **Proof of Vulnerability**:
  Running against:
  ```python
  class ChakraNet:
      def __init__(self, *, use_tta: bool = False):
          self.use_tta = use_tta
  ```
  Exits `1` with: `ChakraNet.__init__ has use_tta=False default: False`.
- **Suggested Remediation**:
  Inspect both positional argument defaults and `kwonlyargs`/`kw_defaults`.

---

### Finding 5 [Minor] — Brittleness on Direct Function Import in Flaw 02
- **What**: `tests/adversarial/test_flaw_02_dead_imagenet_head.py` assumes `timm.create_model` is an `ast.Attribute`.
- **Where**: `tests/adversarial/test_flaw_02_dead_imagenet_head.py`, line 40.
- **Why**:
  If refactored to `from timm import create_model; create_model(...)`, `node.func` is `ast.Name`, triggering `[ERROR] No timm.create_model call found` (exit `2`).
- **Suggested Remediation**:
  Support `isinstance(node.func, ast.Name) and node.func.id == "create_model"`.

---

### Finding 6 [Workspace Integrity] — Primary Source Files in `src/` are Modified
- **What**: Git working tree and staging show modified files in `src/`.
- **Where**:
  - `src/models/chakranet_segmenter.py` (working tree modification)
  - `src/chakra_transformer/transformer_segmenter.py` (working tree modification)
  - `src/conformal/conformal_calibration.py` (staged modification)
- **Why**:
  Task 3 requires: *"Verify that primary source files in M:\chakramodel\src\ remain 100% unmodified."*
  While the tests in `tests/adversarial/` did not modify these files (edits appear to have been made by concurrent agents adding docstrings/annotations), the workspace condition is not 100% clean relative to baseline HEAD.

---

## 3. Verified Claims & Test Executions

| Test Script | Execution on Baseline Codebase | Exit Code | Diagnostic Message Clarity | Integrity / Facade Check | Status |
|---|---|---|---|---|---|
| `test_flaw_01_no_skip_connections.py` | `src/models/chakranet_segmenter.py` | 1 | High (details 16x16 patch restriction & vanishing polyps) | Genuine AST traversal | Verified |
| `test_flaw_02_dead_imagenet_head.py` | `src/models/chakranet_segmenter.py` | 1 | High (details 1.025M dead params, 309M inflation) | Genuine AST traversal | Verified |
| `test_flaw_03_dead_code.py` | `src/models/chakranet_segmenter.py` | 1 | High (exposes unused PraNet/RFB/RA illusion) | Genuine AST traversal | Verified |
| `test_flaw_04_oom_fallback.py` | `src/models/chakranet_segmenter.py` | 1 | High (explains multithreading race condition) | Flawed AST check (Finding 1) | Flawed |
| `test_flaw_05_tta_enabled_by_default.py` | `src/models/chakranet_segmenter.py` | 1 | High (explains 3x latency penalty & metric conflation) | Minor AST gap (Finding 4) | Verified with caveats |
| `test_flaw_06_unguarded_torch_load.py` | Full workspace (src, scripts, kaggle) | 1 | High (lists 31 files & line numbers, CWE-502) | False negative & exit code gap (Finding 2) | Flawed |
| `test_flaw_07_strict_false_state_dict.py` | `src/models/chakranet_segmenter.py` | 1 | High (details 0/312 keys loaded, Dice 0.1835 collapse) | Global un-scoped AST check (Finding 3) | Flawed |

---

## 4. Verification Method for Orchestrator & Remediators

To verify the findings highlighted in this report:

1. **Verify Baseline Detection (Exit 1)**:
   ```powershell
   python tests/adversarial/test_flaw_01_no_skip_connections.py
   python tests/adversarial/test_flaw_02_dead_imagenet_head.py
   python tests/adversarial/test_flaw_03_dead_code.py
   python tests/adversarial/test_flaw_04_oom_fallback.py
   python tests/adversarial/test_flaw_05_tta_enabled_by_default.py
   python tests/adversarial/test_flaw_06_unguarded_torch_load.py
   python tests/adversarial/test_flaw_07_strict_false_state_dict.py
   ```
   *Result*: All 7 scripts correctly exit 1 on the existing repository.

2. **Verify Adversarial Edge-Cases & Flaws**:
   Run the isolation suite created during this review:
   ```powershell
   python .agents/reviewer_m2_1_g12/test_cli_isolation.py
   ```
   *Result*: Fails on Flaw 04 (false positive on tensor `.to('cpu')`), Flaw 06 (exit code 0 on syntax error), Flaw 06 (false negative on direct import), and Flaw 07 (global un-scoped bypass).

3. **Verify Git Modifications in `src/`**:
   ```powershell
   & "C:\Users\imgk3\AppData\Local\GitHubDesktop\app-3.6.3\resources\app\git\cmd\git.exe" status --porcelain src/
   ```

---

## 5. Conclusion & Actionable Next Steps

The detection scripts represent a solid foundation, but the author (`worker_m2_adversarial`) must address the false-positive and false-negative AST flaws before this suite can be safely used as an automated gating harness for Milestone 3 remediation:
1. Fix `test_flaw_04_oom_fallback.py` to only flag `sub.func.value.id == "self"`.
2. Fix `test_flaw_06_unguarded_torch_load.py` to handle direct `load` imports and exit `2` on syntax errors.
3. Fix `test_flaw_07_strict_false_state_dict.py` to scope mismatch validation to the local method context.
4. Fix `test_flaw_05_tta_enabled_by_default.py` to inspect `kwonlyargs`.
5. Revert or cleanly commit unintentional annotations in `src/` to ensure a 100% clean baseline.
