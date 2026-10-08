# Handoff Report: PolypGen Dataset Exploration (Explorer PG 2)

## 1. Observation

### 1.1 Dataset Root & Top-Level Hierarchy
The target dataset directory is:
`J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted`

Inside this directory, the actual dataset structure resides under:
`J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3`

Top-level contents observed:
- `data_C1` to `data_C6`: Single-frame multicenter datasets (6 centers).
- `sequenceData/`: Video sequence data split into `positive/` (seq1 to seq23) and `negativeOnly/` (seq1_neg to seq23_neg).
- `imagesAll_positive/`: Consolidated flat image folder containing 3,762 `.jpg` images (all single frames + all positive sequence frames).
- `dataDetails_PolypGen_SingleFrames/`: CSV metadata files for centers C1 through C5 (`dataDetails_C1.csv` to `dataDetails_C5.csv`; note: no C6 CSV exists).
- `codes/`: Author scripts (`convert2vocFromMask.py`, `extract_PolypBoxes.py`, `trainingDataAnalysis.py`).
- Documentation: `readme.md`, `readme.html`, `license.txt`, `fileStructure_all.txt`, `folderStructure`.

---

### 1.2 Centerwise Single-Frame Breakdown (`data_C1` to `data_C6`)

| Center | Subdirectories Present | Images Count | Masks Count | Bbox TXT Count | Bbox Image Count | Positive Masks (`max > 0`) | Negative Masks (`max == 0`) | Mask Color Modes | Image Resolutions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **C1** | `images_C1`, `masks_C1`, `bbox_C1`, `bbox_image_C1` | 256 | 256 | 256 | 257 *(1 extra)* | 251 | 5 | 241 RGB, 15 L | (1350,1080): 146<br>(1232,1048): 94<br>(628,513): 11<br>(572,498): 4<br>(1008,1042): 1 |
| **C2** | `images_C2`, `masks_C2`, `bbox_C2`, `bbox_image_C2` | 301 | 301 | 301 | 301 | 270 | 31 | 211 RGB, 90 L | 15 distinct resolutions:<br>(1440,1064): 162<br>(1280,1024): 30<br>(1704,1072): 15<br>(1432,1056): 14<br>(1359,1063): 14<br>others: 66 |
| **C3** | `images_C3`, `masks_C3`, `bbox_C3`, `bbox_image_C3` | 457 | 457 | 393 *(64 missing)* | 393 | 456 | 1 | 457 L | (1440,1080): 429<br>(720,576): 23<br>(1240,1040): 5 |
| **C4** | `images_C4`, `masks_C4`, `bbox_C4`, `bbox_image_C4` | 227 | 227 | 227 | 227 | 146 | 81 | 227 L | (1920,1080): 227 |
| **C5** | `images_C5`, `masks_C5`, `bbox_C5`, `bbox_image_C5` | 208 | 208 | 208 | 208 | 206 | 2 | 208 L | (1920,1080): 182<br>(384,288): 26 |
| **C6** | `images_C6`, `masks_C6`, `bbox_C6`, `bbox_images_C6` *(plural!)* | 88 | 88 | 88 | 88 | 83 | 5 | 88 L | (1920,1080): 83<br>(1024,768): 5 |
| **Total** | — | **1,537** | **1,537** | **1,473** | **1,474** | **1,412** | **125** | — | — |

#### Direct Observations on Naming Conventions in Centers C1..C6:
- **Images:** `data_C{i}/images_C{i}/<stem>.jpg` (100% `.jpg`).
- **Masks:** `data_C{i}/masks_C{i}/<stem>_mask.jpg` (100% `.jpg`).
  - **Exception in C3:** Image file `data_C3/images_C3/C3_EndoCV2021_00489_.jpg` has a trailing underscore in the stem, but the corresponding mask is `data_C3/masks_C3/C3_EndoCV2021_00489_mask.jpg` (without trailing underscore).
- **Bbox TXT Files:**
  - In C1, C4, C5, C6: Filenames end with `_mask.txt` (e.g., `326OLCV1_100H0006_mask.txt`).
  - In C2, C3: Filenames end with `.txt` (e.g., `EndoCV2021_001359.txt`, `C3_EndoCV2021_00238.txt`).
  - Format: VOC format `polyp <xmin> <ymin> <xmax> <ymax>` (e.g., `polyp 432 624 648 768\n`).
  - Empty files contain only `\n` (1 byte) for negative frames.
- **Bbox Visualizations:**
  - In C1, C4, C5: Directory is named `bbox_image_C{i}`, files named `<stem>_mask_bbox.jpg`.
  - In C6: Directory is named `bbox_images_C6` (plural `images`), files named `<stem>_mask_bbox.jpg`.
  - In C2, C3: Directory is named `bbox_image_C{i}`, files named `<stem>_bbox.jpg`.
  - **Orphan File in C1:** `data_C1/bbox_image_C1/957OLCV1_100H0002_mask_bbox.jpg` has no matching image, mask, or bbox text file anywhere in C1 or the dataset.
- **Missing Bboxes in C3:**
  - Center C3 has 457 images, 457 masks, but only 393 `.txt` bbox files (64 images lack a bbox file in `bbox_C3`).
  - All 64 missing images have valid non-empty masks with polyps (e.g., `C3_EndoCV2021_0054.jpg`, mask max = 255).

---

### 1.3 Sequence Data Breakdown (`sequenceData/`)

#### A. Positive Sequences (`sequenceData/positive/seq1` to `seq23`):
- **Total Positive Sequence Images:** 2,225 (100% `.jpg`).
- **Total Mask Files:** 2,409 files:
  - 2,225 `.jpg` image masks (1-to-1 match for all 2,225 images).
  - 184 rogue `.txt` files in mask directories (`masks_seq2`: 63 `.txt` files, `masks_seq7`: 48 `.txt` files, `masks_seq8`: 73 `.txt` files). These contain bounding box strings or empty strings.
- **Total Bbox TXT Files:** 2,225 files in `bbox_seq{k}/<stem>.txt`.
- **Total Bbox Visualization Images:** 2,225 files in `bbox_image_seq{k}/<stem>_bbox.jpg`.
- **Positive vs Negative Frames within Positive Sequences:**
  - 1,710 frames have non-zero masks (`max > 0`).
  - 515 frames have all-zero (empty) masks (`max == 0`) and empty bbox text (`\n`).
  - **Completely Empty Sequences:**
    - `seq1`: 36 frames total, **all 36 masks are all-zero**, all 36 bbox files are empty (`\n`).
    - `seq7`: 48 frames total, **all 48 masks are all-zero**, all 48 bbox files are empty (`\n`).
  - Partial empty frame counts in other sequences: `seq2` (3 empty / 63), `seq4` (2 / 48), `seq5` (51 / 250), `seq6` (29 / 91), `seq8` (19 / 73), `seq9` (9 / 51), `seq10` (18 / 25), `seq11` (92 / 228), `seq13` (51 / 250), `seq14` (49 / 249), `seq16` (7 / 40), `seq17` (19 / 63), `seq18` (7 / 63), `seq19` (1 / 56), `seq20` (21 / 52), `seq21` (31 / 56), `seq22` (2 / 46), `seq23` (20 / 56).
  - Sequences with 100% positive frames: `seq3` (15/15), `seq12` (250/250), `seq15` (116/116).
- **Mask Modes:** 20 sequences have 3-channel RGB masks; 3 sequences have 1-channel Grayscale (L) masks.
- **Resolutions in Positive Sequences:**
  - (1440, 1064): 749 frames
  - (1920, 1080): 450 frames
  - (1280, 720): 432 frames
  - (1280, 1024): 250 frames
  - (720, 576): 228 frames
  - (1704, 1072): 116 frames

#### B. Negative Sequences (`sequenceData/negativeOnly/seq1_neg` to `seq23_neg`):
- **Total Negative Sequences:** 23 directories (`seq1_neg` to `seq23_neg`).
- **Total Negative Images:** 4,275 images (100% `.jpg`).
- **Directory Layout:** Flat images stored directly inside each `seq{k}_neg/` folder (no subdirectories).
- **Masks / Bboxes:** None provided (0 masks, 0 bboxes).
- **Modes & Depths:** 100% 8-bit RGB (3 channels).
- **Resolutions:**
  - (1920, 1080): 3,845 frames
  - (720, 576): 430 frames

---

### 1.4 Consolidated Folder: `imagesAll_positive/`
- Contains exactly **3,762 `.jpg` image files**.
- Matches:
  - Exactly 1,537 files match single frames from C1 through C6 (100%).
  - Exactly 2,225 files match positive sequence frames from seq1 through seq23 (100%).
  - Exactly 0 unknown/extra files (1537 + 2225 = 3762).
- Contains only images; no masks are included in this directory.

---

### 1.5 Image & Mask Format Specifications

1. **Extensions:**
   - Images: 100% `.jpg` (JPEG). No `.png`, `.bmp`, or `.tif` files.
   - Masks: 100% `.jpg` (JPEG). Note: There are 184 `.txt` files in `masks_seq2`, `masks_seq7`, `masks_seq8` which are bounding box files mistakenly placed there.
2. **Color Channels & Bit Depth:**
   - Images: 100% 8-bit unsigned integer (uint8) RGB (3 color channels).
   - Masks: 8-bit unsigned integer (uint8). Modes vary:
     - Grayscale (`L`, 1 channel): In C3, C4, C5, C6 (100%), and parts of C1 (15 files), C2 (90 files), and 3 video sequences.
     - 3-Channel RGB (`RGB`, 3 channels): In parts of C1 (241 files), C2 (211 files), and 20 video sequences. (All three channels R, G, B contain identical mask values).
3. **Lossy Compression Artifacts in Masks:**
   - Because masks were saved as lossy JPEG (`.jpg`) rather than lossless PNG, pixel values along polyp boundaries are not strictly binary `0` and `255`.
   - Observed unique pixel values: `[0, 1, 2, 3, 4, 5, ..., 246, 247, 248, 249, 250, 251, 255]`.
   - In `EndoCV2021_001010_mask.jpg` (C2), isolated speckles (6 pixels > 128) exist in an image marked with 0 annotations in CSV and an empty bbox file.
   - Robust binarization rule: `mask = (np.array(Image.open(mask_path).convert('L')) > 127).astype(np.uint8)`.
4. **Dimension Consistency:**
   - Scanned all 1,537 single-frame pairs and all 2,225 sequence pairs:
   - **0 dimension mismatches**. 100% of images and their corresponding masks have identical width and height.

---

## 2. Logic Chain

1. **Stem Matching Rule Formulation:**
   - Direct inspection of all centers and sequences showed that every image `<stem>.jpg` pairs with `<stem>_mask.jpg`, with a single edge case in C3 (`C3_EndoCV2021_00489_.jpg` -> `C3_EndoCV2021_00489_mask.jpg`).
   - Therefore, a robust dataloader matching function should strip the trailing underscore if `<stem>_mask.jpg` does not exist.

2. **Identification of Negative Samples:**
   - We observed that `sequenceData/negativeOnly` provides 4,275 pure negative frames with zero masks and zero polyps.
   - In addition, both single-frame centers and positive sequences contain in-line negative images where the ground-truth mask is all-zero (`np.all(mask == 0)`) and the bbox `.txt` file contains only `\n` or empty string.
   - Specifically: 125 single frames across C1..C6 are negative; 515 frames across positive sequences (including 100% of seq1 and seq7) are negative.
   - Therefore, negative frames can be utilized either by synthesizing an all-zero mask for `negativeOnly/`, or by utilizing the pre-existing empty masks in single frames and sequences.

3. **Mask Reading & Processing Pipeline:**
   - Masks are stored as `.jpg`, with inconsistent modes (`RGB` vs `L`).
   - If loaded directly without conversion, RGB masks yield 3-channel arrays while L masks yield 2D arrays.
   - Furthermore, JPEG lossy compression produces ringing artifacts with low values (1–10) in the background and high values (240–254) in foreground.
   - Therefore, the mask loader must unconditionally convert to single-channel grayscale (`.convert('L')`) and threshold at `127` (`> 127`).
   - When scanning mask directories, the loader must filter for `.endswith('.jpg')` to avoid reading the 184 rogue `.txt` files in `masks_seq2`, `masks_seq7`, and `masks_seq8`.

4. **Directory Structure Normalization:**
   - Center C6 uses `bbox_images_C6` (plural) whereas C1–C5 use `bbox_image_C{i}` (singular).
   - Center C1 contains an orphan bbox visualization (`957OLCV1_100H0002_mask_bbox.jpg`).
   - Center C3 is missing 64 bbox text files for positive frames.
   - However, for semantic segmentation, `images_C{i}` and `masks_C{i}` have clean 1-to-1 correspondences for all 1,537 images.

---

## 3. Caveats

1. **No C6 Metadata CSV:**
   `dataDetails_PolypGen_SingleFrames` only contains CSVs for C1 through C5. Metadata for C6 (88 images) must be computed directly from image/mask files.
2. **Missing Bbox Files in C3:**
   For object detection tasks relying on `bbox_C3`, 64 positive images do not have bounding box text files. If bounding boxes are needed, they must be dynamically derived from the binary masks (e.g. using `codes/extract_PolypBoxes.py`).
3. **Lossy JPEG Compression on Masks:**
   Because the dataset creators saved ground truth masks as JPEG rather than PNG, exact sub-pixel boundaries have compression artifacts. Thresholding at `127` is recommended.
4. **`imagesAll_positive` vs Raw Split Folders:**
   `imagesAll_positive` contains all 3,762 single-frame and sequence positive images combined, but does NOT contain masks. For training segmentation models, data must be loaded from `data_C{1..6}/` and `sequenceData/positive/seq{1..23}/`.

---

## 4. Conclusion & Actionable Specifications

### A. Dataset Summary

| Subset | Total Images | Positive Images | Negative Images | Mask Availability | Bbox Availability |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Single Frames (C1–C6)** | 1,537 | 1,412 | 125 | 1,537 `.jpg` masks | 1,473 `.txt` (64 missing in C3) |
| **Positive Sequences (seq1–seq23)** | 2,225 | 1,710 | 515 | 2,225 `.jpg` masks *(+184 rogue .txt)* | 2,225 `.txt` |
| **Negative Sequences (seq1–seq23 neg)** | 4,275 | 0 | 4,275 | None (all-zero implicit) | None |
| **Entire PolypGen Extracted** | **8,037** | **3,122** | **4,915** | **3,762** | **3,698** |

*(Note: `imagesAll_positive` contains 3,762 images, which is exactly the sum of 1,537 single frames + 2,225 sequence frames).*

### B. Standardized Dataloader Implementation Guidelines

```python
import os
import numpy as np
from PIL import Image

def get_mask_path(image_path):
    """
    Resolves mask path for any PolypGen image in data_C{i} or sequenceData/positive/seq{k}.
    Handles:
      1. data_C{i}/images_C{i}/<stem>.jpg -> data_C{i}/masks_C{i}/<stem>_mask.jpg
      2. C3 trailing underscore: C3_EndoCV2021_00489_.jpg -> C3_EndoCV2021_00489_mask.jpg
      3. sequenceData/positive/seq{k}/images_seq{k}/<stem>.jpg -> masks_seq{k}/<stem>_mask.jpg
    """
    dir_name, filename = os.path.split(image_path)
    stem, ext = os.path.splitext(filename)
    parent_dir, img_folder = os.path.split(dir_name)
    
    mask_folder = img_folder.replace("images_", "masks_")
    mask_dir = os.path.join(parent_dir, mask_folder)
    
    # Primary candidate
    mask_path = os.path.join(mask_dir, f"{stem}_mask.jpg")
    if os.path.exists(mask_path):
        return mask_path
        
    # Handle C3 trailing underscore edge case
    if stem.endswith("_"):
        alt_path = os.path.join(mask_dir, f"{stem[:-1]}_mask.jpg")
        if os.path.exists(alt_path):
            return alt_path
            
    return None

def load_polypgen_pair(image_path):
    """Loads RGB image and standardizes binary mask to uint8 array (0 or 1)."""
    # 1. Load image (ensure 3-channel RGB)
    with Image.open(image_path) as im:
        image = np.array(im.convert("RGB"))
        
    # 2. Load mask
    mask_path = get_mask_path(image_path)
    if mask_path is not None and os.path.exists(mask_path):
        with Image.open(mask_path) as mim:
            # Convert to Grayscale to handle RGB mask files, threshold at 127 to remove JPEG noise
            mask = (np.array(mim.convert("L")) > 127).astype(np.uint8)
    else:
        # Negative sequence or pure negative sample: synthesize all-zero mask
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        
    return image, mask
```

---

## 5. Verification Method

To independently verify these findings, run the following verification commands from `m:\chakramodel`:

1. **Verify Single-Frame Counts & Discrepancies:**
   ```powershell
   python -c "
   import os
   root = r'J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3'
   for c in [f'C{i}' for i in range(1, 7)]:
       p_img = os.path.join(root, f'data_{c}', f'images_{c}')
       p_mask = os.path.join(root, f'data_{c}', f'masks_{c}')
       print(c, 'Images:', len(os.listdir(p_img)), 'Masks:', len(os.listdir(p_mask)))
   "
   ```

2. **Verify the C3 Trailing Underscore Edge Case:**
   ```powershell
   python -c "
   import os
   root = r'J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\data_C3'
   print('Image exists:', os.path.exists(os.path.join(root, 'images_C3', 'C3_EndoCV2021_00489_.jpg')))
   print('Direct mask exists:', os.path.exists(os.path.join(root, 'masks_C3', 'C3_EndoCV2021_00489__mask.jpg')))
   print('Stem-trimmed mask exists:', os.path.exists(os.path.join(root, 'masks_C3', 'C3_EndoCV2021_00489_mask.jpg')))
   "
   ```

3. **Verify Rogue `.txt` Files in Positive Sequences:**
   ```powershell
   python -c "
   import os
   root = r'J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\sequenceData\positive'
   for s in ['seq2', 'seq7', 'seq8']:
       p = os.path.join(root, s, f'masks_{s}')
       txts = [f for f in os.listdir(p) if f.endswith('.txt')]
       print(s, 'has', len(txts), '.txt files in masks folder')
   "
   ```

4. **Verify Negative Sequence Total:**
   ```powershell
   python -c "
   import os
   root = r'J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\sequenceData\negativeOnly'
   total = sum(len(os.listdir(os.path.join(root, d))) for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
   print('Total negativeOnly frames:', total)
   "
   ```

### Invalidation Conditions
- If any file in `data_C1` through `data_C6` or `sequenceData/positive` is modified, deleted, or converted to PNG.
- If additional centers or sequences are added to the dataset root.
