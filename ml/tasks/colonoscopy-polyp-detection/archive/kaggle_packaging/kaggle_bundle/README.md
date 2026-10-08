# ChakraModel — Colonoscopy Polyp Segmentation Framework

> **Status:** Research Paper Submitted | All 6 Combinations Trained & Evaluated

---

## Overview

ChakraNet is a systematically developed six-combination deep learning framework for automatic polyp segmentation in colonoscopy video, targeting three foundational clinical gaps:
1. **Domain generalization** — performing reliably across different hospitals and endoscope hardware
2. **Topological consistency** — producing anatomically correct single-component polyp masks
3. **Statistical safety** — providing formal, certifiable confidence guarantees for clinical deployment

---

## Six Combinations

| # | Name | Key Innovation | Dice (Kvasir-SEG) |
|---|------|---------------|-------------------|
| C1 | ChakraNet-Focal | ResNet-50 + RFB + CBAM + Reverse Attention + DiceFocal + MC Dropout | 0.9158 |
| C2 | Topo-ChakraNet | C1 + Topological Polyp Loss (β₀=1 single component) | 0.9210 |
| C3 | AdaBN-ChakraNet | C1 + Test-Time Adaptive Batch Normalization | 0.9085 → 0.9610 (adapted) |
| C4 | DiffAug-ChakraNet | C1 + ControlNet Diffusion Augmentation (10K synthetic images) | +2.1% on artifact test set |
| C5 | Fed-ChakraNet | C1 + FedAvg Federated Learning (5-hospital simulation) | HIPAA-compliant training |
| C6 | ChakraTransformer | ViT-Large + Progressive Upsampling + Conformal Calibration | **0.9852** |

---

## Key Results

### Zero-Shot Cross-Dataset Performance (No Fine-tuning)

| Model | CVC-ClinicDB | ETIS-Larib | Status vs SOTA |
|-------|-------------|------------|----------------|
| PraNet (2020) | 0.899 | 0.628 | Baseline |
| SAM-2-Adapter (2024) | 0.931 | 0.852 | Previous SOTA |
| **ChakraTransformer (C6)** | **0.9412** | **0.8650** | **🏆 New SOTA** |

### Conformal Safety Certification (α=0.05)
- Empirical Coverage: **95.5%** (target ≥95%) ✅
- τ threshold: 7.33×10⁻⁶

### Overfitting Analysis
| Model | Generalization Gap | Status |
|-------|--------------------|--------|
| ChakraTransformer (C6) | 0.0821 | ✅ Excellent |
| AdaBN-ChakraNet (C3) | 0.1093 | ✅ Healthy |

---

## Files in This Repository

### Models & Weights
- `weights/combo1_best.pth` — ChakraNet-Focal best weights
- `weights/combo2_best.pth` — Topo-ChakraNet best weights  
- `weights/pranet_kvasir_best.pth` — PraNet baseline weights
- `chakra_transformer_vit_large_best (1).pth` — **ChakraTransformer (C6) best weights** 🏆
- `best.pt` / `yolov8n.pt` / `yolo26n.pt` — YOLO detection model weights

### Research Documents
- `ChakraNet_Research_Paper.md` — **Full academic research paper** (~40KB, ~9000 words)
- `model_comparison_report.md` — Quantitative comparison vs. all SOTA models
- `overfitting_analysis_report.md` — Generalization gap analysis across 4 datasets
- `model_comparison_report.md` — Benchmark vs. published literature

### Source Code
- `src/run_all_combos.py` — Master training pipeline for Combos 1–4
- `src/pranet_segmenter.py` — PraNet architecture (Parallel Reverse Attention)
- `src/benchmark_cross_dataset.py` — Cross-dataset zero-shot evaluation
- `src/conformal_calibration.py` — Split-conformal calibration implementation
- `src/train_pranet.py` — PraNet training script
- `src/topo_loss.py` — Topological Polyp Loss implementation
- `src/infer_stream.py` — Real-time video inference pipeline
- `chakra_transformer/transformer_segmenter.py` — ViT-Large segmentation head
- `chakra_transformer/train_transformer.py` — Transformer training script
- `evaluate_all.py` — Comprehensive multi-model evaluation script
- `verify_overfitting.py` — Overfitting verification script

### Notebooks (Kaggle-ready)
- `notebooks/Combo1_ChakraNet_Focal.ipynb`
- `notebooks/Combo2_Topo_ChakraNet.ipynb`
- `notebooks/Combo3_AdaBN_ChakraNet.ipynb`
- `notebooks/Combo4_DiffusionAug_ChakraNet.ipynb`
- `notebooks/Combo5_Federated_ChakraNet.ipynb`
- `notebooks/Combo6_ChakraTransformer.ipynb`

### Datasets (in `data/`)
- `data/kvasir-seg/` — Primary training set (1000 images)
- `data/cvc-clinicdb/` — Zero-shot test set (612 images)
- `data/cvc-colondb/` — Zero-shot test set (380 images)
- `data/etis-larib/` — Hardest zero-shot benchmark (196 images)
- `data/cvc-300/` — Cross-dataset generalization (300 images)

### Results
- `results/combo1_metrics.json` — C1 training history + conformal results

---

## Paper Summary

The full research paper is at [`ChakraNet_Research_Paper.md`](ChakraNet_Research_Paper.md).

**Title:** *ChakraNet: A Multi-Combination Framework for Clinically-Robust Colonoscopy Polyp Segmentation via Vision Transformers, Topological Constraints, Adaptive Domain Normalization, and Conformal Safety Guarantees*

**Key Contributions:**
1. Six-combination systematic ablation framework isolating individual clinical failure modes
2. Topological Polyp Loss (TPL) — 91.2% → 97.3% single-component accuracy
3. EndoBN — 0.1093 generalization gap, tightest non-prompt-based adaptation result
4. DiffPolyp — First ControlNet pipeline for colonoscopy artifact synthesis
5. ChakraTransformer — New SOTA on CVC-ClinicDB (0.9412) and ETIS-Larib (0.8650)
6. CPSC — First formally verified statistical safety guarantee for polyp segmentation

---

## Setup

```bash
# Install dependencies
pip install torch torchvision timm ultralytics albumentations opencv-python tqdm tabulate

# Run evaluation across all datasets
python evaluate_all.py

# Verify overfitting analysis
python verify_overfitting.py

# Train Combo 1 (from scratch)
python src/run_all_combos.py --start 1

# Run real-time inference
python src/infer_stream.py
```

---

*ChakraModel — Tata Centre for Technology and Design, 2026*
