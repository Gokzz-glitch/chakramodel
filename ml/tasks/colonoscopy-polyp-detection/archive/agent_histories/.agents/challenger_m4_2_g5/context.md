# Context for Challenger 2 (Gen 5)

## Scope
Milestone 4 Adversarial Verification: Metric Verification on Kvasir-SEG

## Working Directory
m:\chakramodel\.agents\challenger_m4_2_g5

## Challenge Objectives
1. Independently inspect `results/corrected_eval_kvasir_seg.json`.
2. Sample 5 to 10 images from `results/corrected_eval_kvasir_seg.json` (`per_image_results`).
3. Load the actual images from `data/kvasir-seg/images` and matching masks from `data/kvasir-seg/masks`.
4. Run inference using `ChakraNet` from `src/chakranet_segmenter.py` (with CUDA or CPU).
5. Calculate Dice and IoU on those sampled images from scratch using NumPy.
6. Compare the independently computed Dice and IoU against the recorded numbers in `results/corrected_eval_kvasir_seg.json`. Confirm that the values match within reasonable numerical tolerance (proving no fabrication).
7. Deliver challenge report with independent calculation comparison in `handoff.md`.
