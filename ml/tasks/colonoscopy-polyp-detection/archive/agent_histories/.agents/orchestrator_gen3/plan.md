# Orchestration Plan — Gen 3

## Overview
Orchestrating deep verification of the PolypGen extracted dataset at `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted`.

## Milestones & Execution Plan

### Milestone 1: Exploration & Dataset Discovery
- Dispatch 3 Explorers:
  - `explorer_pg_1`: Discover top-level and subfolder structure in `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted`. Inspect centers (e.g. data_C1..C6, sequence data, single-frame data).
  - `explorer_pg_2`: Inspect image and mask naming conventions, folder patterns (`images_C*`, `masks_C*`, `annotated_frames`, etc.), file formats (.jpg, .png, .tif), byte size distributions.
  - `explorer_pg_3`: Inspect bounding box annotations, txt/csv/json metadata files, bounding box formats, coordinate representations, and existing scripts/references in `m:\chakramodel` relating to PolypGen.

### Milestone 2 & 3: Implementation of Verification Engine & Comprehensive Report
- Dispatch Worker:
  - Implement `m:\chakramodel\verify_polypgen_integrity.py` with robust physical image decoding (PIL `Image.open().load()`, catching `UnidentifiedImageError`, truncated images, etc.).
  - Implement bounding box & mask matching logic: map every positive image to its mask and bounding box.
  - Detect and list any orphaned images, orphaned masks, or orphaned bounding boxes.
  - Execute the script against `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted`.
  - Author comprehensive `m:\chakramodel\POLYPGEN_INTEGRITY_REPORT.md` documenting results, file counts, corruption status, and structural ambiguity analysis.

### Milestone 4: Verification, Adversarial Testing & Forensic Audit
- Dispatch:
  - 2 Reviewers (`teamwork_preview_reviewer`) to independently inspect code quality, edge cases, completeness, and documentation.
  - 2 Challengers (`teamwork_preview_challenger`) to independently execute the script, test edge cases (e.g., inject a temporary corrupted file in a scratch dir to verify detection), and confirm results.
  - 1 Forensic Auditor (`teamwork_preview_auditor`) to perform integrity forensics: ensure zero cheating, zero hardcoding of results, authentic execution of decodes.
- Evaluate gate and report final findings back to parent/Sentinel.
