# Execution Plan: 6 Kaggle Notebooks for ChakraModel

## Objectives
1. Generate 6 standalone, runnable Kaggle Jupyter Notebooks (.ipynb) in `m:\chakramodel\notebooks/` corresponding to the 6 optimized ChakraModel combinations.
2. Ensure automated, robust download of Kvasir-SEG dataset to `/kaggle/working/data/kvasir-seg` in every notebook.
3. Maximize hardware specifications in all notebooks:
   - Batch size 32
   - Workers maxed out (`num_workers=4` or system max)
   - Upgraded model backbones: YOLOv8x, PraNet ResNet-101, ViT-Large (`vit_large_patch16_384`)
4. Verify all 6 notebooks are valid JSON, loadable via `nbformat`, contain zero AST syntax errors in Python code cells, and adhere to max-spec requirements.
5. Perform thorough independent Review, Adversarial Stress Testing (Challenger), and Forensic Integrity Audit before declaring victory.

## Phases
### Phase 1: Exploration & Blueprinting
- Dispatch 3 Explorers (`teamwork_preview_explorer`) to:
  1. Explorer 1: Inspect dataset download mirrors/URLs and extraction scripts to create a bulletproof, network-resilient download cell for Kaggle `/kaggle/working/data/kvasir-seg`.
  2. Explorer 2: Analyze PraNet & ChakraNet architectures (`src/pranet_segmenter.py`, `src/topo_loss.py`, `src/run_all_combos.py`, `notebooks/`) and design the max-spec ResNet-101 implementations with batch size 32 for Combos 1, 2, 3, 4, 5.
  3. Explorer 3: Analyze Transformer & Vision models (`chakra_transformer/`, `vst_fp/`, `notebooks/`) to design the max-spec ViT-Large `vit_large_patch16_384` architecture and conformal calibration pipeline for Combo 6.

### Phase 2: Implementation
- Dispatch Workers (`teamwork_preview_worker`) to generate each notebook in `m:\chakramodel\notebooks/`:
  - Worker 1: Generate `Combo1_ChakraNet_Focal.ipynb` (YOLOv8x + PraNet ResNet-101 + DiceFocalLoss + MC Dropout) & `Combo2_Topo_ChakraNet.ipynb` (PraNet ResNet-101 + Topological Betti Loss).
  - Worker 2: Generate `Combo3_AdaBN_ChakraNet.ipynb` (PraNet ResNet-101 + Test-Time AdaBN) & `Combo4_DiffusionAug_ChakraNet.ipynb` (ControlNet SD1.5 + MC Dropout filter + ResNet-101).
  - Worker 3: Generate `Combo5_Federated_ChakraNet.ipynb` (Multi-Center Federated Learning with PraNet ResNet-101) & `Combo6_ChakraTransformer.ipynb` (ViT-Large `vit_large_patch16_384` + Progressive Upsampling + Conformal Calibration).

### Phase 3: Review & Challenge
- Dispatch 2 Reviewers (`teamwork_preview_reviewer`) to independently review all 6 notebooks for completeness, clarity, schema compliance, and requirement adherence.
- Dispatch 2 Challengers (`teamwork_preview_challenger`) to run automated verification scripts:
  - Validate JSON syntax of all 6 `.ipynb` files.
  - Parse with `nbformat`.
  - Extract and compile all code cells with Python `ast.parse()` to guarantee 0 syntax errors.
  - Verify presence of dataset download commands, `/kaggle/working/data/kvasir-seg` paths, batch size 32, ResNet-101, YOLOv8x, ViT-Large.

### Phase 4: Forensic Audit & Victory Report
- Dispatch Forensic Auditor (`teamwork_preview_auditor`) to ensure authentic implementation without dummy facades or shortcuts.
- Update documentation and send final completion report to Sentinel parent.
