# Project: Kaggle Dataset Decoding and Completeness Verification

## Architecture & Scope
Verify if 11 Kaggle dataset links map correctly to the 4 target evaluation datasets (SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, PolypGen), decode the exact contents of each Kaggle link, and ensure completeness against original baselines.

## Target Evaluation Baselines
1. **SUN-SEG**: 158,690 frames across video sequences (Ji et al., MICCAI 2022 / MedIA 2023).
2. **CVC-VideoClinicDB** (CVC-ClinicVideoDB): 18 colonoscopy video sequences (~11,954 frames).
3. **LDPolypVideo**: 160 video sequences (~40,266 frames) with frame-level bounding boxes/annotations (Ma et al., 2021).
4. **PolypGen**: 8,037 frames/images from multi-center international endoscopy cohorts (Ali et al., 2023).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | URL Identification & Content Decoding | Search all project records to extract all 11 Kaggle dataset URLs and inspect their full directory structures, video counts, image counts, and mask counts. | none | DONE |
| 2 | Baseline Completeness Verification | Compare Kaggle contents against official baselines of SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, and PolypGen to check if anything is missing. | M1 | DONE |
| 3 | Detailed Decoding Report Synthesis | Author structured report mapping each Kaggle URL to real-world counterpart, highlighting missing targets, incomplete datasets, and unexpected datasets. | M1, M2 | DONE |
| 4 | Challenger Verification & Multi-Agent Gate | Independent adversarial audit and review to guarantee zero fabrication and strict adherence to acceptance criteria. | M3 | DONE |

## Code Layout
- Target Report: `m:\chakramodel\KAGGLE_DATASET_DECODING_REPORT.md`
- Agent metadata & intermediate analysis: `m:\chakramodel\.agents/<agent_folder>/`
