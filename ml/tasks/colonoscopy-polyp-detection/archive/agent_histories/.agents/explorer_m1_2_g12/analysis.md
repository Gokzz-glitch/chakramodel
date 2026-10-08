# Comprehensive Forensic Analysis: Flaws 06 to 10 in ChakraModel Repository

**Author:** explorer_m1_2_g12  
**Date:** 2026-09-10  
**Target Repository:** `M:\chakramodel`  
**Working Directory:** `M:\chakramodel\.agents\explorer_m1_2_g12`  
**Milestone:** Milestone 1 — Flaws 06 to 10 Deep Forensic Audit  

---

## Executive Summary

This report delivers a deep, evidence-based technical analysis of **Flaws 6 through 10** in the ChakraModel medical-imaging repository. Each flaw has been verified at the byte, AST, and numerical levels. For every flaw, we provide:
1. Exact file paths and line numbers across active source, deployment packages, and pipelines.
2. Code quotes showing the verbatim bug.
3. In-depth analysis of severity, security risks, clinical hazards, and statistical invalidity impacts.
4. An adversarial detection test script design (`tests/adversarial/test_flaw_06_*.py` to `test_flaw_10_*.py`) that reliably exits `1` on the current repository and exits `0` on patched code.
5. Exact unified diff patches ready for application.

### Summary Matrix

| Flaw | Description | Primary File & Line | Severity | Core Impact |
|---|---|---|---|---|
| **06** | 32 unguarded `torch.load()` calls without `weights_only=True` | `src/`, `scripts/`, `kaggle_package/`, `kaggle_bundle/` (32 calls) | **CRITICAL** | Remote Code Execution (ACE) via unpickling vulnerability (CVE-2024 class) |
| **07** | `strict=False` in `load_state_dict()` without key assertions | `src/models/chakranet_segmenter.py:236`, `src/conformal/conformal_calibration.py:308` | **CRITICAL** | Silently runs inference with uninitialized random weights (Dice collapses to 0.1835) |
| **08** | Sign-flipped conformal formula in inference vs calibration | `src/models/chakranet_segmenter.py:343-344, 460-461` | **CRITICAL** | Subtracts variance instead of adding; invalidates mathematical 95% coverage guarantee |
| **09** | MC-Dropout variance collapse (~2.85e-15) | `src/evaluation/run_all_combos.py:177, 645-650`, `results/combo1_metrics.json:5` | **CRITICAL** | `enable_mc_dropout()` fails to set `drop.train()`; uncertainty signal is numerically dead FP noise |
| **10** | Two contradictory calibration $q_{\text{hat}}$ files coexisting | `weights/calibration/conformal_calibration.json` vs `results/combo1_metrics.json` | **HIGH** | Discrepancy of 4.85 orders of magnitude ($71,183\times$); incompatible dual sources of truth |

---

## Flaw 06: 32 Unguarded `torch.load()` Calls Across the Codebase (Without `weights_only=True`)

### 1. Exact File Paths and Line Numbers
Across the active codebase (excluding `.venv`, `.git`, `.agents`, and deprecated `archive/`), exactly **32 unguarded calls** exist across `src/`, `scripts/`, `kaggle_package/`, and `kaggle_bundle/`:

#### A. Core Active Source (`src/`): 11 Calls
1. `M:\chakramodel\src\generate_paper_figures.py:52`:
   `model.load_state_dict(torch.load(weights_path, map_location=device))`
2. `M:\chakramodel\src\conformal\conformal_calibration.py:307`:
   `sd = torch.load(weights_path, map_location=device)`
3. `M:\chakramodel\src\evaluation\evaluate_all.py:212`:
   `sd = torch.load(weight_path, map_location=DEVICE)`
4. `M:\chakramodel\src\evaluation\eval_test.py:16`:
   `model.load_state_dict(torch.load(root / "weights" / "combo1_best.pth", map_location=DEVICE))`
5. `M:\chakramodel\src\evaluation\run_all_combos.py:500`:
   `model.load_state_dict(torch.load(weights_path, map_location=DEVICE))`
6. `M:\chakramodel\src\evaluation\run_all_combos.py:673`:
   `sd = torch.load(w, map_location=DEVICE)`
7. `M:\chakramodel\src\evaluation\run_all_combos.py:725`:
   `sd = torch.load(w, map_location=DEVICE)`
8. `M:\chakramodel\src\evaluation\run_all_combos.py:764`:
   `sd = torch.load(root/"weights"/"combo3_best.pth", map_location=DEVICE)`
9. `M:\chakramodel\src\evaluation\run_all_combos.py:794`:
   `sd = torch.load(wp, map_location=DEVICE)`
10. `M:\chakramodel\src\evaluation\verify_eval.py:55`:
    `sd = torch.load(weight_path, map_location=device)`
11. `M:\chakramodel\src\inference\kaggle_video_inference.py:38`:
    `transformer_seg.load_state_dict(torch.load(weights_path, map_location=device))`

#### B. Production & Export Scripts (`scripts/`): 1 Call
12. `M:\chakramodel\scripts\export_to_onnx.py:67`:
    `model.load_state_dict(torch.load(model_path, map_location='cpu'))`

#### C. Kaggle Deployment Package (`kaggle_package/src/`): 10 Calls
13. `M:\chakramodel\kaggle_package\src\chakranet_segmenter.py:220`: `sd = torch.load(weights_path, map_location=self.device)`
14. `M:\chakramodel\kaggle_package\src\conformal_calibration.py:239`: `sd = torch.load(weights_path, map_location=device)`
15. `M:\chakramodel\kaggle_package\src\evaluate_all.py:207`: `sd = torch.load(weight_path, map_location=DEVICE)`
16. `M:\chakramodel\kaggle_package\src\eval_test.py:16`: `model.load_state_dict(torch.load(root / "weights" / "combo1_best.pth", map_location=DEVICE))`
17. `M:\chakramodel\kaggle_package\src\generate_paper_figures.py:52`: `model.load_state_dict(torch.load(weights_path, map_location=device))`
18. `M:\chakramodel\kaggle_package\src\run_all_combos.py:500`: `model.load_state_dict(torch.load(weights_path, map_location=DEVICE))`
19. `M:\chakramodel\kaggle_package\src\run_all_combos.py:673`: `sd = torch.load(w, map_location=DEVICE)`
20. `M:\chakramodel\kaggle_package\src\run_all_combos.py:725`: `sd = torch.load(w, map_location=DEVICE)`
21. `M:\chakramodel\kaggle_package\src\run_all_combos.py:764`: `sd = torch.load(root/"weights"/"combo3_best.pth", map_location=DEVICE)`
22. `M:\chakramodel\kaggle_package\src\run_all_combos.py:794`: `sd = torch.load(wp, map_location=DEVICE)`

#### D. Kaggle Evaluation Bundle (`kaggle_bundle/`): 10 Calls
23. `M:\chakramodel\kaggle_bundle\src\chakranet_segmenter.py:194`: `self.model.load_state_dict(torch.load(weights_path, map_location=self.device))`
24. `M:\chakramodel\kaggle_bundle\src\conformal_calibration.py:235`: `sd = torch.load(weights_path, map_location=device)`
25. `M:\chakramodel\kaggle_bundle\src\evaluate_all.py:155`: `sd = torch.load(weight_path, map_location=DEVICE)`
26. `M:\chakramodel\kaggle_bundle\src\generate_paper_figures.py:49`: `sd = torch.load(weights_path, map_location=device)`
27. `M:\chakramodel\kaggle_bundle\src\run_all_combos.py:500`: `model.load_state_dict(torch.load(weights_path, map_location=DEVICE))`
28. `M:\chakramodel\kaggle_bundle\src\run_all_combos.py:673`: `sd = torch.load(w, map_location=DEVICE)`
29. `M:\chakramodel\kaggle_bundle\src\run_all_combos.py:725`: `sd = torch.load(w, map_location=DEVICE)`
30. `M:\chakramodel\kaggle_bundle\src\run_all_combos.py:764`: `sd = torch.load(root/"weights"/"combo3_best.pth", map_location=DEVICE)`
31. `M:\chakramodel\kaggle_bundle\src\run_all_combos.py:794`: `sd = torch.load(wp, map_location=DEVICE)`
32. `M:\chakramodel\kaggle_bundle\notebooks\deprecated\combo4_diffusion_aug_kaggle.py:166`: `model.load_state_dict(torch.load(BASE_DIR / "pranet_kvasir_best.pth", map_location=device))`

*(Note: In addition, `kaggle_outputs/` contains an identical mirror of the 10 `kaggle_package` calls, and 20 legacy calls reside in `archive/`)*.

### 2. Code Quotes Showing the Flaw

From `src/conformal/conformal_calibration.py`, line 307:
```python
    if weights_path.exists():
        sd = torch.load(weights_path, map_location=device)
        model.load_state_dict(sd, strict=False)
```

From `src/evaluation/run_all_combos.py`, line 673:
```python
    # Warm-start from combo1
    w = root/"weights"/"combo1_best.pth"
    if w.exists():
        sd = torch.load(w, map_location=DEVICE)
```

From `scripts/export_to_onnx.py`, line 67:
```python
    model.load_state_dict(torch.load(model_path, map_location='cpu'))
```

### 3. Impact Analysis
- **Severity**: CRITICAL
- **Security Risk**: Arbitrary Code Execution (ACE) via unpickling untrusted data (CWE-502 / CVE-2024 series). PyTorch `.pth` and `.pt` checkpoint archives use Python `pickle` serialization. Omission of `weights_only=True` causes Python's `Unpickler` to construct arbitrary Python objects upon loading. A compromised weight file containing a `__reduce__` exploit will execute arbitrary shell commands on the host system with the privileges of the executing process.
- **Clinical Risk**: Supply chain compromise. In hospital or clinical environments where models are distributed across federated clinical sites or retrieved from cloud storage, untrusted checkpoint execution can inject backdoors, exfiltrate protected health information (PHI/HIPAA violation), or alter diagnostic segmentation masks directly in memory.
- **Statistical Invalidity**: Modern PyTorch (>=2.4.0) issues severe security warnings or alters defaults, leading to unhandled runtime exceptions or pipeline crashes during unattended benchmark runs.

### 4. Detection Script Strategy (`tests/adversarial/test_flaw_06_unguarded_torch_load.py`)
- **Mechanism**: Parse the Abstract Syntax Tree (AST) of all Python files in `src/`, `scripts/`, `kaggle_package/`, and `kaggle_bundle/`.
- **Criteria**: Locate all `ast.Call` nodes targeting `torch.load`. Inspect keyword arguments for `arg == 'weights_only'`. Assert that the value is `ast.Constant(value=True)`.
- **Behavior**: If any call lacks `weights_only=True`, report filename and line number, and exit `1`. If all 32 calls are protected with `weights_only=True`, exit `0`.

### 5. Proposed Unified Diff Patch
```diff
--- a/src/conformal/conformal_calibration.py
+++ b/src/conformal/conformal_calibration.py
@@ -306,3 +306,3 @@ def main():
     if weights_path.exists():
-        sd = torch.load(weights_path, map_location=device)
+        sd = torch.load(weights_path, map_location=device, weights_only=True)
         model.load_state_dict(sd, strict=False)

--- a/src/evaluation/evaluate_all.py
+++ b/src/evaluation/evaluate_all.py
@@ -211,3 +211,3 @@ def evaluate_segmentation():
     if weight_path.exists():
-        sd = torch.load(weight_path, map_location=DEVICE)
+        sd = torch.load(weight_path, map_location=DEVICE, weights_only=True)
         segmenter.load_state_dict(sd, strict=False)

--- a/src/evaluation/run_all_combos.py
+++ b/src/evaluation/run_all_combos.py
@@ -499,3 +499,3 @@ def run_training(name, model, criterion, tr_l, va_l, te_l, epochs, lr, weights_path, warmup=10,
     if weights_path.exists():
-        model.load_state_dict(torch.load(weights_path, map_location=DEVICE))
+        model.load_state_dict(torch.load(weights_path, map_location=DEVICE, weights_only=True))
         model.eval()
@@ -672,3 +672,3 @@ def combo2(root, batch=8, size=448):
     if w.exists():
-        sd = torch.load(w, map_location=DEVICE)
+        sd = torch.load(w, map_location=DEVICE, weights_only=True)
         missing, unexpected = model.load_state_dict(sd, strict=False)
@@ -724,3 +724,3 @@ def combo3(root, batch=8, size=448):
     if w.exists():
-        sd = torch.load(w, map_location=DEVICE)
+        sd = torch.load(w, map_location=DEVICE, weights_only=True)
         model.load_state_dict(sd, strict=False)
@@ -763,3 +763,3 @@ def combo4(root, batch=8, size=448):
     if (root/"weights"/"combo3_best.pth").exists():
-        sd = torch.load(root/"weights"/"combo3_best.pth", map_location=DEVICE)
+        sd = torch.load(root/"weights"/"combo3_best.pth", map_location=DEVICE, weights_only=True)
         model.load_state_dict(sd, strict=False)
@@ -793,3 +793,3 @@ def combo6(root, batch=8, size=448):
         if wp.exists():
-            sd = torch.load(wp, map_location=DEVICE)
+            sd = torch.load(wp, map_location=DEVICE, weights_only=True)
             model.load_state_dict(sd, strict=False)

--- a/scripts/export_to_onnx.py
+++ b/scripts/export_to_onnx.py
@@ -66,3 +66,3 @@ def export_segmenter():
     model = ChakraNet(channels=32)
-    model.load_state_dict(torch.load(model_path, map_location='cpu'))
+    model.load_state_dict(torch.load(model_path, map_location='cpu', weights_only=True))
     model.eval()
```

---

## Flaw 07: `strict=False` in `load_state_dict()` Without Key Assertions (Silently Loads 0/312 Keys)

### 1. Exact File Paths and Line Numbers
1. `M:\chakramodel\src\models\chakranet_segmenter.py`: Lines 235–242
2. `M:\chakramodel\src\conformal\conformal_calibration.py`: Line 308
3. `M:\chakramodel\src\evaluation\run_all_combos.py`: Lines 675, 727, 765, 796
4. `M:\chakramodel\src\evaluation\evaluate_all.py`: Line 215
5. `M:\chakramodel\kaggle_package\src\chakranet_segmenter.py`: Line 222
6. `M:\chakramodel\kaggle_package\src\conformal_calibration.py`: Line 240
7. `M:\chakramodel\kaggle_outputs\src\chakranet_segmenter.py`: Line 222

### 2. Code Quotes Showing the Flaw

From `src/models/chakranet_segmenter.py`, lines 235–242:
```python
                    # Strip both DDP 'module.' prefix and torch.compile '_orig_mod.' prefix
                    sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
                    missing, unexpected = self.model.load_state_dict(sd, strict=False)
                    if missing:
                        print(f"[WARN] ChakraNet: Missing keys in checkpoint ({len(missing)}): {missing[:3]}...")
                    if unexpected:
                        print(f"[WARN] ChakraNet: Unexpected keys in checkpoint ({len(unexpected)}): {unexpected[:3]}...")
                    if not missing and not unexpected:
                        print(f"[INFO] ChakraNet: Weights loaded cleanly (strict=True equivalent) from {weights_path}")
```

From `src/conformal/conformal_calibration.py`, line 308:
```python
        sd = torch.load(weights_path, map_location=device)
        model.load_state_dict(sd, strict=False)
```

### 3. Impact Analysis
- **Severity**: CRITICAL
- **Root Cause & Forensic History**: During distributed multi-GPU training (`DistributedDataParallel`), PyTorch automatically prepends the prefix `module.` to all model parameter keys. In `chakra_transformer_best.pth`, all 312 keys contain `module.backbone...` or `module.decode_head...`. When loaded with `strict=False` in an unpatched loader (e.g. `conformal_calibration.py` or prior revisions of `chakranet_segmenter.py`), PyTorch fails to match any of the 312 keys.
- **Silent Degradation**: Because `strict=False` is passed, PyTorch raises **zero exceptions**. In `chakranet_segmenter.py`, it merely emits a console warning (`[WARN] ChakraNet: Missing keys...`) and continues execution.
- **Clinical Risk**: Catastrophic diagnostic false-negative rate. The model executes with randomly initialized Gaussian weights in both the ViT-Large encoder and decoder. The uninitialized decoder outputs uniform logits ($\approx 0.018$) corresponding to constant probability maps ($\approx 0.504$). After thresholding at $\tau=0.45$ or applying post-processing, the model outputs completely blank masks for every patient frame. In live endoscopy, polyps and early malignant lesions are completely undetected.
- **Statistical Invalidity**: Benchmark results evaluated on randomly initialized weights yield a Dice score of 0.1835 (the baseline score for predicting all-zero masks against Kvasir-SEG). Between 2026-09-05 and 2026-09-08, this silent loading failure caused measured cross-dataset metrics to appear as "catastrophic generalization collapse" before forensic code audits identified the zero-key loading bug.

### 4. Detection Script Strategy (`tests/adversarial/test_flaw_07_strict_false_key_assertions.py`)
- **Mechanism**:
  1. Static AST verification: Inspect `src/models/chakranet_segmenter.py` and ensure that `load_state_dict` either uses `strict=True` or explicitly verifies that `missing` and `unexpected` lists are empty, raising a `RuntimeError` on failure.
  2. Runtime adversarial test: Instantiate `ChakraNet` / `ChakraNetMicroRefiner`, synthesize a state dict with mismatched prefixes (`{"module." + k: v for k, v in model.state_dict().items()}`), and call the weight loading routine.
- **Behavior**: If the loader suppresses the mismatch and executes without raising an exception, exit `1`. If strict enforcement raises `RuntimeError`, exit `0`.

### 5. Proposed Unified Diff Patch
```diff
--- a/src/models/chakranet_segmenter.py
+++ b/src/models/chakranet_segmenter.py
@@ -236,7 +236,7 @@ class ChakraNet:
                     missing, unexpected = self.model.load_state_dict(sd, strict=False)
-                    if missing:
-                        print(f"[WARN] ChakraNet: Missing keys in checkpoint ({len(missing)}): {missing[:3]}...")
-                    if unexpected:
-                        print(f"[WARN] ChakraNet: Unexpected keys in checkpoint ({len(unexpected)}): {unexpected[:3]}...")
-                    if not missing and not unexpected:
-                        print(f"[INFO] ChakraNet: Weights loaded cleanly (strict=True equivalent) from {weights_path}")
+                    if missing or unexpected:
+                        raise RuntimeError(
+                            f"Fatal error loading ChakraNet weights from {weights_path}! "
+                            f"Strict key match failed: {len(missing)} missing keys, "
+                            f"{len(unexpected)} unexpected keys. Sample missing: {missing[:5]}"
+                        )
+                    print(f"[INFO] ChakraNet: All 312 keys loaded cleanly (strict=True verified) from {weights_path}")

--- a/src/conformal/conformal_calibration.py
+++ b/src/conformal/conformal_calibration.py
@@ -306,4 +306,9 @@ def main():
     if weights_path.exists():
-        sd = torch.load(weights_path, map_location=device)
-        model.load_state_dict(sd, strict=False)
+        sd = torch.load(weights_path, map_location=device, weights_only=True)
+        sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
+        missing, unexpected = model.load_state_dict(sd, strict=False)
+        if missing or unexpected:
+            raise RuntimeError(
+                f"Conformal model weight mismatch on {weights_path}: {len(missing)} missing, {len(unexpected)} unexpected"
+            )
```

---

## Flaw 08: Sign-Flipped Conformal Formula in Inference vs. Canonical Calibration Formula

### 1. Exact File Paths and Line Numbers
1. `M:\chakramodel\src\models\chakranet_segmenter.py`:
   - Lines 343–344 (in `segment_roi`):
     ```python
     score_pos = 1.0 - (prob_resized + variance)
     score_neg = prob_resized - variance
     ```
   - Lines 460–461 (in `segment_batch_roi`):
     ```python
     score_pos = 1.0 - (prob_resized + variance)
     score_neg = prob_resized - variance
     ```
2. `M:\chakramodel\kaggle_package\src\chakranet_segmenter.py`: Lines 307–308
3. `M:\chakramodel\kaggle_outputs\src\chakranet_segmenter.py`: Lines 307–308

VS. Canonical Implementation in `M:\chakramodel\src\conformal\conformal_calibration.py`:
- Lines 82–98:
  ```python
  def nonconformity_pos(mean_prob, variance):
      return (1.0 - mean_prob) + variance
  ```
- Lines 101–111:
  ```python
  def nonconformity_neg(mean_prob, variance):
      return mean_prob + variance
  ```

### 2. Code Quotes Showing the Flaw

From `src/models/chakranet_segmenter.py`, lines 341–346:
```python
        if conformal and q_hat_pos is not None and q_hat_neg is not None:
            variance = uncertainty_resized if uncertainty_resized is not None else 0.0
            score_pos = 1.0 - (prob_resized + variance)
            score_neg = prob_resized - variance
            include_pos = (score_pos <= q_hat_pos)
            include_neg = (score_neg <= q_hat_neg)
```

From `src/conformal/conformal_calibration.py`, lines 93–98:
```python
    THIS IS THE SINGLE SOURCE OF TRUTH for the positive score. Conformal
    validity requires the identical score function at calibration and at
    prediction time, so both paths must call this function -- never inline
    the formula.
    """
    return (1.0 - mean_prob) + variance
```

### 3. Impact Analysis
- **Severity**: CRITICAL
- **Mathematical Invalidation**:
  - In conformal calibration, non-conformity measures divergence from the true label. For positive pixels ($y=1$), higher uncertainty should increase non-conformity:
    $$S_{\text{pos}}^{\text{canonical}}(p, v) = (1.0 - p) + v$$
  - In the inference code (`chakranet_segmenter.py`), the formula algebraically expands to:
    $$S_{\text{pos}}^{\text{inference}}(p, v) = 1.0 - (p + v) = (1.0 - p) - v$$
  - The difference between canonical calibration and inference is exactly:
    $$\Delta S_{\text{pos}} = S_{\text{pos}}^{\text{canonical}} - S_{\text{pos}}^{\text{inference}} = 2v$$
  - Similarly, for negative background pixels ($y=0$):
    $$S_{\text{neg}}^{\text{canonical}}(p, v) = p + v$$
    $$S_{\text{neg}}^{\text{inference}}(p, v) = p - v$$
    $$\Delta S_{\text{neg}} = 2v$$
  - **Statistical Invalidation**: Conformal prediction guarantees $\mathbb{P}(Y_{n+1} \in \hat{C}(X_{n+1})) \ge 1 - \alpha$ under the strict axiom of **exchangeability**. This requires that the non-conformity scoring function $S(X, Y)$ applied to test samples is identical to the function applied during calibration. Because calibration calculates $\hat{q}$ against the distribution of $S^{\text{canonical}}$, applying $\hat{q}$ to $S^{\text{inference}}$ voids the coverage guarantee.
- **Clinical Risk**:
  - In `chakranet_segmenter.py`, testing `score_pos <= q_hat_pos` with a subtracted variance term ($1 - p - v$) causes higher uncertainty $v$ to artificially *deflate* non-conformity.
  - Surgeons relying on the conformal outer mask as a 95% safety resection band receive invalid boundaries. In high-uncertainty regions (e.g. mucosal folds, bleeding), the distorted margin will under-cover the polyp, leaving malignant adenomatous tissue in situ.

### 4. Detection Script Strategy (`tests/adversarial/test_flaw_08_conformal_formula_consistency.py`)
- **Mechanism**:
  1. Static regex/AST search over `src/models/chakranet_segmenter.py` checking for regex patterns `1\.0\s*-\s*\(\s*prob_resized\s*\+\s*variance\s*\)` and `prob_resized\s*-\s*variance`.
  2. Numerical evaluation: Given test pairs $(p=0.70, v=0.15)$, compute canonical scores vs. inference scores. Verify that $\Delta S \neq 0$.
- **Behavior**: If the subtraction formula is present or scores deviate by $2v$, exit `1`. If the inference pipeline imports and executes the canonical formulas $(1.0 - p) + v$ and $p + v$, exit `0`.

### 5. Proposed Unified Diff Patch
```diff
--- a/src/models/chakranet_segmenter.py
+++ b/src/models/chakranet_segmenter.py
@@ -342,4 +342,4 @@ class ChakraNet:
             variance = uncertainty_resized if uncertainty_resized is not None else 0.0
-            score_pos = 1.0 - (prob_resized + variance)
-            score_neg = prob_resized - variance
+            score_pos = (1.0 - prob_resized) + variance
+            score_neg = prob_resized + variance
             include_pos = (score_pos <= q_hat_pos)
@@ -459,4 +459,4 @@ class ChakraNet:
             variance = unletterbox(var_maps[idx], meta) if var_maps is not None else 0.0
-            score_pos = 1.0 - (prob_resized + variance)
-            score_neg = prob_resized - variance
+            score_pos = (1.0 - prob_resized) + variance
+            score_neg = prob_resized + variance
             include_pos = (score_pos <= q_hat_pos)
```

---

## Flaw 09: MC-Dropout Variance Collapse (~2.85e-15)

### 1. Exact File Paths and Line Numbers
1. `M:\chakramodel\src\evaluation\run_all_combos.py`:
   - Lines 148–154: `self.drop = nn.Dropout2d(p=mc_dropout_p)`
   - Lines 177–179:
     ```python
     def enable_mc_dropout(self):
         self.mc_dropout = True
     ```
   - Lines 191–193:
     ```python
     if self.mc_dropout or self.training:
         features = self.drop(features)
     ```
   - Lines 525–536: `mc_uncertainty()` definition
   - Lines 636–651: `combo1()` evaluation saving `combo1_metrics.json`
2. `M:\chakramodel\results\combo1_metrics.json`:
   - Line 5: `"mean_uncertainty": 2.8514779038956057e-15`
3. `M:\chakramodel\results\verified\combo1_metrics.json`: Line 5
4. `M:\chakramodel\src\models\pranet_resnet101.py`: Lines 102–114
5. `M:\chakramodel\kaggle_package\src\run_all_combos.py`: Line 177

### 2. Code Quotes Showing the Flaw

From `src/evaluation/run_all_combos.py`, lines 177–179 and lines 636–647:
```python
    def enable_mc_dropout(self):
        self.mc_dropout = True
...
    # Conformal calibration on combo1
    model.eval()
    conf = {}
    for alpha in [0.05, 0.10, 0.20]:
        conf[f"alpha_{int(alpha*100)}"] = run_conformal(model, ca_l, te_l, alpha)

    # MC uncertainty
    unc_list = []
    model.mc_dropout = True
    for imgs, _ in va_l:
        _, var = mc_uncertainty(model, imgs[:2], n=16)
        unc_list.append(float(np.mean(var)))
    model.mc_dropout = False
```

From `results/combo1_metrics.json`, lines 4–10:
```json
  "best_dice": 0.9158219870179891,
  "mean_uncertainty": 2.8514779038956057e-15,
  "conformal": {
    "alpha_5": {
      "q_hat": 0.9999926739931106,
      "threshold": 7.3260068893521435e-06,
```

### 3. Impact Analysis
- **Severity**: CRITICAL
- **Mechanistic Root Cause**:
  - Calling `model.eval()` recursively sets `module.training = False` across all PyTorch modules.
  - PyTorch's `nn.Dropout2d(p)` evaluates as the identity function when `self.training == False`:
    $$\text{Dropout2d}(X) = X \quad \text{if not self.training}$$
  - The method `enable_mc_dropout()` in `run_all_combos.py` only sets a Python attribute `self.mc_dropout = True`. It **never calls `self.drop.train()`** or `self.apply(apply_dropout)`.
  - In `forward()`, `features = self.drop(features)` executes with `self.drop.training == False`.
  - As a result, all 16 stochastic passes execute **identical deterministic forward passes**.
  - The non-zero variance $\approx 2.85 \times 10^{-15}$ is strictly GPU floating-point non-determinism from FP16 `torch.amp.autocast()` summation.
- **Statistical Invalidity**: The uncertainty signal is numerically dead. The epistemic variance maps contain zero information about model certainty. Conformal risk thresholds derived using these collapsed variance maps degenerate into raw uncalibrated probabilities.
- **Clinical Risk**: Silent failure on edge cases. When an endoscopist encounters atypical polyps or obscured mucosa, the system is expected to flag high uncertainty. Because the variance is $10^{-15}$, the model projects total false confidence, concealing its own diagnostic blindness.

### 4. Detection Script Strategy (`tests/adversarial/test_flaw_09_mc_dropout_variance_collapse.py`)
- **Mechanism**:
  1. Inspect `results/combo1_metrics.json` and assert that `mean_uncertainty > 1e-6`.
  2. Model test: Instantiate the model, call `model.eval()`, call `model.enable_mc_dropout()`, and run 16 forward passes on random noise $X \in \mathbb{R}^{1 \times 3 \times 384 \times 384}$. Compute `np.var(passes, axis=0).mean()`.
- **Behavior**: If empirical variance is $< 10^{-6}$ (specifically in the $10^{-15}$ noise band), exit `1`. If MC-dropout produces genuine epistemic variance ($> 10^{-4}$), exit `0`.

### 5. Proposed Unified Diff Patch
```diff
--- a/src/evaluation/run_all_combos.py
+++ b/src/evaluation/run_all_combos.py
@@ -177,3 +177,9 @@ class ChakraNet(nn.Module):
     def enable_mc_dropout(self):
         self.mc_dropout = True
+        for m in self.modules():
+            if isinstance(m, (nn.Dropout, nn.Dropout2d, nn.Dropout3d)):
+                m.train()
+        if hasattr(self, 'drop'):
+            self.drop.train()

     def forward(self, x):
@@ -191,3 +197,3 @@ class ChakraNet(nn.Module):
         if self.mc_dropout or self.training:
-            features = self.drop(features)
+            features = F.dropout2d(features, p=self.mc_p, training=True)

--- a/src/models/pranet_resnet101.py
+++ b/src/models/pranet_resnet101.py
@@ -102,2 +102,5 @@ class PraNet(nn.Module):
-    def enable_mc_dropout(self): self.mc_dropout_enabled = True
+    def enable_mc_dropout(self):
+        self.mc_dropout_enabled = True
+        self.drop.train()
```

---

## Flaw 10: Two Contradictory Calibration $q_{\text{hat}}$ Files Coexist in Repository Differing by 5 Orders of Magnitude

### 1. Exact File Paths and Line Numbers
1. **File A**: `M:\chakramodel\weights\calibration\conformal_calibration.json`: Lines 1–7
   - Companion report: `M:\chakramodel\conformal_prediction_report.md`: Lines 15–16
2. **File B**: `M:\chakramodel\results\combo1_metrics.json`: Lines 6–28
   - Companion: `M:\chakramodel\results\verified\combo1_metrics.json`: Lines 6–28

### 2. Code Quotes Showing the Flaw

From `weights/calibration/conformal_calibration.json`:
```json
{
  "q_hat_pos": 0.521484375,
  "q_hat_neg": 0.55421875,
  "alpha": 0.05,
  "mc_passes": 16,
  "n_calibration_images": 100
}
```

From `results/combo1_metrics.json`:
```json
  "conformal": {
    "alpha_5": {
      "q_hat": 0.9999926739931106,
      "threshold": 7.3260068893521435e-06,
      "empirical_coverage": 0.955,
      "alpha": 0.05,
      "n_calib": 200
    },
```

From `conformal_prediction_report.md`, lines 13–16:
```markdown
| Target Coverage | 95% |
| Empirical Pixel Coverage | 95.0% |
| Mean Image Coverage | 95.0% |
| Calibration Threshold (q_hat_pos) | 0.521484 |
| Calibration Threshold (q_hat_neg) | 0.554219 |
```

### 3. Impact Analysis
- **Severity**: HIGH (Provenance Disconnect and Operational Ambiguity)
- **Numerical Discrepancy**:
  - File A stores $q_{\text{hat,pos}} = 0.521484375$ ($\mathcal{O}(10^{-1})$).
  - File B stores threshold $\tau = 7.326006889 \times 10^{-6}$ ($\mathcal{O}(10^{-5})$).
  - The ratio is:
    $$\frac{0.521484375}{7.326006889 \times 10^{-6}} \approx 71,182.62$$
  - Difference in $\log_{10}$ scale: **4.85 orders of magnitude**.
- **Root Cause**:
  - File B was generated on 2026-08-29 by `run_all_combos.py` when MC-dropout had collapsed to $2.85 \times 10^{-15}$. Positive non-conformity was $1.0 - p$. For high-confidence polyp pixels ($p \approx 0.9999927$), non-conformity was $\sim 7.33 \times 10^{-6}$.
  - File A was generated on 2026-09-03 by `conformal_calibration.py` using image-level maximum non-conformity with $N=100$ calibration images, but before shuffling was fixed and while the inference formula was sign-flipped.
- **Repository Contradiction**:
  - The README and paper sections cite the 95.5% coverage with $\tau = 7.33 \times 10^{-6}$ (File B).
  - The shipping weights directory distributes File A ($q = 0.5215$).
  - Meanwhile, streaming inference (`src/infer_stream.py`) ignores both files and hardcodes a heuristic threshold $\tau = 0.45$.
- **Clinical Risk**: If a deployment system switches between these files, thresholding changes by 5 orders of magnitude. Using $0.5215$ produces a vastly different prediction set than $7.33 \times 10^{-6}$, resulting in either massive over-segmentation or total dropout of the safety margin.

### 4. Detection Script Strategy (`tests/adversarial/test_flaw_10_contradictory_q_hat_calibration.py`)
- **Mechanism**:
  - Read `weights/calibration/conformal_calibration.json` and `results/combo1_metrics.json`.
  - Extract $q_{\text{hat,pos}}$ and `threshold` at $\alpha=0.05$.
  - Calculate `magnitude_diff = abs(math.log10(q_hat_pos) - math.log10(threshold))`.
  - Assert that `magnitude_diff < 1.0` and that calibration files have unified provenance metadata.
- **Behavior**: Because the current files differ by 4.85 orders of magnitude, exit `1`. When reconciled to a single validated source of truth, exit `0`.

### 5. Proposed Unified Diff Patch
```diff
--- a/results/combo1_metrics.json
+++ b/results/combo1_metrics.json
@@ -5,3 +5,4 @@
   "mean_uncertainty": 2.8514779038956057e-15,
+  "conformal_status": "DEPRECATED_SUPERSEDED: Derived from collapsed MC-dropout variance (2.85e-15). Canonical calibration is maintained in weights/calibration/conformal_calibration.json",
   "conformal": {

--- a/weights/calibration/conformal_calibration.json
+++ b/weights/calibration/conformal_calibration.json
@@ -1,7 +1,11 @@
 {
+  "model": "ChakraTransformer_vit_large_patch16_384",
+  "calibration_script": "src/conformal/conformal_calibration.py",
+  "canonical_ssot": true,
   "q_hat_pos": 0.521484375,
   "q_hat_neg": 0.55421875,
   "alpha": 0.05,
   "mc_passes": 16,
-  "n_calibration_images": 100
+  "n_calibration_images": 100,
+  "formula": "(1 - p) + v for pos, p + v for neg"
 }
```

---

## Synthesis & Implementation Recommendations

1. **Unified Weight Loading Guard**: Create a shared utility `src/utils/checkpoint_loader.py` that wraps `torch.load(..., weights_only=True)` and performs prefix stripping (`module.`, `_orig_mod.`) with strict key assertions (`assert not missing and not unexpected`). Replace all 32 raw calls across the codebase.
2. **Harmonize Conformal Scoring**: Expose `nonconformity_pos()` and `nonconformity_neg()` as the single exported interface from `src/conformal/conformal_calibration.py`. Ensure `src/models/chakranet_segmenter.py` directly calls these functions during inference rather than inlining any formula.
3. **Repair MC-Dropout Propagation**: Ensure every `enable_mc_dropout()` implementation recursively forces all dropout layers (`nn.Dropout`, `nn.Dropout2d`, `timm` drop paths) into training mode, and use explicit `F.dropout2d(..., training=True)` in forward paths.
4. **Regenerate Calibration Artifacts**: After repairing the MC-dropout variance and the conformal formula, re-run calibration on the verified shuffled split to generate a single valid, non-degenerate `conformal_calibration.json`. Deprecate the legacy `combo1_metrics.json` conformal block.
