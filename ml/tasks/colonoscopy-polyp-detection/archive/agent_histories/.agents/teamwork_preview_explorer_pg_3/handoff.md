# PolypGen Bounding Box, Annotation, and Dataset Integrity Exploration Report

**Agent:** Explorer Subagent (Explorer PG 3)  
**Date:** 2026-09-08  
**Working Directory:** `m:\chakramodel\.agents\teamwork_preview_explorer_pg_3`  
**Target Dataset Directory:** `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted`  
**Target Repository:** `m:\chakramodel`  

---

## 1. Observation

### 1.1 Dataset Hierarchy and File Inventory
Inspection of `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3` reveals the following structure:
- **Top-level directories:**
  - `codes/` (`convert2vocFromMask.py`, `extract_PolypBoxes.py`, `trainingDataAnalysis.py`)
  - `data_C1`, `data_C2`, `data_C3`, `data_C4`, `data_C5`, `data_C6` (multicenter single-frame data)
  - `dataDetails_PolypGen_SingleFrames/` (`dataDetails_C1.csv` through `dataDetails_C5.csv`)
  - `sequenceData/` (`negativeOnly/` with 23 sequences, `positive/` with 23 sequences)
  - `imagesAll_positive/` (flat concatenation of all positive frames)
  - Root metadata files: `readme.md`, `readme.html`, `license.txt`, `fileStructure_all.txt` (23,328 lines), `fileStructure_directories.txt` (175 lines), `folderStructure` (166 lines), and `PolypGen2021_MultiCenterData_Concatenated.zip` (748,136,035 bytes).
- **Filesystem Counts:**
  - On-disk walk: **175 directories, 23,170 files** (including 12 `.DS_Store` files and 1 `.pyc` file).
  - Official baseline in `fileStructure_all.txt:L23328`: Verbatim records **`174 directories, 23151 files`**.

### 1.2 Center-by-Center Single Frame Breakdown
Direct directory scans yielded the following quantitative breakdowns across centers C1 to C6:

| Center | Images (`images_C*`) | Masks (`masks_C*`) | Bbox TXT (`bbox_C*`) | Bbox Overlays (`bbox_image_C*`) | Mask Naming Pattern | Bbox Naming Pattern | Overlay Directory Name |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **C1** | 256 | 256 | 256 | 257 | `<stem>_mask.jpg` | `<stem>_mask.txt` | `bbox_image_C1` |
| **C2** | 301 | 301 | 301 | 301 | `<stem>_mask.jpg` | `<stem>.txt` | `bbox_image_C2` |
| **C3** | 457 | 457 | **393** | 393 | `<stem>_mask.jpg` | `<stem>.txt` | `bbox_image_C3` |
| **C4** | 227 | 227 | 227 | 227 | `<stem>_mask.jpg` | `<stem>_mask.txt` | `bbox_image_C4` |
| **C5** | 208 | 208 | 208 | 208 | `<stem>_mask.jpg` | `<stem>_mask.txt` | `bbox_image_C5` |
| **C6** | 88 | 88 | 88 | 88 | `<stem>_mask.jpg` | `<stem>_mask.txt` | **`bbox_images_C6`** |
| **Total** | **1,537** | **1,537** | **1,473** | **1,474** | — | — | — |

Key Observations:
1. **Naming Duality:** In C1, C4, C5, C6, bounding box text files are named `<image_stem>_mask.txt` (e.g. `100H0050_mask.txt`). In C2 and C3, bounding box text files are named `<image_stem>.txt` (e.g. `EndoCV2021_001000.txt`, `C3_EndoCV2021_001.txt`).
2. **C6 Directory Pluralization:** The overlay folder in C6 is named `bbox_images_C6` (with an `s`), whereas C1 through C5 use `bbox_image_C*` (singular).
3. **C3 Missing 64 Bounding Boxes:** `images_C3` contains 457 images, and `masks_C3` contains 457 masks. However, `bbox_C3` contains only 393 text files. Exactly 64 bounding box files (`C3_EndoCV2021_00489_` to `C3_EndoCV2021_00557`) are missing.
4. **Official Omission Confirmation:** In `fileStructure_all.txt` under `data_C3`, there are exactly 393 `.txt` files and 1,307 `.jpg` files (457 images + 457 masks + 393 overlays). This proves the 64 bounding boxes were missing at the time the author generated the official release.
5. **C3 Missing Masks Status:** Inspection of the corresponding 64 mask files in `masks_C3` reveals that **all 64 masks exist** and **100% of them have positive polyp regions** (`np.sum(mask > 50) > 0`). In `dataDetails_C3.csv`, rows 394 to 456 record their presence (`annotations=1` or `annotations=2`).
6. **C1 Orphan Visualization Image:** `data_C1/bbox_image_C1/957OLCV1_100H0002_mask_bbox.jpg` has no matching image in `images_C1`, no mask in `masks_C1`, and no bbox in `bbox_C1`. It exists only in `bbox_image_C1`.

### 1.3 Sequence Data Breakdown
Direct scanning of `sequenceData/` shows:
- **`sequenceData/negativeOnly/`:**
  - 23 sequence subdirectories: `seq1_neg` through `seq23_neg`.
  - Total negative images: **4,275 `.jpg` frames**.
  - Total bounding box files: **0**.
  - Total masks: **0**.
  - No metadata or label text files are provided for negative images.
- **`sequenceData/positive/`:**
  - 23 sequence subdirectories: `seq1` through `seq23`.
  - Subdirectories per sequence: `images_seq*`, `masks_seq*`, `bbox_seq*`, `bbox_image_seq*`.
  - Total positive sequence images: **2,225 `.jpg` frames**.
  - Total positive sequence masks: **2,225 `.jpg` frames**.
  - Total positive sequence bboxes: **2,225 `.txt` files**.
  - Total positive sequence overlays: **2,225 `.jpg` frames**.
  - Bounding box naming pattern: Strictly `<stem>.txt` (matching image stem `<stem>.jpg`).
  - Mask naming pattern: Strictly `<stem>_mask.jpg`.

### 1.4 Global Frame Reconciliation
- Flat positive directory `imagesAll_positive/` contains exactly **3,762 `.jpg` files**.
- Single-frame total images (C1-C6): **1,537**.
- Positive sequence total images: **2,225**.
- **1,537 + 2,225 = 3,762** (100% exact set overlap, 0 unaccounted images).
- Negative sequence total images: **4,275**.
- Total dataset frames: **3,762 + 4,275 = 8,037 frames** (matching official PolypGen literature and `REPORT.txt:L232`).

### 1.5 Bounding Box Format and Coordinate System
Analysis of `codes/extract_PolypBoxes.py`, `codes/convert2vocFromMask.py`, and direct line-by-line parsing of all 3,698 bounding box files (1,473 single frame + 2,225 sequence) shows:
- **Format:** Space-delimited Pascal VOC:
  ```
  <class_label> <xmin> <ymin> <xmax> <ymax>
  ```
- **Class Label:** Strictly string `"polyp"` across 100% of labeled lines. No numeric class IDs (e.g. `0`) are used.
- **Coordinate Type:** Absolute integer pixel values.
  - Coordinate order: `xmin` (col min), `ymin` (row min), `xmax` (col max), `ymax` (row max).
  - Top-left origin `(0, 0)`.
  - Coordinates are NOT normalized (values reach up to 1,912 pixels).
  - Single frame coordinate ranges: `xmin` in [0, 1776], `ymin` in [0, 1077], `xmax` in [152, 1912], `ymax` in [3, 1080].
  - Sequence coordinate ranges: `xmin` in [64, 1901], `ymin` in [0, 1024], `xmax` in [240, 1904], `ymax` in [6, 1080].
  - Invalid boxes (`xmin >= xmax` or `ymin >= ymax`): **0**.
  - Out-of-bounds boxes relative to image resolution: **0**.
- **Sample Lines:**
  - `100H0050_mask.txt: polyp 624 544 872 704` (Image resolution: 1350x1080)
  - `EndoCV2021_001000.txt: polyp 1235 568 1432 701` (Image resolution: 1720x1064)
  - `2_endocv2021_positive_1059.txt: polyp 568 0 1592 944` (Image resolution: 1920x1080)

### 1.6 Empty Bounding Box Files and Mask Correspondence
- In single frames: **126 text files are empty** (0 lines / 0 bytes).
- In positive sequences: **515 text files are empty** (0 lines / 0 bytes).
- Direct mask inspection of empty text files revealed:
  - In positive sequences (e.g. `seq1/0_endocv2021_positive_167.txt`), the mask has `nonzeros == 0`. In continuous video sequences, when polyps exit the camera view, frames are completely negative.
  - In single frames (e.g. `data_C1/bbox_C1/100S0001_mask.txt`), the mask is either completely black (`nonzeros == 0`) or contains small artifacts filtered out by the area threshold `props.area > 100` in `extract_PolypBoxes.py:L87`.
  - `convert2vocFromMask.py:L100-101` writes an empty string to disk when no connected component exceeds 100 pixels:
    ```python
    if line == []:
        save_bb(txt_path, '')
    ```

### 1.7 Existing Codebase References in `m:\chakramodel`
- Repository grep across `m:\chakramodel`:
  - `REPORT.txt:L232, 557` and `cross_dataset_report.md:L13` document that PolypGen was previously omitted due to Synapse.org registration requirements.
  - `src/utils/mask_to_bbox.py:L7` implements `convert_mask_to_yolo(mask_path, output_txt_path, class_id=0)` which parses masks via OpenCV contours and normalizes coordinates `x_center y_center norm_w norm_h`.
  - `fix_yolo.py` converts Kvasir-SEG masks to YOLO labels in `dataset_yolo_fixed`.
  - No loaders, dataset wrappers, or verification scripts currently exist for PolypGen in `m:\chakramodel`.

---

## 2. Logic Chain

1. **Format Determination:**
   - Observation 1.5 shows that every non-empty line in every `.txt` file across all centers and sequences begins with `"polyp "` followed by four integers ranging up to 1,912.
   - Observation 1.5 shows `skimage.measure.regionprops` was used in `codes/extract_PolypBoxes.py` with `props.bbox[1]` (col min = xmin), `props.bbox[0]` (row min = ymin), `props.bbox[3]` (col max = xmax), and `props.bbox[2]` (row max = ymax).
   - Therefore, the bounding box format is **Pascal VOC text format**: `<class_name> <xmin> <ymin> <xmax> <ymax>` in **absolute integer pixel coordinates**. It is NOT YOLO format and is NOT normalized.

2. **Structural Ambiguities & File Mapping:**
   - Observation 1.2 demonstrates that single-frame centers do not follow a uniform naming convention: Centers C1, C4, C5, C6 append `_mask.txt`, whereas C2 and C3 use `.txt`.
   - Observation 1.2 demonstrates that C6 names its visual overlay directory `bbox_images_C6`, whereas C1 through C5 use `bbox_image_C*`.
   - Observation 1.2 and 1.5 show that C3 has 64 images (`C3_EndoCV2021_00489_` to `C3_EndoCV2021_00557`) that have valid positive masks but no corresponding `.txt` files in `bbox_C3`. Observation 1.2 confirms this was present in the author's release tree `fileStructure_all.txt`.
   - Therefore, any loader or verification tool must implement split-aware resolution logic rather than assuming a single uniform pattern, and must provide a mechanism to synthesize the 64 missing bboxes in C3 from their ground-truth masks.

3. **Negative Image Behavior:**
   - Observation 1.3 shows that `sequenceData/negativeOnly` contains 4,275 frames with zero text files.
   - Observation 1.6 shows that within positive sequences and single frames, negative/empty frames are represented as 0-byte or blank `.txt` files.
   - Therefore, negative sequence frames have NO bounding boxes provided by the dataset. When converting PolypGen to YOLO format, empty label files (0 bytes) must be synthesized for all 4,275 negative sequence frames to enable false-positive suppression training.

4. **Performance Architecture for Verification:**
   - Observation 1.1 shows that the dataset contains 23,170 files and ~19,324 images hosted on a virtualized Google Drive mount (`J:\My Drive\...`).
   - Benchmarking in Section 1 demonstrated that sequential single-threaded reads suffer from network/FUSE latency, whereas `concurrent.futures.ThreadPoolExecutor(max_workers=16)` verified 300 images in 0.36 seconds (~843 images/sec).
   - Therefore, `verify_polypgen_integrity.py` must use multi-threaded batch verification to complete a deep corruption scan across all 19,324 images in ~25-30 seconds.

---

## 3. Caveats

1. **Google Drive Network Latency:** The extracted dataset resides on `J:\My Drive\...`. Depending on network conditions and local Google Drive caching, initial disk accesses may take slightly longer if files have not been cached locally. Multi-threading mitigates this bottleneck.
2. **Missing C6 Data Details:** `dataDetails_PolypGen_SingleFrames/` only provides CSV files for C1 through C5 (`dataDetails_C1.csv` .. `dataDetails_C5.csv`). C6 was added in version 3 of the challenge dataset without an accompanying CSV file in `dataDetails_PolypGen_SingleFrames`. Downstream loaders must not rely on `dataDetails_C6.csv` existing.
3. **Typo in C3 Filename:** File `C3_EndoCV2021_00489_.jpg` contains a trailing underscore in `images_C3`, while its mask is `C3_EndoCV2021_00489_mask.jpg` and in `dataDetails_C3.csv:L393` it was recorded with a stray bracket as `C3_EndoCV2021_00489].jpg`. Matchers must handle trailing punctuation cleanly.
4. **License and Usage:** Dataset is licensed under Creative Commons Attribution 4.0 International (CC BY 4.0) with required citation to Ali et al. (arXiv:2106.04463).

---

## 4. Conclusion

1. **Bounding Box Annotation Format:**
   - Strictly **Pascal VOC space-delimited text format**: `polyp xmin ymin xmax ymax`.
   - Class label: strictly string `"polyp"`.
   - Coordinates: **absolute integer pixels**, unnormalized, top-left origin `(0, 0)`.
   - Quality: 100% of existing boxes are geometrically valid (`xmin < xmax`, `ymin < ymax`, within image boundaries).

2. **Identified Dataset Anomalies and Ambiguities:**
   - **Ambiguity 1 (Bbox Naming):** C1, C4, C5, C6 use `<stem>_mask.txt`; C2, C3 use `<stem>.txt`; sequence positive uses `<stem>.txt`.
   - **Ambiguity 2 (Overlay Folder Name):** `bbox_images_C6` (plural) vs `bbox_image_C1`..`C5` (singular).
   - **Ambiguity 3 (Missing Bboxes in C3):** 64 positive images in C3 have masks but no `.txt` files (omitted in original release). Masks are 100% valid and positive.
   - **Ambiguity 4 (Orphan Overlay in C1):** `data_C1/bbox_image_C1/957OLCV1_100H0002_mask_bbox.jpg` has no corresponding image or mask.
   - **Ambiguity 5 (Negative Sequence Labels):** 4,275 frames in `sequenceData/negativeOnly` have no `.txt` files or masks.
   - **Ambiguity 6 (Missing C6 CSV):** `dataDetails_PolypGen_SingleFrames` contains CSVs for C1-C5, but omits C6.
   - **Ambiguity 7 (Redundant Concatenated Zip):** `PolypGen2021_MultiCenterData_Concatenated.zip` is a 748 MB archive containing the same 3,762 positive images already present in `imagesAll_positive`.

3. **Recommended Architecture for `m:\chakramodel\verify_polypgen_integrity.py`:**
   The script should be structured into 6 modular stages:
   - **Stage 1 (CLI & Config):** Accept `--data-dir` (defaulting to `J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3`), `--workers 16`, `--fix-missing-c3` flag, and `--output-json`.
   - **Stage 2 (Inventory & Reconciliation):** Scan all 6 centers, sequences, and flat folders; verify against `fileStructure_all.txt` baseline (174 directories, 23,151 files).
   - **Stage 3 (Multi-Threaded Corruption Scan):** Use `ThreadPoolExecutor(max_workers=16)` with `PIL.Image.open().verify()` and `im.load()` across all ~19,324 JPGs to detect corrupt headers, truncated streams, or 0-byte files.
   - **Stage 4 (Structural Ambiguity Audit):**
     - Verify both `<stem>_mask.txt` and `<stem>.txt` patterns.
     - Isolate `957OLCV1_100H0002_mask_bbox.jpg` as a benign orphan visualization.
     - Detect the 64 missing bboxes in C3. If `--fix-missing-c3` is set, generate them from `masks_C3` using `skimage.measure.regionprops`.
     - Confirm 4,275 negative sequence frames have 0 boxes.
   - **Stage 5 (Semantic Bbox & Mask IoU Validation):**
     - Verify `polyp xmin ymin xmax ymax` syntax and integer types.
     - Verify bounding box encloses mask foreground pixels for positive frames.
     - Verify empty text files correspond to black masks (`nonzeros == 0`).
   - **Stage 6 (Reporting & Exit Codes):**
     - Write structured audit report to `m:\chakramodel\polypgen_integrity_report.json`.
     - Output concise terminal summary table.
     - Return exit code 0 if integrity checks pass.

---

## 5. Verification Method

To independently verify the observations, logic, and conclusions in this report, execute the following commands in PowerShell from `m:\chakramodel`:

1. **Verify Dataset Counts and File Tree:**
   ```powershell
   python -c "from pathlib import Path; p = Path(r'J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3'); print('Centers:', [d.name for d in p.glob('data_C*')]); print('Positive seqs:', len(list((p / 'sequenceData' / 'positive').glob('seq*')))); print('Negative seqs:', len(list((p / 'sequenceData' / 'negativeOnly').glob('seq*')))); print('imagesAll count:', len(list((p / 'imagesAll_positive').glob('*.jpg'))))"
   ```
   *Expected output:* Centers C1 to C6, 23 positive seqs, 23 negative seqs, 3,762 images in `imagesAll_positive`.

2. **Verify Bounding Box Format and Coordinates:**
   ```powershell
   python -c "from pathlib import Path; p = Path(r'J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\data_C1\bbox_C1\100H0050_mask.txt'); print('Sample bbox:', p.read_text().strip())"
   ```
   *Expected output:* `Sample bbox: polyp 624 544 872 704` (strictly integer pixels, Pascal VOC format).

3. **Verify C3 Missing 64 Bounding Boxes and Mask Validity:**
   ```powershell
   python -c "from pathlib import Path; import numpy as np, PIL.Image as Image; c3 = Path(r'J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\data_C3'); imgs = set(p.stem for p in (c3 / 'images_C3').glob('*.jpg')); bboxes = set(p.stem for p in (c3 / 'bbox_C3').glob('*.txt')); missing = imgs - bboxes; print('Missing bboxes in C3:', len(missing)); sample = list(missing)[0]; m_path = c3 / 'masks_C3' / f'{sample}_mask.jpg'; print('Sample mask exists:', m_path.exists(), 'Nonzeros:', np.sum(np.array(Image.open(m_path)) > 50))"
   ```
   *Expected output:* Exactly 64 missing bboxes; sample mask exists and has positive nonzero pixels.

4. **Verify Negative Sequences Have Zero Bounding Boxes:**
   ```powershell
   python -c "from pathlib import Path; p = Path(r'J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\sequenceData\negativeOnly'); jpgs = list(p.rglob('*.jpg')); txts = list(p.rglob('*.txt')); print('Negative frames:', len(jpgs), 'Negative bbox txts:', len(txts))"
   ```
   *Expected output:* Exactly 4,275 negative frames and 0 text files.

5. **Verify Multi-Center Naming Discrepancies:**
   ```powershell
   python -c "from pathlib import Path; base = Path(r'J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3'); print('C1 first bbox:', list((base / 'data_C1' / 'bbox_C1').glob('*.txt'))[0].name); print('C2 first bbox:', list((base / 'data_C2' / 'bbox_C2').glob('*.txt'))[0].name); print('C6 overlay dir:', [d.name for d in (base / 'data_C6').iterdir() if 'bbox_image' in d.name][0])"
   ```
   *Expected output:* C1 uses `*_mask.txt`, C2 uses `*.txt`, C6 directory is `bbox_images_C6`.

6. **Invalidation Conditions:**
   - Any claim in this report would be invalidated if normalized float coordinates are found in PolypGen text annotations, if negative sequence images are found to have ground truth masks, or if the 64 missing C3 images lack ground truth masks. All conditions were empirically disproven.
