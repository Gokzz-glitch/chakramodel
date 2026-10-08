# Detailed Execution Plan — Orchestrator Gen 4

## Objective
Orchestrate the end-to-end verification of the weight loading fix, dataset evaluation, documentation generation (`FIXES.md`), and Kaggle notebook update (`notebooks/Kaggle_Final_Proof_Eval.ipynb`), culminating in multi-agent review, empirical stress-testing, and forensic integrity auditing.

## Step-by-Step Plan

### Phase 1: Milestone 1 — Verification of Weight Loading Fix (R1)
1. Spawn 3 Explorers (`teamwork_preview_explorer_m1_1_g4`, `teamwork_preview_explorer_m1_2_g4`, `teamwork_preview_explorer_m1_3_g4`):
   - Explorer 1: Inspect `src/chakranet_segmenter.py` (specifically line 224 and surrounding state dict logic) and `weights/chakra_transformer_best.pth`.
   - Explorer 2: Inspect `src/verify_weights_load.py` and run/evaluate its verification logic, checking key matching, missing/unexpected keys, output range, and mean.
   - Explorer 3: Inspect local data availability (`datasets/kvasir-seg`, `data/kvasir-seg`, etc.) for Milestone 2 readiness.
2. If `src/verify_weights_load.py` requires fixes or adjustments to achieve 100% PASS with 0 missing and 0 unexpected keys:
   - Spawn Worker to implement/adjust fix and verify that `python src/verify_weights_load.py` prints PASS cleanly.

### Phase 2: Milestone 2 — Quick DSC Evaluation (R2)
1. Spawn Worker (`worker_m2_eval_g4`):
   - If local Kvasir-SEG data exists with images and masks: evaluate the fixed model on >=50 images, compute mean DSC and mean IoU.
   - If no local data exists: run synthetic evaluation (20 random 224x224 images + known circular masks r=50) and test for spatially varying outputs.
   - Save output to `results/corrected_eval_kvasir_seg.json` with keys `{mean_dsc, mean_iou, n_images, timestamp, model_path, weight_loading_status}`.
   - Ensure absolutely NO fabrication or hardcoding.

### Phase 3: Milestone 3 — Documentation & Notebook Update (R3, R4)
1. Spawn Worker (`worker_m3_docs_g4`):
   - Write `m:/chakramodel/FIXES.md` with:
     * Root cause (DDP `module.` prefix not stripped)
     * Exact lines changed in `src/chakranet_segmenter.py`
     * Before/after code diff
     * Evidence from weight inspection (312 keys, `module.decode_head.6.bias = -0.011656`)
     * Results after fix (DSC from R2)
     * Timestamp: 2026-09-08
   - Update `notebooks/Kaggle_Final_Proof_Eval.ipynb`:
     * Insert cell at position 2 (after imports, before evaluation loop)
     * Strip `module.` prefix before loading
     * Print PASS/FAIL check
     * Timestamp comment: 2026-09-08
   - Verify valid JSON structure of notebook.

### Phase 4: Milestone 4 — Multi-Agent Review, Empirical Stress-Test & Forensic Audit
1. Spawn Reviewers (`teamwork_preview_reviewer`): Verify code quality, fix correctness, JSON validity, notebook cell positioning, and completeness of `FIXES.md`.
2. Spawn Challengers (`teamwork_preview_challenger`): Independently execute the verification script, test weight loading under adverse conditions, and verify probability range > 0.05.
3. Spawn Forensic Auditor (`teamwork_preview_auditor`): Audit codebase, evaluation script, json results, and notebook for any integrity violation, dummy facade, hardcoding, or fabrication.
4. Final Gate Evaluation: Pass only if all checks pass and Forensic Auditor verdict is CLEAN.
5. Synthesize results and report completion to parent sentinel (`fbdb1085-7a0b-4f1c-82d8-0802357dc560`).
