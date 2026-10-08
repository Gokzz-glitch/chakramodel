# Orchestration Plan: ChakraModel Performance & Quality Analysis

## Objective
Address the 3.7 FPS inference bottleneck in ChakraModel through comprehensive performance profiling, video dataset and literature research, and compile an actionable optimization strategy report at `docs/PERFORMANCE_ANALYSIS.md`.
CRITICAL CONSTRAINT: No code changes to the core pipeline in `src/` (read-only execution).

## Milestones

### Milestone 1: Exploration & Research
- **Explorer 1 (Profiling & Architecture Analyst)**: Analyze `src/infer_stream.py`, model loading, YOLO detection step, cropping, ViT-Large transformer inference (`src/transformer_segmenter.py` / `src/chakranet_segmenter.py`), GPU tensor transfer overheads. Propose an external, non-intrusive profiling script outside `src/` to capture ms and FPS metrics.
- **Explorer 2 (Video Datasets Analyst)**: Research polyp video datasets (e.g., SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, PolypGen). Catalog characteristics, sizes, frame rates, annotation types, and availability.
- **Explorer 3 (Literature & Optimization Strategist)**: Research state-of-the-art video polyp segmentation literature (PNS-Net, VPS, temporal modules) and common failure modes (motion blur, temporal inconsistency, specular highlights, rapid endoscopic withdrawal). Formulate concrete optimization strategies (TensorRT, ONNX Runtime, INT8/FP16 quantization, distillation, temporal smoothing).

### Milestone 2: Benchmarking & Report Synthesis
- **Worker**: Execute external profiling script to obtain verified empirical latency breakdown (YOLO detection, ViT inference, data transfer, postprocessing). Synthesize all findings into `docs/PERFORMANCE_ANALYSIS.md`. Verify git status confirms zero changes in `src/`.

### Milestone 3: Multi-Agent Review & Forensic Integrity Audit
- **Reviewer 1 & Reviewer 2**: Thorough review of `docs/PERFORMANCE_ANALYSIS.md` against requirements R1, R2, R3 and acceptance criteria.
- **Challenger 1 & Challenger 2**: Adversarially test and verify acceptance criteria:
  - Latency breakdown with specific ms / FPS metrics for YOLO and ViT.
  - At least two specific open-source video datasets named.
  - Specific literature/open-source projects cited with at least two common failure modes.
  - Programmatic verification that `src/` has zero modifications.
- **Forensic Auditor (`teamwork_preview_auditor`)**: Perform binary integrity verification on the analysis artifacts and check for genuine profiling execution.
