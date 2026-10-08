# Project: PolypGen Dataset Integrity and Structural Ambiguity Verification

## Mission & Scope
Verify the integrity of the extracted PolypGen dataset at `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted` to ensure no files are broken or corrupted, and resolve any structural ambiguities.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Structure Discovery | Inspect directory tree, file extensions, centers (C1..C6), annotations, masks, images, bounding boxes | None | DONE |
| 2 | Deep Corruption Scan & Tooling | Implement Python script to decode every image and mask; log unreadable/0-byte/corrupted files | M1 | IN_PROGRESS |
| 3 | Structural Ambiguity & Counterpart Check | Check positive images vs masks vs bounding boxes; detect orphaned files; produce comprehensive report | M2 | IN_PROGRESS |
| 4 | Independent Review, Stress-Test & Forensic Audit | 2 Reviewers, 2 Challengers, 1 Forensic Auditor for rigorous audit and verification | M3 | PLANNED |

## Code & Artifact Layout
- Verification Script: `m:\chakramodel\verify_polypgen_integrity.py`
- Authoritative Report: `m:\chakramodel\POLYPGEN_INTEGRITY_REPORT.md`
- Target Dataset: `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted`
- Coordination Metadata: `m:\chakramodel\.agents\orchestrator_gen3\`

## Key Exploration Findings (Milestone 1)
- Total Unique Images: 8,037 (3,762 positive + 4,275 negative sequence frames).
- Single-Frame Centers (C1–C6): 1,537 images, 1,537 masks, 1,473 bounding box text files, 1,474 overlay images.
- Positive Sequences (seq1–seq23): 2,225 images, 2,225 masks, 2,225 bounding box text files, 2,225 overlay images.
- Negative Sequences (seq1_neg–seq23_neg): 4,275 frames with 0 masks and 0 bounding boxes.
- Consolidated Folder (`imagesAll_positive`): 3,762 images ($1,537 + 2,225 = 3,762$).
- Formats: 100% 8-bit RGB JPEG for images; 100% 8-bit JPEG for masks (mixed RGB/L); Pascal VOC integer pixel coordinates for bounding boxes (`polyp xmin ymin xmax ymax`).
- Critical Ambiguities:
  1. Dual bbox naming: C1, C4, C5, C6 use `<stem>_mask.txt`; C2, C3, and sequence positive use `<stem>.txt`.
  2. Overlay directory naming: C6 uses `bbox_images_C6` (plural) vs `bbox_image_C*` (singular).
  3. 64 missing bboxes in C3: images `C3_EndoCV2021_00489_` to `00557` have valid positive masks, but lack `.txt` bounding boxes (official release omission).
  4. Orphan overlay in C1: `data_C1/bbox_image_C1/957OLCV1_100H0002_mask_bbox.jpg` has no matching image, mask, or bbox text file.
  5. 184 rogue `.txt` files in mask directories (`masks_seq2`: 63, `masks_seq7`: 48, `masks_seq8`: 73).
  6. Trailing underscore in C3: `images_C3/C3_EndoCV2021_00489_.jpg` maps to `masks_C3/C3_EndoCV2021_00489_mask.jpg`.
  7. Negative sequences have 0 annotations.
  8. Missing C6 metadata CSV.
