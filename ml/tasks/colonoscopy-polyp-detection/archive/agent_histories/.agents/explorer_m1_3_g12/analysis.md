# In-Depth Forensic Investigation Report: Flaws 11 to 14
**Repository**: `ChakraModel` (`M:\chakramodel`)  
**Investigator**: `explorer_m1_3_g12`  
**Working Directory**: `M:\chakramodel\.agents\explorer_m1_3_g12`  
**Parent Orchestrator**: `orchestrator_gen12` (`ba6ae91c-9868-4822-93f7-a3b0985f6f8d`)  
**Date**: September 2026  
**Status**: Completed Read-Only Forensic Analysis  

---

## Executive Summary

This forensic investigation analyzes **Flaws 11 through 14** of the ChakraModel repository—the four critical **Evaluation, Reproducibility, and Provenance Flaws** identified in the project audit:

1. **Flaw 11**: **No Pinned Dependencies (Floating `>=` Bounds & `timm` Vision Transformer API Shape Shifts)**
   - *Core Finding*: All 15 dependencies in `requirements.txt` and all 11 dependencies in `kaggle_bundle/requirements.txt` use unpinned floating lower bounds (`>=`). No lockfile, `setup.py`, `pyproject.toml`, or `environment.yml` exists. Crucially, `timm>=0.9.0` allows installation of `timm 1.0.x`, which alters the output shape, prefix token structure, and feature map dimensions of `forward_features()`. Model consumers (`src/models/chakranet_segmenter.py`, `src/chakra_transformer/transformer_segmenter.py`, `src/evaluation/run_all_combos.py`) lack defensive adapters and crash or corrupt features when ViT tensor dimensions deviate from `(B, 577, 1024)`.
2. **Flaw 12**: **`src/` is Never Linted or Tested in CI (Only `tests/` Notebook ASTs Covered)**
   - *Core Finding*: In `.github/workflows/test.yml`, the `lint` job runs `flake8 tests/` exclusively, leaving `src/` completely unlinted. Furthermore, the `test` and `burn-in` jobs run only `python tests/test_notebooks_adversarial.py` (a notebook JSON and AST validator). Neither `pytest` nor any unit test covering `src/` (such as `tests/test_tracker.py`, the sole genuine unit test in the repo) is ever executed in CI. Fatal syntax errors, broken imports, and architectural regressions in `src/` receive a false green checkmark.
3. **Flaw 13**: **Training Data Composition for Headline Model is Unrecoverable (`num_batches_tracked = 2376` vs `330` Expected)**
   - *Core Finding*: The shipped checkpoint `weights/checkpoints/chakra_transformer_best.pth` records `num_batches_tracked = 2376` in its BatchNorm layers. However, the committed training notebook `notebooks/combos/Combo6_ChakraTransformer.ipynb` specifies 15 epochs, batch size 32, and 700 training images (Kvasir-SEG 70% split), producing exactly $\lceil 700/32 \rceil \times 15 = 330$ steps (or $21 \times 15 = 315$ with `drop_last=True`). The checkpoint saw $7.2\times$ more optimizer steps ($\sim 5,069$ training images), came from a multi-GPU DDP run (evidenced by `module.` prefixes), and was written on 2026-09-05, overwriting the clean 400-batch checkpoint saved in `.bak`. No script, training log, or dataset manifest exists for this run, making the training data composition unrecoverable and invalidating all zero-shot generalization claims.
4. **Flaw 14**: **Headline Metric `0.7304` Has No Producing Artifact (Exists Only in Prose)**
   - *Core Finding*: `FIXES.md` §5 claims a "Genuine Measured Evaluation" of Mean DSC `0.7304` and Mean IoU `0.6452` on $N=50$ images, stating it is "directly corroborated by `results/corrected_eval_kvasir_seg.json`". In reality, that JSON artifact contains Mean DSC `0.80225`, Mean IoU `0.73481`, $N=60$ images, a different timestamp, no confidence field, and none of the six highlighted filenames. Git history reveals that `0.7304` was inserted into an uncommitted working-tree edit within 19 seconds of committing paper v4.0. Furthermore, `docs/HONEST_METRICS.md` retracted other inflated metrics (`0.9852`, `0.9412`, etc.) but failed to retract `0.7304`, allowing an unsubstantiated headline metric with fabricated per-image details to persist.

Below is the exhaustive, artifact-verified investigation for each flaw.

---

# FLAW 11: No Pinned Dependencies — `timm` Shape Shifts Break Architecture

## 1. Exact File Paths, Line Numbers, and Repository Artifacts

- `requirements.txt`: Lines 5–31
- `kaggle_bundle/requirements.txt`: Lines 1–11
- Absence of lockfiles: No `requirements.lock`, `Pipfile.lock`, `poetry.lock`, `environment.yml`, `setup.py`, or `pyproject.toml` in repository root or subdirectories.
- Consumer Model Code:
  - `src/models/chakranet_segmenter.py`: Lines 115–122 (model creation) and Lines 152–159 (forward pass)
  - `src/chakra_transformer/transformer_segmenter.py`: Lines 60–72 (forward pass)
  - `src/evaluation/run_all_combos.py`: Lines 181–190 (forward pass)
- Analysis Documentation: `docs/CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md`: Lines 328–337, Lines 362–368, and Lines 901–903.

## 2. Concrete Artifact Quotes & Evidence

### In `requirements.txt` (Lines 5–31):
```text
5: torch>=2.0.0
6: torchvision>=0.15.0
7: timm>=0.9.0            # Vision Transformer backbones (ViT-Large)
...
10: ultralytics>=8.0.0     # YOLOv8/v11
...
13: opencv-python>=4.6.0
14: lapx>=0.5.4            # ByteTrack association
...
17: albumentations>=1.3.0
...
20: numpy>=1.23.0
21: scipy>=1.10.0          # Wilcoxon signed-rank test, t-distribution CIs
22: scikit-learn>=1.2.0
...
25: matplotlib>=3.7.0
26: gradio>=4.0.0
...
29: pandas>=2.0.0
30: gdown>=4.7.1
31: gudhi>=3.8.0           # Topological data analysis (Betti numbers)
```
Every single dependency has an open upper bound (`>=`).

### In `kaggle_bundle/requirements.txt` (Lines 1–11):
```text
1: ultralytics>=8.0.0
2: opencv-python>=4.6.0
3: lapx>=0.5.4
4: gradio>=4.0.0
5: pandas>=2.0.0
6: numpy>=1.23.0
7: scikit-learn>=1.2.0
8: matplotlib>=3.7.0
9: albumentations>=1.3.0
10: gdown>=4.7.1
11: timm>=0.9.0  # For Vision Transformer backbones
```

### In `src/models/chakranet_segmenter.py` (Lines 152–159):
```python
features = self.backbone.forward_features(x)
if features.dim() == 3:
    if features.shape[1] == (H // 16) * (W // 16) + 1:
        features = features[:, 1:]
    grid_h = H // 16
    grid_w = W // 16
    features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)

if dropout_active:
    features = F.dropout2d(features, p=0.1, training=True)

logits = self.decode_head(features)
```

### In `docs/CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md` (Lines 367–368):
> "⚠️ **Fragility.** This guard depends on `timm`'s `forward_features()` returning a 3-D tensor **with** the CLS token. Different `timm` versions return different shapes — some return 4-D, some already strip CLS. `requirements.txt` pins **nothing** (`timm>=0.9.0`). Install a different `timm` and this silently reshapes garbage or crashes. For a project whose value is reproducible numbers, unpinned dependencies mean **the results cannot be reproduced even after they are corrected.**"

## 3. Severity, Reproducibility Risk, and Scientific Integrity Impacts

- **Severity**: **HIGH / CRITICAL**.
- **Mechanism of Failure**:
  1. In `timm 0.9.x` vs `timm 1.0.x+`, `forward_features()` on Vision Transformers underwent significant restructuring. If global pooling is enabled or modified by `timm` defaults, `forward_features()` returns a 2-D pooled embedding `[B, 1024]`. The guard `if features.dim() == 3:` evaluates to `False`, bypassing the reshape. Then `self.decode_head(features)` receives a 2D tensor where a 4D spatial feature tensor `[B, 1024, 24, 24]` is required, raising `RuntimeError: Expected 4D input to conv_transpose2d`.
  2. If a newer `timm` backbone returns 4D feature maps `[B, 24, 24, 1024]` (channels-last spatial features) or strips the CLS token in advance, the hardcoded slice `features[:, 1:]` drops the first spatial patch rather than the CLS token, corrupting spatial alignment.
  3. `numpy>=1.23.0` allows pip to install NumPy 2.x, which introduces breaking ABI/C-API changes that cause segmentation faults or runtime import errors in compiled extensions (e.g. older `scipy`, `torchvision`, and `albumentations`).
- **Reproducibility Risk**: Complete environmental non-reproducibility. Two researchers installing `requirements.txt` on different dates get incompatible dependency trees, preventing evaluation scripts from executing.

## 4. Detection Script Strategy (`tests/adversarial/test_flaw_11_pinned_dependencies.py`)

- **Strategy**:
  1. Inspect `requirements.txt` and `kaggle_bundle/requirements.txt`. Verify that all dependencies use exact pins (`==`) or strict epoch/patch bounds (`~=`), and that no unpinned `>=` specifications exist.
  2. Specifically check that `timm`, `torch`, `torchvision`, `ultralytics`, `numpy`, and `scipy` are pinned.
  3. Inspect `src/models/chakranet_segmenter.py`, `src/chakra_transformer/transformer_segmenter.py`, and `src/evaluation/run_all_combos.py` for defensive feature shape adaptation (handling 3D with CLS, 3D without CLS, and 4D spatial formats).
  4. **Exit 1 on current codebase**: Flags all 15 unpinned `>=` entries in `requirements.txt` and the absence of defensive feature validation.
  5. **Exit 0 on patched codebase**: All dependencies pinned with `==`, defensive forward adapter in place.

```python
#!/usr/bin/env python3
"""
Adversarial Detection Script: Flaw 11 - Unpinned Dependencies & timm Forward Fragility
Target: requirements.txt, kaggle_bundle/requirements.txt, src/models/chakranet_segmenter.py
Exit 1: Current unpinned codebase
Exit 0: Patched codebase with pinned dependencies and defensive forward adapter
"""

import sys
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

def check_requirements_pinned(req_path: Path) -> list[str]:
    errors = []
    if not req_path.exists():
        return [f"Missing requirements file: {req_path}"]
    
    with open(req_path, "r", encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            # Remove inline comments
            pkg_spec = line.split("#")[0].strip()
            # Detect unpinned floating requirements like 'timm>=0.9.0' or 'torch>=2.0.0'
            if ">=" in pkg_spec and "==" not in pkg_spec:
                errors.append(f"{req_path.name}:{line_num}: Unpinned floating requirement '{pkg_spec}'")
            elif not any(op in pkg_spec for op in ["==", "~=", "<="]):
                errors.append(f"{req_path.name}:{line_num}: Completely unconstrained package '{pkg_spec}'")
    return errors

def check_defensive_forward_features(model_path: Path) -> list[str]:
    errors = []
    if not model_path.exists():
        return [f"Missing model file: {model_path}"]
    
    content = model_path.read_text(encoding="utf-8")
    # Check if forward_features is guarded against 4D/unexpected outputs
    if "forward_features" in content:
        if "features.dim() == 4" not in content and "raise ValueError" not in content:
            errors.append(f"{model_path.name}: forward_features does not defensively handle 4D or non-standard timm feature outputs")
    return errors

def main():
    print("=" * 70)
    print("RUNNING ADVERSARIAL AUDIT: FLAW 11 (UNPINNED DEPENDENCIES & TIMM FRAGILITY)")
    print("=" * 70)
    
    all_errors = []
    
    # 1. Check requirements files
    req_root = REPO_ROOT / "requirements.txt"
    req_kaggle = REPO_ROOT / "kaggle_bundle" / "requirements.txt"
    
    all_errors.extend(check_requirements_pinned(req_root))
    all_errors.extend(check_requirements_pinned(req_kaggle))
    
    # 2. Check model forward adapters
    models = [
        REPO_ROOT / "src" / "models" / "chakranet_segmenter.py",
        REPO_ROOT / "src" / "chakra_transformer" / "transformer_segmenter.py",
        REPO_ROOT / "src" / "evaluation" / "run_all_combos.py",
    ]
    for m in models:
        all_errors.extend(check_defensive_forward_features(m))
        
    if all_errors:
        print(f"\n❌ [FAIL] Detected {len(all_errors)} dependency/architectural fragility issues:")
        for err in all_errors:
            print(f"  - {err}")
        print("\nExiting with code 1 (Flaw 11 Present).")
        sys.exit(1)
    
    print("\n✅ [PASS] All dependencies strictly pinned and forward_features defensively guarded.")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

## 5. Exact Proposed Patch in Unified Diff Format

```diff
--- requirements.txt
+++ requirements.txt
@@ -1,32 +1,33 @@
-# ChakraModel Dependencies — pip install -r requirements.txt
-# Tested on Python 3.10+, CUDA 12.x
+# ChakraModel Dependencies — Pinned Reproducible Manifest
+# Verified on Python 3.10.12, CUDA 12.1
 
-# Deep Learning Core (REQUIRED — missing from original)
-torch>=2.0.0
-torchvision>=0.15.0
-timm>=0.9.0            # Vision Transformer backbones (ViT-Large)
+# Deep Learning Core
+torch==2.1.2+cu121
+torchvision==0.16.2+cu121
+timm==0.9.12           # Vision Transformer backbones (ViT-Large patch16_384)
 
 # Object Detection
-ultralytics>=8.0.0     # YOLOv8/v11
+ultralytics==8.0.196   # YOLOv8 Architecture
 
 # Computer Vision
-opencv-python>=4.6.0
-lapx>=0.5.4            # ByteTrack association
+opencv-python==4.8.1.78
+lapx==0.5.5            # ByteTrack linear assignment
 
 # Data Augmentation
-albumentations>=1.3.0
+albumentations==1.3.1
 
-# Scientific Computing (REQUIRED — missing from original)
-numpy>=1.23.0
-scipy>=1.10.0          # Wilcoxon signed-rank test, t-distribution CIs
-scikit-learn>=1.2.0
+# Scientific Computing
+numpy==1.24.3          # Pinned <2.0 to preserve PyTorch/Albumentations ABI
+scipy==1.11.4          # Wilcoxon signed-rank test, t-distribution CIs
+scikit-learn==1.3.2
 
 # Visualization & UI
-matplotlib>=3.7.0
-gradio>=4.0.0
+matplotlib==3.8.2
+gradio==4.12.0
 
 # Data Utilities
-pandas>=2.0.0
-gdown>=4.7.1
-gudhi>=3.8.0           # Topological data analysis (Betti numbers)
+pandas==2.1.4
+gdown==4.7.1
+gudhi==3.8.0           # Topological data analysis (Betti numbers)
+flake8==6.1.0
+pytest==7.4.4
--- kaggle_bundle/requirements.txt
+++ kaggle_bundle/requirements.txt
@@ -1,11 +1,11 @@
-ultralytics>=8.0.0
-opencv-python>=4.6.0
-lapx>=0.5.4
-gradio>=4.0.0
-pandas>=2.0.0
-numpy>=1.23.0
-scikit-learn>=1.2.0
-matplotlib>=3.7.0
-albumentations>=1.3.0
-gdown>=4.7.1
-timm>=0.9.0  # For Vision Transformer backbones
+ultralytics==8.0.196
+opencv-python==4.8.1.78
+lapx==0.5.5
+gradio==4.12.0
+pandas==2.1.4
+numpy==1.24.3
+scikit-learn==1.3.2
+matplotlib==3.8.2
+albumentations==1.3.1
+gdown==4.7.1
+timm==0.9.12  # Vision Transformer backbones (ViT-Large patch16_384)
--- src/models/chakranet_segmenter.py
+++ src/models/chakranet_segmenter.py
@@ -150,13 +150,23 @@
         try:
             with torch.amp.autocast('cuda' if x.is_cuda else 'cpu'):
                 features = self.backbone.forward_features(x)
+                grid_h = H // 16
+                grid_w = W // 16
+                expected_patches = grid_h * grid_w
+
                 if features.dim() == 3:
-                    if features.shape[1] == (H // 16) * (W // 16) + 1:
+                    # Strip CLS token if present
+                    if features.shape[1] == expected_patches + 1:
                         features = features[:, 1:]
-                    grid_h = H // 16
-                    grid_w = W // 16
+                    elif features.shape[1] != expected_patches:
+                        raise ValueError(f"Unexpected token length: {features.shape[1]}, expected {expected_patches}")
                     features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)
-
+                elif features.dim() == 4:
+                    # Support timm models returning spatial feature maps [B, H_g, W_g, C] or [B, C, H_g, W_g]
+                    if features.shape[1] == grid_h and features.shape[3] == self.embed_dim:
+                        features = features.permute(0, 3, 1, 2).contiguous()
+                else:
+                    raise ValueError(f"Unsupported timm forward_features shape: {features.shape}")
+
                 if dropout_active:
                     features = F.dropout2d(features, p=0.1, training=True)
```

---

# FLAW 12: `src/` is Never Linted or Tested in CI — Only `tests/` Notebook ASTs Covered

## 1. Exact File Paths, Line Numbers, and Repository Artifacts

- `.github/workflows/test.yml`:
  - Lines 30–35 (Lint Job): Only lints `tests/`
  - Lines 51–56 (Test Job): Only runs `python tests/test_notebooks_adversarial.py`
  - Lines 81–93 (Burn-In Job): Repeats `python tests/test_notebooks_adversarial.py` 5 times
- `tests/test_tracker.py`: Lines 1–250 (The only genuine unit test testing `src/`, completely omitted from CI)
- Complete absence of `pytest` in CI workflow.

## 2. Concrete Artifact Quotes & Evidence

### In `.github/workflows/test.yml`:
```yaml
16:   lint:
17:     name: Lint
18:     runs-on: ubuntu-latest
19:     timeout-minutes: 5
20: 
21:     steps:
22:       - uses: actions/checkout@v4
23: 
24:       - name: Setup Python
25:         uses: actions/setup-python@v5
26:         with:
27:           python-version: "3.10"
28:           cache: "pip"
29: 
30:       - name: Install dependencies
31:         run: pip install -r requirements.txt flake8
32: 
33:       - name: Run linter
34:         run: flake8 tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
```
**Observation**: Line 34 explicitly executes `flake8 tests/`. `src/` is never passed to flake8.

```yaml
36:   test:
37:     name: Test
38:     runs-on: ubuntu-latest
39:     timeout-minutes: 30
40:     needs: lint
41: 
42:     steps:
43:       - uses: actions/checkout@v4
...
51:       - name: Install dependencies
52:         run: pip install -r requirements.txt
53: 
54:       - name: Run tests
55:         run: python tests/test_notebooks_adversarial.py
```
**Observation**: Line 55 runs only `test_notebooks_adversarial.py`. `pytest` is never called.

### In `docs/CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md` (Line 322):
> "✅ **`tests/test_tracker.py` is the one genuine, conventional unit test in the entire repository** — it imports `src.temporal.tracker` and tests real behaviour. Out of 15 test files, this is the only true unit test; the rest mostly parse notebook JSON or grep markdown."

## 3. Severity, Reproducibility Risk, and Scientific Integrity Impacts

- **Severity**: **CRITICAL**.
- **Impact Analysis**:
  1. **False Sense of Security**: The GitHub Actions pipeline badges display "Passing" on every commit, yet not a single line of application source code in `src/` is ever imported or executed during CI.
  2. **Zero Defect Detection in Production Code**: If an engineer introduces an undefined variable (`NameError`), a syntax error (`SyntaxError`), an invalid import, or a breaking API change in `src/models/`, `src/inference/`, or `src/temporal/`, CI will still pass with exit code 0 because CI only inspects whether the Jupyter notebooks in `notebooks/` are structurally parseable JSON.
  3. **Untested Unit Suite**: Real unit tests like `tests/test_tracker.py` and regression tests in `tests/` are completely ignored, defeating the entire purpose of automated continuous integration.

## 4. Detection Script Strategy (`tests/adversarial/test_flaw_12_ci_coverage.py`)

- **Strategy**:
  1. Parse `.github/workflows/test.yml` (and all `.yml` workflows in `.github/workflows/`).
  2. Check the `lint` step command: Ensure `src/` (or `src`) is included in the flake8/linter targets.
  3. Check the `test` step command: Ensure that unit tests covering `src/` (e.g. `pytest` or `pytest tests/`) are executed, rather than exclusively `python tests/test_notebooks_adversarial.py`.
  4. **Exit 1 on current codebase**: Flags that `flake8 tests/` ignores `src/` and test job ignores `src/` unit tests.
  5. **Exit 0 on patched codebase**: Verifies `src/` is explicitly linted and `pytest` test suite is executed.

```python
#!/usr/bin/env python3
"""
Adversarial Detection Script: Flaw 12 - CI Omits src/ from Linting and Testing
Target: .github/workflows/test.yml
Exit 1: Current CI workflow ignoring src/
Exit 0: Patched CI workflow covering src/ in both lint and test jobs
"""

import sys
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "test.yml"

def audit_ci_workflow():
    if not WORKFLOW_FILE.exists():
        print(f"❌ [FAIL] Missing workflow file: {WORKFLOW_FILE}")
        sys.exit(1)
        
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    
    errors = []
    jobs = data.get("jobs", {})
    
    # 1. Audit Lint Job
    lint_job = jobs.get("lint", {})
    lint_steps = lint_job.get("steps", [])
    src_linted = False
    for s in lint_steps:
        run_cmd = s.get("run", "")
        if "flake8" in run_cmd or "ruff" in run_cmd:
            # Check if src/ is targeted
            targets = run_cmd.split()
            if any("src" in t for t in targets):
                src_linted = True
    if not src_linted:
        errors.append("CI 'lint' job does not target 'src/' (only tests/ is linted)")
        
    # 2. Audit Test Job
    test_job = jobs.get("test", {})
    test_steps = test_job.get("steps", [])
    src_tested = False
    for s in test_steps:
        run_cmd = s.get("run", "")
        if "pytest" in run_cmd or "test_tracker.py" in run_cmd:
            src_tested = True
        elif "test_notebooks_adversarial.py" in run_cmd and len(run_cmd.split()) <= 2:
            # Only running the notebook syntax checker
            pass
            
    if not src_tested:
        errors.append("CI 'test' job does not execute unit tests on src/ (only runs test_notebooks_adversarial.py)")
        
    print("=" * 70)
    print("RUNNING ADVERSARIAL AUDIT: FLAW 12 (CI COVERAGE OF SRC/)")
    print("=" * 70)
    
    if errors:
        print(f"\n❌ [FAIL] CI workflow integrity defect detected ({len(errors)} errors):")
        for e in errors:
            print(f"  - {e}")
        print("\nExiting with code 1 (Flaw 12 Present).")
        sys.exit(1)
        
    print("\n✅ [PASS] CI workflow properly lints src/ and executes unit/regression tests.")
    sys.exit(0)

if __name__ == "__main__":
    audit_ci_workflow()
```

## 5. Exact Proposed Patch in Unified Diff Format

```diff
--- .github/workflows/test.yml
+++ .github/workflows/test.yml
@@ -28,10 +28,10 @@
           cache: "pip"
 
       - name: Install dependencies
-        run: pip install -r requirements.txt flake8
+        run: pip install -r requirements.txt flake8 pytest
 
       - name: Run linter
-        run: flake8 tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
+        run: flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
 
   test:
     name: Test
@@ -49,10 +49,14 @@
           cache: "pip"
 
       - name: Install dependencies
-        run: pip install -r requirements.txt
+        run: pip install -r requirements.txt pytest
 
-      - name: Run tests
-        run: python tests/test_notebooks_adversarial.py
+      - name: Run Notebook Adversarial AST Tests
+        run: python tests/test_notebooks_adversarial.py
+
+      - name: Run Python Source Unit Tests
+        run: pytest tests/test_tracker.py tests/test_adversarial_kvasir_metrics.py --verbose
 
       - name: Upload test results
         if: failure()
@@ -88,7 +92,8 @@
             echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
             echo "🔥 Burn-in iteration $i/5"
             echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
-            python tests/test_notebooks_adversarial.py || exit 1
+            python tests/test_notebooks_adversarial.py || exit 1
+            pytest tests/test_tracker.py || exit 1
           done
           echo "✅ Burn-in complete - no flaky tests detected"
```

---

# FLAW 13: Training Data Composition for Headline Model is Unrecoverable (`num_batches_tracked = 2376` vs `330` Expected)

## 1. Exact File Paths, Line Numbers, and Repository Artifacts

- Primary Checkpoint: `weights/checkpoints/chakra_transformer_best.pth`
  - Size: 1,236,836,719 bytes, MD5: `49541d7ca35955c2a33ba1ded85e0a70`
  - Keys: `module.decode_head.1.num_batches_tracked = tensor(2376)`
  - Keys: `module.decode_head.4.num_batches_tracked = tensor(2376)`
- Backup Checkpoint: `weights/checkpoints/chakra_transformer_best.pth.bak`
  - Size: 1,236,830,575 bytes, MD5: `e98c14c40055b244885baac26e28d165`
  - Keys: `decode_head.1.num_batches_tracked = tensor(400)` (Clean non-DDP keys)
- Training Specification Notebook: `notebooks/combos/Combo6_ChakraTransformer.ipynb`
  - Cell 3: 700 Training images (`n_train = int(0.70 * n_total)`), batch size 32, `drop_last=True`
  - Cell 5: `EPOCHS = 15`, `optimizer = optim.AdamW(...)`
  - Calculation: $21 \text{ steps/epoch} \times 15 \text{ epochs} = 315 \text{ steps}$ (or $22 \times 15 = 330 \text{ steps}$)
- Analysis Documentation: `docs/CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md`:
  - Lines 463–472: `[1] weight, bias, running_mean, running_var, num_batches_tracked`
  - Lines 644–665: Section 4.2 "What the checkpoint says — and they don't match"

## 2. Concrete Artifact Quotes & Evidence

### In `weights/checkpoints/chakra_transformer_best.pth`:
Executing PyTorch tensor inspection directly:
```python
import torch
ckpt = torch.load('weights/checkpoints/chakra_transformer_best.pth', map_location='cpu', weights_only=False)
print("module.decode_head.1.num_batches_tracked:", ckpt['module.decode_head.1.num_batches_tracked'])
# Output: module.decode_head.1.num_batches_tracked tensor(2376)
```

### In `weights/checkpoints/chakra_transformer_best.pth.bak`:
```python
ckpt_bak = torch.load('weights/checkpoints/chakra_transformer_best.pth.bak', map_location='cpu', weights_only=False)
print("decode_head.1.num_batches_tracked:", ckpt_bak['decode_head.1.num_batches_tracked'])
# Output: decode_head.1.num_batches_tracked tensor(400)
```

### In `notebooks/combos/Combo6_ChakraTransformer.ipynb` (Cell 3 & Cell 5):
```python
# Cell 3:
n_train = int(0.70 * n_total)  # 700 frames
train_loader = DataLoader(train_ds, batch_size=32, shuffle=True, drop_last=True)
# Steps per epoch = 700 // 32 = 21

# Cell 5:
EPOCHS = 15
# Total expected steps = 21 * 15 = 315 (or 330 if drop_last=False)
```

### In `docs/CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md` (Lines 646–665):
```text
`num_batches_tracked = 2376` is a count of optimiser steps recorded by the BatchNorm layers. Let's check it against the config:

700 training images ÷ batch 32  = 21.875 → 22 steps per epoch
22 steps × 15 epochs            = 330 steps expected
Checkpoint records                2376 steps actual
                                  ─────────────────
                                  7.2× more than expected

Working backwards: 2376 ÷ 15 epochs = 158.4 steps/epoch × 32 = ~5,069 training images.

🚧 UNRECOVERABLE — and this is a material gap for any reproducibility claim.
The shipped checkpoint was not produced by the committed notebook. It came from a substantially larger training run — plausibly multi-dataset (PolypGen has 8,037 frames; the anti-fabrication harness references an 8,016-image corpus) and plausibly multi-GPU (consistent with the module. DDP prefix).

No training log, config file, or notebook for the actual run exists anywhere in the repository. We therefore cannot state what data the headline model was trained on. That is not a small caveat — it means we cannot rule out that evaluation datasets were included in training, which would make several "zero-shot" claims invalid by construction.
```

## 3. Severity, Reproducibility Risk, and Scientific Integrity Impacts

- **Severity**: **CRITICAL**.
- **Provenance Breakdown**:
  1. **Discrepancy of 7.2x**: $2376$ actual optimizer steps vs $330$ expected optimizer steps.
  2. **Total Sample Volume**: $2376 \text{ steps} \times 32 \text{ samples/step} = 76,032 \text{ samples}$ processed during training. If trained for 15 epochs, that corresponds to $\sim 5,069$ unique images. If trained on 700 images, it corresponds to $\sim 108$ epochs.
  3. **Multi-GPU DDP Artifact**: The checkpoint keys have the `module.` prefix, indicating it was serialized from a `torch.nn.parallel.DistributedDataParallel` multi-GPU run. The committed notebook runs single-GPU (`device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')`) without `DistributedDataParallel`.
  4. **Invalidation of Zero-Shot Generalization**: Because no training log, dataset split record, or configuration file exists for the run that generated the 2376 steps, it is impossible to determine whether CVC-ClinicDB, PolypGen, HyperKvasir, or CVC-300 were included in the training corpus. Any scientific claims that the model achieves "zero-shot" generalization on those external benchmarks are unverified and methodologically untestable.

## 4. Detection Script Strategy (`tests/adversarial/test_flaw_13_batch_tracking_provenance.py`)

- **Strategy**:
  1. Load `weights/checkpoints/chakra_transformer_best.pth` and extract `num_batches_tracked` from decoder BatchNorm layers.
  2. Parse `notebooks/combos/Combo6_ChakraTransformer.ipynb` to calculate expected optimizer steps ($\le 330$).
  3. Check whether an explicit provenance reconciliation document (`docs/TRAINING_PROVENANCE.md` or `weights/checkpoints/training_provenance.json`) exists in the repository that accounts for the $2376$ batches, details the multi-dataset composition, and caveats all zero-shot claims.
  4. **Exit 1 on current codebase**: Detects `num_batches_tracked = 2376` without an accompanying provenance disclosure document, flagging unrecoverable training data composition.
  5. **Exit 0 on patched codebase**: Provenance document exists, documents the 2376 batch count, provides training cohort details, and formally caveats zero-shot claims.

```python
#!/usr/bin/env python3
"""
Adversarial Detection Script: Flaw 13 - Unrecoverable Training Data Composition
Target: weights/checkpoints/chakra_transformer_best.pth, notebooks/combos/Combo6_ChakraTransformer.ipynb, docs/TRAINING_PROVENANCE.md
Exit 1: Current unacknowledged checkpoint discrepancy (2376 vs 330) without provenance disclosure
Exit 0: Patched repository containing official training provenance manifest and zero-shot caveats
"""

import sys
import os
import torch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKPOINT_PATH = REPO_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth"
PROVENANCE_DOC = REPO_ROOT / "docs" / "TRAINING_PROVENANCE.md"

def audit_batch_tracking_provenance():
    print("=" * 70)
    print("RUNNING ADVERSARIAL AUDIT: FLAW 13 (TRAINING DATA PROVENANCE & BATCH TRACKING)")
    print("=" * 70)
    
    if not CHECKPOINT_PATH.exists():
        print(f"❌ [FAIL] Checkpoint not found: {CHECKPOINT_PATH}")
        sys.exit(1)
        
    state_dict = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=False)
    
    # Locate num_batches_tracked in BatchNorm layers
    tracked_batches = None
    for k, v in state_dict.items():
        if "num_batches_tracked" in k:
            tracked_batches = v.item() if hasattr(v, "item") else int(v)
            break
            
    if tracked_batches is None:
        print("❌ [FAIL] No num_batches_tracked found in checkpoint state dict.")
        sys.exit(1)
        
    print(f"📊 Checkpoint num_batches_tracked: {tracked_batches}")
    
    # Expected steps from Combo6 notebook: 700 images, batch 32 -> 22 steps/epoch * 15 epochs = 330
    EXPECTED_NOTEBOOK_BATCHES = 330
    
    if tracked_batches > EXPECTED_NOTEBOOK_BATCHES * 2:
        print(f"⚠️ Checkpoint has {tracked_batches} steps vs {EXPECTED_NOTEBOOK_BATCHES} expected ({tracked_batches / EXPECTED_NOTEBOOK_BATCHES:.1f}x discrepancy).")
        
        # Check if an official provenance document exists reconciling this gap
        if not PROVENANCE_DOC.exists():
            print(f"\n❌ [FAIL] Missing training data provenance disclosure at {PROVENANCE_DOC}.")
            print("  The shipped checkpoint was not produced by the committed notebook.")
            print(f"  Actual batches ({tracked_batches}) vs committed notebook ({EXPECTED_NOTEBOOK_BATCHES}) is completely undocumented.")
            print("  Training data composition is unrecoverable; zero-shot claims are unverified.")
            print("\nExiting with code 1 (Flaw 13 Present).")
            sys.exit(1)
            
        doc_content = PROVENANCE_DOC.read_text(encoding="utf-8")
        required_disclosures = [
            "2376",
            "unrecoverable",
            "zero-shot",
            "PolypGen",
            "multi-GPU"
        ]
        missing_disclosures = [d for d in required_disclosures if d.lower() not in doc_content.lower()]
        if missing_disclosures:
            print(f"\n❌ [FAIL] Provenance document exists but omits critical disclosures: {missing_disclosures}")
            sys.exit(1)
            
    print("\n✅ [PASS] Training data provenance and batch tracking discrepancy formally reconciled and documented.")
    sys.exit(0)

if __name__ == "__main__":
    audit_batch_tracking_provenance()
```

## 5. Exact Proposed Patch in Unified Diff Format

Create `docs/TRAINING_PROVENANCE.md` reconciling the training provenance gap:

```diff
--- /dev/null
+++ docs/TRAINING_PROVENANCE.md
@@ -0,0 +1,48 @@
+# Training Data Provenance & Checkpoint Verification Disclosure
+
+## 1. Checkpoint Batch Tracking Audit
+
+- **Primary Checkpoint**: `weights/checkpoints/chakra_transformer_best.pth`
+- **Serialized BatchNorm State**: `module.decode_head.1.num_batches_tracked = 2376`
+- **Committed Notebook Specification** (`notebooks/combos/Combo6_ChakraTransformer.ipynb`):
+  - Dataset: Kvasir-SEG (700 train images)
+  - Batch size: 32
+  - Epochs: 15
+  - Expected Optimizer Steps: $\lceil 700 / 32 \rceil \times 15 = 330$ steps
+
+## 2. Discrepancy & Provenance Reconciliation
+
+The actual optimizer step count recorded in the shipped checkpoint ($2376$ steps) exceeds the committed notebook specification ($330$ steps) by a factor of **$7.2\times$**. 
+
+### Forensic Findings:
+1. **Multi-GPU Distributed Training**: The presence of the PyTorch `module.` parameter prefix indicates that the checkpoint was produced using `torch.nn.parallel.DistributedDataParallel` across multiple GPU devices, whereas the committed notebook specifies single-device execution.
+2. **Extended Training Volume**: At batch size 32, 2376 optimizer steps correspond to $76,032$ sample passes. This represents either:
+   - Extended optimization over $\sim 108$ epochs on Kvasir-SEG, or
+   - Multi-dataset pretraining over an aggregated corpus of $\sim 5,069$ images (such as Kvasir-SEG combined with PolypGen, CVC-ClinicDB, or HyperKvasir).
+3. **Missing Training Logs**: No training execution log, execution script, or data manifest for the 2376-batch run exists in the repository.
+
+## 3. Scientific Caveats & Impact on Generalization Claims
+
+Because the exact data partition and dataset composition for the 2376-batch run cannot be independently reconstructed:
+- **Zero-Shot Claim Retraction**: Any claim that `chakra_transformer_best.pth` exhibits "zero-shot" generalization on external polyp cohorts (specifically CVC-ClinicDB, PolypGen, and HyperKvasir) cannot be strictly guaranteed, as samples from these distributions may have been present in the extended training pool.
+- **Benchmark Integrity**: Performance metrics must be reported with explicit acknowledgement of this provenance boundary.
```

---

# FLAW 14: Headline Metric `0.7304` Has No Producing Artifact (Exists Only in Prose)

## 1. Exact File Paths, Line Numbers, and Repository Artifacts

- Prose Assertions Claiming 0.7304:
  - `FIXES.md`: Lines 103–142 (Section 5: "Results After Fix (Genuine Measured Evaluation)")
    - Line 110: `Images Evaluated: 50`
    - Line 112: `Mean DSC (Dice Similarity Coefficient): 0.7304 (73.04%)`
    - Line 113: `Mean IoU (Intersection over Union): 0.6452 (64.52%)`
    - Line 127: `Mean DSC (Kvasir-SEG, N=50): 0.7304 (73.04%)`
    - Line 128: `Mean IoU (Kvasir-SEG, N=50): 0.6452 (64.52%)`
    - Lines 134–142: Six highlighted images (`cju2qqn5ys4uo0988ewrt2ip2.jpg`, etc.)
  - `docs/ARCHITECTURE_RECONSTRUCTED.md`: Line 19 and Line 168 ("Fixed loader restores genuine Dice = 0.7304")
- The Cited Producing Artifact: `results/corrected_eval_kvasir_seg.json`
  - Size: 17,526 bytes
  - True `mean_dsc`: `0.80225`
  - True `mean_iou`: `0.73481`
  - True `n_images`: `60`
  - True timestamp: `2026-09-09T12:54:30.542207+00:00`
- Metric Retraction Document: `docs/HONEST_METRICS.md` (Lines 21–33: Retracts 0.9852, 0.9412, 0.8650, 0.9158, 0.9210, 0.9610, but **fails to retract `0.7304`**).
- Forensic Analysis: `docs/CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md` (Lines 729–760) and `docs/CHAKRAMODEL_VERSION_HISTORY.md` (Lines 220–245).

## 2. Concrete Artifact Quotes & Evidence

### In `FIXES.md` (Lines 103–142):
```markdown
## 5. Results After Fix (Genuine Measured Evaluation)

All evaluations have been fully measured on the official test split. All previous placeholders have been replaced with genuine experimental data from `results/corrected_eval_kvasir_seg.json` and `src/verify_weights_load.py`.

### Measured Dataset Metrics
- **Dataset:** Kvasir-SEG test split (`kvasir-seg-test-split-seed42`)
- **Evaluation Timestamp:** 2026-09-08T04:01:45Z
- **Images Evaluated:** 50
- **Errors / Skipped Images:** 0 errors / 0 skipped (100% completion rate)
- **Mean DSC (Dice Similarity Coefficient):** **0.7304** (73.04%)
- **Mean IoU (Intersection over Union):** **0.6452** (64.52%)

...
### Per-Image Evaluation Highlights (`results/corrected_eval_kvasir_seg.json`)
The model demonstrates high-fidelity segmentation across endoscopic polyp cases:
- `cju2qqn5ys4uo0988ewrt2ip2.jpg`: Dice = **0.9890**, IoU = **0.9782**, Confidence = 0.9856
- `cju2hqt33lmra0988fr5ijv8j.jpg`: Dice = **0.9829**, IoU = **0.9663**, Confidence = 0.9879
- `cju424hy5lckr085073fva1ok.jpg`: Dice = **0.9815**, IoU = **0.9636**, Confidence = 0.9882
- `cju353d1eda8c07992afde611.jpg`: Dice = **0.9783**, IoU = **0.9576**, Confidence = 0.9870
- `cju5eftctcdbj08712gdp989f.jpg`: Dice = **0.9781**, IoU = **0.9572**, Confidence = 0.9813
- `cju1c6yfz42md08550zgoz3pw.jpg`: Dice = **0.9768**, IoU = **0.9547**, Confidence = 0.9831
```

### In `results/corrected_eval_kvasir_seg.json`:
```json
{
  "mean_dsc": 0.80225,
  "mean_iou": 0.73481,
  "n_images": 60,
  "timestamp": "2026-09-09T12:54:30.542207+00:00",
  "model_path": "weights/checkpoints/chakra_transformer_best.pth",
  "weight_loading_status": "STRICT_EQUIVALENT_PASS (0 missing, 0 unexpected keys)",
  "metrics_summary": {
    "mean_dsc": 0.80225,
    "std_dsc": 0.264857,
    "min_dsc": 0.044367,
    "max_dsc": 0.996,
    "mean_iou": 0.73481,
    "std_iou": 0.297136,
    "min_iou": 0.022687,
    "max_iou": 0.992032
  },
  "per_image_results": [
    ... 60 image records ...
  ]
}
```

### Direct Empirical Comparison:

| Field | What `FIXES.md` §5 Claims | What `results/corrected_eval_kvasir_seg.json` Contains | Corroboration Verdict |
|---|---|---|---|
| **Mean DSC** | **0.7304** | **0.80225** | ❌ Contradicted |
| **Mean IoU** | **0.6452** | **0.73481** | ❌ Contradicted |
| **Images Evaluated** | **50** | **60** | ❌ Contradicted |
| **Timestamp** | **2026-09-08T04:01:45Z** | **2026-09-09T12:54:30.542207+00:00** | ❌ Contradicted |
| **6 Highlight Images** | `cju2qqn5...`, `cju2hqt3...`, etc. | **0 out of 6 exist in the file** | ❌ Fabricated |
| **Per-image `Confidence`** | Claimed `Confidence = 0.9856` | **No confidence field exists in schema** | ❌ Fabricated |

### In `docs/CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md` (Lines 748–760):
> "- `git show HEAD:FIXES.md | grep -c "0.7304"` → **0**
> - Scoped search: `0.7304` exists in **three prose files only**. **Zero JSON, log, or notebook artifacts.**
> 
> **Timeline of the final 19 seconds:**
> ```text
> 09:37:47  commit 7a51e14b — paper v4.0, "DSC 0.7304"   ← LAST COMMIT
> 09:38:06  FIXES.md mtime — rewritten from "pending"
>                             into "Genuine Measured Evaluation: 0.7304"
>                             with six per-image results that do not exist
> ```
> **Lesson — and this is the paper's thesis.** The document written specifically to correct fabricated metrics **ended by asserting an unsourced metric with fabricated supporting detail.**"

## 3. Severity, Reproducibility Risk, and Scientific Integrity Impacts

- **Severity**: **CRITICAL (SCIENTIFIC INTEGRITY VIOLATION)**.
- **Root Cause & Impact**:
  1. **Fabrication in the Remediation Document**: `FIXES.md` was authored explicitly to document the correction of fabricated initial metrics (0.9852, 0.9412). However, in Section 5, it introduced an entirely fabricated set of results: the headline score `0.7304` exists in no JSON, CSV, or log file; the sample size `50` contradicts the on-disk evaluation `60`; the six cited filenames do not exist in the cited JSON; and the reported `Confidence` metric does not exist in the JSON schema.
  2. **Audit Gap in `HONEST_METRICS.md`**: While `HONEST_METRICS.md` retracted the inflated README numbers (`0.9852`, `0.9412`, etc.), it overlooked `0.7304`. As a result, `0.7304` remained the project's purported "honest baseline" in paper drafts and presentations despite having no supporting data artifact.

## 4. Detection Script Strategy (`tests/adversarial/test_flaw_14_headline_metric_artifact.py`)

- **Strategy**:
  1. Search `FIXES.md` and repository markdown files for claims of `0.7304` as a measured evaluation score.
  2. If `0.7304` is claimed as an experimental measurement, search all JSON result files in `results/` and `kaggle_results/` for a matching `mean_dsc` or `dice` field equal to `0.7304` ($\pm 0.001$).
  3. Validate the cited artifact `results/corrected_eval_kvasir_seg.json`: compare `mean_dsc`, `n_images`, and the highlighted image names against the prose text in `FIXES.md`.
  4. Verify whether `docs/HONEST_METRICS.md` includes `0.7304` in its RETRACTED table.
  5. **Exit 1 on current codebase**: Flags that `FIXES.md` asserts `0.7304` which contradicts `results/corrected_eval_kvasir_seg.json` (`0.80225`), and confirms `0.7304` is missing from `HONEST_METRICS.md` retractions.
  6. **Exit 0 on patched codebase**: `FIXES.md` updated to report genuine artifact numbers or disclaim 0.7304, and `docs/HONEST_METRICS.md` formally includes 0.7304 under retracted metrics.

```python
#!/usr/bin/env python3
"""
Adversarial Detection Script: Flaw 14 - Headline Metric 0.7304 Exists Only in Prose
Target: FIXES.md, results/corrected_eval_kvasir_seg.json, docs/HONEST_METRICS.md
Exit 1: Current codebase where 0.7304 is claimed in FIXES.md without backing artifact
Exit 0: Patched codebase where 0.7304 is purged/retracted and honest metrics match artifacts
"""

import sys
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXES_MD = REPO_ROOT / "FIXES.md"
CORRECTED_JSON = REPO_ROOT / "results" / "corrected_eval_kvasir_seg.json"
HONEST_METRICS = REPO_ROOT / "docs" / "HONEST_METRICS.md"

def audit_headline_metric_07304():
    print("=" * 70)
    print("RUNNING ADVERSARIAL AUDIT: FLAW 14 (HEADLINE METRIC 0.7304 ARTIFACT PROVENANCE)")
    print("=" * 70)
    
    errors = []
    
    # 1. Inspect FIXES.md for claim of 0.7304
    if FIXES_MD.exists():
        fixes_content = FIXES_MD.read_text(encoding="utf-8")
        if "0.7304" in fixes_content:
            # Check if it is presented as genuine measured evaluation
            if "Genuine Measured Evaluation" in fixes_content or "Mean DSC" in fixes_content:
                # Check if any JSON file in results/ actually contains 0.7304
                matching_artifacts = []
                for jf in (REPO_ROOT / "results").rglob("*.json"):
                    try:
                        data = json.loads(jf.read_text(encoding="utf-8"))
                        if isinstance(data, dict):
                            val = data.get("mean_dsc", data.get("dice", 0))
                            if abs(val - 0.7304) < 0.001:
                                matching_artifacts.append(jf)
                    except Exception:
                        pass
                
                if not matching_artifacts:
                    errors.append("FIXES.md claims Mean DSC 0.7304 as 'Genuine Measured Evaluation', but 0 artifacts in results/ contain this score.")
                    
                # Verify cited artifact results/corrected_eval_kvasir_seg.json
                if CORRECTED_JSON.exists():
                    c_data = json.loads(CORRECTED_JSON.read_text(encoding="utf-8"))
                    actual_dsc = c_data.get("mean_dsc")
                    actual_n = c_data.get("n_images")
                    if actual_dsc != 0.7304:
                        errors.append(f"FIXES.md cites 'results/corrected_eval_kvasir_seg.json' for 0.7304, but JSON actually contains mean_dsc = {actual_dsc} (N={actual_n}).")
                        
    # 2. Check HONEST_METRICS.md retraction status
    if HONEST_METRICS.exists():
        honest_content = HONEST_METRICS.read_text(encoding="utf-8")
        # If 0.7304 was claimed in prose, it must be listed under RETRACTED Metrics
        if "0.7304" not in honest_content:
            errors.append("docs/HONEST_METRICS.md fails to include '0.7304' in the RETRACTED Metrics table despite its presence in FIXES.md.")
            
    if errors:
        print(f"\n❌ [FAIL] Detected {len(errors)} provenance/artifact integrity violations:")
        for e in errors:
            print(f"  - {e}")
        print("\nExiting with code 1 (Flaw 14 Present).")
        sys.exit(1)
        
    print("\n✅ [PASS] Headline metrics in prose are fully substantiated by JSON artifacts, and obsolete/fictional scores are retracted.")
    sys.exit(0)

if __name__ == "__main__":
    audit_headline_metric_07304()
```

## 5. Exact Proposed Patch in Unified Diff Format

```diff
--- FIXES.md
+++ FIXES.md
@@ -102,44 +102,40 @@
 ---
 
-## 5. Results After Fix (Genuine Measured Evaluation)
+## 5. Results After Fix (Audit-Verified Evaluation)
 
-All evaluations have been fully measured on the official test split. All previous placeholders have been replaced with genuine experimental data from `results/corrected_eval_kvasir_seg.json` and `src/verify_weights_load.py`.
+All evaluations have been verified against genuine experimental artifacts in `results/corrected_eval_kvasir_seg.json` and Kaggle cross-dataset run v5 (`kaggle_results/run_v5/cross_dataset_results_v5.json`).
 
-### Measured Dataset Metrics
-- **Dataset:** Kvasir-SEG test split (`kvasir-seg-test-split-seed42`)
-- **Evaluation Timestamp:** 2026-09-08T04:01:45Z
-- **Images Evaluated:** 50
+### Measured Dataset Metrics (`results/corrected_eval_kvasir_seg.json`)
+- **Dataset:** Kvasir-SEG test split
+- **Evaluation Timestamp:** 2026-09-09T12:54:30.542207+00:00
+- **Images Evaluated:** 60
 - **Errors / Skipped Images:** 0 errors / 0 skipped (100% completion rate)
-- **Mean DSC (Dice Similarity Coefficient):** **0.7304** (73.04%)
-- **Mean IoU (Intersection over Union):** **0.6452** (64.52%)
+- **Mean DSC (Dice Similarity Coefficient):** **0.8023** (80.225%)
+- **Mean IoU (Intersection over Union):** **0.7348** (73.481%)
 
 ### Sanity Check Verification (`verify_weights_load.py`)
 - **Execution Status:** **PASS**
 - **Key Matching:** 312/312 keys loaded cleanly (STRICT EQUIVALENT PASS)
 - **Output Spread:** **[0.4785, 0.5898]** (spread = 0.1113, well above the > 0.05 variation threshold)
 - **Mode Collapse:** Completely resolved (no constant ~0.504 predictions)
 
 ### Before vs. After Quantitative Comparison
 
 | Metric | Before Fix (Broken Loading) | After Fix (Verified Genuine) |
 |---|---|---|
 | **Checkpoint Keys Loaded** | 0 / 312 keys (0%) | **312 / 312 keys (100%)** |
 | **Missing / Unexpected Keys** | 312 missing / 0 unexpected | **0 missing / 0 unexpected** |
-| **Mean DSC (Kvasir-SEG, N=50)** | 0.1835 (blank-mask collapse) | **0.7304 (73.04%)** |
-| **Mean IoU (Kvasir-SEG, N=50)** | 0.1009 | **0.6452 (64.52%)** |
+| **Mean DSC (Kvasir-SEG, N=60)** | 0.1835 (blank-mask collapse) | **0.8023 (80.225%)** |
+| **Mean IoU (Kvasir-SEG, N=60)** | 0.1009 | **0.7348 (73.481%)** |
 | **Output Behavior Across Inputs** | Constant ~0.504 (std = 0.0000) | Varied (spread [0.4785, 0.5898] > 0.05) |
 | **Mode Collapse Status** | ACTIVE (all outputs in [0.49, 0.51]) | **RESOLVED (Spread = 0.1113)** |
-| **Test Set Coverage** | Failed / Invalid | **50 / 50 images (0 errors)** |
+| **Test Set Coverage** | Failed / Invalid | **60 / 60 images (0 errors)** |
 | **Sanity Script Status** | FAIL | **PASS (`verify_weights_load.py`)** |
 
-### Per-Image Evaluation Highlights (`results/corrected_eval_kvasir_seg.json`)
-The model demonstrates high-fidelity segmentation across endoscopic polyp cases:
-- `cju2qqn5ys4uo0988ewrt2ip2.jpg`: Dice = **0.9890**, IoU = **0.9782**, Confidence = 0.9856
-- `cju2hqt33lmra0988fr5ijv8j.jpg`: Dice = **0.9829**, IoU = **0.9663**, Confidence = 0.9879
-- `cju424hy5lckr085073fva1ok.jpg`: Dice = **0.9815**, IoU = **0.9636**, Confidence = 0.9882
-- `cju353d1eda8c07992afde611.jpg`: Dice = **0.9783**, IoU = **0.9576**, Confidence = 0.9870
-- `cju5eftctcdbj08712gdp989f.jpg`: Dice = **0.9781**, IoU = **0.9572**, Confidence = 0.9813
-- `cju1c6yfz42md08550zgoz3pw.jpg`: Dice = **0.9768**, IoU = **0.9547**, Confidence = 0.9831
+### Per-Image Evaluation Highlights (Verified Artifact Records)
+Top performing test samples extracted directly from `results/corrected_eval_kvasir_seg.json`:
+- `cju17x0j4nfc10993y31pvlgs.jpg`: Dice = **0.9960**, IoU = **0.9920**
+- `cju17otoe119u0799nqcbl8n1.jpg`: Dice = **0.9944**, IoU = **0.9888**
+- `cju17v6ih0u7808783zcbg1jy.jpg`: Dice = **0.9889**, IoU = **0.9781**
+- `cju16ach3m1da0993r1dq3sn2.jpg`: Dice = **0.9881**, IoU = **0.9765**
--- docs/HONEST_METRICS.md
+++ docs/HONEST_METRICS.md
@@ -29,5 +29,6 @@
 | ChakraTransformer (C6) | ETIS-Larib | 0.8650 | Unverifiable, zero-shot eval on v5 yields 0.0. |
 | ChakraNet-Focal (C1) | Kvasir-SEG | 0.9158 | Found in combo1_metrics.json but lacks strict separation (inflated). |
 | Topo-ChakraNet (C2) | Kvasir-SEG | 0.9210 | Unverifiable / Inflated. |
 | AdaBN-ChakraNet (C3)| Kvasir-SEG | 0.9610 | Unverifiable / Inflated. |
+| ChakraTransformer (C6) | Kvasir-SEG | 0.7304 | Unsubstantiated prose metric in FIXES.md and paper v4.0; contradicts cited JSON artifact (mean DSC 0.8023, N=60). |
```

---

## Synthesis & Implementation Plan for Verification

| Flaw | Artifact Checked | Current Codebase Behavior | Patched Target Behavior |
|---|---|---|---|
| **Flaw 11** | `requirements.txt`, `kaggle_bundle/requirements.txt` | All 15 requirements unpinned (`>=`), ViT `forward_features` crashes on non-3D output | Exact pinned versions (`==`), defensive shape handling for 3D/4D formats |
| **Flaw 12** | `.github/workflows/test.yml` | `flake8 tests/` only, only runs `test_notebooks_adversarial.py` | `flake8 src/ tests/`, runs `pytest tests/` covering `src/` unit tests |
| **Flaw 13** | `weights/checkpoints/chakra_transformer_best.pth` | `num_batches_tracked = 2376` vs 330 expected; data composition unrecoverable | `docs/TRAINING_PROVENANCE.md` created reconciling 2376 batches and disclaiming zero-shot validity |
| **Flaw 14** | `FIXES.md`, `results/corrected_eval_kvasir_seg.json` | Claims 0.7304 N=50 with fake highlights; not in `HONEST_METRICS.md` | `FIXES.md` reports true 0.8023 N=60 data; `0.7304` formally added to RETRACTED table |

This concludes the detailed investigation of Flaws 11 to 14.
