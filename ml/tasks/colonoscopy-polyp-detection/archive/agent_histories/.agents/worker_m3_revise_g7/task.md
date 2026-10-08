# Worker M3 (Gen 7) Task Assignment: Revise COLAB_EVALUATION_AUDIT_REPORT.md

## Mission
Update and perfect `m:\chakramodel\COLAB_EVALUATION_AUDIT_REPORT.md` by directly incorporating all feedback, empirical findings, and defect resolutions from Reviewer 2, Challenger 1, and Challenger 2.

## Mandatory Revisions to Incorporate into `COLAB_EVALUATION_AUDIT_REPORT.md`:
1. **Archive Naming & Extraction Alignment (Reviewer 2, Defect 1 & 2)**:
   - In Colab Cell 2 (Artifact 1), align search patterns to support BOTH unified archives (`chakramodel_colab_complete.zip`) AND dual archives (`chakramodel_data_scripts.zip` + `chakramodel-weights.zip`), ensuring both data and weights are properly extracted.
2. **Whole-Architecture Catalog Completeness (Reviewer 2, Defect 3)**:
   - Expand Section 6 to include `src/verify_eval.py` (Line 11: `torch.cuda.is_available = lambda: False`), `src/chakranet_segmenter.py` (line 200: CUDA requirement assertion), and `notebooks/Colab_ChakraTransformer_Evaluation.ipynb` (hardcoded Drive paths).
3. **Eliminate Hardcoded Paths in Proposed Fixes (Reviewer 2, Defect 4)**:
   - In Artifact 3 (`local_eval.py`), remove the hardcoded paths in `resolve_base_dir()` (`/content/drive/MyDrive/chakramodel`, etc.) and replace with the dynamic 4-Tier Asset Resolver.
4. **POSIX Case-Insensitive Directory Matching (Reviewer 2, Defect 5 & Challenger 1)**:
   - In Colab Cell 2 and all resolver scripts, use case-insensitive matching for `chakra*` directories so `ChakraModel`, `CHAKRAMODEL`, etc. are discovered.
5. **Add Kaggle Read-Only Input Paths (Reviewer 2, Defect 6)**:
   - Include `/kaggle/input/` and `/kaggle/working/` in candidate search roots.
6. **Robust Mask Binarization (Reviewer 2, Defect 7)**:
   - In Artifact 2, use adaptive binarization `(gt_resized > 127 if gt_resized.max() > 1 else gt_resized > 0.5)` to seamlessly handle both `[0, 255]` and `[0, 1]` ground truth masks.
7. **Fail-Fast CLI Validation & Environment Variables (Challenger 1)**:
   - In the 4-Tier Asset Resolver, fail fast if a specified CLI argument or env var does not exist, rather than silently falling back.
   - Include explicit Tier 2 env var checks: `CHAKRA_WEIGHTS`, `CHAKRA_DATA_ROOT`, `CHAKRA_PROJECT_ROOT`.
8. **Checkpoint Nuance & Accuracy (Challenger 2)**:
   - In §3.3 and §4.3, correct the claim about `.pth` vs `.pth.bak`: state that `.bak` is the unprefixed checkpoint from the historical PDF run, while `.pth` is a distinct DDP snapshot with `module.` prefixes (310/312 tensors differ numerically).
   - Clarify parameter vs buffer counts: 309,173,737 learnable parameters + 642 BatchNorm buffers = 309,174,379 total state dict elements.
   - Document `weights/best.pt` loading nuance with PyTorch 2.6+ (`weights_only=False` or `YOLO('weights/best.pt')`).
   - Document transient VRAM mitigation (load state dict on CPU before GPU transfer).

## Hard Constraint:
REPORT ONLY: Edit ONLY `m:\chakramodel\COLAB_EVALUATION_AUDIT_REPORT.md` and your worker metadata in `.agents/worker_m3_revise_g7`. Do not modify any source code files!
