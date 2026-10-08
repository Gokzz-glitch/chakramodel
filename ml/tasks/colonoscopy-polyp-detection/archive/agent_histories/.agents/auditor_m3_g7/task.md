# Forensic Auditor M3 (Gen 7) Task Assignment

## Mission
Conduct a strict forensic integrity audit on the `chakramodel` codebase and the newly authored report `m:\chakramodel\COLAB_EVALUATION_AUDIT_REPORT.md`.

## Verification Scope
1. Zero Code Modification Audit:
   - Check `git status` and `git diff` on `m:\chakramodel`.
   - Verify that NO source code files (`.py`, `.ipynb`, `.sh`, `.bat`, etc.) and NO test files were modified or deleted.
   - Verify that the ONLY new file outside `.agents/` is `m:\chakramodel\COLAB_EVALUATION_AUDIT_REPORT.md`.
2. Anti-Fabrication & Empirical Integrity Audit:
   - Verify that all claims in `COLAB_EVALUATION_AUDIT_REPORT.md` are genuine, non-fabricated, and accurately cite actual repository files.
   - Verify that all reported Dice scores (0.8125, 0.8004) originate directly from historical logs (`COLLABRUNTESTING.pdf`).
   - Verify that parameter counts and key counts match the actual checkpoint tensors on disk.
3. Verdict:
   - Issue a binary verdict: CLEAN or INTEGRITY VIOLATION.
   - Write your audit report in `m:\chakramodel\.agents\auditor_m3_g7\audit_report.md` and `handoff.md`.
