# Handoff Report: PolypGen Deep Integrity & Structural Audit (PG M2-M3)

**Agent**: Worker Subagent (Worker PG M2-M3)  
**Working Directory**: `m:\chakramodel\.agents\worker_pg_m2_m3`  
**Target Dataset Directory**: `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted`  
**Resolved Dataset Root**: `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3`  
**Date**: 2026-09-08  
**Handoff Type**: Hard (Task Complete)  

---

## 1. Observation

### 1.1 Physical File Verification
Using `verify_polypgen_integrity.py` with `ThreadPoolExecutor(max_workers=16)` and PIL 12.3.0 (`Image.open().verify()` and `Image.open().load()` with `ImageFile.LOAD_TRUNCATED_IMAGES = False`):
- **Total visual files physically scanned**: **19,260** files.
  - Single frame images (C1-C6): 1,537 files
  - Single frame masks (C1-C6): 1,537 files
  - Single frame overlays (C1-C6): 1,474 files (includes `data_C1/bbox_image_C1/957OLCV1_100H0002_mask_bbox.jpg`)
  - Positive sequence images (seq1-seq23): 2,225 files
  - Positive sequence masks (seq1-seq23): 2,225 files
  - Positive sequence overlays (seq1-seq23): 2,225 files
  - Negative sequence images (seq1_neg-seq23_neg): 4,275 files
  - Pooled images (`imagesAll_positive`): 3,762 files
- **Total Corrupted Files Detected**: **0** (0%).
- **Total 0-Byte Visual Files Detected**: **0** (0%).
- **Execution Duration**: **131.63 seconds** (throughput: **146.3 files/sec** across Google Drive mount).

### 1.2 Dataset Census & Reconciliation
- **Total Unique Frames**: **8,037** frames (matching official challenge literature).
  - Positive frames: 3,762 (1,537 single frames across Centers C1-C6 + 2,225 sequence frames across seq1-seq23).
  - Negative frames: 4,275 frames across seq1_neg-seq23_neg.
- **Pooled Folder `imagesAll_positive`**:
  $$\text{Single (1,537)} + \text{Sequence Positive (2,225)} = 3,762$$
  Set equality verification confirms:
  $$\text{set}(\text{imagesAll\_positive}) \setminus (\text{Single} \cup \text{Seq}) = \emptyset$$
  $$(\text{Single} \cup \text{Seq}) \setminus \text{set}(\text{imagesAll\_positive}) = \emptyset$$
  Exactly 0 missing, 0 extraneous files.

### 1.3 Structural Ambiguities Audit
Direct scanning and validation confirmed:
1. **Ambiguity 1 (Bbox Naming)**: Centers C1, C4, C5, C6 use `<stem>_mask.txt`; Centers C2, C3, and seq1-seq23 use `<stem>.txt`.
2. **Ambiguity 2 (Overlay Directory Pluralization)**: Center C6 directory is named `bbox_images_C6` (plural with 's'); Centers C1-C5 use `bbox_image_C{i}` (singular).
3. **Ambiguity 3 (C3 Missing Bboxes)**: Center C3 contains 457 images, 457 masks, but only 393 bounding box files (omitted in original challenge release). All 64 missing bboxes (`C3_EndoCV2021_00489_` to `00557`) have 100% valid, uncorrupted masks in `masks_C3` with positive polyp regions (`max > 0`).
4. **Ambiguity 4 (C1 Orphan Overlay)**: `data_C1/bbox_image_C1/957OLCV1_100H0002_mask_bbox.jpg` (330,729 bytes, 1350x1080) exists without matching image or mask.
5. **Ambiguity 5 (Rogue TXT Files in Masks)**: Positive sequences contain exactly 184 rogue `.txt` bounding box files inside mask directories (`seq2`: 63, `seq7`: 48, `seq8`: 73).
6. **Ambiguity 6 (C3 Trailing Underscore)**: Image `data_C3/images_C3/C3_EndoCV2021_00489_.jpg` has a trailing underscore in its stem, while its mask is named `data_C3/masks_C3/C3_EndoCV2021_00489_mask.jpg`.
7. **Ambiguity 7 (Negative Sequences)**: 23 negative sequences in `sequenceData/negativeOnly` contain 4,275 `.jpg` frames with strictly 0 masks and 0 bounding boxes.
8. **Ambiguity 8 (Single-Frame CSV Absence)**: `dataDetails_PolypGen_SingleFrames/` contains CSV files for C1 through C5 (1,449 rows) but omits Center C6 (88 frames), reflecting C6's role as the sequestered test center.

### 1.4 Bounding Box Format & Geometry
Line-by-line validation across all 3,698 bounding box text files:
- **Total Bbox Files**: 3,698 (641 empty/negative, 3,057 positive).
- **Total Boxes Parsed**: 3,365 instances.
- **Format**: Space-delimited Pascal VOC: `polyp <xmin> <ymin> <xmax> <ymax>`.
- **Classes**: Strictly `["polyp"]`.
- **Invalid Formats**: 0.
- **Invalid Geometry ($x_{\text{min}} \ge x_{\text{max}}$ or $y_{\text{min}} \ge y_{\text{max}}$)**: 0.
- **Out-of-Bounds Boxes**: 0 (validated against exact decoded image resolutions).
- **Mean Box Dimensions**: $376.4 \times 356.5$ pixels (mean area: 179,515.5 $\text{px}^2$).

---

## 2. Logic Chain

1. **Physical Integrity Premise**:
   - High-performance models cannot train on truncated or broken images.
   - The test script `verify_polypgen_integrity.py` subjected every one of the 19,260 visual files to `Image.open().verify()` and `Image.open().load()`.
   - Because 0 errors occurred and all 19,260 files decompressed completely, the dataset is physically sound and ready for production training.

2. **Dataloader Ingestion Rules**:
   - Dataloaders that assume `<stem>_mask.txt` fail on C2, C3, and sequences; dataloaders that assume `<stem>.txt` fail on C1, C4, C5, C6.
   - Dataloaders that read all files in `masks_seq*` fail on `seq2`, `seq7`, `seq8` due to the 184 rogue `.txt` files.
   - By implementing split-aware resolution and extension filtering (`.endswith('.jpg')`), 100% of positive images pair with valid masks and bounding boxes.

3. **Segmentation vs Detection Utility**:
   - For semantic segmentation, all 3,762 positive images (1,537 single + 2,225 sequence) have 1:1 ground-truth binary masks. The C3 missing bounding boxes do not affect segmentation.
   - For object detection, the 64 positive images in C3 can have their bounding boxes generated dynamically from their binary masks using `skimage.measure.regionprops`.
   - Negative sequence frames (4,275) must be incorporated with all-zero masks or empty label files to ensure high specificity and false-positive suppression.

---

## 3. Caveats

1. **Google Drive Mount Latency**: The dataset is hosted on a Google Drive virtual filesystem (`J:\My Drive\...`). While multi-threaded reading mitigated this (146 files/sec), local NVMe caching is recommended for model training loops to prevent GPU starvation.
2. **JPEG Mask Compression Artifacts**: Masks are saved as `.jpg` rather than lossless `.png`. Boundary pixels exhibit ringing artifacts (`[1..254]`). Downstream loaders must binarize with `mask = (np.array(im.convert('L')) > 127).astype(np.uint8)`.
3. **Inconsistent Mask Color Channels**: Masks are stored inconsistently as either 3-channel `RGB` or 1-channel `L`. Loaders must unconditionally call `.convert('L')`.
4. **C1 Orphan File**: `957OLCV1_100H0002_mask_bbox.jpg` in `data_C1/bbox_image_C1` has no image counterpart. Training loaders must enumerate `images_C1`, not `bbox_image_C1`.

---

## 4. Conclusion

The PolypGen 2021 dataset at `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3` is **verified 100% physically intact, uncorrupted, and structurally mapped**.
All deliverables are in place:
1. `m:\chakramodel\verify_polypgen_integrity.py`: Production-grade multi-threaded verification tool.
2. `m:\chakramodel\polypgen_integrity_report.json`: Comprehensive machine-readable audit artifact.
3. `m:\chakramodel\POLYPGEN_INTEGRITY_REPORT.md`: Authoritative human-readable documentation with complete statistics, resolution rules, and PyTorch dataset code.

---

## 5. Verification Method

To independently verify these results, execute the following commands in PowerShell from `m:\chakramodel`:

1. **Re-run the Complete Audit Tool**:
   ```powershell
   python m:\chakramodel\verify_polypgen_integrity.py --data-dir "J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted" --workers 16 --json-report "m:\chakramodel\polypgen_integrity_report.json" --full-scan
   ```
   *Expected*: Exit code 0, 19,260 images passed, 0 corrupted, overall verdict PASS.

2. **Verify JSON Audit Artifact Values**:
   ```powershell
   python -c "
   import json
   with open(r'm:\chakramodel\polypgen_integrity_report.json') as f:
       d = json.load(f)
   assert d['verdict']['status'] == 'PASS'
   assert d['deep_corruption_scan']['total_scanned'] == 19260
   assert d['deep_corruption_scan']['total_corrupted'] == 0
   assert d['dataset_census']['pooled_images_reconciliation']['exact_match'] is True
   assert d['bounding_box_validation']['invalid_format_boxes'] == 0
   assert d['bounding_box_validation']['invalid_geometry_boxes'] == 0
   print('ALL INDEPENDENT ASSERTIONS PASSED.')
   "
   ```

### Invalidation Conditions
- If any file in `data_C1` through `data_C6` or `sequenceData` is deleted or corrupted.
- If negative sequence frames are found to contain non-zero mask files.
- If bounding box files are converted to normalized floats without updating loader logic.
