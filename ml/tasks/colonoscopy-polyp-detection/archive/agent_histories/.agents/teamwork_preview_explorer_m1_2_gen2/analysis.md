# Deep Content & Directory Structure Inspection Report: Kaggle Datasets & Archives

**Author:** teamwork_preview_explorer  
**Date:** 2026-09-07  
**Working Directory:** `m:\chakramodel\.agents\teamwork_preview_explorer_m1_2_gen2`  
**Milestone:** Milestone 1 — Deep Content & Directory Structure Inspection  

---

## 1. Executive Summary

A comprehensive, non-destructive, byte-level investigation was conducted across all local archives, filesystem directories, and pipeline scripts associated with the Kaggle datasets in `m:\chakramodel`.

### Key Discoveries & Structural Realities:
1. **`CVC_ClinicVideoDB_Kaggle.zip` (13.65 GB / 12.71 GB compressed):**
   - Contains **85 video files** representing 42 colonoscopy sequences (`1_1` through `1_42`) in dual formats (42 `.avi` + 42 `.mp4`), 1 analyzed demonstration video (`1_1_analyzed.mp4`), 2 directory records (`polyp/`, `polyp/extracted/`), and 1 nested raw video ZIP (`polyp/videos with polyps-20260804T054937Z-1-001.zip`, 2.08 GB uncompressed).
   - Standard Python `zipfile` raises `BadZipFile` because the archive structure contains an embedded ZIP with an unconventional ZIP64 header at offset `12,528,682,767`, but all 88 local file headers are 100% intact and sequential.
2. **`ChakraModel_Evaluation_Datasets.zip` & `Kaggle_Datasets_Upload` (105.75 MB uncompressed / 94.74 MB compressed):**
   - The directory `Kaggle_Datasets_Upload` is a 100% byte-for-byte, path-for-path mirror of `ChakraModel_Evaluation_Datasets.zip`.
   - Contains exactly **3,000 files**: 1,500 unmasked images and 1,500 ground-truth masks across 3 evaluation datasets:
     - `kvasir-seg`: 1,000 images + 1,000 masks (JPEG)
     - `cvc-clinicdb`: 495 images + 495 masks (PNG) — note this is 495 frames, not the original full 612 frames.
     - `etis-larib`: 5 images + 5 masks (PNG) — **synthetic data** (`synth_0.png` to `synth_4.png`), not the 196-image clinical benchmark.
3. **Unhydrated Git LFS Pointer Files in `data/cvc-colondb`:**
   - All 760 files (380 images and 380 masks) in `data/cvc-colondb` are 130-byte Git LFS pointer text files pointing to GitHub LFS sha256 hashes, not actual PNG images. Total directory size is only 0.10 MB.
4. **Format Masquerade in `data/datasets_archive/CVC-ClinicDB.zip`:**
   - `data/datasets_archive/CVC-ClinicDB.zip` (46.79 MB) has magic bytes `52 61 72 21 1a 07` (`Rar!\x1a\x07`), meaning it is actually a **RAR archive** misnamed with a `.zip` extension.
5. **Anti-Fabrication Canary Files in `data/`:**
   - Security canary files (`CANARY_<hash>.png`) exist across multiple subdirectories: `data/cvc-300` contains 16 files (all 16 are canaries); `data/etis-larib` contains 16 canaries; `data/cvc-clinicdb` contains 14 canaries.
6. **`dataset_yolo` vs `dataset_yolo_fixed`:**
   - `dataset_yolo` (1.16 GB, 14,423 files) is heavily imbalanced with **6,210 hard negative colonoscopy images** (empty labels: stool, bubbles, fecal matter, normal mucosa) and **1,000 positive images** (7,210 total images).
   - `dataset_yolo_fixed` (24.84 MB, 1,402 files) was created via `fix_yolo.py` as a sanitized dataset containing strictly the 700 positive training images from Kvasir-SEG (751 bounding boxes) without hard negatives.

---

## 2. Comprehensive Inventory Matrix

| Target Representation | Type | Total Size | Total Files | Video Files | Image Files (Unmasked) | Mask Files | Key Extensions | Integrity / Status |
|---|---|---|---|---|---|---|---|---|
| `CVC_ClinicVideoDB_Kaggle.zip` | Archive | 13,648,757,889 B (12.71 GB) | 88 entries | 85 | 0 | 0 | `.avi` (42), `.mp4` (43), `.zip` (1) | Local headers valid; embedded zip at tail |
| `ChakraModel_Evaluation_Datasets.zip` | Archive | 99,339,812 B (94.74 MB) | 3,000 | 0 | 1,500 | 1,500 | `.jpg` (2000), `.png` (1000) | Fully intact, 1:1 image-mask paired |
| `Kaggle_Datasets_Upload` | Directory | 109,350,551 B (104.28 MB) | 3,000 | 0 | 1,500 | 1,500 | `.jpg` (2000), `.png` (1000) | 1:1 identical to Evaluation_Datasets.zip |
| `chakramodel-weights.zip` | Archive | 1,155,023,765 B (1.10 GB) | 3 | 0 | 0 | 0 | `.pt` (1), `.pth` (1), `.json` (1) | Fully intact (ViT-L + YOLOv8 + Conformal) |
| `chakramodel_weights_PRIVATE.zip` | Archive | 2,516,940,586 B (2.40 GB) | 10 | 0 | 0 | 0 | `.pt` (4), `.pth` (4), `.bak` (1), `.json` (1) | Complete research checkpoint suite |
| `chakramodel_data_scripts.zip` | Archive | 240,662,934 B (229.51 MB) | 979 | 0 | 440 | 440 | `.png` (880), `.py` (57), `.pyc` (38), `.pt` (1) | Contains 440 synthetic image/mask pairs |
| `CVC_SampleVideo.zip` | Archive | 34,783,585 B (33.17 MB) | 1 | 1 | 0 | 0 | `.mp4` (1) | Fully intact (`1_1.mp4`, 4994 frames) |
| `kaggle_bundle for testing.zip` | Archive | 211,832,415 B (202.02 MB) | 3,290 | 1 | 1,600 | 1,600 | `.jpg` (2000), `.png` (1200), `.ipynb` (15), `.py` (48) | Complete evaluation bundle |
| `kaggle_upload.zip` | Archive | 1,155,351,335 B (1.10 GB) | 94 | 0 | 0 | 0 | `.pth` (1), `.pt` (1), `.ipynb` (1), `.py` (52) | Deployment package for Kaggle |
| `dataset_yolo` | Directory | 1,216,513,446 B (1.16 GB) | 14,423 | 0 | 7,210 | 0 (7,210 labels) | `.jpg` (7210), `.txt` (7210), `.yaml` (1), `.cache` (2) | 1,000 pos / 6,210 hard neg colonoscopy |
| `dataset_yolo_fixed` | Directory | 26,045,952 B (24.84 MB) | 1,402 | 0 | 700 | 0 (700 labels) | `.jpg` (700), `.txt` (700), `.yaml` (1), `.cache` (1) | Clean Kvasir-SEG 70% train split only |
| `datasets/` | Directory | 1,538,582,333 B (1.47 GB) | 12,244 | 0 | 11,240 | 0 (1,000 labels) | `.jpg` (11240), `.txt` (1000), `.yaml` (1), `.json` (1) | Raw colon cancer images + YOLO train set |
| `data/` | Directory | 3,381,878,056 B (3.23 GB) | 24,490 | 0 | 12,727 | 4,519 (masks) | `.jpg` (14240), `.txt` (7214), `.png` (3006), `.zip` (2) | Contains LFS pointers, canaries, archives |

---

## 3. Deep Dive Breakdown by Target Representation

### Target 1: `CVC_ClinicVideoDB_Kaggle.zip`
- **Location:** `m:\chakramodel\CVC_ClinicVideoDB_Kaggle.zip`
- **Total Compressed Size:** 13,648,757,889 bytes (13,016.47 MB / 12.711 GB)
- **Total Uncompressed Size of Valid Payloads:** 14,422,720,016 bytes (13.43 GB)
- **Archive Structure Analysis:**
  - Standard ZIP extraction tools fail because the central directory record at the end of the file is displaced by an embedded ZIP archive (`polyp/videos with polyps-20260804T054937Z-1-001.zip`).
  - Binary header traversal confirmed 88 sequential local file headers beginning with magic `PK\x03\x04`.
- **Content Breakdown:**
  - **42 AVI Video Files:** `1_1.avi` through `1_42.avi`. Sizes range from 33.23 MB (`1_35.avi`) to 508.12 MB (`1_20.avi`). Total uncompressed: 9,969.83 MB.
  - **42 MP4 Video Files:** `1_1.mp4` through `1_42.mp4`. Sizes range from 7.62 MB (`1_35.mp4`) to 111.15 MB (`1_18.mp4`). Total uncompressed: 2,367.61 MB.
  - **1 Demonstration Video:** `1_1_analyzed.mp4` (87.47 MB uncompressed / 80.32 MB compressed).
  - **1 Nested Raw Archive:** `polyp/videos with polyps-20260804T054937Z-1-001.zip` (Offset: 12,528,682,767; uncompressed size: 2,085,288,450 bytes / 1.94 GB).
  - **2 Directory Records:** `polyp/` and `polyp/extracted/`.
- **Total Sample Counts:** 42 distinct colonoscopy video sequences represented in parallel formats.

---

### Target 2: `ChakraModel_Evaluation_Datasets.zip` & `Kaggle_Datasets_Upload`
- **Locations:**
  - Archive: `m:\chakramodel\ChakraModel_Evaluation_Datasets.zip` (99,339,812 bytes / 94.74 MB)
  - Directory: `m:\chakramodel\Kaggle_Datasets_Upload` (109,350,551 bytes / 104.28 MB)
- **Equivalence:** 100% identical. Every file path, file size, and file content matches.
- **Directory Hierarchy & Counts:**
  ```text
  Kaggle_Datasets_Upload/
  ├── cvc-clinicdb/
  │   ├── images/    [495 PNG files: 0000.png - 0494.png, 20,240,683 bytes]
  │   └── masks/     [495 PNG files: 0000.png - 0494.png,  2,044,481 bytes]
  ├── etis-larib/
  │   ├── images/    [  5 PNG files: synth_0.png - synth_4.png, 3,485,320 bytes]
  │   └── masks/     [  5 PNG files: synth_0.png - synth_4.png,    53,091 bytes]
  └── kvasir-seg/
      ├── images/    [1000 JPG files: cju...jpg, 52,836,666 bytes]
      └── masks/     [1000 JPG files: cju...jpg, 32,223,059 bytes]
  ```
- **File Metrics:**
  - Total Files: 3,000
  - Video files: 0
  - Unmasked images: 1,500 (495 CVC-ClinicDB + 5 ETIS-Larib + 1,000 Kvasir-SEG)
  - Ground-truth masks: 1,500 (495 CVC-ClinicDB + 5 ETIS-Larib + 1,000 Kvasir-SEG)
  - Pairing ratio: 1:1 exact pairing.
- **Key Observation on Data Distribution:**
  - Original CVC-ClinicDB contains 612 frames; this evaluation pack contains a 495-frame subset.
  - ETIS-Larib contains only 5 synthetic sample pairs (`synth_0.png` to `synth_4.png`), explicitly acknowledged in `build_crossval_v5.py:L281`: *"Full dataset: catastrophic failure, Dice=0.0000. Only 5-image subset available on Kaggle."*

---

### Target 3: Model Weights Archives
#### A. `chakramodel-weights.zip` (Public Release Bundle)
- **Size:** 1,155,023,765 bytes (1,101.52 MB compressed, 1.15 GB uncompressed)
- **Contents:**
  1. `best.pt` (6,209,450 bytes / 5.92 MB): Fine-tuned Ultralytics YOLOv8 detector checkpoint.
  2. `chakra_transformer_best.pth` (1,236,836,719 bytes / 1,179.54 MB): Main ViT-Large/16 384 segmentation backbone state dict.
  3. `conformal_calibration.json` (130 bytes): Conformal prediction parameters:
     ```json
     {
       "q_hat_pos": 0.521484375,
       "q_hat_neg": 0.55421875,
       "alpha": 0.05,
       "mc_passes": 16,
       "n_calibration_images": 100
     }
     ```

#### B. `chakramodel_weights_PRIVATE.zip` (Research Suite)
- **Size:** 2,516,940,586 bytes (2,400.34 MB compressed, 3.61 GB uncompressed)
- **Contents (inside `weights/`):**
  1. `weights/best.pt` (6,241,834 bytes / 5.95 MB)
  2. `weights/chakra_transformer_best.pth` (1,236,836,719 bytes / 1,179.54 MB)
  3. `weights/chakra_transformer_best.pth.bak` (1,236,830,575 bytes / 1,179.53 MB)
  4. `weights/combo1_best.pth` (102,677,499 bytes / 97.92 MB)
  5. `weights/combo2_best.pth` (102,677,499 bytes / 97.92 MB)
  6. `weights/conformal_calibration.json` (130 bytes)
  7. `weights/pranet_kvasir_best.pth` (6,191,937 bytes / 5.91 MB)
  8. `weights/yolo26n.pt` (5,544,453 bytes / 5.29 MB)
  9. `weights/yolov8n.pt` (6,549,796 bytes / 6.25 MB)
  10. `weights/yolo_custom_best.pt` (6,241,834 bytes / 5.95 MB)

---

### Target 4: `chakramodel_data_scripts.zip`
- **Location:** `m:\chakramodel\chakramodel_data_scripts.zip`
- **Size:** 240,662,934 bytes (229.51 MB compressed, 269.64 MB uncompressed)
- **Total Files:** 979 files
- **Image & Mask Breakdown:**
  - `data/cvc-300/images`: 60 synthetic PNG images (`synthetic_0000.png` to `synthetic_0059.png`)
  - `data/cvc-300/masks`: 60 synthetic PNG masks
  - `data/cvc-colondb/images`: 380 synthetic PNG images (`synthetic_0000.png` to `synthetic_0379.png`)
  - `data/cvc-colondb/masks`: 380 synthetic PNG masks
  - Total images: 880 (440 unmasked + 440 masks)
- **Code Breakdown:**
  - `src/`: 57 python scripts across subpackages: `chakra_transformer/`, `metrics/`, `temporal/`, `utils/`, `vst_fp/`.
  - 38 `.pyc` files, 1 `.pt` checkpoint file, 1 `.md`, 1 `.txt`, 1 `.bak`.

---

### Target 5: `CVC_SampleVideo.zip`
- **Location:** `m:\chakramodel\CVC_SampleVideo.zip`
- **Size:** 34,783,585 bytes (33.17 MB compressed, 34,817,214 bytes uncompressed)
- **File:** `1_1.mp4` (Single colonoscopy video sequence)
- **Verified Video Stream Metrics:**
  - **Resolution:** 768 x 576 (PAL standard definition colonoscopy)
  - **Frame Rate:** 24.83 FPS
  - **Frame Count:** 4,994 frames
  - **Duration:** 201.10 seconds (~3.35 minutes)
  - **Codec:** H.264 / AVC (MPEG-4 Part 10)
- Used as the reference video input for Kaggle inference demonstrations under the dataset alias `cvc-sample-video`.

---

### Target 6: `kaggle_bundle for testing.zip` & `kaggle_upload.zip`
#### A. `kaggle_bundle for testing.zip`
- **Size:** 211,832,415 bytes (202.02 MB)
- **Total Files:** 3,290 files
- **Video:** 1 video (`kaggle_bundle/test_input.mp4`: 26,347 bytes, 640x480, 30.00 fps, 60 frames, 2.00s)
- **Images:** 3,200 total (1,600 unmasked + 1,600 masks):
  - `kvasir-seg`: 1,000 images + 1,000 masks
  - `filtered_synthetic_polyps`: 300 images + 300 masks
  - `synthetic_polyps`: 300 images + 300 masks
- **Weights:** `best.pt`, `pranet_kvasir_best.pth`
- **Notebooks:** 8 active notebooks + 7 deprecated notebooks

#### B. `kaggle_upload.zip`
- **Size:** 1,155,351,335 bytes (1,101.83 MB)
- **Total Files:** 94 files (52 `.py`, 38 `.pyc`, 1 `.ipynb`, 2 weights)
- **Weights:** `weights/best.pt` (5.92 MB), `weights/chakra_transformer_best.pth` (1,179.54 MB)
- **Notebook:** `Kaggle_ChakraTransformer_Evaluation.ipynb`

---

### Target 7: YOLO Dataset Representations
#### A. `dataset_yolo` (Multi-Source with Hard Negatives)
- **Path:** `m:\chakramodel\dataset_yolo`
- **Size:** 1,160.19 MB (1.16 GB)
- **Total Files:** 14,423 files
- **Configuration (`dataset.yaml`):**
  - `train: images/train`, `val: images/val`, `test: images/test`
  - `names: {0: polyp}`
- **Split Breakdown & Class Distribution:**

| Split | Images | Labels | Positive Polyp Images | Hard Negative Images | Total Bounding Boxes |
|---|---|---|---|---|---|
| `train` | 5,047 | 5,047 | 700 | 4,347 | 758 |
| `val` | 721 | 721 | 100 | 621 | 101 |
| `test` | 1,442 | 1,442 | 200 | 1,242 | 212 |
| **Total** | **7,210** | **7,210** | **1,000** | **6,210** | **1,071** |

- **Origin of Hard Negatives:** Sourced from `colon_cancer_dataset` / EndoCV2021 non-polyp sequences (bubbles, occlusion, fecal matter, normal colon wall) to suppress false positives in video streams.

#### B. `dataset_yolo_fixed` (Clean Single-Source Train Split)
- **Path:** `m:\chakramodel\dataset_yolo_fixed`
- **Size:** 24.84 MB
- **Total Files:** 1,402 files
- **Configuration (`dataset.yaml`):**
  - `train: images/train`, `val: images/train` (hackathon rapid training configuration)
  - `names: {0: polyp}`
- **Split Breakdown:**
  - `train`: 700 images, 700 labels (700 positive images, 751 bounding boxes, 0 negative images).
  - Derived directly from the first 70% of Kvasir-SEG by `fix_yolo.py`.

---

### Target 8: Filesystem Directories `datasets/` and `data/`
#### A. `datasets/` Directory (1.47 GB, 12,244 files)
1. `colon_cancer_dataset/` (10,242 files, 1,429.34 MB):
   - 10,240 JPG images across 5 classes:
     - `bubbles-occlusion/`: 1,444 images
     - `dyed-lifted-polyps/`: 1,002 images
     - `fecal/`: 1,840 images
     - `impacted-stool/`: 954 images
     - `negative/`: 5,000 images
   - Metadata: 1 `.json`, 1 `.docx`
2. `yolo/` (2,002 files, 37.96 MB):
   - `images/train`: 1,000 JPG images (Kvasir-SEG)
   - `labels/train`: 1,000 YOLO TXT labels (Kvasir-SEG bounding boxes)
   - `dataset.yaml`: NIT Hackathon YOLO training configuration

#### B. `data/` Directory (3.23 GB, 24,490 files)
1. `colon_cancer_dataset/` (17,456 files, 1,430.31 MB): 10,240 images + 7,212 TXT labels.
2. `cvc-colondb/` (760 files, 0.10 MB): **All 760 files are Git LFS text pointer files** (380 images + 380 masks).
3. `cvc-300/` (16 files, 4.62 MB): **All 16 files are CANARY security files** (`CANARY_...png`).
4. `cvc-clinicdb/` (1,004 files, 57.83 MB): 495 frames + 495 masks + 14 CANARY security files.
5. `etis-larib/` (26 files, 5.13 MB): 5 synthetic pairs + 16 CANARY security files.
6. `kvasir-seg/` (2,000 files, 49.97 MB): 1,000 clinical images + 1,000 masks.
7. `raw_kvasir/` (2,001 files, 50.11 MB): Unpacked official Kvasir-SEG distribution + metadata JSON.
8. `filtered_synthetic_polyps/` (600 files, 73.27 MB): 300 synthetic images + 300 masks.
9. `synthetic_polyps/` (600 files, 73.27 MB): 300 synthetic images + 300 masks.
10. `datasets_archive/` (2 files, 1,479.94 MB):
    - `colon_cancer_dataset.zip` (1,433.15 MB): Valid ZIP of colon cancer images.
    - `CVC-ClinicDB.zip` (46.79 MB): **RAR archive** misnamed as `.zip`.
11. `leads/` (10 files, 0.43 MB): CSV marketing/submission leads.
12. `scripts/` (12 files, 0.03 MB): Data conversion and utility scripts.

---

## 4. Script References & Kaggle Mounting Path Analysis

Inspection of `build_crossval_v5.py`, `build_crossval_v4.py`, `build_master_eval_notebook.py`, and `package_kaggle.py` reveals how datasets are discovered and mounted during Kaggle evaluation:

### Kaggle Mount Path Conventions:
1. **Mounting Prefix Asymmetry:**
   - In modern Kaggle environments, user datasets are mounted under `/kaggle/input/datasets/<username>/<slug>/` rather than directly under `/kaggle/input/<slug>/`.
   - `build_crossval_v5.py` incorporates explicit dual-path resolution:
     ```python
     BASE = "/kaggle/input/datasets/gokulrocky"
     # Fallbacks check both /kaggle/input/<slug> and /kaggle/input/datasets/gokulrocky/<slug>
     ```
2. **Kaggle Dataset Slugs Identified in Code:**
   - `gokulrocky/chakramodel-evaluation-datasets` -> Maps to `ChakraModel_Evaluation_Datasets.zip` / `Kaggle_Datasets_Upload` (Kvasir-SEG 1000, CVC-ClinicDB 495, ETIS-Larib 5 synthetic).
   - `gokulrocky/endoscene-cvc300-polyp-raw-dataset` -> Maps to `CVC-300` (60 images/masks).
   - `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset` -> Maps to HyperKvasir segmented subset (1,000 images) and LDPolyp labeled images.
   - `gokulrocky/polypdb-polyp-raw-stress-testdataset` -> Maps to PolypDB multi-modality stress test dataset.
   - `cvc-sample-video` -> Maps to `CVC_SampleVideo.zip` (`1_1.mp4`).

---

## 5. Critical Findings & Anomaly Summary

| Finding ID | Artifact / Directory | Nature of Finding | Impact & Technical Context |
|---|---|---|---|
| **ANOM-01** | `CVC_ClinicVideoDB_Kaggle.zip` | Archive trailer displacement by nested ZIP | Standard `zipfile.ZipFile` raises `BadZipFile`. All 88 local headers are intact. Contains 42 AVI, 42 MP4, 1 demo MP4, 1 nested 2.08 GB ZIP. |
| **ANOM-02** | `data/cvc-colondb` | Unhydrated Git LFS pointer files | 760 files (380 images + 380 masks) are 130-byte ASCII text pointers with sha256 hashes. Cannot be read by image loaders without git lfs pull. |
| **ANOM-03** | `data/datasets_archive/CVC-ClinicDB.zip` | Format masquerade (RAR named .zip) | File begins with `52 61 72 21 1a 07` (`Rar!\x1a\x07`). `zipfile` fails; requires `rarfile` / `unrar` to extract. |
| **ANOM-04** | `data/cvc-300`, `data/etis-larib`, `data/cvc-clinicdb` | Anti-fabrication canary files | Contains `CANARY_<hash>.png` files (16 in cvc-300, 16 in etis-larib, 14 in cvc-clinicdb) inserted by anti-fabrication toolkit. |
| **ANOM-05** | `ChakraModel_Evaluation_Datasets.zip` / `etis-larib` | Synthetic placeholder data | `etis-larib` contains only 5 synthetic images (`synth_0.png` - `synth_4.png`), not the 196-image clinical ETIS-Larib benchmark. |
| **ANOM-06** | `dataset_yolo` | Extreme hard negative ratio | 7,210 total images contain 6,210 negative frames (empty label files) and only 1,000 positive frames. |
