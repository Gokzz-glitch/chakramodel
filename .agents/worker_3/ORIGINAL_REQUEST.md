## 2026-08-29T07:19:05Z
You are Worker 3 (Notebook Generator for Combos 5 & 6).
Your working directory is: m:\chakramodel\.agents\worker_3
Scope document: m:\chakramodel\PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Inputs:
- Read `m:\chakramodel\.agents\explorer_1\analysis.md` for the verified bulletproof Kvasir-SEG dataset download and extraction code snippet for `/kaggle/working/data/kvasir-seg`.
- Read `m:\chakramodel\.agents\explorer_2\analysis.md` for the PraNet ResNet-101 architecture and Federated Learning (FedAvg) blueprint.
- Read `m:\chakramodel\.agents\explorer_3\analysis.md` for the ChakraTransformer ViT-Large (`vit_large_patch16_384`), Progressive Upsampling Decoder, and Conformal Uncertainty Calibration blueprint.
- Read `m:\chakramodel\PROJECT.md`.

Deliverables:
1. Create `m:\chakramodel\notebooks\Combo5_Federated_ChakraNet.ipynb`:
   - Title: Combo #5: Fed-ChakraNet (Multi-Center Federated Learning across Decentralized Clinical Cohorts)
   - Complete Markdown theory cells explaining GDPR/HIPAA-compliant federated learning, non-IID endoscopic data distribution, and FedAvg weight aggregation across hospital nodes.
   - Code Cells 1-4: Environment, setup, Kvasir-SEG download/extraction to `/kaggle/working/data/kvasir-seg`, and multi-hospital client data partitioning (`batch_size=32` per client node, `num_workers=4`).
   - Code Cell 5: Full `PraNetResNet101` architecture.
   - Code Cell 6: Federated Server and Client classes implementing local training epochs (AMP FP16, batch size 32) and FedAvg parameter aggregation.
   - Code Cell 7: Multi-round Federated training execution loop (simulating Hospital A: Kvasir Norway, Hospital B: CVC Spain, Hospital C: ETIS France).
   - Code Cell 8: Global model vs local standalone model evaluation, convergence curves across federated communication rounds, and visual segmentation overlays.

2. Create `m:\chakramodel\notebooks\Combo6_ChakraTransformer.ipynb`:
   - Title: Combo #6: ChakraTransformer (Vision Transformer ViT-Large `vit_large_patch16_384` + Progressive Decoder + Conformal Uncertainty Calibration)
   - Complete Markdown theory cells explaining Vision Transformers for mucosal attention, ViT-Large patch embeddings (24x24 grid, embed_dim=1024), progressive transpose convolution upsampling, and distribution-free conformal calibration.
   - Code Cells 1-3: Environment (`timm`, `torchvision`, `scikit-learn`), setup, and Kvasir-SEG download/extraction to `/kaggle/working/data/kvasir-seg`.
   - Code Cell 4: High-resolution Dataset & DataLoader (384x384 resolution, `batch_size=32`, `num_workers=4`, `pin_memory=True`, Albumentations/Torchvision augmentations).
   - Code Cell 5: Full standalone `ChakraTransformerSegmenter` class using `timm.create_model('vit_large_patch16_384', pretrained=True)` and 4-stage Progressive Transpose Convolution Decoder Head (24x24 -> 48x48 -> 96x96 -> 192x192 -> 384x384).
   - Code Cell 6: `DiceFocalLoss` (alpha=0.25, gamma=2.0) and AMP FP16 training loop with AdamW and CosineAnnealingLR.
   - Code Cell 7: Inductive Split-Conformal Calibration module calculating non-conformity scores and conformal threshold tau_alpha on calibration set, producing mathematically bounded Inner Core and Outer Safety masks (alpha=0.10 -> 90% coverage, alpha=0.05 -> 95% coverage).
   - Code Cell 8: Comprehensive test evaluation (Dice, mIoU, empirical conformal coverage rate) and multi-panel visualization of RGB input, ground truth, predicted mask, and conformal safety bounding intervals.

3. Verify both `.ipynb` files:
   - Validate JSON syntax.
   - Parse with `nbformat.read()`.
   - Parse all code cells with Python `ast.parse()` to guarantee 0 syntax errors.
   - Execute verification tests and document results in `m:\chakramodel\.agents\worker_3\handoff.md`.
