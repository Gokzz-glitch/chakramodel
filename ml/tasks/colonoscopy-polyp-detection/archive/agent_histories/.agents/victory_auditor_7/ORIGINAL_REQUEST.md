# Original User Request

## 2026-09-09T18:27:34Z

Conduct a comprehensive performance and quality analysis of ChakraModel to address the 3.7 FPS bottleneck. This includes profiling the inference pipeline, researching open-source and literature approaches for video dataset training, and identifying optimization strategies. No code changes should be made to the core pipeline yet.

Working directory: M:\chakramodel
Integrity mode: benchmark

## Requirements

### R1. Performance Profiling
Run external profiling scripts on the current inference pipeline to identify the specific bottlenecks causing the 3.7 FPS limit. Break down the latency by component (e.g., YOLO detection time, ViT-Large inference time, data loading, CPU/GPU tensor transfers).

### R2. Video Dataset & Literature Research
Research the use of video datasets in polyp segmentation. Identify available open-source video datasets (e.g., SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, PolypGen), analyze state-of-the-art literature to understand how others handle video data, and document the common failures they face (e.g., motion blur, temporal inconsistency, specular glare). Investigate GitHub and open-source projects for existing solutions (e.g., PNS-Net, ST-PUNet).

### R3. Optimization Strategy Report
Compile all findings into a structured report at `docs/PERFORMANCE_ANALYSIS.md`. The report must include the profiling numbers, a summary of video datasets and literature, and a list of concrete, actionable optimization strategies (e.g., TensorRT, ONNX, model distillation, temporal modules).

## Acceptance Criteria

### Independent Review
- [ ] An independent auditor agent verifies that `docs/PERFORMANCE_ANALYSIS.md` exists and contains a latency breakdown with specific millisecond/FPS metrics for at least the YOLO and ViT components.
- [ ] An independent auditor agent verifies that the report names at least two specific open-source video datasets for polyp segmentation.
- [ ] An independent auditor agent verifies that the report cites specific literature or open-source projects and lists at least two common failure modes in video polyp segmentation.
- [ ] A programmatic check verifies that no core source files in `src/` were modified by this analysis (read-only execution).
