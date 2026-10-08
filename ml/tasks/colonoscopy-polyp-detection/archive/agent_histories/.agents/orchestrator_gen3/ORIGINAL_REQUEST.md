# Original User Request

## 2026-09-07T18:43:16Z

Verify the integrity of the extracted PolypGen dataset to ensure no files are broken or corrupted, and resolve any structural ambiguities.

Working directory for your coordination files: m:\chakramodel\.agents\orchestrator_gen3
Project workspace: m:\chakramodel
Target dataset directory: J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted
Integrity mode: development
Authoritative request file: m:\chakramodel\.agents\ORIGINAL_REQUEST.md (under section ## 2026-09-07T18:43:16Z)

Requirements:
R1. Deep Corruption Scan:
Write a script to physically attempt to open and decode every single image and mask file in the dataset to definitively prove they are not corrupted or broken.

R2. Structural Ambiguity Check:
Verify that every positive image has a corresponding mask and bounding box annotation, and highlight any orphaned files or structural inconsistencies.

Acceptance Criteria:
- An automated Python script is provided that iterates through the entire dataset and attempts to decode each image/mask.
- A final report is generated listing the exact paths of any corrupted, 0-byte, or unreadable files found by the script.
- The report explicitly flags any orphaned images (e.g., an image in images_C1 that lacks a counterpart in masks_C1).

Please orchestrate your team (dispatching explorers, workers, reviewers, challengers as needed). Keep plan.md, progress.md, and context.md updated in your working directory. When all requirements and acceptance criteria are fully met and verified, report completion back to Sentinel.
