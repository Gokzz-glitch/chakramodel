# Original User Request

## 2026-09-09T13:50:24Z

You are the PROJECT ORCHESTRATOR (Generation 9) for ChakraModel.

Working directory: m:\chakramodel\.agents\orchestrator_gen9
Project root: m:\chakramodel

Your objective and requirements are defined in `m:\chakramodel\.agents\ORIGINAL_REQUEST.md` under timestamp `## 2026-09-09T13:50:24Z`:

Goal: Revise the ChakraModel academic paper to remove all fabricated metrics (e.g., Kvasir DSC 0.9852, "State of the Art" claims) and replace them with the empirically verified, honest results from the Kaggle v5 cross-validation suite. The narrative must be adjusted to reflect a competent but non-SOTA medical imaging segmentation model.

Requirements:
- R1. Metric Replacement: Update all tables, figures, and inline text references in both `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md` to reflect the honest metrics documented in `docs/HONEST_METRICS.md` (e.g., Kvasir-SEG DSC of 0.8131 ± 0.1747). Remove any tables or claims referencing ETIS-Larib (as no real data was ever evaluated) and remove the fabricated CVC-ClinicDB scores.
- R2. Narrative Tone Adjustment: Rewrite the Abstract, Introduction, and Conclusion sections in both files. The tone should pivot from claiming a "New State-of-the-Art" to presenting a "competent baseline implementation combining YOLO detection with ViT-Large segmentation." The paper must explicitly acknowledge that leading SOTA models achieve ~0.90+ Dice, positioning ChakraModel accurately within the literature.

Acceptance Criteria:
1. Programmatic Verification:
   - A programmatic text scan of `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md` returns zero matches (case-insensitive) for the following strings: "SOTA", "State of the Art", "State-of-the-Art", "0.9852", "0.9412", "0.8650".
   - A programmatic text scan confirms the presence of the string "0.8131" in both files.
2. Independent Review:
   - An independent auditor agent reviews the Abstract and Conclusion of both files and confirms the narrative explicitly acknowledges the model is a "competent baseline" and not SOTA.

Operational instructions:
- Create and maintain `BRIEFING.md`, `plan.md`, and `progress.md` in `m:\chakramodel\.agents\orchestrator_gen9/`. Keep `progress.md` updated frequently so the Sentinel can monitor progress.
- Decompose the work, spawn specialist subagents (workers/reviewers/challengers) into their own `.agents/<type>_<milestone>...` directories as needed to implement and verify the changes.
- Ensure all acceptance criteria are fully met.
- When finished and verified, send a message back to the Sentinel (parent) reporting completion and victory claim.
