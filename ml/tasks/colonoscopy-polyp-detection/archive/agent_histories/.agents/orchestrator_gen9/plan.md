# Plan: Academic Paper Revision to Honest Metrics & Non-SOTA Baseline

## Objective
Revise `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md` to remove all fabricated metrics and SOTA claims, replace them with verified Kaggle v5 cross-validation results from `docs/HONEST_METRICS.md`, adjust the narrative to a competent baseline (~0.8131 DSC, leading models ~0.90+), and verify all criteria programmatically and through multi-agent review.

## Milestones

### Milestone 1: Exploration & Lineage Audit
- **Goal**: Scan `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md` for all occurrences of:
  - Fabricated metrics ("0.9852", "0.9412", "0.8650", "0.9225", "0.9081", "0.8215", "0.7949", etc.)
  - SOTA claims ("SOTA", "State of the Art", "State-of-the-Art")
  - ETIS-Larib and fabricated CVC-ClinicDB scores
  - Map target replacements from `docs/HONEST_METRICS.md` (e.g. Kvasir-SEG DSC 0.8131 ± 0.1747, HyperKvasir 0.8360 ± 0.1610, CVC-ClinicDB zero-shot 0.7561 ± 0.2131, CVC-300 0.7402 ± 0.1590, PolypDB 0.7283 ± 0.2544, ETIS-Larib removed/disclosed).
- **Assigned Subagent**: `teamwork_preview_explorer` (`.agents/explorer_m1_g9`)

### Milestone 2: Implementation & Paper Revision (R1 & R2)
- **Goal**:
  - Update `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md`:
    - R1: Replace metrics in tables, text, captions with honest metrics from `docs/HONEST_METRICS.md` (presence of "0.8131" in both files). Remove ETIS-Larib claims/tables and fabricated CVC-ClinicDB scores.
    - R2: Rewrite Abstract, Introduction, and Conclusion in both files. Position as a "competent baseline" combining YOLO detection with ViT-Large segmentation, explicitly acknowledging leading SOTA models achieve ~0.90+ Dice.
    - Purge all prohibited tokens: "SOTA", "State of the Art", "State-of-the-Art", "0.9852", "0.9412", "0.8650".
- **Assigned Subagent**: `teamwork_preview_worker` (`.agents/worker_m2_g9`)

### Milestone 3: Adversarial Multi-Agent Verification & Integrity Audit
- **Reviewers (2)**:
  - `reviewer_1_g9`: Verify LaTeX structure of `paper/main.tex` and Markdown structure of `docs/paper/ChakraModel_Final_Paper.md`, narrative tone, and adherence to R1 and R2.
  - `reviewer_2_g9`: Independent review of Abstract and Conclusion across both files, confirming explicit "competent baseline" and non-SOTA acknowledgment.
- **Challengers (2)**:
  - `challenger_1_g9`: Programmatic text scan for forbidden substrings (case-insensitive) and verification of "0.8131".
  - `challenger_2_g9`: Verification of all metric values against `docs/HONEST_METRICS.md` and verification that no ETIS-Larib or fabricated scores remain.
- **Forensic Auditor (1)**:
  - `auditor_g9`: Full integrity audit on changes made, certifying clean implementation and zero cheating.

### Milestone 4: Final Synthesis & Victory Reporting
- Synthesize all findings and report victory to Sentinel.
