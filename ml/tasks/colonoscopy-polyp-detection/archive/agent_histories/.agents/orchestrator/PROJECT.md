# Project: ChakraModel Truth Documentation

## Architecture & Documentation Target
The ChakraModel project has evolved rapidly with extensive discussions, research papers, Kaggle notebooks, and architectural claims.
The objective is to create an authoritative, deeply researched, code-verified, and honest suite of documentation located at:
`m:\chakramodel\true_docs/`

Target Structure of `true_docs/`:
- `true_docs/index.md`: Executive summary, overview of findings, truth vs myth scorecard, and directory index.
- `true_docs/history_and_timeline.md`: Detailed chronological history with explicit timestamps, dates, commit hashes/tags, logs, and conversation cross-references (from OM_rama_krish_convo.md, september1to4afternnon_chat.json, commits, etc.).
- `true_docs/architecture_evolution.md`: Evolution of ideas from early concepts to the current implementation, tracing what was proposed, what was attempted, what succeeded, and what failed or was discarded.
- `true_docs/theoretical_claims_vs_code.md`: Exhaustive investigation of theoretical claims (Topological Loss / persistent homology, Conformal Calibration, ChakraSLAM / Endo-SLAM, Hybrid Crop, FL Non-IID Partitioner) with direct code pointers proving whether they exist as executable, integrated production code or remain aspirational / standalone stubs.
- `true_docs/verified_benchmarks_and_metrics.md`: Verified model parameters, FLOPs, model weight architectures (YOLOv8n vs YOLOv8x, ViT-Large, etc.), cross-validation datasets, benchmark truncation provenance, and empirical performance extracted directly via script execution against models and logs.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Historical Timeline & Origin Investigation | Comprehensive analysis of git logs, commit history, OM_rama_krish_convo.md, september1to4afternnon_chat.json, logs, and documentation to build a verified chronological narrative. | none | DONE |
| 2 | Architectural Evolution & Theoretical Claims vs Code Reality | Deep dive into codebase (src/, scripts, notebooks, root files) to verify whether claims like Topological Loss, Conformal Calibration, and ChakraSLAM are implemented in executable code vs markdown claims. | none | DONE |
| 3 | Empirical Metrics & Benchmark Script Verification | Direct execution and verification of parameter counting scripts, model inspection (weights/, yolov8x.pt, fcbformer, etc.), and benchmark extraction from raw logs and outputs. | none | DONE |
| 4 | True Documentation Suite Synthesis & Final Gate | Assemble all verified findings into true_docs/ (.md files), peer review for completeness and accuracy, verify all criteria met, and submit final report. | M1, M2, M3 | DONE |

## Key Outputs
- `true_docs/index.md` (Executive Clinical Summary, Truth vs Myth Scorecard, Documentation Navigation)
- `true_docs/history_and_timeline.md` (7-Phase Timeline, Master Table of 26 Git Commits, Authorship Roster, 552-Chat Synthesis, GAN Audits, Anti-Fabrication Tripwires)
- `true_docs/architecture_evolution.md` (Progression from 6 Standalone Combos to Edge-Native Hybrid, Crop-and-Forward Post-Mortem, 8-Step Runtime Trace)
- `true_docs/theoretical_claims_vs_code.md` (Line-by-Line Forensic Audit across 7 Focus Areas, Master Claim vs Reality Matrix)
- `true_docs/verified_benchmarks_and_metrics.md` (Physically Verified Parameters: 309.17M ViT, 3.01M YOLOv8n, 25.55M PraNet; 10% Test Tail Artifact Disclosure; Full-Cohort OOD Collapse Data; Real-Time Latency Analysis; Statistical Significance Invalidation)

## Code Layout
- Target documentation: `m:\chakramodel\true_docs/*.md`
- Agent metadata and investigation reports: `m:\chakramodel\.agents/<agent_name>/`
