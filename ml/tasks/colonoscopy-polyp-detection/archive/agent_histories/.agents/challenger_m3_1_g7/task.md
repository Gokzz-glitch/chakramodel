# Challenger M3-1 (Gen 7) Task Assignment

## Mission
Empirically challenge and stress-test the archive layouts, path resolution mechanics, and proposed 4-Tier Asset Resolver from `m:\chakramodel\COLAB_EVALUATION_AUDIT_REPORT.md`.

## Verification Scope
1. Empirically verify zip structures (`chakramodel_data_scripts.zip`, `chakramodel-weights.zip`, `chakramodel_weights_PRIVATE.zip`) by writing and running inspection scripts in your directory.
2. Empirically implement and test the proposed 4-Tier Dynamic Asset Resolver in a standalone test script under your directory:
   - Test resolving paths when running from repo root, from a subfolder, with and without environment variables, and simulating Colab `/content` vs Windows environments.
   - Test fail-fast behavior when assets are missing.
3. Stress-test edge cases: spaces in directory paths, casing differences (`.PNG` vs `.png`), missing directories.
4. Write your findings and empirical verdict in `m:\chakramodel\.agents\challenger_m3_1_g7\challenge.md` and `handoff.md`.
