# Execution Plan: Comprehensive Flaw Audit, Detection Scripts, and Proven Patches

## Objectives
1. Programmatically detect all 14 known flaws across the ChakraModel repository via automated adversarial test scripts in `M:\chakramodel\tests\adversarial\`.
2. Ensure each adversarial test script exits with code 1 against the current primary codebase (exposing the flaw) and exits 0 when run against an isolated patched copy.
3. Generate detailed patch markdown files for each flaw in `M:\chakramodel_audit\patches\PATCH_XX_<short_name>.md` including location, severity, clinical/benchmark impact, diff-formatted patch, and embedded execution output log proving exit 0.
4. Produce a master audit report in `M:\chakramodel_audit\FULL_AUDIT_REPORT.md` synthesizing all 14 flaws and architectural analysis.
5. Guarantee that primary codebase files in `M:\chakramodel\` remain 100% UNMODIFIED.

## The 14 Flaws Breakdown
- **Flaw 1**: No skip connections in the decoder (finest detail 16x16 pixels).
- **Flaw 2**: Dead ImageNet classifier head (~1M parameters) carried in every checkpoint.
- **Flaw 3**: 75 lines of dead code (BasicConv2d, RFBBlock, ReverseAttention) never instantiated.
- **Flaw 4**: Dangerous OOM fallback calling `self.to('cpu')` in `forward()`.
- **Flaw 5**: Test-Time Augmentation (TTA) enabled by default (`use_tta = getattr(self, 'use_tta', True)`).
- **Flaw 6**: 32 unguarded `torch.load()` calls without `weights_only=True`.
- **Flaw 7**: `strict=False` in `load_state_dict()` without key assertions.
- **Flaw 8**: Sign-flipped conformal prediction formula in inference path vs canonical formula.
- **Flaw 9**: MC-Dropout variance collapse (~2.85e-15) making uncertainty signal dead.
- **Flaw 10**: Two contradictory calibration q_hat files differing by 5 orders of magnitude.
- **Flaw 11**: No pinned dependencies (especially `timm` output shape shifts).
- **Flaw 12**: `src/` never linted or tested in CI (only `tests/` covered).
- **Flaw 13**: Training data composition unrecoverable (`num_batches_tracked = 2376` vs 330 expected).
- **Flaw 14**: Headline metric 0.7304 has no producing artifact (prose-only).

## Milestones
### Milestone 1: Exploration & Flaw Evidence Gathering
- Spawn 3 parallel Explorers:
  - `explorer_m1_1_g12`: Inspect Flaws 1-5 (chakranet_segmenter.py architecture & safety).
  - `explorer_m1_2_g12`: Inspect Flaws 6-10 (torch.load security, state_dict loading, conformal calibration & MC-Dropout).
  - `explorer_m1_3_g12`: Inspect Flaws 11-14 (dependencies, CI workflow, training data tracking & headline metric provenance).
- Deliverables: Comprehensive exploration reports with exact line numbers, AST/regex check strategies, and patch designs.

### Milestone 2: Automated Detection Scripts in `tests/adversarial/`
- Spawn Worker to write all 14 detection scripts in `M:\chakramodel\tests\adversarial\`.
- Each script:
  - Must exit 1 when run on current codebase.
  - Supports `--target-file` or isolated file arguments so it can be evaluated against patched copies.
- Independent Reviewers (2) and Challengers (2) empirically verify that all 14 scripts exit 1 on current codebase.
- Forensic Auditor confirms no mock/hardcoded cheats.

### Milestone 3: Audit Report, Isolated Patch Proving & Patch Documentation
- Spawn Worker to:
  - Prepare isolated temporary copies of target files.
  - Apply patches to the copies.
  - Run the detection scripts against patched copies, proving exit 0.
  - Capture stdout/stderr logs.
  - Delete temporary copies (ensuring primary codebase is completely untouched).
  - Write `M:\chakramodel_audit\FULL_AUDIT_REPORT.md` and all 14 `M:\chakramodel_audit\patches\PATCH_XX_*.md` files.
- Independent Reviewers, Challengers, and Forensic Auditor verify report completeness and zero diff on primary codebase.

### Milestone 4: Final Verification & Sentinel Victory Claim
- Verify all acceptance criteria.
- Send formal Victory Claim message to Sentinel.
