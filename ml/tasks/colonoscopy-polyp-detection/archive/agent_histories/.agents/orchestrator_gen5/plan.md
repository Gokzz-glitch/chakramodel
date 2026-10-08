# Detailed Execution Plan — Orchestrator Gen 5

## Objective
Orchestrate the end-to-end verification of the weight loading fix, dataset evaluation on Kvasir-SEG, documentation finalization (`FIXES.md`), and Kaggle notebook update (`notebooks/Kaggle_Final_Proof_Eval.ipynb`), followed by multi-agent review, empirical stress-testing, and forensic integrity auditing.

## Milestones & Execution Workflow

### Phase 1: Milestone 1 & 2 Execution
1. Dispatch Worker (`worker_m1_m2_g5`):
   - Run `python src/verify_weights_load.py` and confirm clean output: PASS, 0 missing keys, 0 unexpected keys, output span > 0.05, mean not in [0.49, 0.51].
   - Evaluate the fixed model on >= 50 pairs from `data/kvasir-seg` (images and masks).
   - Save output to `results/corrected_eval_kvasir_seg.json` with keys `{mean_dsc, mean_iou, n_images, timestamp, model_path, weight_loading_status}`.
   - Ensure strictly NO fabrication or hardcoding.

### Phase 2: Milestone 3 Execution
1. Dispatch Worker (`worker_m3_g5`):
   - Update `m:\chakramodel\FIXES.md` with:
     * Root cause (DDP `module.` prefix not stripped)
     * Exact lines changed in `src/chakranet_segmenter.py`
     * Before/after code diff
     * Evidence from weight inspection (312 keys, `module.decode_head.6.bias = -0.011656`)
     * Actual measured results after fix (from `results/corrected_eval_kvasir_seg.json`)
     * Timestamp: 2026-09-08
   - Update `notebooks/Kaggle_Final_Proof_Eval.ipynb`:
     * Ensure cell position 2 (after imports, before evaluation loop) strips `module.` prefix, prints PASS/FAIL check, and has timestamp comment: 2026-09-08.
     * Ensure weights loading path handling doesn't fail due to cell order dependencies.

### Phase 3: Milestone 4 — Multi-Agent Review, Empirical Stress-Test & Forensic Audit
1. Spawn 2 Reviewers (`reviewer_m4_1_g5`, `reviewer_m4_2_g5`):
   - Verify code quality, fix correctness, JSON schema, notebook cell positioning, and completeness of `FIXES.md`.
2. Spawn 2 Challengers (`challenger_m4_1_g5`, `challenger_m4_2_g5`):
   - Empirically execute the verification script and evaluate DSC on test inputs.
   - Verify probability range > 0.05 and no collapse zone.
3. Spawn 1 Forensic Auditor (`teamwork_preview_auditor_m4_g5`):
   - Run integrity forensics on `results/corrected_eval_kvasir_seg.json`, `FIXES.md`, and `src/chakranet_segmenter.py`.
   - Verify no hardcoded metrics, no facades, genuine execution.
4. Gate:
   - All pass criteria must hold, and Forensic Auditor verdict must be CLEAN.
5. Report to Parent Sentinel (`fbdb1085-7a0b-4f1c-82d8-0802357dc560`).
