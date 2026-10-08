# Detailed Execution Plan — Orchestrator Gen 6

## Objective
Execute and finalize Milestone 4 for the ChakraModel weight loading bug fix and evaluation project.
Verify all 4 Acceptance Criteria:
1. `src/verify_weights_load.py` prints PASS, output probabilities span > 0.05.
2. `results/corrected_eval_kvasir_seg.json` exists, valid JSON, mean_dsc > 0.50.
3. `FIXES.md` exists with all 5 mandatory sections filled, Kaggle notebook updated.
4. No fabrication; all metrics genuine.

## Execution Workflow

### Step 1: Initialize Orchestrator Environment
- Create `ORIGINAL_REQUEST.md`, `BRIEFING.md`, `plan.md`, `progress.md`.
- Start heartbeat cron (`*/10 * * * *`).

### Step 2: Multi-Agent Dispatch for Milestone 4
1. **Reviewer 1** (`teamwork_preview_reviewer` in `.agents/reviewer_m4_1_g6`):
   - Review code fix in `src/chakranet_segmenter.py` (lines 223-232) and verify clean state dict loading.
   - Review `src/verify_weights_load.py` logic.
   - Review `results/corrected_eval_kvasir_seg.json` format, completeness, and validity.
2. **Reviewer 2** (`teamwork_preview_reviewer` in `.agents/reviewer_m4_2_g6`):
   - Review `FIXES.md` ensuring all 5 mandatory sections are present with zero unresolved placeholders.
   - Review `notebooks/Kaggle_Final_Proof_Eval.ipynb` ensuring cell 2 exists, strips DDP `module.` prefix, has PASS/FAIL check, and timestamp 2026-09-08.
3. **Challenger 1** (`teamwork_preview_challenger` in `.agents/challenger_m4_1_g6`):
   - Execute `python src/verify_weights_load.py` in powershell.
   - Confirm it prints PASS, loads 312 keys with 0 missing and 0 unexpected, and output span > 0.05.
   - Verify outputs on diverse synthetic inputs.
4. **Challenger 2** (`teamwork_preview_challenger` in `.agents/challenger_m4_2_g6`):
   - Read `results/corrected_eval_kvasir_seg.json`.
   - Calculate independent mean DSC and IoU across all 60 per-image results.
   - Verify mean_dsc > 0.50 and no constant/blank predictions.
5. **Forensic Auditor** (`teamwork_preview_auditor` in `.agents/auditor_m4_g6`):
   - Perform forensic integrity checks on code, results, documentation, and notebook.
   - Verify zero fabrication, zero hardcoding, genuine metrics.

### Step 3: Synthesis & Gating
- Collect all handoff reports.
- Evaluate gate: All Reviewers approve, Challengers pass, Auditor is CLEAN.
- Update `progress.md` and `PROJECT.md`.

### Step 4: Final Reporting
- Send victory message to parent Sentinel (`fbdb1085-7a0b-4f1c-82d8-0802357dc560`).
- Sentinel will spawn the mandatory Victory Auditor.
