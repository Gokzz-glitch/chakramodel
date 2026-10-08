# BRIEFING — 2026-09-09T15:07:00Z

## Mission
Investigate the ChakraModel inference pipeline to understand why inference operates at ~3.7 FPS and design an external profiling script without touching src/.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: M:\chakramodel\.agents\explorer_m1_1_g10
- Original parent: 39578642-3df9-46b1-9513-eea8bc4aa461
- Milestone: Milestone 1 (Generation 10)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Do NOT modify any files in `src/`. All work is read-only on `src/`.
- CODE_ONLY network mode: no external HTTP/web requests

## Current Parent
- Conversation ID: 39578642-3df9-46b1-9513-eea8bc4aa461
- Updated: 2026-09-09T15:04:13Z

## Investigation State
- **Explored paths**:
  - `src/inference/infer_stream.py` (streaming pipeline, 4-panel multi-view, 5 VideoWriters)
  - `src/models/chakranet_segmenter.py` (`ChakraNetMicroRefiner` wrapping `vit_large_patch16_384` with default 3-pass TTA)
  - `src/chakra_transformer/transformer_segmenter.py` (`ChakraTransformerSegmenter` with 309.17M params)
  - `src/hardware_monitor.py` (240s warmup capping VRAM at 40%, OOM CPU fallback)
  - `src/evaluation/benchmark_fps.py` & `src/evaluation/ablation_study.py` (historical 3.7 FPS and 48.8 FPS benchmarks)
  - `weights/checkpoints/` & `weights/yolo/` (verified weights on disk)
  - `scripts/profile_inference_pipeline.py` (implemented external profiler)
- **Key findings**:
  - Root cause of ~3.7 FPS (~270 ms) confirmed empirically:
    1. ViT-Large backbone (`vit_large_patch16_384`, 309.17M params, ~190 GFLOPs/pass) takes ~167.3 ms (FP32) or ~87.3 ms (AMP).
    2. Default 3-pass Test-Time Augmentation (TTA: original, flip, brightness * 1.1) in `ChakraNet.segment_roi` triples ViT-Large compute to 175.2 ms.
    3. Multi-polyp sequential scaling: 2 polyps with 3-Pass TTA consume 376.0 ms (2.7 FPS).
    4. Streaming overhead: 5 concurrent OpenCV VideoWriters in `infer_stream.py` add 20-30 ms on CPU.
    5. VRAM peak: 1,868.8 MB allocated, 1,972.0 MB reserved on 4GB RTX 3050 Laptop GPU.
- **Unexplored areas**: TensorRT quantization engine compilation on Jetson Orin NX (requires physical edge target or cross-compilation environment).

## Key Decisions Made
- Authored external non-intrusive profiler at `scripts/profile_inference_pipeline.py` (strictly outside `src/`).
- Verified zero source modifications in `src/`.
- Executed empirical GPU benchmarks across all stages.

## Artifact Index
- `ORIGINAL_REQUEST.md` — Original task prompts and parent check-ins
- `BRIEFING.md` — Working context and index
- `progress.md` — Liveness heartbeat
- `scripts/profile_inference_pipeline.py` — External profiling tool
- `outputs/eval/pipeline_profiling_report.json` — Detailed JSON profiling metrics
- `outputs/eval/pipeline_profiling_report.md` — Markdown profiling summary
- `analysis.md` — Comprehensive technical investigation report
- `handoff.md` — Self-contained 5-component handoff report
