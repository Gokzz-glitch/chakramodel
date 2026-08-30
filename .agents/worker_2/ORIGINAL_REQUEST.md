## 2026-08-29T07:19:05Z
You are Worker 2 (Notebook Generator for Combos 3 & 4).
Your working directory is: m:\chakramodel\.agents\worker_2
Scope document: m:\chakramodel\PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Inputs:
- Read `m:\chakramodel\.agents\explorer_1\analysis.md` for the verified bulletproof Kvasir-SEG dataset download and extraction code snippet for `/kaggle/working/data/kvasir-seg`.
- Read `m:\chakramodel\.agents\explorer_2\analysis.md` for the PraNet ResNet-101 architecture, AdaBN domain adaptation, Stable Diffusion + ControlNet Canny synthetic data pipeline, and Combo 3 & 4 blueprints.
- Read `m:\chakramodel\PROJECT.md`.

Deliverables:
1. Create `m:\chakramodel\notebooks\Combo3_AdaBN_ChakraNet.ipynb`:
   - Title: Combo #3: AdaBN-ChakraNet (Test-Time Adaptive Batch Normalization for Cross-Hospital Generalization)
   - Complete Markdown theory cells explaining domain shift in endoscopy, multi-center distribution differences, and how AdaBN recalibrates BatchNorm statistics without parameter fine-tuning.
   - Code Cells 1-4: Environment, setup, Kvasir-SEG download/extraction to `/kaggle/working/data/kvasir-seg`, and DataLoader (`batch_size=32`, `num_workers=4`).
   - Code Cell 5: Full `PraNetResNet101` architecture.
   - Code Cell 6: Source domain training loop (AMP FP16, batch size 32) using `DiceFocalLoss`.
   - Code Cell 7: Test-Time AdaBN adaptation algorithm (resetting running stats and re-estimating mean/variance on target cohorts like CVC-ClinicDB or unlabelled target batches).
   - Code Cell 8: Cross-domain evaluation metrics before vs after AdaBN, domain drift quantification, and visual prediction overlays.

2. Create `m:\chakramodel\notebooks\Combo4_DiffusionAug_ChakraNet.ipynb`:
   - Title: Combo #4: DiffusionAug-ChakraNet (ControlNet SD1.5 Synthetic Polyp Generation + MC Dropout Quality Gating + ResNet-101 Retraining)
   - Complete Markdown theory cells explaining generative diffusion models for medical imaging, ControlNet edge conditioning from polyp masks, epistemic uncertainty filtering via MC Dropout, and data augmentation retraining.
   - Code Cells 1-4: Environment, setup, Kvasir-SEG download/extraction to `/kaggle/working/data/kvasir-seg`, and DataLoader (`batch_size=32`, `num_workers=4`).
   - Code Cell 5: Stable Diffusion v1.5 + ControlNet Canny pipeline for mask-conditioned synthetic polyp generation with prompt formatting.
   - Code Cell 6: MC Dropout uncertainty evaluation filter to reject synthetic images with high epistemic variance (filtering threshold < 0.04).
   - Code Cell 7: `PraNetResNet101` retraining on combined real Kvasir-SEG + uncertainty-filtered synthetic polyp dataset with batch size 32, AMP FP16.
   - Code Cell 8: Comparison evaluation: baseline vs diffusion-augmented model, ablation metrics, and synthetic vs real visual overlays.

3. Verify both `.ipynb` files:
   - Validate JSON syntax.
   - Parse with `nbformat.read()`.
   - Parse all code cells with Python `ast.parse()` to guarantee 0 syntax errors.
   - Execute verification tests and document results in `m:\chakramodel\.agents\worker_2\handoff.md`.

Update `progress.md` in your folder as you work. Send a message to your orchestrator when done.
