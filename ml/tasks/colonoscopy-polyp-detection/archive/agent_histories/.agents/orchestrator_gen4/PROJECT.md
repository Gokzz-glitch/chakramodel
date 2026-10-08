# Project: ChakraModel Weight Loading Fix & Validation (Gen 4)

## Architecture
- Model Architecture: YOLO + ViT-Large (ChakraNet Segmenter, `src/chakranet_segmenter.py`)
- Checkpoint: `weights/chakra_transformer_best.pth` (1.2GB, 312 keys saved from DDP with `module.*` prefix)
- Evaluation Harness: `src/verify_weights_load.py`, local dataset or synthetic evaluation
- Outputs: `results/corrected_eval_kvasir_seg.json`, `FIXES.md`, `notebooks/Kaggle_Final_Proof_Eval.ipynb`

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Verify Weight Loading Fix (R1) | Inspect weights, verify `module.` strip in `src/chakranet_segmenter.py`, execute `src/verify_weights_load.py` until PASS, check missing/unexpected keys & output range | none | PLANNED |
| M2 | Quick DSC Evaluation (R2) | Discover local dataset (`datasets/kvasir-seg` or `data/kvasir-seg`) or generate synthetic evaluation (20 images + circular masks); record `results/corrected_eval_kvasir_seg.json` | M1 | PLANNED |
| M3 | Documentation & Kaggle Notebook (R3, R4) | Write `m:/chakramodel/FIXES.md` (all 5 sections) and update `notebooks/Kaggle_Final_Proof_Eval.ipynb` at cell 2 | M1, M2 | PLANNED |
| M4 | Comprehensive Multi-Agent Verification & Forensic Audit | Reviewers, Challengers, and Forensic Auditor verify clean loading, real metric calculation, no hardcoding/fabrication | M1, M2, M3 | PLANNED |

## Interface Contracts & Constraints
- `src/verify_weights_load.py` output: Must exit 0 and print PASS with 0 missing keys, 0 unexpected keys, output mean not in [0.49, 0.51], and output probabilities spanning range > 0.05.
- `results/corrected_eval_kvasir_seg.json`: Must contain `{mean_dsc, mean_iou, n_images, timestamp, model_path, weight_loading_status}`.
- `FIXES.md`: Must cover root cause, exact lines changed, before/after diff, weight inspection evidence, results after fix, timestamp 2026-09-08.
- `notebooks/Kaggle_Final_Proof_Eval.ipynb`: Cell position 2 (after imports, before evaluation loop) strips `module.` prefix, prints PASS/FAIL check, and has timestamp comment.
- Zero tolerance on fabrication.
