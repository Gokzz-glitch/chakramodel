## 2026-09-09T14:02:06Z
You are Reviewer 1 (Milestone 3, Generation 9) for ChakraModel.
Working directory: m:\chakramodel\.agents\reviewer_m3_1_g9 (create it if needed).
Parent: orchestrator_gen9 (ID: 3c29125b-8d51-40b5-ad4e-3a4853f5fd31).

Mission:
Objectively and adversarially review `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md` to ensure complete compliance with Requirements R1 & R2 and all project criteria:
1. Structural integrity:
   - In `paper/main.tex`: Verify LaTeX document syntax, packages, documentclass, environments (`document`, `abstract`, `table`, `tabular`, `minipage`), column specs, and captioning.
   - In `docs/paper/ChakraModel_Final_Paper.md`: Verify Markdown formatting, headers, table syntax, and completeness.
2. Metric Verification (R1):
   - Verify that all metrics in tables and text match `docs/HONEST_METRICS.md` (Kvasir-SEG DSC 0.8131 ± 0.1747, HyperKvasir 0.8360 ± 0.1610, CVC-ClinicDB zero-shot 0.7561 ± 0.2131, EndoScene CVC-300 zero-shot 0.7402 ± 0.1590, PolypDB 0.7283 ± 0.2544).
   - Verify that ETIS-Larib is correctly documented as catastrophic failure (0.0000 DSC / 5 canary files) and no positive claims are made.
   - Verify that all fabricated/obsolete numbers (0.9225, 0.9081, 0.8215, 0.7949, 0.7304) are purged.
3. Automated Tests:
   - Run `pytest tests/test_milestone2_manuscript_verification.py -v`.
   - Run `python m:\chakramodel\.agents\worker_m2_g9\verify_requirements.py`.
4. Output:
   - Write `m:\chakramodel\.agents\reviewer_m3_1_g9\review.md` and `m:\chakramodel\.agents\reviewer_m3_1_g9\handoff.md`.
   - Report verdict: APPROVE or REJECT.
   - Send message back to parent (3c29125b-8d51-40b5-ad4e-3a4853f5fd31).
