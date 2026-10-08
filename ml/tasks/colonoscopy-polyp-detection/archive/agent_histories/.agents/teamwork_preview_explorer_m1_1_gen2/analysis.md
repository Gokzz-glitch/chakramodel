# Analysis Report: Comprehensive Identification and Cataloging of Kaggle Dataset URLs & Slugs

**Agent**: `teamwork_preview_explorer` (Explorer 1 — Milestone 1)  
**Assigned Working Directory**: `m:\chakramodel\.agents\teamwork_preview_explorer_m1_1_gen2`  
**Parent Orchestrator**: `36543f26-eb69-43b9-b71e-5908641fe1ef`  
**Timestamp**: 2026-09-07T17:05:00Z  

---

## Executive Summary

An exhaustive, forensic scan of the entire ChakraModel project workspace was executed. Every Python script (`build_crossval_v4.py`, `build_crossval_v5.py`, `build_master_eval_notebook.py`, `run_kaggle_diagnostic.py`, `run_kaggle_diagnostic_generalized.py`, etc.), Jupyter notebook (`*.ipynb`), conversation log (`OM_rama_krish_all_data.json`, `OM_rama_krish_convo.md`, `september1to4afternnon_chat.json`), documentation file, and guide was analyzed using automated AST/regex extraction and manual verification.

### Key Discoveries:
1. **11 Primary Polyp Benchmark & Evaluation Datasets**: Exactly 11 Kaggle dataset URLs/slugs represent image, video, and annotation datasets for polyp detection and segmentation.
2. **Target Dataset Status**:
   - **SUN-SEG**: ❌ **MISSING** from all Kaggle dataset uploads. (Documented in `build_master_eval_notebook.py` line 13 as "Pending / Missing: SUN-SEG not uploaded yet, 12.5 GB").
   - **CVC-VideoClinicDB**: ❌ **MISSING** from all Kaggle dataset uploads. (Conflated in docs with static CVC-ClinicDB; documented in `REPORT.txt` line 502 and research reports as non-downloadable without direct GIANA authorization).
   - **LDPolypVideo**: ❌ **MISSING as video dataset**. Only partially and fragmentarily present as static labeled frames in `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset` (`LDPolyp_images labeled-part 1`). Full 160-video dataset (7.5 GB) is noted as pending/missing in `build_master_eval_notebook.py` line 14.
   - **PolypGen**: ❌ **MISSING** from all Kaggle uploads.
3. **Unexpected Datasets Present**: Instead of the 4 target video benchmarks, the Kaggle uploads contain:
   - **Kvasir-SEG** (`debeshjha1/kvasirseg`, `ivannikov2002/...`, and inside `gokulrocky/chakramodel-evaluation-datasets`)
   - **CVC-ClinicDB** (`balraj98/cvcclinicdb`, `ahaan2/...`, and inside `gokulrocky/chakramodel-evaluation-datasets`)
   - **ETIS-Larib** (`tamimm91437/...`, `nguyenvoquocduong/...`, and a 5-image subset inside `gokulrocky/chakramodel-evaluation-datasets`)
   - **EndoScene CVC-300** (`gokulrocky/endoscene-cvc300-polyp-raw-dataset`)
   - **HyperKvasir Segmented** (`gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset`)
   - **PolypDB Multi-Modal Stress Test** (`gokulrocky/polypdb-polyp-raw-stress-testdataset`)
   - **Ad-hoc Video Collection** (`gokulrocky/polypdataset-gokul`)
4. **Complete Kaggle Asset Footprint**: A total of **22 unique Kaggle slugs** were identified across the workspace, which includes the 11 primary polyp evaluation datasets, 6 model weight checkpoint datasets, and 5 code/runtime packages.

---

## 1. Catalog of the 11 Primary Kaggle Dataset URLs & Slugs

The following table summarizes the 11 primary Kaggle dataset URLs/slugs corresponding to polyp benchmark and evaluation datasets:

| # | Exact Kaggle Slug | Full Kaggle URL | Owner / Uploader | Real-World Counterpart Dataset | Modality & Scale | Primary Workspace References |
|---|-------------------|-----------------|------------------|--------------------------------|-------------------|-----------------------------|
| 1 | `debeshjha1/kvasirseg` | `https://www.kaggle.com/datasets/debeshjha1/kvasirseg` | Debesh Jha (`debeshjha1`) | Kvasir-SEG (Simula Research Laboratory) | 1,000 static images + PNG masks + JSON bbox | `REPORT.txt`:228, `CLADUE nit.md`:227, `ChakraModel_Research_Report CLAUDE 2.md`:73 |
| 2 | `balraj98/cvcclinicdb` | `https://www.kaggle.com/datasets/balraj98/cvcclinicdb` | Balraj Ashwath (`balraj98`) | CVC-ClinicDB (CVC Barcelona) | 612 static images (BMP) + masks (29 sequences) | `REPORT.txt`:229,502, `ChakraModel_Research_Report CLAUDE 2.md`:22,74 |
| 3 | `ahaan2/cvc-clinicdb` | `https://www.kaggle.com/datasets/ahaan2/cvc-clinicdb` | `ahaan2` | CVC-ClinicDB (Public Kaggle mirror) | 612 static images + masks | `generate_kaggle_eval.py`:14,354, `OM_rama_krish_all_data.json`:2072,2326 |
| 4 | `ivannikov2002/kvasir-seg-data-polyp-segmentation-detection` | `https://www.kaggle.com/datasets/ivannikov2002/kvasir-seg-data-polyp-segmentation-detection` | `ivannikov2002` | Kvasir-SEG (Public Kaggle mirror) | 1,000 static images + masks | `generate_kaggle_eval.py`:13,332, `OM_rama_krish_all_data.json`:2072,2326 |
| 5 | `tamimm91437/etis-laribpolypdb` | `https://www.kaggle.com/datasets/tamimm91437/etis-laribpolypdb` | `tamimm91437` | ETIS-Larib Polyp DB | 196 static HD images + masks | `generate_kaggle_eval.py`:15,367, `OM_rama_krish_all_data.json`:2072,2326 |
| 6 | `nguyenvoquocduong/etis-laribpolypdb` | `https://www.kaggle.com/datasets/nguyenvoquocduong/etis-laribpolypdb` | `nguyenvoquocduong` | ETIS-Larib Polyp DB (Public mirror) | 196 static HD images + masks | `run_kaggle_diagnostic_generalized.py`:9 |
| 7 | `gokulrocky/endoscene-cvc300-polyp-raw-dataset` | `https://www.kaggle.com/datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset` | Gokul (`gokulrocky`) | EndoScene CVC-300 | 60 images + 60 binary masks | `build_crossval_v4.py`:31,412, `build_crossval_v5.py`:17,22, `run_kaggle_diagnostic.py`:37 |
| 8 | `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset` | `https://www.kaggle.com/datasets/gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset` | Gokul (`gokulrocky`) | HyperKvasir Segmented + LDPolyp static images | 1,000 segmented images + static LDPolyp frames | `build_crossval_v4.py`:32,444, `build_master_eval_notebook.py`:11,49,338 |
| 9 | `gokulrocky/polypdb-polyp-raw-stress-testdataset` | `https://www.kaggle.com/datasets/gokulrocky/polypdb-polyp-raw-stress-testdataset` | Gokul (`gokulrocky`) | PolypDB Multi-Modal Stress Test | 3,934 images across 5 modalities (WLI, NBI, LCI, BLI, FICE) | `build_crossval_v4.py`:33,491, `build_crossval_v5.py`:344, `build_master_eval_notebook.py`:9,50 |
| 10 | `gokulrocky/polypdataset-gokul` | `https://www.kaggle.com/datasets/gokulrocky/polypdataset-gokul` | Gokul (`gokulrocky`) | Custom / Ad-hoc Testing Videos | Colonoscopy video files (.mp4, .avi) | `OM_rama_krish_all_data.json`:936, `september1to4afternnon_chat.json`:1110 |
| 11 | `gokulrocky/chakramodel-evaluation-datasets` | `https://www.kaggle.com/datasets/gokulrocky/chakramodel-evaluation-datasets` | Gokul (`gokulrocky`) | Unified Evaluation Bundle (Kvasir + CVC + ETIS) | 1,000 Kvasir images, 495 CVC images, 5 ETIS images | `build_crossval_v5.py`:14-22, `Final_Evaluation_MultiCell.ipynb`:39-42, `OM_rama_krish_all_data.json`:3182 |

---

## 2. Forensic Profile & Source References for Each Dataset

### 1. `debeshjha1/kvasirseg`
- **URL**: `https://www.kaggle.com/datasets/debeshjha1/kvasirseg`
- **Owner**: `debeshjha1` (Debesh Jha, lead researcher and author of the Kvasir-SEG paper).
- **Workspace References**:
  - `REPORT.txt` (Line 228):
    ```markdown
    | **Kvasir-SEG** | 46.2 MB | 1,000 | Direct: https://datasets.simula.no/kvasir-seg/ OR Kaggle: https://www.kaggle.com/datasets/debeshjha1/kvasirseg | < 5 min | JPG + PNG masks + JSON bbox | Seg mask + bounding box | CC-BY-4.0 |
    ```
  - `REPORT.txt` (Line 553):
    ```markdown
    | **Kvasir-SEG** | 1,000 static images + segmentation masks | Freely downloadable in minutes via Kaggle (`debeshjha1/kvasirseg`) or HuggingFace | **Use — primary training set** |
    ```
  - `docs\reports\CLADUE nit.md` (Line 227): Identical citation table entry as in `REPORT.txt`.
  - `ChakraModel_Research_Report CLAUDE 2.md` (Line 73): Recommends `debeshjha1/kvasirseg` as the primary training set.
  - `model_output_extracted\.virtual_documents\__notebook_source__.ipynb` (Line 126):
    ```python
    dataset_dir = Path("/kaggle/input/datasets/debeshjha1/kvasirseg/Kvasir-SEG/Kvasir-SEG")
    ```
- **Apparent Purpose**: Standard open-access medical benchmark consisting of 1,000 gastrointestinal polyp images annotated with ground-truth segmentation masks. Used as the core training dataset (70% train split) and validation/test baseline (15% calib, 15% test).
- **Target Dataset Analysis**: Does not contain SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, or PolypGen.

---

### 2. `balraj98/cvcclinicdb`
- **URL**: `https://www.kaggle.com/datasets/balraj98/cvcclinicdb`
- **Owner**: `balraj98` (Balraj Ashwath, Kaggle community contributor).
- **Workspace References**:
  - `REPORT.txt` (Line 229):
    ```markdown
    | **CVC-ClinicDB** | ~50 MB | 612 | Kaggle: https://www.kaggle.com/datasets/balraj98/cvcclinicdb | < 5 min | BMP images + masks | Seg mask (convert to bbox with scikit-image) | Research only |
    ```
  - `REPORT.txt` (Line 502):
    ```markdown
    2. **CVC-ClinicVideoDB (the actual name — "CVC-VideoClinicDB" is a common misspelling) is not casually downloadable.** It's a GIANA/MICCAI challenge dataset. To get it you must **contact the GIANA challenge organizers directly** — there is no self-serve Kaggle or GitHub mirror with the actual video files and ground truth. (The Kaggle link commonly cited for this — `balraj98/cvcclinicdb` — is the *static-image* CVC-ClinicDB, a different 612-image dataset from a different challenge track. Multiple papers and even the AVPDN repo itself conflate these two.)
    ```
  - `ChakraModel_Research_Report CLAUDE 2.md` (Lines 22, 74): Warning that `balraj98/cvcclinicdb` is strictly static images, not video sequences.
  - `docs\reports\CLADUE nit.md` (Line 228).
- **Apparent Purpose**: Official static benchmark containing 612 frames extracted from 29 colonoscopy sequences with binary masks. Used for cross-domain static segmentation benchmark testing.
- **Target Dataset Analysis**: **Critical negative finding**: Directly referenced in the context of CVC-VideoClinicDB, but definitively proven to **NOT** contain CVC-VideoClinicDB. It contains only 612 static frames, whereas CVC-VideoClinicDB requires 18 video sequences with ~11,954 frames.

---

### 3. `ahaan2/cvc-clinicdb`
- **URL**: `https://www.kaggle.com/datasets/ahaan2/cvc-clinicdb`
- **Kaggle Mount Path**: `/kaggle/input/notebooks/ahaan2/cvc-clinicdb`
- **Owner**: `ahaan2` (Kaggle public contributor).
- **Workspace References**:
  - `generate_kaggle_eval.py` (Line 14, 354):
    ```python
    # Cell 0 mount list:
    "- `/kaggle/input/notebooks/ahaan2/cvc-clinicdb`\n"
    # Discovery search candidates:
    "/kaggle/input/notebooks/ahaan2/cvc-clinicdb",
    ```
  - `notebooks\Kaggle_ChakraTransformer_Evaluation_Standalone.ipynb` (Lines 15, 350): Required dataset mount in standalone evaluation notebook.
  - `OM_rama_krish_all_data.json` (Line 2072):
    ```json
    "<USER_REQUEST>\n/kaggle/input/datasets/gokulrocky/kaggle-upload-zip4, NEXT /kaggle/input/notebooks/ahaan2/cvc-clinicdb, NEXT /kaggle/input/notebooks/ivannikov2002/kvasir-seg-data-polyp-segmentation-detection NEXT /kaggle/input/notebooks/tamimm91437/etis-laribpolypdb\n\nNOW UPDATE THE NOTE BOOK \n</USER_REQUEST>"
    ```
  - `OM_rama_krish_all_data.json` (Lines 2326, 2481, 2495, 2521, 2535, 2669, 2703, 2767).
  - `september1to4afternnon_chat.json` (Lines 7586, 7847, 7954).
- **Apparent Purpose**: Public Kaggle mount of CVC-ClinicDB used for zero-shot cross-dataset evaluation of the ChakraTransformer (ViT-Large 384) model.
- **Target Dataset Analysis**: Contains 612 static frames. Does not contain CVC-VideoClinicDB or any video sequences.

---

### 4. `ivannikov2002/kvasir-seg-data-polyp-segmentation-detection`
- **URL**: `https://www.kaggle.com/datasets/ivannikov2002/kvasir-seg-data-polyp-segmentation-detection`
- **Kaggle Mount Path**: `/kaggle/input/notebooks/ivannikov2002/kvasir-seg-data-polyp-segmentation-detection`
- **Owner**: `ivannikov2002` (Kaggle public contributor).
- **Workspace References**:
  - `generate_kaggle_eval.py` (Lines 13, 332):
    ```python
    "- `/kaggle/input/notebooks/ivannikov2002/kvasir-seg-data-polyp-segmentation-detection`\n"
    ```
  - `notebooks\Kaggle_ChakraTransformer_Evaluation_Standalone.ipynb` (Lines 14, 328).
  - `OM_rama_krish_all_data.json` (Lines 2072, 2326, 2481, 2495, 2521, 2535, 2669, 2703, 2767).
  - `september1to4afternnon_chat.json` (Lines 7586, 7847, 7954).
- **Apparent Purpose**: Public Kaggle mirror of Kvasir-SEG used to provide test images and masks when running standalone evaluation notebooks without local file uploads.
- **Target Dataset Analysis**: 1,000 static Kvasir images. Does not contain SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, or PolypGen.

---

### 5. `tamimm91437/etis-laribpolypdb`
- **URL**: `https://www.kaggle.com/datasets/tamimm91437/etis-laribpolypdb`
- **Kaggle Mount Path**: `/kaggle/input/notebooks/tamimm91437/etis-laribpolypdb`
- **Owner**: `tamimm91437` (Tamim, Kaggle public contributor).
- **Workspace References**:
  - `generate_kaggle_eval.py` (Lines 15, 367):
    ```python
    "- `/kaggle/input/notebooks/tamimm91437/etis-laribpolypdb`\n"
    ```
  - `notebooks\Kaggle_ChakraTransformer_Evaluation_Standalone.ipynb` (Lines 16, 363).
  - `OM_rama_krish_all_data.json` (Lines 2072, 2326, 2481, 2495, 2521, 2535, 2669, 2703, 2767).
  - `september1to4afternnon_chat.json` (Lines 7586, 7847, 7954).
- **Apparent Purpose**: Public Kaggle mount of the ETIS-Larib polyp database used for zero-shot testing of small, flat, and camouflaged polyps.
- **Target Dataset Analysis**: Contains 196 static images. Does not contain any of the 4 target video/multi-center benchmarks.

---

### 6. `nguyenvoquocduong/etis-laribpolypdb`
- **URL**: `https://www.kaggle.com/datasets/nguyenvoquocduong/etis-laribpolypdb`
- **Owner**: `nguyenvoquocduong` (Nguyen Vo Quoc Duong, Kaggle public contributor).
- **Workspace References**:
  - `run_kaggle_diagnostic_generalized.py` (Lines 8–10):
    ```python
    base_url = sys.argv[1]
    dataset_slug = sys.argv[2] # e.g. "nguyenvoquocduong/etis-laribpolypdb"
    ```
  - `run_kaggle_diagnostic_generalized.py` (Lines 38–41):
    ```python
    dataset_slug = "{dataset_slug}"
    print(f"Downloading dataset: {dataset_slug}")
    dataset_path = kagglehub.dataset_download(dataset_slug)
    ```
- **Apparent Purpose**: Referenced as an archetype public dataset slug in the generalized Kaggle evaluation runner script (`run_kaggle_diagnostic_generalized.py`) to download and evaluate arbitrary datasets on a Kaggle remote session using `kagglehub`.
- **Target Dataset Analysis**: Public ETIS-Larib mirror. Does not contain SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, or PolypGen.

---

### 7. `gokulrocky/endoscene-cvc300-polyp-raw-dataset`
- **URL**: `https://www.kaggle.com/datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset`
- **Kaggle Mount Path**: `/kaggle/input/datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset` or `/kaggle/input/endoscene-cvc300-polyp-raw-dataset`
- **Owner**: `gokulrocky` (Gokul, ChakraModel lead developer).
- **Workspace References**:
  - `run_kaggle_diagnostic.py` (Line 37):
    ```python
    dataset_path = kagglehub.dataset_download("gokulrocky/endoscene-cvc300-polyp-raw-dataset")
    print("Dataset downloaded to:", dataset_path)
    ```
  - `build_crossval_v4.py` (Lines 31, 412–420, 437):
    ```python
    # | 3 | `gokulrocky/endoscene-cvc300-polyp-raw-dataset` | CVC-300 (60 images) |
    cvc300_candidates = [
        "/kaggle/input/endoscene-cvc300-polyp-raw-dataset/CVC-300",
        "/kaggle/input/endoscene-cvc300-polyp-raw-dataset",
    ]
    ```
  - `build_crossval_v5.py` (Lines 17, 22, 55):
    ```python
    # /kaggle/input/datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset/CVC-300/images [60 images]
    # /kaggle/input/datasets/gokulrocky/endoscene-cvc300-polyp-raw-dataset/CVC-300/masks  [60 masks]
    ```
  - `build_master_eval_notebook.py` (Lines 8, 19, 48):
    ```markdown
    | EndoScene CVC-300 | `gokulrocky/endoscene-cvc300-polyp-raw-dataset` | 🔴 Required |
    ```
  - `crossvali1_dump.txt` (Lines 14, 918, 922, 943).
  - `crossvali2_dump.txt` (Lines 14, 271, 275, 296).
  - `notebooks\Kaggle_CrossVal_v4_FIXED.ipynb` (Lines 19, 106, 479).
  - `notebooks\Kaggle_CrossVal_v5_PATHS_FIXED.ipynb` (Lines 20, 25, 59, 126, 335).
  - `notebooks\Kaggle_Master_CrossDataset_Eval_v3.ipynb` (Lines 20, 48, 298, 302).
- **Apparent Purpose**: Standardized unseen-domain test set consisting of 60 colonoscopy images and 60 corresponding binary masks (`CVC-300/images`, `CVC-300/masks`) containing flat and peduncular polyps.
- **Target Dataset Analysis**: Unexpected dataset. Does not contain SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, or PolypGen.

---

### 8. `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset`
- **URL**: `https://www.kaggle.com/datasets/gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset`
- **Kaggle Mount Path**: `/kaggle/input/hyperkvasir-dataset-first-half-and-and-ld-dataset` or `/kaggle/input/datasets/gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset`
- **Alias**: `/kaggle/input/hyperkvasir-dataset-first-half-ld-dataset`
- **Owner**: `gokulrocky` (Gokul).
- **Workspace References**:
  - `build_crossval_v4.py` (Lines 32, 102, 444):
    ```markdown
    | 4 | `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset` | HyperKvasir + LDPolyp |
    ```
  - `build_master_eval_notebook.py` (Lines 11, 49, 338, 343, 446–450):
    ```python
    # - HyperKvasir Segmented (1000 images subset, gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset)
    # Search paths inside:
    "/kaggle/input/hyperkvasir-dataset-first-half-and-and-ld-dataset/LDPolyp_images labeled-part 1",
    "/kaggle/input/hyperkvasir-dataset-first-half-and-and-ld-dataset/LDPolyp_images labelled",
    ```
  - `crossvali1_dump.txt` (Lines 15, 950, 955, 1064, 1065, 1068).
  - `crossvali2_dump.txt` (Lines 15, 303, 308, 408, 409, 412).
  - `notebooks\Kaggle_CrossVal_v4_FIXED.ipynb` (Lines 20, 107, 512).
  - `notebooks\Kaggle_Master_CrossDataset_Eval_v3.ipynb` (Lines 21, 353, 365, 498).
  - `build_new_eval_notebooks.py` (Line 238): `create_eval_notebook("Kaggle_HyperKvasir_Eval.ipynb", "HyperKvasir", "/kaggle/input/hyperkvasir-dataset-first-half-ld-dataset")`
  - `kaggle_hardened_pipeline_multi.py` (Line 35), `notebooks\Kaggle_HyperKvasir_Eval.ipynb` (Lines 12, 196).
- **Apparent Purpose**: Dual dataset upload containing:
  1. The 1,000 segmented polyp subset from HyperKvasir (`hyper-kvasir-segmented-images`).
  2. Static labeled images from LDPolyp (`LDPolyp_images labeled-part 1` / `LDPolyp_images labelled`).
- **Target Dataset Analysis**: **Critical finding regarding LDPolypVideo**: This Kaggle package contains *only static frame partitions* of LDPolyp, **not** the 160 video files of LDPolypVideo. As confirmed in `build_master_eval_notebook.py` line 14: `"⏳ Pending / Missing: LDPolyp Video (in progress, 7.5 GB)"`.

---

### 9. `gokulrocky/polypdb-polyp-raw-stress-testdataset`
- **URL**: `https://www.kaggle.com/datasets/gokulrocky/polypdb-polyp-raw-stress-testdataset`
- **Kaggle Mount Path**: `/kaggle/input/polypdb-polyp-raw-stress-testdataset` or `/kaggle/input/datasets/gokulrocky/polypdb-polyp-raw-stress-testdataset`
- **Owner**: `gokulrocky` (Gokul).
- **Workspace References**:
  - `build_crossval_v4.py` (Lines 33, 103, 491):
    ```markdown
    | 5 | `gokulrocky/polypdb-polyp-raw-stress-testdataset` | PolypDB 5 modalities |
    ```
  - `build_crossval_v5.py` (Line 344):
    ```python
    direct = Path("/kaggle/input/datasets/gokulrocky/polypdb-polyp-raw-stress-testdataset")
    ```
  - `build_master_eval_notebook.py` (Lines 9, 21, 50, 384, 388, 411):
    ```python
    # 4. PolypDB (all 5 modalities) (gokulrocky/polypdb-polyp-raw-stress-testdataset)
    pdb_root = "/kaggle/input/polypdb-polyp-raw-stress-testdataset"
    # Subdirectories evaluated: WLI, NBI, LCI, BLI, FICE
    ```
  - `build_new_eval_notebooks.py` (Line 239): `create_eval_notebook("Kaggle_PolypDB_Stress_Test.ipynb", "PolypDB Stress Test", "/kaggle/input/polypdb-polyp-raw-stress-testdataset")`
  - `kaggle_hardened_pipeline_multi.py` (Line 36), `kaggle_hardened_pipeline_multi.ipynb` (Line 45).
  - `notebooks\Kaggle_CrossVal_v4_FIXED.ipynb` (Lines 21, 108, 571).
  - `notebooks\Kaggle_CrossVal_v5_PATHS_FIXED.ipynb` (Line 396).
  - `notebooks\Kaggle_Master_CrossDataset_Eval_v3.ipynb` (Lines 22, 410, 421, 444).
  - `notebooks\Kaggle_PolypDB_Stress_Test.ipynb` (Lines 12, 196).
  - `crossvali1_dump.txt` (Lines 16, 999, 1003, 1026).
  - `crossvali2_dump.txt` (Lines 16, 349, 353, 376).
- **Apparent Purpose**: 3,934 multi-center colonoscopy images across 5 distinct optical imaging modalities (White Light Imaging, Narrow Band Imaging, Linked Color Imaging, Blue Light Imaging, and FICE). Used to stress-test the model against chromatic shifts and non-standard clinical lighting.
- **Target Dataset Analysis**: Unexpected dataset. Does not contain SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, or PolypGen.

---

### 10. `gokulrocky/polypdataset-gokul`
- **URL**: `https://www.kaggle.com/datasets/gokulrocky/polypdataset-gokul`
- **Kaggle Mount Path**: `/kaggle/input/polypdataset-gokul` or `/kaggle/input/datasets/gokulrocky/polypdataset-gokul`
- **Owner**: `gokulrocky` (Gokul).
- **Workspace References**:
  - `OM_rama_krish_all_data.json` (Line 936):
    ```json
    "<USER_REQUEST>\nhttps://www.kaggle.com/datasets/gokulrocky/polypdataset-gokul this is the file location in kaggle where videos for testing are there videos are in both mp4 &avi format update the notebook to be ready to run\n</USER_REQUEST>"
    ```
  - `OM_rama_krish_all_data.json` (Lines 950, 963, 977, 1068, 1076):
    ```python
    video_dir = Path('/kaggle/input/polypdataset-gokul')
    video_files = list(video_dir.glob('*.mp4')) + list(video_dir.glob('*.avi'))
    ```
  - `september1to4afternnon_chat.json` (Lines 1110, 1561, 2053):
    ```python
    possible_paths = [
        Path("/kaggle/input/datasets/gokulrocky/polypdataset-gokul"),
        Path("/kaggle/input/polypdataset-gokul"),
        Path("/kaggle/input")
    ]
    ```
- **Apparent Purpose**: Ad-hoc testing dataset uploaded by Gokul containing colonoscopy video clips in `.mp4` and `.avi` formats, sourced from local storage (`video for testing` folder). Used to test frame-by-frame inference, temporal persistence smoothing, and annotated video generation in Kaggle.
- **Target Dataset Analysis**: **Critical finding**: This is an informal, unstandardized video collection. It is **NOT** the SUN-SEG benchmark (110 clips, 158k frames), nor CVC-VideoClinicDB (18 sequences, 11k frames), nor LDPolypVideo (160 videos, 40k frames).

---

### 11. `gokulrocky/chakramodel-evaluation-datasets`
- **URL**: `https://www.kaggle.com/datasets/gokulrocky/chakramodel-evaluation-datasets`
- **Kaggle Mount Path**: `/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets` or `/kaggle/input/chakramodel-evaluation-datasets`
- **Owner**: `gokulrocky` (Gokul).
- **Workspace References**:
  - `build_crossval_v4.py` (Lines 30, 362, 384, 385, 389).
  - `build_crossval_v5.py` (Lines 12–24, 52–54):
    ```python
    # EXACT PATHS CONFIRMED:
    # Images:
    #   /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/images  [495 images]
    #   /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/etis-larib/images    [5 images]
    #   /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/images    [1000 images]
    # Masks:
    #   /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/masks   [495 masks]
    #   /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/etis-larib/masks     [5 masks]
    #   /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/masks     [1000 masks]
    ```
  - `build_master_eval_notebook.py` (Lines 18, 46, 269):
    ```markdown
    | ChakraModel Eval Datasets (Kvasir-SEG test) | `gokulrocky/chakramodel-evaluation-datasets` | 🔴 Required |
    ```
  - `Final_Evaluation_MultiCell.ipynb` (Lines 39–42).
  - `generate_final_multicell.py` (Lines 17–20).
  - `kaggle_hardened_pipeline.py` (Lines 24–26).
  - `kaggle_hardened_pipeline.ipynb` (Lines 33–35).
  - `OM_rama_krish_all_data.json` (Lines 3182, 3286, 5478, 5597, 56921).
  - `september1to4afternnon_chat.json` (Lines 7695, 7847).
  - `crossvali1_dump.txt` (Lines 12, 142, 143, 868).
  - `crossvali2_dump.txt` (Lines 12, 221, 222, 226).
  - `notebooks\Kaggle_ChakraTransformer_Evaluation.ipynb` (Lines 13, 30).
  - `notebooks\Kaggle_CrossVal_v4_FIXED.ipynb` (Lines 18, 105, 420).
  - `notebooks\Kaggle_CrossVal_v5_PATHS_FIXED.ipynb` (Lines 17–24, 56–58).
  - `notebooks\Kaggle_Master_CrossDataset_Eval_v3.ipynb` (Lines 19, 46, 245).
- **Apparent Purpose**: The unified, primary multi-dataset archive compiled from `ChakraModel_Evaluation_Datasets.zip` on the developer's desktop and uploaded to Kaggle. It bundles three static datasets together to simplify Kaggle kernel inputs.
- **Target Dataset Analysis**:
  - Contains **Kvasir-SEG** (1,000 images, 1,000 masks)
  - Contains **CVC-ClinicDB** (495 images, 495 masks)
  - Contains **ETIS-Larib** (5 images, 5 masks — severely truncated subset)
  - **Does NOT contain** SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, or PolypGen.

---

## 3. Analysis of Target Datasets vs. Kaggle Uploads

A core objective of Milestone 1 is to evaluate whether the 4 target evaluation datasets are represented among these 11 Kaggle links:

| Target Evaluation Dataset | Official Baseline Benchmark | Status in Kaggle Links | Evidence in Codebase | Real Cause / Note |
|---------------------------|-----------------------------|------------------------|----------------------|-------------------|
| **SUN-SEG** | 158,690 frames across 110 video clips (annotated with polygons and masks) | ❌ **ABSENT** | `build_master_eval_notebook.py`:13: `"⏳ Pending / Missing: SUN-SEG (not uploaded yet, 12.5 GB)"` | Upload was never completed due to large size (12.5 GB). Never mounted in any executable evaluation script. |
| **CVC-VideoClinicDB** | 18 full-length colonoscopy sequences (~11,954 annotated frames) | ❌ **ABSENT** | `REPORT.txt`:502; `ChakraModel_Research_Report CLAUDE 2.md`:22 | Confused in documentation with static CVC-ClinicDB (`balraj98/cvcclinicdb`). Video archive requires GIANA organizer credentialing and was never acquired or uploaded to Kaggle. |
| **LDPolypVideo** | 160 colonoscopy video sequences (~40,266 annotated frames) | ❌ **ABSENT as Video** (Static subset only) | `build_master_eval_notebook.py`:14: `"⏳ Pending / Missing: LDPolyp Video (in progress, 7.5 GB)"` | Full video dataset (7.5 GB) pending. Only static image frames were uploaded inside `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset/LDPolyp_images`. |
| **PolypGen** | 8,037 frames from multiple European clinical centers across 6 modalities | ❌ **ABSENT** | No Kaggle dataset slug exists anywhere in workspace. | Not uploaded to Kaggle. |

### Explanation of Unexpected Datasets Found
Instead of the 4 target video benchmarks, the developer uploaded and evaluated the following alternative datasets:
1. **EndoScene CVC-300** (`gokulrocky/endoscene-cvc300-polyp-raw-dataset`): 60 images/masks used as an out-of-distribution static test.
2. **PolypDB** (`gokulrocky/polypdb-polyp-raw-stress-testdataset`): 3,934 images across 5 optical modalities (WLI, NBI, LCI, BLI, FICE) used as a multi-modal lighting stress test.
3. **HyperKvasir Segmented** (`gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset`): 1,000 segmented images used as an expanded Kvasir-style benchmark.
4. **Ad-hoc Video Collection** (`gokulrocky/polypdataset-gokul`): Informal `.mp4` and `.avi` video clips used for pipeline latency and visual tracking verification.

---

## 4. Comprehensive Inventory of All 22 Kaggle Slugs Discovered

For total forensic transparency, the remaining 11 Kaggle slugs discovered in the workspace are cataloged below:

### Category B: Model Weights Checkpoint Datasets (6 Slugs)
1. **`gokulraj324/chakramodel-weights`** (`https://www.kaggle.com/datasets/gokulraj324/chakramodel-weights`):
   - Referenced in 13 files (`AutoDiscover_Evaluation.ipynb`:97, `Final_Evaluation_MultiCell.ipynb`:61, `generate_autodiscover_notebook.py`:71, `generate_final_multicell.py`:33, `run_kaggle_diagnostic.py`:43, etc.).
   - Contains `best.pt` (YOLOv8 weights) and `chakra_transformer_best.pth` (ViT-Large 384 weights).
2. **`gokulraj324/chakramodel-weightsupdated4`** (`https://www.kaggle.com/datasets/gokulraj324/chakramodel-weightsupdated4`):
   - Referenced in `notebooks\Kaggle_Final_Proof_Eval.ipynb`:53 and `notebooks\gen.py`:56.
   - 4th updated revision of the model weights.
3. **`gokulrocky/chakramodel-weights`** (`https://www.kaggle.com/datasets/gokulrocky/chakramodel-weights`):
   - Referenced in 11 files (`AutoDiscover_Evaluation.ipynb`:96, `Final_Evaluation_MultiCell.ipynb`:60, `generate_autodiscover_notebook.py`:70, etc.).
   - Same model weights under Gokul's primary Kaggle account.
4. **`gokulrocky/chakratransformer-weights`** (`https://www.kaggle.com/datasets/gokulrocky/chakratransformer-weights`):
   - Referenced in 9 files (`build_crossval_v4.py`:29,199, `build_master_eval_notebook.py`:47, `crossvali1_dump.txt`:13, etc.).
   - Dedicated standalone dataset for `chakra_transformer_best.pth` (309.17M params).
5. **`gokulrocky/kaggle-upload-zip4`** (`https://www.kaggle.com/datasets/gokulrocky/kaggle-upload-zip4`):
   - Referenced in 6 files (`OM_rama_krish_all_data.json`:2072,2727, `generate_kaggle_eval.py`:12,341, `notebook_diff.txt`:34, etc.).
   - Initial private zip upload containing model weights and Kvasir data.
6. **`gokulrocky/chakramodel-yolo-combo-dataset`** (`https://www.kaggle.com/datasets/gokulrocky/chakramodel-yolo-combo-dataset`):
   - Referenced in `kaggle_yolo_retrain.py`:25.
   - YOLOv8 training dataset formatted with `images/train`, `images/val`, and `dataset.yaml`.

### Category C: Code, Deployment & Workspace Packages (5 Slugs)
1. **`gokulrocky/chakramodel`** (`https://www.kaggle.com/datasets/gokulrocky/chakramodel`):
   - Referenced in `september1to4afternnon_chat.json`:790,823,836,952.
   - Upload of full project repository / bundle for execution in Kaggle kernels.
2. **`gokulrocky/chakramodel-kaggle-code`** (`https://www.kaggle.com/datasets/gokulrocky/chakramodel-kaggle-code`):
   - Referenced in `OM_rama_krish_all_data.json`:9466 and `notebooks\Kaggle_ChakraTransformer_Evaluation.ipynb`:30.
   - Python code bundle (`src/` tree and `requirements.txt`).
3. **`gokulrocky/chakramodel-kaggle-codethen`** (`https://www.kaggle.com/datasets/gokulrocky/chakramodel-kaggle-codethen`):
   - Referenced in `OM_rama_krish_all_data.json`:5478.
   - Chat transcript typo/variant representing the code package.
4. **`gokulrocky/om-finalkaggle-upload`** (`https://www.kaggle.com/datasets/gokulrocky/om-finalkaggle-upload`):
   - Referenced in `notebooks\Kaggle_ChakraTransformer_Evaluation.ipynb`:29.
   - Final code and notebook deployment package.
5. **`gokulrocky/updated-kaggle`** (`https://www.kaggle.com/datasets/gokulrocky/updated-kaggle`):
   - Referenced in `OM_rama_krish_all_data.json`:1076,1090,1130,1146 and `fix_notebook.py`:15,30.
   - 1.1 GB deployment package containing code, weights, and video inference scripts.

---

## 5. Summary & Actionable Recommendations for Milestone 2 & 3

1. **Definitive Baseline Comparison**: When comparing against SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, and PolypGen, Milestone 2 can decisively conclude that none of the 4 target video benchmarks were evaluated in complete video form on Kaggle.
2. **Dataset Substitution Audit**: The documentation and evaluation pipeline substituted:
   - SUN-SEG → Not evaluated (pending upload).
   - CVC-VideoClinicDB → CVC-ClinicDB static images (495/612 images) + EndoScene CVC-300 (60 images).
   - LDPolypVideo → Static labeled subset inside HyperKvasir (`LDPolyp_images`) + ad-hoc unstandardized video clips (`polypdataset-gokul`).
   - PolypGen → PolypDB (3,934 multi-modal images).
3. **Verification**: All paths, line numbers, and URLs documented herein are directly verifiable by opening the respective files or executing the automated scan script.
