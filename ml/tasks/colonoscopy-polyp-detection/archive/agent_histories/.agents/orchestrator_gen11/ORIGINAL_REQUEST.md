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

## 2026-09-09T18:29:35Z

You are the Project Orchestrator (orchestrator_gen11) for ChakraModel performance analysis.
Your working directory is M:\chakramodel\.agents\orchestrator_gen11.
Your mission is defined in M:\chakramodel\.agents\ORIGINAL_REQUEST.md.
Review your inherited plan at M:\chakramodel\.agents\orchestrator_gen11\plan.md and briefing at M:\chakramodel\.agents\orchestrator_gen11\BRIEFING.md.

Context:
Milestones 1 & 2 were executed by orchestrator_gen10:
- Pipeline profiling was conducted: `scripts/profile_inference_pipeline.py`, with empirical data in `outputs/eval/pipeline_profiling_report.json`.
- The target analysis report `docs/PERFORMANCE_ANALYSIS.md` was authored (978 lines, ~94 KB).
- Source tree `src/` is read-only (zero modifications allowed).

Your Immediate Task:
1. Initialize your state in `M:\chakramodel\.agents\orchestrator_gen11\progress.md` and `BRIEFING.md`.
2. Execute Milestone 3: Multi-Agent Review & Verification.
   Verify all acceptance criteria:
   - `docs/PERFORMANCE_ANALYSIS.md` exists and contains a latency breakdown with specific millisecond/FPS metrics for at least the YOLO and ViT components.
   - The report names at least two specific open-source video datasets for polyp segmentation.
   - The report cites specific literature or open-source projects and lists at least two common failure modes in video polyp segmentation.
   - Programmatic check verifies that no core source files in `src/` were modified (read-only execution).
3. When all acceptance criteria and Milestone 3 checks pass, submit your Victory Claim and completion report directly to Sentinel (Parent Conversation ID: 972780f5-b886-49eb-b03a-fc5ac13e31d4).

