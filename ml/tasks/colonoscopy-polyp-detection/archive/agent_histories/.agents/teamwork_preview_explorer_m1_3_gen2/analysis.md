# Target Dataset Mapping & Unexpected Datasets Analysis

**Milestone 1 — Target Dataset Mapping & Unexpected Datasets Analysis Report**  
**Investigator**: `teamwork_preview_explorer` (Explorer 3, Gen 2)  
**Assigned Working Directory**: `m:\chakramodel\.agents\teamwork_preview_explorer_m1_3_gen2`  
**Parent Orchestrator**: `36543f26-eb69-43b9-b71e-5908641fe1ef`  
**Date**: September 7, 2026  

---

## 1. Executive Summary

This investigation examines how the datasets uploaded to Kaggle and referenced throughout the **ChakraModel** repository map to the four official target evaluation baselines:
1. **SUN-SEG** (158,690 frames, 110 clips — Ji et al., MICCAI 2022 / MedIA 2023)
2. **CVC-VideoClinicDB** / CVC-ClinicVideoDB (18 video sequences, ~11,954 frames — GIANA / MICCAI 2017)
3. **LDPolypVideo** (160 videos, ~40,266 frames — Ma et al., MICCAI 2021)
4. **PolypGen** (8,037 multi-center images/videos — Ali et al., Scientific Data 2023)

### Core Findings
- **Zero of the 4 target video/multi-center datasets are present in complete form** in the Kaggle datasets.
  - **SUN-SEG**: **Completely Missing** (0 frames, 0 clips). Gated access requiring author email; explicit scope-cut documented in `REPORT.txt` and `CLADUE nit.md`.
  - **CVC-ClinicVideoDB**: **Completely Missing** (0 video sequences). The repository and Kaggle pipelines conflated this gated video challenge dataset with the 2D static-image `CVC-ClinicDB` (495 images). The local archive `CVC_ClinicVideoDB_Kaggle.zip` (13.6 GB) is corrupt/truncated (`zipfile.BadZipFile`, lacking central directory).
  - **LDPolypVideo**: **Completely Missing as Video; Fragmentary Static Frames Only**. The 160 continuous video sequences were never evaluated. A sub-directory of extracted static frames (`LDPolyp_images labeled-part 1`) was included in the slug `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset`, but failed to mount during cross-validation runs. The 42 raw videos in `gokulrocky/polypdataset-gokul` have **zero ground-truth annotations**. Claims of evaluating temporal stability on LDPolypVideo in `ChakraModel_Final_Paper.md` were confirmed fabricated by internal audit (`HISTORY.JSON:L79921`).
  - **PolypGen**: **Completely Missing** (0 images, 0 masks). Required academic Synapse registration; never downloaded or uploaded to Kaggle.
- **Unexpected Datasets Present Instead**:
  The evaluation pipeline substituted a disparate collection of static 2D image benchmarks, partial subsets, and weight/code artifacts:
  - **HyperKvasir Segmented** (1,000 images/masks subset; full 110K dataset omitted due to 30+ GB size)
  - **EndoScene CVC-300** (60 images/masks test set)
  - **Kvasir-SEG** (1,000 images/masks; in-distribution training set, 150 test frames evaluated)
  - **CVC-ClinicDB** (495 images/masks; static 2D image dataset, not the video database)
  - **ETIS-Larib** (Severely truncated to **5 images** in Kaggle upload vs. 196 full; resulted in 0.0000 DSC catastrophic failure)
  - **PolypDB Stress Test** (3,934 image-mask pairs / 7,868 files across WLI, NBI, LCI, BLI, FICE; substituted for PolypGen)
  - **Model Weights & Code Deployment Archives** (`chakratransformer-weights`, `chakramodel-weights`, `kaggle-upload-zip4`, `chakramodel-kaggle-code`, `polypdataset-gokul`)

---

## 2. Target Baseline Mapping & Completeness Audit

| Target Dataset Baseline | Expected Specifications | Actual Presence in Kaggle Datasets | Completeness Status | Missing Elements & Deficiencies | Root Cause & Project Context |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **1. SUN-SEG** | 158,690 frames, 110 clips, VOS masks, boundary maps, optical flow (Ji et al., 2022/2023) | **None** (0 files, 0 MB) | **Completely Missing (0%)** | 100% of video sequences, frames, and ground-truth masks are absent. | **Access Friction & Scope Cut**: `REPORT.txt:L159-160` notes website is inaccessible and requires email approval. Explicitly excluded from plan (`REPORT.txt:L240,L445`). |
| **2. CVC-VideoClinicDB** (CVC-ClinicVideoDB) | 18 SD colonoscopy video sequences, 11,954 annotated frames (GIANA / MICCAI 2017) | **None** (0 video sequences) | **Completely Missing (0%)** | 18 full video sequences and continuous annotations absent. Substituted by static `cvc-clinicdb` (495 frames). | **Challenge Gating & Misleading Conflation**: Requires contacting GIANA organizers directly (`REPORT.txt:L502`). Local 13.6 GB zip is corrupt. Static 495-image subset substituted instead. |
| **3. LDPolypVideo** | 160 colonoscopy videos, 40,266 frames with continuous temporal bounding boxes (Ma et al., 2021) | **Fragmentary Static Frames Only** (`LDPolyp_images labeled-part 1`) | **Missing as Video (<2% static)** | Zero continuous video sequences evaluated. Unannotated demo clips (`polypdataset-gokul`) lack ground truth. | **Bandwidth / Mount Failure**: Full 7.5 GB video set marked "in progress" (`build_master_eval_notebook.py:L14`). Paper claims of video evaluation were confirmed fabricated (`HISTORY.JSON:L79921`). |
| **4. PolypGen** | 8,037 images/videos across 6 international centers (3,762 pos + 4,275 neg) (Ali et al., 2023) | **None** (0 files, 0 MB) | **Completely Missing (0%)** | Zero images, masks, or multi-center metadata present. | **Access Gating & Substitution**: Required Synapse registration; marked optional stretch goal (`REPORT.txt:L557`). Replaced by `polypdb-polyp-raw-stress-testdataset`. |

---

## 3. Deep Dive into the 4 Target Baselines

### 3.1 Target 1: SUN-SEG (Ji et al., MICCAI 2022 / MedIA 2023)
- **Official Specification**: The largest benchmark for video polyp segmentation (VPS), containing 158,690 frames extracted from 110 colonoscopy video clips (split into SUN-SEG-Easy with 33 clips/49,136 frames, and SUN-SEG-Hard with 67 clips/90,899 frames, plus positive/negative controls). Provides dense pixel-level masks, bounding boxes, polyp boundary labels, and attribute annotations.
- **Kaggle Presence**: **0%**. No Kaggle dataset slug created by the team (`gokulrocky/...`, `gokulraj324/...`) or attached public mirror contains SUN-SEG.
- **Evidence in Code & Documentation**:
  - `REPORT.txt` (Section 2.5, lines 159–160):
    > *"The largest video dataset for polyp segmentation (SUN-SEG, 158,690 frames) is technically open-access but requires emailing the original database maintainer for backup access. The primary website (`amed8k.sundatabase.org`) is 'no longer maintained and sometimes inaccessible' (per the VPS GitHub README). For a 36-hour hackathon, any dataset that requires email approval is a non-starter."*
  - `REPORT.txt` (line 240, line 445):
    > *"3. Do NOT wait for LDPolypVideo or SUN-SEG — their access path takes too long."*  
    > *"| LDPolypVideo / SUN-SEG not accessible in time | Very High | Low | Already excluded from plan; stick to image datasets |"*
  - `docs/reports/CLADUE nit.md` (lines 158–160, 233, 444): Verbatim replicates the access barrier and exclusion verdict.
  - `build_master_eval_notebook.py` (lines 12–13):
    > *"⏳ Pending / Missing:\n  - SUN-SEG (not uploaded yet, 12.5 GB)"*
  - `Kaggle_ZeroTrust_Verification.ipynb` (line 10) & `build_kaggle_zerotrust_nb.py` (line 33): Contains marketing narrative claiming *"we can rapidly process massive datasets like HyperKvasir and SUN-SEG"*, but the notebook itself contains zero code loading or referencing SUN-SEG.

### 3.2 Target 2: CVC-VideoClinicDB / CVC-ClinicVideoDB (Bernal et al., GIANA/MICCAI 2017)
- **Official Specification**: 18 video sequences recorded in standard definition (SD) with optical colonoscopy, totaling ~11,954 frames with ground-truth polyp bounding boxes and segmentation masks.
- **Kaggle Presence**: **0%**. Zero sequences from CVC-ClinicVideoDB exist in any Kaggle dataset.
- **The Critical Conflation / Substitution**:
  - Throughout early pitch decks, letters of endorsement (`mon_jul_27_2026_previous_research_papers_on_polyp_detection.json:L48`), and the project README, the authors claimed:
    > *"The solution is validated on real colonoscopy video sequences from CVC-ClinicVideoDB, processed frame-by-frame, delivering a stable and clinically trustworthy detection overlay..."*
  - In reality, the authors mistakenly used the **static image** dataset `CVC-ClinicDB` (612 frames total, 495 in the Kaggle zip).
  - This error was caught during independent technical review in `REPORT.txt` (lines 502, 555) and `ChakraModel_Research_Report CLAUDE 2.md` (lines 22, 75):
    > *"CVC-ClinicVideoDB (the actual name — 'CVC-VideoClinicDB' is a common misspelling) is not casually downloadable. It's a GIANA/MICCAI challenge dataset. To get it you must contact the GIANA challenge organizers directly — there is no self-serve Kaggle or GitHub mirror with the actual video files and ground truth. (The Kaggle link commonly cited for this — `balraj98/cvcclinicdb` — is the static-image CVC-ClinicDB, a different 612-image dataset from a different challenge track. Multiple papers and even the AVPDN repo itself conflate these two.) Budgeting '~30 minutes via Kaggle' for this dataset is wrong and will burn hours of your hackathon chasing a registration email that may not get answered in time."*
- **Local Workspace File Reality**:
  - `m:\chakramodel\CVC_ClinicVideoDB_Kaggle.zip` (13,648,757,889 bytes / 12.71 GB): Inspection via Python `zipfile` reveals it is **severely corrupt/truncated** (`zipfile.BadZipFile: File is not a zip file`). Binary analysis reveals the zip central directory record (`PK\x05\x06`) is completely missing.
  - `m:\chakramodel\CVC_SampleVideo.zip` (34,783,585 bytes / 34.8 MB): Contains only a single video file (`1_1.mp4`) with zero annotations.
  - In `fix_notebook_indent.py` (line 18), the video evaluation fallback is hardcoded to:
    `' "ClinicVideoDB": "cvc-sample-video" # Looks for the zip we uploaded'`

### 3.3 Target 3: LDPolypVideo (Ma et al., MICCAI 2021)
- **Official Specification**: 160 colonoscopy video sequences totaling 40,266 frames (33,024 positive polyp frames + 7,242 negative control frames) captured across 160 patients, annotated with frame-by-frame bounding boxes. Specifically designed to test temporal continuity and detector degradation under camera motion and procedural artifacts.
- **Kaggle Presence**: **Partially Present as Extracted Static Slices (<2%); 0% Evaluated as Video**.
  - In `build_master_eval_notebook.py` (lines 14, 444–450), the author noted:
    > *"⏳ Pending / Missing:\n  - LDPolyp Video (in progress, 7.5 GB)"*  
    > And attempted to search for extracted frames inside the combined HyperKvasir slug:  
    > `ldpolyp_candidates = ["/kaggle/input/hyperkvasir-dataset-first-half-and-and-ld-dataset/LDPolyp_images labeled-part 1"]`
  - However, when executed on Kaggle (`crossvali1_dump.txt:L1083`), the system logged:
    `"ℹ️ LDPolyp labeled images not found — may not be attached yet."`
    Resulting in `ALL_RESULTS["LDPolyp Images"] = None` (Skipped).
  - In `gokulrocky/polypdataset-gokul`, raw video files named `1_1.avi` through `1_42.avi` were uploaded. While these files originate from LDPolypVideo recording sessions (Ma et al. numbering), they were uploaded as **raw unannotated video clips**. They contain **0 bounding boxes and 0 masks**, meaning no quantitative evaluation (mAP, IoU, recall, FPS tracking stability) was ever run against ground truth.
- **Forensic Confirmation of Fabrication**:
  - In `ChakraModel_Final_Paper.md` (§4.1), the paper claimed:
    > *"LDPolypVideo: Evaluated for artifact robustness and temporal stability in real-time video context."*
  - Internal audit report (`conversation_history/HISTORY.JSON:L79921`) officially exposed this claim:
    > *"A thorough audit of the codebase, scripts, and output logs reveals zero implementation or execution of any evaluation on LDPolypVideo. Furthermore, the project's own internal reports (`REPORT.txt`, `docs/reports/CLADUE nit.md`) explicitly state: 'LDPolypVideo / SUN-SEG not accessible in time | Very High | Low | Already excluded from plan; stick to image datasets'. The claim of evaluating real-time temporal stability on this dataset is entirely fabricated."*

### 3.4 Target 4: PolypGen (Ali et al., Scientific Data 2023)
- **Official Specification**: 8,037 frames from multi-center international trials (6 clinical centers across UK, France, Italy, Norway, Egypt), comprising 3,762 positive polyp frames with dense segmentation masks and bounding boxes, and 4,275 negative mucosal frames.
- **Kaggle Presence**: **0%**. No PolypGen data exists in any Kaggle dataset.
- **Evidence in Code & Documentation**:
  - `REPORT.txt` (line 232, line 557):
    > *"PolypGen: Multi-center dataset (6 clinical centers), useful for generalization testing. Available via academic portals/Synapse; access process not as instant as Kaggle. Optional stretch goal, not Day-1 critical path."*
  - `docs/reports/OPUS REPORT.md` (line 270):
    > *"PolypGen: 3,762+ images, ~2-3 GB, Synapse.org, Multi-center; great for robustness. Setup time: 1-2 hours."*
  - **Substitution**: Due to Synapse registration delays, PolypGen was abandoned. In its place, the team uploaded `gokulrocky/polypdb-polyp-raw-stress-testdataset` (a multi-modality dataset containing 3,934 image-mask pairs across WLI, NBI, LCI, BLI, and FICE) to test cross-domain generalization. Additionally, `PICCOLO` was attempted (`build_master_eval_notebook.py:L421-436`), but failed to attach.

---

## 4. Unexpected Datasets Present in Kaggle & Local Workspace

Because none of the four target evaluation baselines could be utilized, the project substituted an entirely different array of datasets. Below is the detailed forensic catalog of what actually exists in the Kaggle datasets and workspace.

### 4.1 Catalog of Unexpected Datasets

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   UNEXPECTED DATASETS INVENTORIED                                      │
├────────────────────────────────────────────────────┬────────────────────┬──────────────┬───────────────┤
│ Dataset / Archive Name                             │ Modality           │ Images/Clips │ Masks/Annots  │
├────────────────────────────────────────────────────┼────────────────────┼──────────────┼───────────────┤
│ 1. Kvasir-SEG (in chakramodel-eval-datasets)       │ Static 2D Images   │ 1,000 images │ 1,000 masks   │
│ 2. CVC-ClinicDB (in chakramodel-eval-datasets)     │ Static 2D Images   │ 495 images   │ 495 masks     │
│ 3. ETIS-Larib (in chakramodel-eval-datasets)       │ Static 2D Images   │ 5 images     │ 5 masks       │
│ 4. EndoScene CVC-300 (endoscene-cvc300-polyp-raw)  │ Static 2D Images   │ 60 images    │ 60 masks      │
│ 5. HyperKvasir Segmented (hyperkvasir-and-ld)      │ Static 2D Images   │ 1,000 images │ 1,000 masks   │
│ 6. PolypDB Multi-Modal (polypdb-polyp-raw-stress)  │ Multi-Spectral 2D  │ 3,934 images │ 3,934 masks   │
│ 7. PolypDataset Gokul (polypdataset-gokul)         │ Raw Video Clips    │ 42 videos    │ 0 annotations │
│ 8. Model Checkpoints & Runtimes (various slugs)    │ Weights / Code     │ 0 images     │ PyTorch .pth  │
└────────────────────────────────────────────────────┴────────────────────┴──────────────┴───────────────┘
```

### 4.2 Detailed Breakdown of Unexpected Datasets

#### 1. Kvasir-SEG (`gokulrocky/chakramodel-evaluation-datasets/kvasir-seg`)
- **Origin**: Jha et al. (Simula Research Laboratory, Norway, 2020).
- **Contents**: 1,000 RGB images (`.jpg`) and 1,000 binary ground-truth segmentation masks (`.png`).
- **File Structure**:
  - `images/`: 1,000 JPG files (`cju0qoxq3ur Sahara...jpg`)
  - `masks/`: 1,000 PNG files
- **Role in Pipeline**: Primary training set for both Stage 1 YOLOv8n detector and Stage 2 ViT-Large segmenter. In evaluation notebooks (`build_crossval_v5.py:L248-255`), a held-out 15% test split (150 images, seed=42) was evaluated as in-distribution validation, achieving **0.8131 ± 0.1747 Dice**.
- **External Kaggle Mirrors Cited**: `debeshjha1/kvasirseg`, `ivannikov2002/kvasir-seg-data-polyp-segmentation-detection`.

#### 2. CVC-ClinicDB (`gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb`)
- **Origin**: Bernal et al. (Hospital Clínic, Barcelona, 2015).
- **Contents**: 495 images (`.png`) and 495 binary masks (`.png`).
- **Discrepancy**: The official CVC-ClinicDB release contains **612 images** across 29 sequences. The version uploaded to Kaggle contains only **495 images** (a 117-image truncation from an incomplete scrape or pre-split subset).
- **Role in Pipeline**: Evaluated as a zero-shot cross-center benchmark in `build_crossval_v5.py` and `cross_dataset_report.md`, achieving **0.7561 ± 0.2131 Dice**.
- **External Kaggle Mirrors Cited**: `balraj98/cvcclinicdb`, `ahaan2/cvc-clinicdb`.

#### 3. ETIS-LaribPolypDB (`gokulrocky/chakramodel-evaluation-datasets/etis-larib`)
- **Origin**: Silva et al. (Lariboisière Hospital, Paris, MICCAI 2014).
- **Contents**: **5 images** (`.png`) and **5 binary masks** (`.png`).
- **Severe Truncation**: The full ETIS-Larib dataset contains **196 high-resolution images** (1225×966) representing small, flat, camouflaged polyps. The uploaded dataset contained only 5 images.
- **Role in Pipeline**: In `build_crossval_v5.py:L270-282`, the script explicitly notes:
  > *"⚠️ Only a subset of ETIS-Larib is available (5 images vs 196 full dataset)\nRecording historical score: Dice=0.0000 (documented catastrophic failure)"*
- **Benchmark Collapse**: When evaluated zero-shot across both the 5-image slice and the full 196-image cohort, ChakraModel suffered **total catastrophic generalization collapse** (**Dice: 0.0000 ± 0.0000**), failing to detect a single lesion (`cross_dataset_report.md:L14`).
- **External Kaggle Mirrors Cited**: `tamimm91437/etis-laribpolypdb`, `nguyenvoquocduong/etis-laribpolypdb`.

#### 4. EndoScene CVC-300 (`gokulrocky/endoscene-cvc300-polyp-raw-dataset`)
- **Origin**: Vázquez et al. (2017), derived from the CVC-ColonDB database.
- **Contents**: 60 images (`.png`) and 60 masks (`.png`) located in `CVC-300/images/` and `CVC-300/masks/`.
- **Role in Pipeline**: Evaluated as an unseen out-of-distribution benchmark testing flat and peduncular morphologies in `build_crossval_v5.py` and `cross_dataset_report.md`, achieving **0.7402 ± 0.1590 Dice**.

#### 5. HyperKvasir Segmented (`gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset`)
- **Origin**: Borgli et al. (Nature Scientific Data, 2020).
- **Contents**: 1,000 segmented polyp images and masks (`hyper-kvasir-segmented-images/`).
- **Scope Truncation**: The full HyperKvasir dataset spans 110,079 images and 374 video sequences (~30–58 GB). The team could not upload or process the full dataset due to Kaggle's 20 GB upload limit per dataset. Only the 1,000-image segmented slice was attached.
- **Role in Pipeline**: Evaluated in `cross_dataset_report.md:L12`, scoring **0.8360 ± 0.1610 Dice** (benefiting from identical sensor characteristics to Kvasir-SEG).

#### 6. PolypDB Multi-Modality Stress Test (`gokulrocky/polypdb-polyp-raw-stress-testdataset`)
- **Contents**: 3,934 image-mask pairs (7,868 total files) covering five optical imaging modalities:
  - White-Light Imaging (WLI)
  - Narrow-Band Imaging (NBI)
  - Linked Color Imaging (LCI)
  - Blue Laser Imaging (BLI)
  - Flexible Spectral Imaging Color Enhancement (FICE)
- **Role in Pipeline**: Served as the comprehensive zero-shot stress test across optical wavelengths, evaluated in `cross_dataset_report.md:L13` (**0.7283 ± 0.2544 Dice**).

#### 7. Qualitative Video Archive (`gokulrocky/polypdataset-gokul`)
- **Contents**: 42 raw video files (`1_1.avi` through `1_42.avi`, with transcoded `.mp4` counterparts).
- **Deficiency**: Completely unannotated. Contains zero ground-truth bounding box text files or mask images. Used strictly for feeding into `src/infer_stream.py` or Gradio `app.py` to record qualitative demo screen captures showing bounding-box persistence overlays.

#### 8. Model Weight and Code Checkpoint Slugs
- `gokulrocky/chakratransformer-weights` / `gokulraj324/chakramodel-weights` / `gokulrocky/kaggle-upload-zip4`:
  - Contains `chakra_transformer_best.pth` (309,173,737 parameter ViT-LargeFloat32 segmenter checkpoint, 1.18 GB).
  - Contains `best.pt` (3,011,043 parameter YOLOv8n detector checkpoint, 5.95 MB).
- `gokulrocky/chakramodel-kaggle-code` / `gokulrocky/updated-kaggle` / `gokulrocky/om-finalkaggle-upload`:
  - Packaged Python execution runtime containing `src/`, `requirements.txt`, and automated evaluation runners.

---

## 5. Cross-Reference with Project Documentation & Scripts

The following table cross-references each finding against primary project documents, establishing complete evidence traceability.

| Document / Script | Exact Path | Line Citations | Verbatim Text / Documented Fact | Significance to Investigation |
| :--- | :--- | :--- | :--- | :--- |
| **REPORT.txt** | `m:\chakramodel\REPORT.txt` | L159–160 | *"SUN-SEG Access Problem: The largest video dataset... requires emailing maintainer... website is no longer maintained... non-starter."* | Explains why SUN-SEG was never acquired or uploaded to Kaggle. |
| **REPORT.txt** | `m:\chakramodel\REPORT.txt` | L240, L445 | *"Do NOT wait for LDPolypVideo or SUN-SEG... Already excluded from plan; stick to image datasets."* | Direct confirmation of planned omission of video baselines. |
| **REPORT.txt** | `m:\chakramodel\REPORT.txt` | L502 | *"CVC-ClinicVideoDB... is not casually downloadable... requires contacting GIANA organizers directly... balraj98/cvcclinicdb is the static-image CVC-ClinicDB."* | Proves the 495-image Kaggle dataset is static CVC-ClinicDB, not CVC-ClinicVideoDB. |
| **CLADUE nit.md** | `m:\chakramodel\docs\reports\CLADUE nit.md` | L158–160 | *"The primary website (amed8k.sundatabase.org) is 'no longer maintained'... backup requires email."* | Corroborates SUN-SEG access impossibility during development. |
| **OPUS REPORT.md**| `m:\chakramodel\docs\reports\OPUS REPORT.md`| L270–272 | *"PolypGen: 3,762+ images, ~2-3 GB, Synapse.org, 1-2 hours... SUN-SEG: 158K frames, 15-25 GB, 4-6 hours."* | Documents knowledge of PolypGen and SUN-SEG as heavy stretch goals. |
| **build_crossval_v5.py** | `m:\chakramodel\build_crossval_v5.py` | L4–32 | *"CRITICAL FIX: Kaggle is mounting datasets under: /kaggle/input/datasets/gokulrocky/... Kvasir-SEG: 1000, ClinicDB: 495, ETIS-Larib: 5 (subset!), CVC-300: 60."* | Exact file counts of actual mounted datasets in live Kaggle run. |
| **build_crossval_v5.py** | `m:\chakramodel\build_crossval_v5.py` | L270–282 | *"⚠️ Only a subset of ETIS-Larib is available (5 images vs 196 full dataset)... catastrophic failure, Dice=0.0000."* | Documents 5-image truncation and catastrophic failure of ETIS-Larib. |
| **build_master_eval_notebook.py** | `m:\chakramodel\build_master_eval_notebook.py` | L12–15 | *"⏳ Pending / Missing: - SUN-SEG (not uploaded yet, 12.5 GB), - LDPolyp Video (in progress, 7.5 GB)."* | Author's explicit admission that SUN-SEG and LDPolypVideo were never uploaded. |
| **crossvali1_dump.txt** | `m:\chakramodel\crossvali1_dump.txt` | L1083 | *"ℹ️ LDPolyp labeled images not found — may not be attached yet."* | Runtime evidence that LDPolyp evaluation was skipped due to missing mount. |
| **crossvali2_dump.txt** | `m:\chakramodel\crossvali2_dump.txt` | L625–644 | *"Total files: 3184, Total size: 13.8 GB, Image files: 3120... cvc-clinicdb: 495, etis-larib: 5, kvasir-seg: 1000, CVC-300: 60."* | Physical Kaggle `/kaggle/input` scan proving only 4 unexpected datasets were mounted. |
| **cross_dataset_report.md** | `m:\chakramodel\cross_dataset_report.md` | L7–15 | *"Kvasir-SEG: 0.8131, ClinicDB: 0.7561, CVC-300: 0.7402, HyperKvasir: 0.8360, PolypDB: 0.7283, ETIS-Larib: 0.0000."* | Final recorded cross-dataset scores showing the substitution matrix in action. |
| **verified_benchmarks_and_metrics.md** | `m:\chakramodel\true_docs\verified_benchmarks_and_metrics.md` | L96–116 | *"Truncating to the last 10%... image_paths[-n_test:]... evaluated on 100, 49, 38, 6, 1 images."* | Exposes how earlier high generalization scores in Table 5.1 were 10% tail artifacts. |
| **HISTORY.JSON** | `m:\chakramodel\conversation_history\HISTORY.JSON` | L79921 | *"1. Fabricated Dataset Evaluation (LDPolypVideo)... codebase reveals zero implementation or execution of any evaluation on LDPolypVideo."* | Conclusive evidence that paper claims of LDPolypVideo evaluation were fabricated. |

---

## 6. Synthesis & Final Assessment

### 6.1 Systematic Substitution Pattern
The investigation reveals a consistent, systematic substitution pattern driven by access friction, file corruption, and execution deadlines:
1. **SUN-SEG (158K video frames)** $\longrightarrow$ **Completely dropped** due to website inaccessibility and email gate; substituted with **HyperKvasir Segmented (1,000 static images)**.
2. **CVC-ClinicVideoDB (18 videos)** $\longrightarrow$ **Conflated and replaced** with the static 2D image dataset **CVC-ClinicDB (495 images)**; local 13.6 GB archive corrupted.
3. **LDPolypVideo (160 videos)** $\longrightarrow$ **Replaced** with **42 raw unannotated video clips** (`polypdataset-gokul`) for qualitative demo visuals; quantitative video evaluation was omitted and fabricated in paper drafts.
4. **PolypGen (8,037 multi-center frames)** $\longrightarrow$ **Dropped** due to Synapse registration hurdles; substituted with **PolypDB Multi-Modality Stress Test (3,934 image-mask pairs)** and **EndoScene CVC-300 (60 images)**.

### 6.2 Data Integrity Summary Table

```
====================================================================================================
EVALUATION BASELINE       | TARGET STATUS         | PHYSICAL KAGGLE COUNTERPART      | INTEGRITY STATUS
====================================================================================================
1. SUN-SEG                | Completely Missing    | None (HyperKvasir 1k subset)     | 0% Evaluated
2. CVC-VideoClinicDB      | Completely Missing    | Static CVC-ClinicDB (495 imgs)   | Conflation / Corrupt Zip
3. LDPolypVideo           | Missing as Video      | Unannotated Clips (0 masks)      | Fabricated in Paper Draft
4. PolypGen               | Completely Missing    | PolypDB Multi-Modal (3,934 imgs) | Substituted
----------------------------------------------------------------------------------------------------
UNEXPECTED DATASETS       | PROVENANCE            | KAGGLE CONTENTS                  | ROLE IN PIPELINE
----------------------------------------------------------------------------------------------------
• Kvasir-SEG              | Simula Research       | 1,000 images, 1,000 masks        | Training + 15% Test Split
• CVC-ClinicDB            | Hosp. Clinic BCN      | 495 images, 495 masks            | Zero-Shot 2D Image Eval
• EndoScene CVC-300       | Vázquez et al. 2017   | 60 images, 60 masks              | Zero-Shot 2D Image Eval
• HyperKvasir Segmented   | Simula Research       | 1,000 images, 1,000 masks        | Zero-Shot In-Domain Eval
• ETIS-Larib (Truncated)  | Lariboisière Paris    | 5 images, 5 masks                | 0.0000 DSC Total Collapse
• PolypDB Multi-Modality  | Multi-Center Spectral | 3,934 images, 3,934 masks        | Cross-Spectral Stress Test
• Model Weights & Runtimes| PyTorch / Ultralytics | .pth (309M), .pt (3.01M)         | Model Checkpoints / Code
====================================================================================================
```
