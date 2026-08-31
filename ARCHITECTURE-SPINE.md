# ChakraModel Architecture Spine

## Overview
This document defines the architectural invariants for the **ChakraModel Colonoscopy Polyp Segmentation Framework**. It serves as the "spine" that keeps the 6 deep learning combinations structurally consistent.

## Architectural Decisions (ADs)

### AD-01: Framework and Compute Paradigm
- **Rule:** All models must be implemented using **PyTorch**, optimized for hardware acceleration (CUDA/GPU).
- **Binds:** Model definitions, loss functions, data loaders, and training loops.
- **Prevents:** Mixing of ML frameworks (e.g., TensorFlow/Keras) which would break the unified evaluation pipeline.

### AD-02: Self-Contained Deployment
- **Rule:** Each of the 6 core combinations must exist as a self-contained, standalone Jupyter Notebook (`.ipynb`) tailored for the Kaggle environment.
- **Binds:** `notebooks/Combo*.ipynb`.
- **Prevents:** Complex dependency chains or external data downloads that require manual intervention before running the notebook.

### AD-03: Unified Data Acquisition Pipeline
- **Rule:** The system must automatically download and extract the Kvasir-SEG dataset into `/kaggle/working/data/kvasir-seg` upon execution.
- **Binds:** Data preparation scripts and notebook setup cells.
- **Prevents:** Hardcoded local absolute paths and manual dataset management.

### AD-04: Backbone and Metric Standards
- **Rule:** C1-C5 rely on `ResNet-101` backbones. C6 must use a **Hybrid CNN-Transformer** (e.g., Pyramid Vision Transformer or GSViT) rather than a monolithic ViT-Large. Evaluation must always report Dice Similarity Coefficient (DSC), Mean Intersection over Union (mIoU), and Inference FPS on target edge hardware.
- **Binds:** Model instantiations and the `evaluate_all.py` script.
- **Prevents:** The deployment of vanilla Transformers with quadratic complexity that fail the real-time latency (<50ms) requirement. Ad-hoc metric reporting and unapproved model drift.

### AD-05: Topological and Statistical Safety Invariants
- **Rule:** Advanced combinations (C2, C6) must integrate their respective safety/correctness constraints directly into the loss/inference loop (e.g., Betti number penalty, split-conformal calibration with α=0.05).
- **Binds:** Custom loss functions (`topo_loss.py`) and conformal thresholding logic (`conformal_calibration.py`).
- **Prevents:** Deploying high-performing but clinically unsafe (uncalibrated) predictive models.

## Deferred (Out of Scope for Spine)
- **Hyperparameter Tuning:** Learning rates, batch sizes (though 32 is standard), and epochs are left to the specific notebook implementation.
- **Frontend / Deployment UI:** The architecture governs the ML pipeline, not the UI (if any).
- **Specific Augmentation Algorithms:** Aside from the ControlNet pipeline in C4, standard augmentations (Albumentations) are seed-level implementation details.

### AD-06: Edge-Cloud Hybrid Deployment (Clinical Integration)
- **Rule:** The final production architecture must deploy the inference model (C6 Hybrid + Conformal) via an Edge-Native Zero-Copy pipeline (e.g., GStreamer/TensorRT on NVIDIA Jetson).
- **Binds:** Inference scripts and hardware configuration documentation.
- **Prevents:** Attempting cloud-based inference for real-time video, which violates FDA latency limits and introduces surgical risk.
