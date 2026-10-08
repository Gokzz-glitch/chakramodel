# Context for Worker M1-M2 (Gen 5)

## Scope
Milestone 1: Verify Weight Loading Fix (R1)
Milestone 2: Quick DSC Evaluation on Kvasir-SEG (R2)

## Working Directory
m:\chakramodel\.agents\worker_m1_m2_g5

## Instructions
1. Verify Weight Loading Fix:
   Run `python src/verify_weights_load.py`. Ensure clean PASS output with:
   - 0 missing keys
   - 0 unexpected keys
   - Output mean NOT in [0.49, 0.51]
   - Output probabilities span range > 0.05
2. Quick DSC Evaluation:
   Evaluate the fixed model on >= 50 images from `data/kvasir-seg` (images and masks exist with 1,000 pairs).
   Inspect `src/run_corrected_eval.py` — make sure it evaluates at least 50 images (e.g., 50 images from the test split to run efficiently, or full test split if GPU is available). Check if CUDA is available to accelerate inference.
   Save output to `results/corrected_eval_kvasir_seg.json` with keys:
   `{mean_dsc, mean_iou, n_images, timestamp, model_path, weight_loading_status}`.
   Verify that DSC and IoU are computed honestly from pixel comparisons. NO FABRICATION.
3. Write `handoff.md` and report back.
