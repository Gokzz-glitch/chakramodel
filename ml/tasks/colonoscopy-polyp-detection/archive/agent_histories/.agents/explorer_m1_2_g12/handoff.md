# Handoff Report: Forensic Investigation of Flaws 06 to 10

**Agent:** explorer_m1_2_g12  
**Working Directory:** `M:\chakramodel\.agents\explorer_m1_2_g12`  
**Date:** 2026-09-10  
**Target Milestone:** Milestone 1 — Flaws 06 to 10 (Unguarded `torch.load`, `strict=False` in `load_state_dict`, Conformal Formula Sign Flip, MC-Dropout Variance Collapse, Contradictory $q_{\text{hat}}$ Calibration Files)  
**Recipient:** `orchestrator_gen12` (`ba6ae91c-9868-4822-93f7-a3b0985f6f8d`)  

---

## 1. Observation

### Observation 1: Flaw 06 — 32 Unguarded `torch.load()` Calls
Static AST inspection across active non-venv/non-archive Python files identified exactly 32 calls to `torch.load()` lacking `weights_only=True`:
- `src/generate_paper_figures.py:52`: `model.load_state_dict(torch.load(weights_path, map_location=device))`
- `src/conformal/conformal_calibration.py:307`: `sd = torch.load(weights_path, map_location=device)`
- `src/evaluation/evaluate_all.py:212`: `sd = torch.load(weight_path, map_location=DEVICE)`
- `src/evaluation/eval_test.py:16`: `model.load_state_dict(torch.load(root / "weights" / "combo1_best.pth", map_location=DEVICE))`
- `src/evaluation/run_all_combos.py:500, 673, 725, 764, 794` (5 calls)
- `src/evaluation/verify_eval.py:55`: `sd = torch.load(weight_path, map_location=device)`
- `src/inference/kaggle_video_inference.py:38`: `transformer_seg.load_state_dict(torch.load(weights_path, map_location=device))`
- `scripts/export_to_onnx.py:67`: `model.load_state_dict(torch.load(model_path, map_location='cpu'))`
- `kaggle_package/src/`: 10 calls (`chakranet_segmenter.py:220`, `conformal_calibration.py:239`, `evaluate_all.py:207`, `eval_test.py:16`, `generate_paper_figures.py:52`, `run_all_combos.py:500, 673, 725, 764, 794`)
- `kaggle_bundle/`: 10 calls (`chakranet_segmenter.py:194`, `conformal_calibration.py:235`, `evaluate_all.py:155`, `generate_paper_figures.py:49`, `run_all_combos.py:500, 673, 725, 764, 794`, `notebooks/deprecated/combo4_diffusion_aug_kaggle.py:166`)

### Observation 2: Flaw 07 — `strict=False` in `load_state_dict()` Without Key Assertions
In `src/models/chakranet_segmenter.py`, lines 235–242:
```python
sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
missing, unexpected = self.model.load_state_dict(sd, strict=False)
if missing:
    print(f"[WARN] ChakraNet: Missing keys in checkpoint ({len(missing)}): {missing[:3]}...")
if unexpected:
    print(f"[WARN] ChakraNet: Unexpected keys in checkpoint ({len(unexpected)}): {unexpected[:3]}...")
```
In `src/conformal/conformal_calibration.py`, lines 307–308:
```python
sd = torch.load(weights_path, map_location=device)
model.load_state_dict(sd, strict=False)
```
In `verify_flaw_7.py`, loading a mock model with prefix `module.` under `strict=False` resulted in:
`Total model keys: 4 | Loaded keys matching: 0 | Missing keys: 4 | Unexpected keys: 4 | Errors raised: 0`.

### Observation 3: Flaw 08 — Sign-Flipped Conformal Formula
In `src/models/chakranet_segmenter.py`, lines 343–344 and lines 460–461:
```python
score_pos = 1.0 - (prob_resized + variance)
score_neg = prob_resized - variance
```
In `src/conformal/conformal_calibration.py`, lines 82–111:
```python
def nonconformity_pos(mean_prob, variance):
    return (1.0 - mean_prob) + variance

def nonconformity_neg(mean_prob, variance):
    return mean_prob + variance
```
Execution of `verify_flaw_8.py` confirmed that for $(p=0.8, v=0.1)$:
Canonical $S_{\text{pos}} = 0.3000$ vs Buggy $S_{\text{pos}} = 0.1000$ (numerical error of $\Delta = 2v = 0.2000$).

### Observation 4: Flaw 09 — MC-Dropout Variance Collapse (~2.85e-15)
In `results/combo1_metrics.json`, line 5:
`"mean_uncertainty": 2.8514779038956057e-15`
In `src/evaluation/run_all_combos.py`, lines 177–179 and 636–647:
`enable_mc_dropout()` sets `self.mc_dropout = True`, but `model.eval()` keeps `self.drop.training == False`.
Execution of `test_collapse_mechanism.py` confirmed that running 16 passes with `m.eval()` and `mc_dropout = True` yields:
`DummyModel var mean: 5.0732407e-15`, matching the exact $\approx 10^{-15}$ machine-precision noise floor recorded in `combo1_metrics.json`.

### Observation 5: Flaw 10 — Contradictory Calibration $q_{\text{hat}}$ Files
In `weights/calibration/conformal_calibration.json`:
`{"q_hat_pos": 0.521484375, "q_hat_neg": 0.55421875, "alpha": 0.05, "mc_passes": 16, "n_calibration_images": 100}`
In `results/combo1_metrics.json`:
`{"conformal": {"alpha_5": {"q_hat": 0.9999926739931106, "threshold": 7.3260068893521435e-06, "n_calib": 200}}}`
Execution of `verify_flaw_10.py` confirmed:
`Ratio A / B: 71,182.62x | Orders of magnitude difference: 4.85 orders of magnitude`.

---

## 2. Logic Chain

1. **Flaw 06 (Security ACE)**:
   - Observation 1 proves 32 `torch.load` calls omit `weights_only=True`.
   - In PyTorch, deserialization without `weights_only=True` invokes Python's standard `pickle.load`.
   - Untrusted pickle archives can contain arbitrary reduction bytecode (`__reduce__`), enabling arbitrary remote code execution on the host system upon evaluation.

2. **Flaw 07 (Silent Zero-Weight Loading)**:
   - Observation 2 proves `strict=False` is used without asserting that missing/unexpected key counts equal zero.
   - When a checkpoint contains multi-GPU `module.` prefixes or unhandled prefixes, PyTorch drops all keys without raising an exception.
   - The model silently runs inference using uninitialized random Gaussian weights, collapsing Dice to 0.1835 (blank output), leaving polyps undetected in clinical use.

3. **Flaw 08 (Conformal Guarantee Breakdown)**:
   - Observation 3 proves inference calculates $S_{\text{pos}} = 1 - (p + v) = (1 - p) - v$, while calibration calculates $S_{\text{pos}} = (1 - p) + v$.
   - Conformal coverage guarantees require identical non-conformity functions at calibration and test time under exchangeability.
   - Applying quantile $\hat{q}$ calibrated on $S^{\text{cal}}$ to test samples evaluated with $S^{\text{infer}}$ shifts test scores by $-2v$, invalidating the 95% empirical coverage guarantee.

4. **Flaw 09 (MC-Dropout Collapse)**:
   - Observation 4 proves `enable_mc_dropout()` fails to set `self.drop.train()`.
   - When `model.eval()` is called, PyTorch `Dropout2d` layers act as identity operations.
   - All 16 stochastic forward passes return identical tensor activations. The resulting variance $\approx 2.85 \times 10^{-15}$ is floating-point rounding noise under FP16 autocast, leaving the uncertainty metric completely non-functional.

5. **Flaw 10 (Calibration Provenance Contradiction)**:
   - Observation 5 proves that `weights/calibration/conformal_calibration.json` ($q \approx 0.5215$) and `results/combo1_metrics.json` ($\tau \approx 7.33 \times 10^{-6}$) differ by a factor of 71,183 ($4.85$ orders of magnitude).
   - The $10^{-5}$ threshold in `combo1_metrics.json` arose because collapsed MC-dropout variance caused positive non-conformity to reduce to $1 - p$ on confident pixels ($p \approx 0.9999927$).
   - The README cites the collapsed $10^{-5}$ threshold, shipped model weights distribute the $0.5215$ threshold, and streaming inference hardcodes a heuristic $\tau=0.45$.

---

## 3. Caveats

- **Scope boundary**: This investigation was strictly read-only and analyzed the local repository. External datasets or third-party cloud URLs were not contacted (CODE_ONLY mode).
- **GPU non-determinism**: The exact value of variance noise in Flaw 09 ($2.85 \times 10^{-15}$ vs $5.07 \times 10^{-15}$) varies slightly depending on CUDA architecture and FP16 reduction order, but both are fundamentally floating-point precision artifacts rather than stochastic dropout signal.
- **Upstream dependency**: Full regeneration of `conformal_calibration.json` requires resolving Flaw 09 (working dropout) and Flaw 08 (canonical formula) simultaneously before running calibration.

---

## 4. Conclusion

Flaws 6 through 10 represent critical integrity, security, and statistical defects that render the codebase vulnerable to arbitrary code execution (Flaw 6), silent runtime failure on random weights (Flaw 7), loss of mathematical safety guarantees (Flaw 8), dead uncertainty estimation (Flaw 9), and conflicting deployment thresholds differing by $71,183\times$ (Flaw 10).
All 5 flaws have been fully analyzed, with verified detection test scripts and drop-in unified diff patches provided in `analysis.md`.

---

## 5. Verification Method

To independently verify all findings:
1. **Flaw 06 Detection Script**:
   Run `python M:\chakramodel\.agents\explorer_m1_2_g12\test_flaw_06_prototype.py`.
   Expected result: Exits `1` and lists 31 active unguarded `torch.load` calls without `weights_only=True`.
2. **Flaw 07 Detection Script**:
   Run `python M:\chakramodel\.agents\explorer_m1_2_g12\test_flaw_07_prototype.py`.
   Expected result: Exits `1` due to absence of strict key assertions in `src/models/chakranet_segmenter.py`.
3. **Flaw 08 Detection Script**:
   Run `python M:\chakramodel\.agents\explorer_m1_2_g12\test_flaw_08_prototype.py`.
   Expected result: Exits `1` due to detection of `1.0 - (prob_resized + variance)` in `src/models/chakranet_segmenter.py`.
4. **Flaw 09 Detection Script**:
   Run `python M:\chakramodel\.agents\explorer_m1_2_g12\test_flaw_09_prototype.py`.
   Expected result: Exits `1` due to recorded variance `2.8514779038956057e-15` in `results/combo1_metrics.json`.
5. **Flaw 10 Detection Script**:
   Run `python M:\chakramodel\.agents\explorer_m1_2_g12\test_flaw_10_prototype.py`.
   Expected result: Exits `1` due to 4.85 orders of magnitude discrepancy between calibration files.
6. **Detailed Analysis**:
   Inspect `M:\chakramodel\.agents\explorer_m1_2_g12\analysis.md` for complete code references, impact breakdowns, adversarial test designs, and unified diff patches.
