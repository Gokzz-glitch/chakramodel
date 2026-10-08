## 2026-09-15T23:23:54Z

<USER_REQUEST>
You are challenger_m1_1_g15.
Your working directory is M:\chakramodel\.agents\challenger_m1_1_g15\
Your parent is orchestrator_gen15 (e9d0dc6b-8d4f-4c1a-924e-6152f16b1473).

Mission:
Empirically stress-test Acceptance Criteria A & B (Target Directories Verification and Auto-Fix).
Requirement:
- Modifying a file in a backup directory causes the script to detect corruption via hash mismatch and restore it from source.
- Deleting a file in a backup directory causes the script to detect missing file and restore it from source.

Tasks:
1. Write and execute an adversarial test harness that creates realistic mock target environments:
   - Single-byte corruption in middle of files (same size, altered SHA-256).
   - Size-truncated corruption (different size).
   - Multiple corrupted files in subdirectories.
   - Deleted files in target.
   - Read-only corrupted target file.
2. Test both `--dry-run` (verifies reporting without changes) and live execution (`--verify-and-sync`).
3. Verify that:
   - Hashing is genuine SHA-256.
   - Auto-fix completely restores the file to match the source SHA-256 byte-for-byte.
   - Temp files (.tmp_autofix) are cleaned up.
   - Exclusions work as intended.
4. Output your test scripts, captured execution logs, and empirical verdict (PASS / FAIL) to:
   `M:\chakramodel\.agents\challenger_m1_1_g15\challenge_report.md` and `M:\chakramodel\.agents\challenger_m1_1_g15\handoff.md`.
Keep progress.md updated. When done, message parent orchestrator_gen15.
</USER_REQUEST>
