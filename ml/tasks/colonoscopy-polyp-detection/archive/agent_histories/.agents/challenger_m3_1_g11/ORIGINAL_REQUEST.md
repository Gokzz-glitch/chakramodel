## 2026-09-09T18:30:43Z
You are Challenger 1 (teamwork_preview_challenger) for Milestone 3 of ChakraModel performance analysis.
Your working directory is: M:\chakramodel\.agents\challenger_m3_1_g11.
Your parent orchestrator is: orchestrator_gen11 (conversation ID: 929eaf1b-9df4-4d0c-8e8f-d867ed24ca1c).

Mission:
Adversarially stress-test and verify all Acceptance Criteria for `docs/PERFORMANCE_ANALYSIS.md`:
1. `docs/PERFORMANCE_ANALYSIS.md` exists and contains a latency breakdown with specific millisecond/FPS metrics for at least the YOLO and ViT components.
2. The report names at least two specific open-source video datasets for polyp segmentation.
3. The report cites specific literature or open-source projects and lists at least two common failure modes in video polyp segmentation.

Instructions:
1. Initialize your working directory `M:\chakramodel\.agents\challenger_m3_1_g11` with `BRIEFING.md` and `progress.md`.
2. Write and execute an automated verification script (e.g. in your working directory `M:\chakramodel\.agents\challenger_m3_1_g11\verify_criteria.py` or powershell commands) to programmatically check:
   - File existence and non-zero size of `docs/PERFORMANCE_ANALYSIS.md`.
   - Extraction of regex patterns for YOLO latency (ms) and FPS, ViT latency (ms) and FPS. Verify they match numbers in `outputs/eval/pipeline_profiling_report.json`.
   - Search and count for dataset names (SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, PolypGen, etc.). Verify count >= 2.
   - Search and count for literature citations (PNS-Net, ST-PUNet, FSNet, MICCAI, etc.) and failure modes (motion blur, specular reflection/glare, temporal flicker, etc.). Verify count >= 2.
3. Adversarially challenge the report:
   - Are there any vague claims, missing units, or unsupported assertions?
   - Are there any inconsistencies between tables, text, and profiling JSON?
4. Write your challenge report to `M:\chakramodel\.agents\challenger_m3_1_g11\challenge.md`.
5. Write your handoff report to `M:\chakramodel\.agents\challenger_m3_1_g11\handoff.md` with:
   - Empirical test execution logs
   - Specific checks passed/failed
   - PASS/FAIL verdict
6. Use `send_message` to notify your parent orchestrator (929eaf1b-9df4-4d0c-8e8f-d867ed24ca1c).
Constraint: Source files in `src/` are read-only. Do not modify any files in `src/`.
