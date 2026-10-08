# Original User Request

## 2026-09-10T02:32:00Z

You are the PROJECT ORCHESTRATOR (generation 12).
Your working directory is: M:\chakramodel\.agents\orchestrator_gen12.
The user's authoritative request is recorded in M:\chakramodel\.agents\ORIGINAL_REQUEST.md under timestamp ## 2026-09-10T02:32:00Z.

MISSION:
Produce a comprehensive written audit report covering the flaws in the ChakraModel repository, generate automated evaluation scripts to detect these flaws, and provide detailed, proven code patch suggestions explaining what needs to change without permanently modifying the primary codebase.

Working directory: M:\chakramodel
Integrity mode: benchmark

BACKGROUND & KNOWN FLAWS:
Documented in:
- M:\chakramodel\docs\CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md
- M:\chakramodel\docs\HONEST_METRICS.md
- M:\chakramodel\src\models\chakranet_segmenter.py

Flaws to analyze, detect, and patch (14 total):
1. No skip connections in the decoder — finest detail is 16x16 pixels
2. Dead ImageNet classifier head (~1M parameters) carried in every checkpoint
3. 75 lines of dead code (BasicConv2d, RFBBlock, ReverseAttention) that are never instantiated but mislead readers about the architecture
4. Dangerous OOM fallback in forward() that calls self.to('cpu') — mutates a live shared module, is a race condition for threaded servers, silently includes CPU-speed passes in FPS benchmarks, and drops autocast
5. Test-Time Augmentation (TTA) is enabled by default (use_tta = getattr(self, 'use_tta', True)) — conflates TTA performance with baseline model performance in all benchmarks
6. 32 unguarded torch.load() calls across the codebase (without weights_only=True)
7. strict=False in load_state_dict() without key assertions — silently loads 0/312 keys if prefix mismatch occurs (the DDP module. bug)
8. Sign-flipped conformal formula in the inference path (score_pos = 1.0 - (prob_resized + variance)) vs. canonical formula in conformal_calibration.py (return (1.0 - mean_prob) + variance) — coverage guarantee does not hold
9. MC-Dropout variance collapse (~2.85e-15) — all 16 stochastic passes return identical outputs, making uncertainty signal numerically dead
10. Two contradictory calibration q_hat files coexist in the repo with values differing by 5 orders of magnitude
11. No pinned dependencies — timm in particular changes forward_features output shapes across versions, breaking the architecture
12. src/ is never linted or tested in CI — only tests/ is covered
13. Training data composition for the headline model is unrecoverable (num_batches_tracked = 2376 vs 330 expected from committed notebook)
14. Headline metric 0.7304 has no producing artifact — exists only in prose

REQUIREMENTS:
R1. Audit Report & Patch Suggestions:
- Comprehensive report at M:\chakramodel_audit\FULL_AUDIT_REPORT.md
- Individual patch documents at M:\chakramodel_audit\patches\PATCH_XX_<short_name>.md
- For each flaw: state flaw, location, severity, exact impact (accuracy, benchmarks, clinical safety), proposed patch in diff format, and proof log from temporary isolated test.

R2. Automated Detection Scripts:
- Save in M:\chakramodel\tests\adversarial\
- Each script exits 0 if no flaw, exits 1 with clear error message if flaw is present
- Running against the current primary codebase MUST exit 1, exposing each flaw!

R3. Proving Patch Correctness:
- Copy relevant source file to temporary location
- Apply patch to copy
- Run detection script pointing at patched copy -> exits 0
- Capture script output (exit code + stdout/stderr)
- Embed captured output in patch markdown document as proof
- Delete temporary copy
- PRIMARY M:\chakramodel SOURCE FILES MUST REMAIN UNMODIFIED!

ORCHESTRATION RULES:
- Maintain your own plan.md, progress.md, and context.md in M:\chakramodel\.agents\orchestrator_gen12/.
- Decompose the work into milestones.
- Dispatch tasks to specialized subagents (explorers, workers, reviewers, challengers) following file workspace conventions.
- When all milestones are complete and verified, send a message to the Sentinel with your formal Victory Claim.
