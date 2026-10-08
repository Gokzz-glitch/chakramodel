# Execution Plan — Kaggle Dataset Decoding and Completeness Verification

## Objective
Decode 11 Kaggle dataset links, map them to real-world datasets, determine presence/absence of SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, and PolypGen, verify completeness, and produce an exhaustive decoding report.

## Phase 1: URL Identification & Deep Content Inspection (M1)
1. Spawn 3 Explorers (`teamwork_preview_explorer`):
   - Explorer 1: Exhaustive search of workspace, python scripts, jupyter notebooks, logs, and `OM_rama_krish_all_data.json` / `september1to4afternnon_chat.json` to extract all 11 Kaggle dataset URLs / slugs.
   - Explorer 2: Deep inspection of local dataset bundles, extracted zip archives, directory trees, file counts, and image/video/mask metrics corresponding to the Kaggle datasets.
   - Explorer 3: Verify Kaggle dataset metadata, owner names (`gokulrocky`, `gokulraj324`, external authors), and cross-check with Kaggle upload scripts.
2. Spawn Worker (`teamwork_preview_worker`) to assemble raw directory listings, file inventories, and count statistics for each of the 11 Kaggle datasets.
3. Reviewer check on M1 outputs.

## Phase 2: Completeness Verification against Baselines (M2)
1. Worker/Explorer analysis comparing the decoded Kaggle contents against the official reference baselines:
   - SUN-SEG baseline (158,690 frames, 110 clips)
   - CVC-VideoClinicDB baseline (18 sequences, ~11,954 frames)
   - LDPolypVideo baseline (160 videos, ~40,266 frames)
   - PolypGen baseline (8,037 frames across multiple centers)
2. Detail missing sequences, frame truncations, missing mask annotations, or non-matching modalities.

## Phase 3: Comprehensive Report Synthesis (M3)
1. Spawn Worker to author `m:\chakramodel\KAGGLE_DATASET_DECODING_REPORT.md` conforming to all acceptance criteria:
   - All 11 Kaggle URLs listed with exact slugs
   - Decoded directory structures and exact file counts (videos, images, masked vs unmasked)
   - Real-world counterpart mapping
   - Explicit presence/absence table for the 4 target datasets
   - Detailed completeness audit & explanation of unexpected datasets (e.g. HyperKvasir, EndoScene CVC-300, Kvasir-SEG, CVC-ClinicDB).

## Phase 4: Adversarial Challenger, Reviewer & Final Gate (M4)
1. Spawn 2 Challengers to empirically verify file counts, directory paths, and absence/presence claims.
2. Spawn 2 Reviewers to review report against R1, R2, R3.
3. Spawn Forensic Auditor to verify integrity and zero fabrication.
4. Gate check: pass all criteria, update progress, write handoff, notify Sentinel.
