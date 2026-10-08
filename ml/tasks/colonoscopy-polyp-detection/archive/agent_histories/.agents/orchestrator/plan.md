# Implementation Plan: ChakraModel Truth Documentation

## Overview
Deconstruct the documentation mission into 4 verifiable milestones.
Ensure complete compliance with the Dispatch-Only Orchestrator pattern: orchestrator delegates exploration, analysis, script running, and document drafting to subagents.

## Phase 1: Investigation & Empirical Verification (Milestones 1, 2, 3)
### Milestone 1: Historical Timeline & Origin Investigation
- **Objective**: Uncover complete timeline from git history, conversations (`OM_rama_krish_convo.md`, `september1to4afternnon_chat.json`), logs, and project notes.
- **Dispatch**:
  - Spawn `teamwork_preview_explorer` (Explorer 1 - History & Timeline Specialist)
- **Deliverables**: Chronological breakdown with dates, commit hashes, participants, milestones reached, roadblocks faced, and strategic shifts.

### Milestone 2: Architectural Evolution & Theory vs Code Reality
- **Objective**: Contrast theoretical architectural claims against real executable code.
  - Specifically check: Topological Loss (persistent homology/Betti numbers), Conformal Calibration (conformal prediction/evaluator), ChakraSLAM (SLAM/ORB-SLAM/temporal tracking), Hybrid Crop, Federated Learning Non-IID partitioner.
  - Check `src/`, notebooks (`kaggle_om_v4.ipynb`, `kaggle_wrapper_v6.ipynb`, etc.), standalone scripts vs integrated production pipelines.
- **Dispatch**:
  - Spawn `teamwork_preview_explorer` (Explorer 2 - Code Architecture & Theory Auditor)
- **Deliverables**: Verification matrix for all theoretical claims (Implemented & Integrated, Implemented as standalone prototype, Stub/Import only, or Purely Markdown/Paper claim).

### Milestone 3: Empirical Metrics & Benchmark Script Verification
- **Objective**: Execute Python scripts to inspect real model files (`yolov8x.pt`, `weights/`, `new_weights/`, etc.), count exact parameters, calculate FLOPs, and extract verified benchmark metrics from raw evaluation logs (`crossvali1_dump.txt`, `crossvali2_dump.txt`, etc.).
- **Dispatch**:
  - Spawn `teamwork_preview_explorer` (Explorer 3 - Benchmarks & Model Weight Inspector)
- **Deliverables**: Exact verified parameter numbers, model components, and evaluation scores with script execution outputs.

## Phase 2: Synthesis & Documentation Drafting (Milestone 4)
- **Objective**: Produce the full suite of files in `m:\chakramodel\true_docs/`:
  - `true_docs/index.md`
  - `true_docs/history_and_timeline.md`
  - `true_docs/architecture_evolution.md`
  - `true_docs/theoretical_claims_vs_code.md`
  - `true_docs/verified_benchmarks_and_metrics.md`
- **Dispatch**:
  - Spawn `teamwork_preview_worker` (Worker - Documentation Author) to draft the complete documentation suite in `true_docs/`.
  - Spawn `teamwork_preview_reviewer` (Reviewer 1) and `teamwork_preview_reviewer` (Reviewer 2) to audit accuracy, completeness, and adherence to evidence.
  - Spawn `teamwork_preview_challenger` to stress-test claims against raw files.
  - Spawn `teamwork_preview_auditor` to perform forensic integrity check on the generated documentation.

## Phase 3: Final Review & Sentinel Delivery
- Review audit results.
- Ensure all 4 acceptance criteria are met.
- Compile summary and deliver completion report via `send_message` to parent Sentinel.
