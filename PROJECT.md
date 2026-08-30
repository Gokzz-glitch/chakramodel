# Project: ChakraModel Kaggle Notebooks Suite

## Architecture
The ChakraModel project provides 6 standalone, plug-and-play Kaggle `.ipynb` notebooks corresponding to the 6 optimized polyp detection and segmentation combinations.
Each notebook is entirely self-contained, requiring zero external repository cloning or manual file transfers. It automates dataset acquisition (Kvasir-SEG extraction into `/kaggle/working/data/kvasir-seg`), configures maximized hardware parameters (batch size 32, max workers, upgraded backbones: YOLOv8x, ResNet-101, ViT-Large `vit_large_patch16_384`), and provides comprehensive Markdown theory alongside runnable, production-grade PyTorch training/evaluation cells.

```
Kaggle Notebooks Environment (/kaggle/working)
  ├── Automated Data Pipeline: Download & Extract Kvasir-SEG -> /kaggle/working/data/kvasir-seg/
  ├── Max-Spec Model Backbones:
  │     ├── Combo 1: YOLOv8x + PraNet (ResNet-101) + DiceFocalLoss + MC Dropout
  │     ├── Combo 2: Topo-ChakraNet (ResNet-101) + Topological Loss (Betti Number Regularization)
  │     ├── Combo 3: AdaBN-ChakraNet (ResNet-101) + Test-Time Adaptive Batch Normalization
  │     ├── Combo 4: DiffusionAug-ChakraNet (ControlNet SD1.5 + MC Dropout Filter + ResNet-101)
  │     ├── Combo 5: Fed-ChakraNet (Federated Learning FedAvg Multi-Center + ResNet-101)
  │     └── Combo 6: ChakraTransformer (ViT-Large vit_large_patch16_384 + Progressive Upsampling + Conformal Calibration)
  └── Evaluation & Metrics: DSC, mIoU, Precision, Recall, FPS, Conformal Coverage
```

## Milestones
| # | Name | Scope | Dependencies | Status | Key Outputs |
|---|------|-------|-------------|--------|-------------|
| M1 | Combo 1 Notebook | `Combo1_ChakraNet_Focal.ipynb` (YOLOv8x + PraNet ResNet-101 + DiceFocal) | None | DONE | `m:\chakramodel\notebooks\Combo1_ChakraNet_Focal.ipynb` (61.5 KB, 8 cells, ResNet-101, batch 32) |
| M2 | Combo 2 Notebook | `Combo2_Topo_ChakraNet.ipynb` (PraNet ResNet-101 + Topological Loss) | None | DONE | `m:\chakramodel\notebooks\Combo2_Topo_ChakraNet.ipynb` (60.6 KB, 8 cells, TopoLoss Betti penalty) |
| M3 | Combo 3 Notebook | `Combo3_AdaBN_ChakraNet.ipynb` (PraNet ResNet-101 + Test-Time AdaBN) | None | DONE | `m:\chakramodel\notebooks\Combo3_AdaBN_ChakraNet.ipynb` (69.2 KB, 8 cells, AdaBN domain adaptation) |
| M4 | Combo 4 Notebook | `Combo4_DiffusionAug_ChakraNet.ipynb` (ControlNet + MC Dropout + ResNet-101) | None | DONE | `m:\chakramodel\notebooks\Combo4_DiffusionAug_ChakraNet.ipynb` (71.5 KB, 8 cells, SD1.5 Canny ControlNet) |
| M5 | Combo 5 Notebook | `Combo5_Federated_ChakraNet.ipynb` (Multi-Hospital FedAvg + ResNet-101) | None | DONE | `m:\chakramodel\notebooks\Combo5_Federated_ChakraNet.ipynb` (74.9 KB, 8 cells, FedAvg multi-cohort) |
| M6 | Combo 6 Notebook | `Combo6_ChakraTransformer.ipynb` (ViT-Large vit_large_patch16_384 + Conformal) | None | DONE | `m:\chakramodel\notebooks\Combo6_ChakraTransformer.ipynb` (63.3 KB, 8 cells, ViT-Large + Conformal) |
| M7 | E2E Verification & Forensic Audit | Parse all 6 `.ipynb` with `nbformat`, AST check, verify links & max-spec | M1-M6 | DONE | 100% PASS (Reviewers 1 & 2 APPROVE, Challengers 1 & 2 PASS, Auditor 1 CLEAN) |

## Interface Contracts
### Notebook Cell Structure Contract
Each of the 6 `.ipynb` files follows the standard Jupyter Notebook v4 JSON schema:
1. **Markdown Header Cell**: Title, architecture diagram/explanation, clinical rationale, max-spec configurations.
2. **Environment & Dependencies Cell**: `!pip install ...`, PyTorch/CUDA verification, GPU VRAM checks.
3. **Automated Dataset Acquisition Cell**: Robust automated download and extraction of Kvasir-SEG dataset directly into `/kaggle/working/data/kvasir-seg` with multi-mirror fallback and offline synthetic generator fallback.
4. **Dataset Loader Cell**: PyTorch `Dataset` & `DataLoader` with `batch_size=32`, `num_workers=4`, `pin_memory=True`, Albumentations/Torchvision augmentations.
5. **Model Architecture Cell**: Complete self-contained model classes with upgraded backbones (ResNet-101 / ViT-Large `vit_large_patch16_384` / YOLOv8x).
6. **Loss Function & Optimizer Cell**: DiceFocalLoss, TopoLoss, or Conformal functions with AdamW/SGD and cosine annealing.
7. **Training / Fine-Tuning Execution Cell**: Full training loop with AMP FP16, tqdm progress bars, validation metric tracking (Dice, mIoU).
8. **Evaluation & Visualization Cell**: Visualizing prediction masks overlaid on endoscopic frames, quantitative metrics calculation.

## Code Layout
- Target Notebooks Directory: `m:\chakramodel\notebooks/`
  - `Combo1_ChakraNet_Focal.ipynb` (61.5 KB)
  - `Combo2_Topo_ChakraNet.ipynb` (60.6 KB)
  - `Combo3_AdaBN_ChakraNet.ipynb` (69.2 KB)
  - `Combo4_DiffusionAug_ChakraNet.ipynb` (71.5 KB)
  - `Combo5_Federated_ChakraNet.ipynb` (74.9 KB)
  - `Combo6_ChakraTransformer.ipynb` (63.3 KB)
- Agent Metadata & Audits: `m:\chakramodel\.agents/`
