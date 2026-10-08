# Review Report: ChakraNet Weight Loading Fix & Verification (M4.1 Gen 4)

**Reviewer**: Reviewer M4.1 (Gen 4) — reviewer & adversarial critic  
**Date**: 2026-09-08  
**Verdict**: **APPROVE**  
**Integrity Assessment**: **CLEAN (No violations detected)**  
**Overall Risk Assessment**: **LOW**  

---

## Executive Summary

A comprehensive quality review and adversarial critique was conducted on the M4.1 Gen 4 deliverables:
1. Weight loading logic in `src/chakranet_segmenter.py` (lines 224–232).
2. Verification script `src/verify_weights_load.py` (including stream encoding fix and runtime verification).
3. Benchmark evaluation artifact `results/corrected_eval_kvasir_seg.json`.

All required checks passed. Independent execution of `src/verify_weights_load.py` confirmed clean loading (0 missing, 0 unexpected keys, strict-equivalent pass), exit code 0, and non-collapsed output probabilities across diverse inputs with an output mean range of `[0.5312, 0.5898]` (span `0.058594 > 0.05`, outside mode-collapse zone `[0.49, 0.51]`). Mathematical validation of `results/corrected_eval_kvasir_seg.json` confirmed 100% internal consistency across all 60 image entries and top-level summary metrics.

---

## 1. Quality Review Findings

### 1.1 Weight Loading Fix (`src/chakranet_segmenter.py:224-232`)

- **Code Inspected**:
  ```python
  223: sd = torch.load(weights_path, map_location=self.device)
  224: # Strip both DDP 'module.' prefix and torch.compile '_orig_mod.' prefix
  225: sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
  226: missing, unexpected = self.model.load_state_dict(sd, strict=False)
  227: if missing:
  228:     print(f"[WARN] ChakraNet: Missing keys in checkpoint ({len(missing)}): {missing[:3]}...")
  229: if unexpected:
  230:     print(f"[WARN] ChakraNet: Unexpected keys in checkpoint ({len(unexpected)}): {unexpected[:3]}...")
  231: if not missing and not unexpected:
  232:     print(f"[INFO] ChakraNet: Weights loaded cleanly (strict=True equivalent) from {weights_path}")
  ```

- **Prefix Stripping Verification**:
  - `module.`: Correctly handles checkpoints serialized from `torch.nn.parallel.DistributedDataParallel` (DDP).
  - `_orig_mod.`: Correctly handles checkpoints serialized from models wrapped with `torch.compile` (Dynamo/Inductor).
  - Chained replacement `.replace("module.", "").replace("_orig_mod.", "")` handles compound wraps (e.g. DDP wrapping a compiled model or vice-versa).
- **Strict-Equivalence Verification**:
  - `self.model.load_state_dict(sd, strict=False)` captures `missing` and `unexpected` lists.
  - Lines 231–232 check `if not missing and not unexpected:`, which guarantees that the loaded state dict is identical in keys to `strict=True`.
  - When tested against `weights/chakra_transformer_best.pth`, the key count before and after stripping is 312 keys with exactly 0 missing and 0 unexpected keys.

### 1.2 Verification Script (`src/verify_weights_load.py`)

- **Stream Encoding Fix**:
  - Inspected lines 16–20:
    ```python
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    ```
  - Purpose: Fixes Windows console codec crash (`UnicodeEncodeError: 'charmap' codec can't encode character...`) when outputting Unicode/emojis (`✅`, `⛔`, `⚠️`, `✓`).
  - Correctness: Uses standard Python 3.7+ `reconfigure()` with `errors='replace'` and `line_buffering=True`, ensuring cross-platform safety.
- **Independent Execution**:
  - Command: `python src/verify_weights_load.py`
  - Exit code: `0`
  - Output summary:
    - Raw checkpoint keys: 312
    - After prefix stripping: 312 keys
    - Sample keys after stripping: `['backbone.cls_token', 'backbone.pos_embed', 'backbone.patch_embed.proj.weight']`
    - Checkpoint key match: `[OK] All keys loaded cleanly — STRICT EQUIVALENT PASS`
    - Forward passes on 5 distinct inputs:
      - `random_noise`: `mean_prob=0.542969` (✓ VARIED)
      - `all_zeros`: `mean_prob=0.546875` (✓ VARIED)
      - `all_ones`: `mean_prob=0.566406` (✓ VARIED)
      - `gradient`: `mean_prob=0.589844` (✓ VARIED)
      - `wide_uniform`: `mean_prob=0.531250` (✓ VARIED)
    - Output std: `0.020581`
    - Output span: `max(outputs) - min(outputs) = 0.589844 - 0.531250 = 0.058594` (`> 0.05`)
    - Mean exclusion: None of the outputs lie in `[0.49, 0.51]` (minimum is `0.531250`).
    - Final status string: `RESULT: ✅ PASS — Weights loaded cleanly, outputs vary with input`

### 1.3 Evaluation Artifact (`results/corrected_eval_kvasir_seg.json`)

- **JSON Format & Schema Validation**:
  - Valid JSON syntax, parses cleanly with `json.load`.
  - Required top-level keys verified:
    - `mean_dsc`: `0.80225` (present, float)
    - `mean_iou`: `0.73481` (present, float)
    - `n_images`: `60` (present, int)
    - `timestamp`: `"2026-09-08T04:07:28.325623+00:00"` (present, valid ISO-8601 UTC string)
    - `model_path`: `"weights/chakra_transformer_best.pth"` (present, string)
    - `weight_loading_status`: `"STRICT_EQUIVALENT_PASS (0 missing, 0 unexpected keys)"` (present, string)
- **Metric Consistency & Plausibility**:
  - Independent recalculation of all 60 image records:
    - `calc_mean_dsc = sum(dice) / 60 = 0.802250` (matches `mean_dsc` within `< 1e-6`)
    - `calc_mean_iou = sum(iou) / 60 = 0.734811` (matches `mean_iou` within `< 1e-6`)
  - Pixel arithmetic checked:
    - For all 60 images, `dice == 2 * inter / (pred + gt)` and `iou == inter / (pred + gt - inter)` verified with 0 mismatches.
    - Mathematical invariant `IoU <= Dice` holds universally across all items.
  - Plausibility:
    - `mean_dsc = 0.80225` and `mean_iou = 0.73481` reflect realistic polyp segmentation performance on Kvasir-SEG test subset.
    - Distribution reflects expected variance on challenging endoscopic images (min Dice 0.044 on tiny lesion `cju0tl3uz8blh0993wxvn7ly3.jpg`, max Dice 0.996 on well-circumscribed lesion `cju17x0j4nfc10993y31pvlgs.jpg`).

---

## 2. Adversarial Challenge & Stress-Testing

### Challenge 1: Substring vs. Prefix Replacement in Key Transformation [Minor / Advisory]
- **Assumption Challenged**: Key transformation assumes `replace("module.", "")` and `replace("_orig_mod.", "")` will only alter key prefixes.
- **Attack Scenario**: If a future model architecture or third-party backbone introduces an internal submodule named `module` or parameter containing `module.` (e.g., `feature_extractor.module.dense.weight`), `.replace()` will mutate the internal parameter name to `feature_extractor.dense.weight`, causing unexpected key mismatches.
- **Blast Radius**: Low in `ChakraNetMicroRefiner` (verified: none of the 312 keys contain internal `module.` or `_orig_mod.` substrings).
- **Mitigation**: In future refactors, prefer explicit prefix removal:
  ```python
  def strip_prefix(k):
      for prefix in ("module.", "_orig_mod."):
          if k.startswith(prefix):
              k = k[len(prefix):]
      return k
  ```

### Challenge 2: Non-Failing `strict=False` in Silent Mismatch Scenarios [Minor / Advisory]
- **Assumption Challenged**: If a corrupted or altered checkpoint is loaded where keys are missing, `ChakraNet.__init__` logs a warning but proceeds with random weights for uninitialized layers without raising an error.
- **Attack Scenario**: A user passes a partial checkpoint (e.g. only backbone without decode_head). The model logs `[WARN]` to stdout and executes inference, potentially generating mode-collapsed predictions silently in production.
- **Mitigation**: While `strict=False` was intentionally used to avoid unhandled crash during experimental loading, for production deployment it is advisable to expose a `strict=True` argument or raise an explicit error when `missing` contains critical submodules (e.g. `decode_head`).

---

## 3. Integrity Verification Checklist

| Integrity Check | Status | Evidence |
|---|---|---|
| Hardcoded outputs in source | PASSED | Model computes genuine forward passes in `src/chakranet_segmenter.py` and `src/verify_weights_load.py`. |
| Dummy or facade implementation | PASSED | Full ViT-Large backbone (`timm`) and `ChakraNetMicroRefiner` decode head instantiated and evaluated. |
| Shortcuts bypassing task | PASSED | Checkpoint genuinely loaded, keys transformed, and evaluated across inputs. |
| Fabricated verification logs | PASSED | `verify_weights_load.py` executed live with exit code 0; JSON per-pixel metrics mathematically verified. |
| Self-certifying without verification | PASSED | Independent script execution and mathematical validation performed. |

---

## 4. Final Verdict

**APPROVE**  
All criteria of M4.1 Gen 4 are met with high technical quality, verified reproducibility, and zero integrity violations.
