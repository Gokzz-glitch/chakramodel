## 2026-08-29T07:19:05Z
You are Worker 1 (Notebook Generator for Combos 1 & 2).
Your working directory is: m:\chakramodel\.agents\worker_1
Scope document: m:\chakramodel\PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Inputs:
- Read `m:\chakramodel\.agents\explorer_1\analysis.md` for the verified bulletproof Kvasir-SEG dataset download and extraction code snippet for `/kaggle/working/data/kvasir-seg`.
- Read `m:\chakramodel\.agents\explorer_2\analysis.md` for the PraNet ResNet-101 architecture, YOLOv8x integration, Topological Loss formulation, and Combo 1 & 2 blueprints.
- Read `m:\chakramodel\PROJECT.md`.

Deliverables:
1. Create `m:\chakramodel\notebooks\Combo1_ChakraNet_Focal.ipynb`:
   - Title: Combo #1: ChakraNet-Focal (YOLOv8x + PraNet ResNet-101 + DiceFocalLoss + MC Dropout)
   - Complete Markdown theory cells explaining two-stage detection + segmentation architecture, ResNet-101 backbone, and MC Dropout uncertainty.
   - Code Cell 1: Environment check, package install, and GPU VRAM info.
   - Code Cell 2: Kaggle working directory setup (`/kaggle/working/data/kvasir-seg`).
   - Code Cell 3: Robust automated Kvasir-SEG download and extraction snippet into `/kaggle/working/data/kvasir-seg` with mirror fallback & 1000-image verification.
   - Code Cell 4: Max-spec Dataset & DataLoader (`batch_size=32`, `num_workers=4`, `pin_memory=True`, Albumentations/Torchvision augmentations).
   - Code Cell 5: Full standalone `PraNetResNet101` model architecture with 4-stage RFB blocks, PPD global saliency, Reverse Attention modules, and MC Dropout.
   - Code Cell 6: `DiceFocalLoss` and Deep Supervision loss over all 5 output maps.
   - Code Cell 7: Full AMP FP16 training loop (batch size 32), CosineAnnealingLR, validation metrics logging (Dice, mIoU, Sensitivity, Specificity).
   - Code Cell 8: MC Dropout uncertainty estimation pass and visual overlay generation on test images.

2. Create `m:\chakramodel\notebooks\Combo2_Topo_ChakraNet.ipynb`:
   - Title: Combo #2: Topo-ChakraNet (PraNet ResNet-101 + Differentiable Topological Regularization)
   - Complete Markdown theory cells explaining persistent homology, Betti numbers (beta_0=1 connected component, beta_1=0 no spurious holes), and mucosal boundary preservation.
   - Code Cells 1-4: Environment, setup, Kvasir-SEG download/extraction to `/kaggle/working/data/kvasir-seg`, and DataLoader (`batch_size=32`, `num_workers=4`).
   - Code Cell 5: Full `PraNetResNet101` architecture.
   - Code Cell 6: `TopoAwareLoss` (DiceFocalLoss + Topological Loss regularizer penalizing fragmented clusters and holes).
   - Code Cell 7: Full AMP FP16 training loop with warm-start capability and topological accuracy tracking.
   - Code Cell 8: Connected components evaluation, topological stability metrics, and visual comparison overlays.

3. Verify both `.ipynb` files:
   - Validate JSON syntax.
   - Parse with `nbformat.read()`.
   - Parse all code cells with Python `ast.parse()` to guarantee 0 syntax errors.
   - Execute verification tests and document results in `m:\chakramodel\.agents\worker_1\handoff.md`.

Update `progress.md` in your folder as you work. Send a message to your orchestrator when done.
