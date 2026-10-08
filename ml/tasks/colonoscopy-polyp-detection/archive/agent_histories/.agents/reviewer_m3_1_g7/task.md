# Reviewer M3-1 (Gen 7) Task Assignment

## Mission
Perform an exhaustive technical review of `m:\chakramodel\COLAB_EVALUATION_AUDIT_REPORT.md`.

## Verification Scope
1. Verify all code citations, exact line numbers, and logic descriptions against actual codebase files:
   - `src/verify_strict.py` (lines 9-10, 15-16, 37, 48, 102-104, 110-112, 122, 126-128, 142-149)
   - `local_eval.py` (lines 12-46, 72-99, 100-118, 135, 138-146, 149, 159, 162-163)
   - `setup_colab.py` (lines 5-6, 11-48, 78)
   - `Colab_GPU_Fast_Verify.ipynb` (Cells 2, 3, 4)
   - `COLLABRUNTESTING.pdf` (Page 2 logs, Dice scores 0.8125, 0.8004)
   - Zip archives (`chakramodel_data_scripts.zip`, `chakramodel-weights.zip`, `chakramodel_weights_PRIVATE.zip`)
2. Verify that no vague assumptions exist and every claim is backed by concrete evidence.
3. Write your review findings and verdict (PASS/FAIL) in `m:\chakramodel\.agents\reviewer_m3_1_g7\review.md` and `handoff.md`.
