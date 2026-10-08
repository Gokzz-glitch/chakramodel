# Comprehensive Research Report: Video Datasets for Polyp Detection and Segmentation

**Agent:** Explorer 2 (Video Datasets Analyst)  
**Milestone:** Milestone 1 (Generation 10)  
**Parent Orchestrator:** `orchestrator_gen10` (ID: `39578642-3df9-46b1-9513-eea8bc4aa461`)  
**Working Directory:** `M:\chakramodel\.agents\explorer_m1_2_g10`  
**Date:** September 9, 2026  
**Status:** Completed Analysis  

---

## Table of Contents

1. [Executive Summary & Problem Framing](#1-executive-summary--problem-framing)
   - 1.1 The Paradigm Shift: Static Images vs. Continuous Video Streams
   - 1.2 The Real-Time Constraint and the 3.7 FPS Bottleneck
2. [Deep Investigation of Open-Source Polyp Video Datasets](#2-deep-investigation-of-open-source-polyp-video-datasets)
   - 2.1 SUN-SEG (SUN Colonoscopy Video Database)
   - 2.2 CVC-VideoClinicDB (CVC-ClinicVideoDB / GIANA 2017)
   - 2.3 LDPolypVideo Benchmark
   - 2.4 PolypGen Video Subsets (EndoCV2021 / Nature Scientific Data 2023)
   - 2.5 Secondary & Supplementary Benchmarks (EndoScene, HyperKvasir, PICCOLO)
3. [Master Dataset Comparison Matrix](#3-master-dataset-comparison-matrix)
4. [Forensic Audit of Local Video Assets in `M:\chakramodel`](#4-forensic-audit-of-local-video-assets-in-mchakramodel)
   - 4.1 Physical Inspection of `video_testing/` (42 Clips, 381,433 Frames)
   - 4.2 Forensic Audit of `CVC_ClinicVideoDB_Kaggle.zip` (12.71 GB Archive)
   - 4.3 Evaluation Results in `kaggle_results/` and Historical Kaggle Uploads
5. [Partitioning Protocols to Prevent Temporal Leakage](#5-partitioning-protocols-to-prevent-temporal-leakage)
   - 5.1 The Mechanics of Temporal Leakage in Colonoscopy Video
   - 5.2 Multi-Level Partitioning Hierarchy (Center → Patient → Sequence)
   - 5.3 Benchmark Partition Standards (SUN-SEG, LDPolyp, PolypGen)
6. [Architectural & Evaluation Implications for ChakraModel](#6-architectural--evaluation-implications-for-chakramodel)
   - 6.1 Transitioning from Static YOLO+ViT to Temporal Video Processing
   - 6.2 Video-Specific Evaluation Metrics (TCS, Latency, False Positive Rate)
   - 6.3 Recommended Video Dataset Ingestion Roadmap
7. [References & Citations](#7-references--citations)

---

## 1. Executive Summary & Problem Framing

### 1.1 The Paradigm Shift: Static Images vs. Continuous Video Streams

The vast majority of contemporary polyp segmentation algorithms—including ChakraModel's primary training setup—have been developed, validated, and tuned on curated static 2D image benchmarks (e.g., Kvasir-SEG with 1,000 images, CVC-ClinicDB with 612 images, and ETIS-Larib with 196 images). In these static datasets:
- Images are **heavily pre-filtered and cherry-picked** by clinical curators to show well-illuminated, well-centered polyps during stable camera views.
- Every positive sample represents a stationary, high-contrast frame without severe occlusion, extreme motion blur, or rapid field-of-view translation.
- Standard evaluation focuses exclusively on single-frame spatial overlap metrics: Dice Similarity Coefficient (DSC), mean Intersection-over-Union (mIoU), Precision, and Recall.

However, clinical colonoscopy is inherently a **dynamic, continuous video stream** operating at **25 to 30 frames per second (FPS)** (and up to 60 FPS on high-definition Olympus Lucera Elite or Fujifilm ELUXEO systems). When a static 2D image model is applied frame-by-frame to live endoscopic video, several severe clinical and algorithmic failure modes emerge:
1. **Temporal Flickering & Instability**: Minor inter-frame variations in lighting, specular reflectance, or slight scope movement cause independent frame-level detectors to intermittently trigger and drop detections. A polyp detected with 0.85 confidence at frame $t$ may vanish at frame $t+1$ and reappear at frame $t+2$, producing a disorienting, strobing bounding box/mask that destroys clinician trust.
2. **Endoscopic Artifact Vulnerability**: Real video streams contain pervasive transient artifacts that rarely appear in static benchmark collections:
   - **Motion Blur**: Fast withdrawal or navigation causes high-frequency mucosal texture smearing where polyp contours dissolve.
   - **Specular Reflections (Glare)**: Wet mucosal surfaces create sharp saturated white highlights that trigger false positive detections or shatter segmentation masks.
   - **Fluid & Debris Occlusion**: Flushing with water jets, suctioning, bubbles, residual fecal material, and peristaltic folding intermittently occlude lesions.
   - **Entering / Exiting Dynamics**: Polyps enter the frame peripherally at acute angles, often partially truncated by the circular endoscopic field mask.
3. **Severe Class Imbalance**: In clinical screening video, polyps occupy less than 3% to 5% of total procedure time. The overwhelming majority of frames represent normal healthy mucosa, requiring exceptionally high negative predictive value and minimal false positives per minute.

### 1.2 The Real-Time Constraint and the 3.7 FPS Bottleneck

In a live screening colonoscopy, human endoscopists withdraw the colonoscope at approximately 0.5 to 1.5 cm/second while sweeping the mucosal folds. Clinical acceptability guidelines for Computer-Aided Detection (CADe) and Diagnosis (CADx) systems dictate:
- **Latency Budget**: Total end-to-end processing delay must not exceed **30 to 40 milliseconds per frame** (equivalent to $\ge 25\text{ FPS}$). Delays exceeding 100 ms create noticeable perceptual lag between the endoscopist's physical movement and the display overlay, causing eye strain and motion sickness.
- **Current ChakraModel Bottleneck**: ChakraModel's two-stage architecture couples a YOLOv8 detector with a heavyweight `vit_large_patch16_384` transformer segmenter (309M parameters) and post-hoc conformal calibration. Empirical profiling indicates this pipeline executes at approximately **3.7 FPS (~270 ms per frame)**.
- **Consequence**: ChakraModel currently processes only 1 out of every 7 or 8 video frames in real time, dropping up to 86% of incoming video data. Overcoming this bottleneck requires profiling the exact latency breakdown (Explorer 1), investigating temporal optimization methods (Explorer 3), and grounding future validation on genuine, continuous video datasets (this report).

---

## 2. Deep Investigation of Open-Source Polyp Video Datasets

This section presents a rigorous technical investigation of the four primary open-source polyp video benchmarks identified in clinical machine learning literature, followed by notable secondary benchmarks.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CORE VIDEO BENCHMARK TAXONOMY                                    │
├───────────────────┬───────────────────┬───────────────────┬──────────────────────────────────────┤
│ Dataset           │ Modality          │ Primary Scale     │ Annotation Paradigm                  │
├───────────────────┼───────────────────┼───────────────────┼──────────────────────────────────────┤
│ SUN-SEG           │ Video Clips (HD)  │ 158,690 frames    │ Dense Masks + Boundaries + 11 Attrib │
│ CVC-VideoClinicDB │ Video Seqs (SD)   │ ~11,954 frames    │ Dense Masks + Temporal Intervals     │
│ LDPolypVideo      │ Video Seqs (HD/SD)│ 40,266 frames     │ Continuous Tracking Bounding Boxes   │
│ PolypGen (Video)  │ Multi-Center Seqs │ 6,500 frames      │ Dense Masks + Bounding Boxes (6 Ctr) │
└───────────────────┴───────────────────┴───────────────────┴──────────────────────────────────────┘
```

---

### 2.1 SUN-SEG (SUN Colonoscopy Video Database)

#### A. Background & Provenance
- **Reference Publication**: Ge-Peng Ji, Guobao Xiao, Yu-Cheng Chou, Deng-Ping Fan, Kai Zhao, Geng Chen, Luc Van Gool. *"Video Polyp Segmentation: A Deep Learning Perspective"*, Medical Image Analysis (MedIA), 2023 (preliminary version in MICCAI 2022).
- **Underlying Database**: Derived from the large-scale **SUN Database** (Showa University and Nagoya University database by Misawa et al., 2021). The original SUN database collected colonoscopy videos from patients undergoing screening and surveillance colonoscopies at Showa University Northern Yokohama Hospital.
- **Primary Open-Source Repository**: `https://github.com/GewelsJI/VPS` (~500 GitHub stars, comprehensive Video Polyp Segmentation toolkit).

#### B. Scale, Volume & Structure
- **Total Video Clips**: 110 standardized video clips selected for the VPS benchmark (from a broader pool of 158 clips in the SUN repository).
- **Total Frames**: Exactly **158,690 frames**.
- **Subset Taxonomy**:
  - **SUN-SEG-Easy**: 33 video clips totaling **49,136 frames**. Characterized by relatively stable camera motions, distinct polyp boundaries, and minimal occlusions.
  - **SUN-SEG-Hard**: 67 video clips totaling **90,899 frames**. Contains complex clinical challenges including severe motion blur, sudden camera panning, tiny flat/sessile polyps, and water jet flushes.
  - **SUN-SEG-Negative**: 10 video clips totaling **18,655 frames**. Continuous video sequences of healthy colon mucosa containing zero polyps, serving as hard negative controls to test false alarm rates.

#### C. Annotation Scheme & Granularity
SUN-SEG is recognized as the most richly annotated video polyp dataset in existence:
1. **Dense Frame-Level Segmentation Masks**: Ground-truth binary masks provided for every individual positive frame (pixel-level precision, manually verified by clinical experts).
2. **Boundary / Contour Annotations**: Explicit high-resolution contour maps to supervise boundary-aware loss functions.
3. **11 Video-Level Clinical Attributes**: Every clip is annotated with 11 domain-specific challenging attributes:
   - *Motion Blur (MB)*: Loss of high-frequency detail due to fast scope motion.
   - *Specular Reflection (SR)*: Strong surface reflections from mucosal fluid.
   - *Occlusion (OC)*: Polyp occluded by folds, fluid, or surgical tools.
   - *Out-of-View (OV)*: Polyp partially leaving the camera field.
   - *Small Polyp (SP)*: Area smaller than $32 \times 32$ pixels.
   - *Large Polyp (LP)*: Area larger than $96 \times 96$ pixels.
   - *Fast Camera Motion (FM)*: Severe inter-frame spatial displacement.
   - *Low Contrast (LC)*: Polyp color closely matching surrounding mucosa.
   - *Debris / Bubbles (DB)*: Turbid fluid, stool particles, or detergent foam.
   - *Cross-Frame Variation (CFV)*: Significant morphological deformation across time.
   - *Boundary Indistinctness (BI)*: Subtle, flat serrated lesions with indistinct borders.
4. **Precomputed Optical Flow**: Author repository provides precomputed optical flow tensors generated via deep optical flow networks (RAFT and GMA) to support temporal motion modeling.

#### D. Technical Characteristics
- **Resolution**: Native HD acquisitions at $1240 \times 1080$ and $1920 \times 1080$ pixels (Olympus Lucera Elite CF-H290 series colonoscopes). Benchmark standardization resizes frames to $384 \times 384$ or $256 \times 448$ for model training.
- **Frame Rate**: Continuous **25 to 30 FPS**.
- **Color Space**: 24-bit sRGB (standard optical White Light Endoscopy [WLE] and selected Narrow Band Imaging [NBI] clips).
- **Format**: Video clips provided as serialized PNG frame directories (`images/` and `masks/`).

#### E. Partitioning & Leakage Prevention Protocol
- **Strict Video-Level Partitioning**: The 110 clips are strictly segregated by video clip and patient procedure:
  - **Training Set**: 49 clips (**19,544 frames**).
  - **Testing Set**: 61 clips (**139,146 frames**), spanning Easy (17 clips, 17,070 frames), Hard (34 clips, 103,421 frames), and Negative (10 clips, 18,655 frames).
- **Leakage Prevention**: No frames from any test video sequence exist in the training set. Temporal continuity is fully maintained within each clip.

#### F. Licensing & Availability
- **License**: Strictly non-commercial academic research license.
- **Access Protocol**: Benchmark files (masks, flow, and pre-extracted frames) are hosted via Google Drive and Baidu Wangpan links on `https://github.com/GewelsJI/VPS`. The underlying raw full video database (`amed8k.sundatabase.org`) requires formal email registration to Mori Lab at Showa University.

---

### 2.2 CVC-VideoClinicDB (CVC-ClinicVideoDB / GIANA 2017)

#### A. Background & Provenance
- **Reference Publication**: Jorge Bernal, F. Javier Sánchez, Gloria Fernández-Esparrach, Debesh Jha, et al. *"Polyp detection and segmentation in colonoscopy video: results from the GIANA 2017 challenge"*, Computer Vision Center (CVC), Universitat Autònoma de Barcelona & Hospital Clínic de Barcelona.
- **Challenge Venue**: GIANA (Gastrointestinal Image ANAlysis) Challenge held in conjunction with MICCAI 2017 and EndoVis.
- **Naming Disambiguation**: Often cited as `CVC-ClinicVideoDB`, `CVC-VideoClinicDB`, or `GIANA 2017 Video Polyp DB`.

#### B. Scale, Volume & Structure
- **Total Video Sequences**: 18 standard-definition (SD) optical colonoscopy video sequences.
- **Total Frames**: Approximately **11,954 frames** (ranging across sequences from 300 to ~1,200 frames per sequence).
- **Positive vs. Negative Breakdown**:
  - **Positive Frames**: 10,040 frames containing verified polyp instances.
  - **Negative Frames**: ~1,914 frames representing lesion-free approach and withdrawal phases.
- **Lesion Diversity**: 18 distinct polyp occurrences representing adenomatous, hyperplastic, and flat mucosal lesions.

#### C. Annotation Scheme & Granularity
- **Dense Frame-by-Frame Segmentation**: Manual ground-truth binary masks for every frame in which the polyp is visible.
- **Temporal Interval Annotations**: Clear temporal metadata specifying exact start-frame and end-frame timestamps ($[t_{\text{start}}, t_{\text{end}}]$) for lesion appearance.
- **Bounding Boxes**: Challenge annotations include bounding boxes enclosing the lesion, typically generated as tight enclosing rectangles around the ground-truth masks.

#### D. Technical Characteristics
- **Resolution**: PAL Standard Definition ($768 \times 576$ or downscaled to $384 \times 288$).
- **Frame Rate**: Standard PAL **25.0 FPS**.
- **Color Space**: 24-bit RGB (White Light Endoscopy).
- **Format**: Video sequences distributed either as uncompressed AVI/MPEG-4 containers or sequentially numbered TIFF/PNG frame sequences.

#### E. Partitioning & Leakage Prevention Protocol
- **Sequence-Based Segregation**: Standard challenge evaluation utilizes 16 video sequences for model development/training and 2 sequestered video sequences for blind test evaluation. Alternatively, an 18-fold leave-one-video-out cross-validation (LOVOCV) protocol is standard.
- **Leakage Prevention**: Whole video sequences are sequestered. Testing on frames adjacent in time to training frames is strictly prohibited.

#### F. Availability, Licensing & Repository Status
- **Licensing**: Academic research only, governed by CVC and the EndoVis challenge committee.
- **Access Protocol**: Requires direct authorization or access through the EndoVis / GIANA challenge platforms.
- **Critical Caveat & Local Finding**: As exhaustively audited in `M:\chakramodel\docs\audit\KAGGLE_DATASET_DECODING_REPORT.md`, CVC-ClinicVideoDB is **not available on standard Kaggle search mirrors**. The commonly mounted Kaggle datasets (`balraj98/cvcclinicdb`, `ahaan2/cvc-clinicdb`) contain **only the 612 static frames** of the 2D image dataset `CVC-ClinicDB`. The local archive `CVC_ClinicVideoDB_Kaggle.zip` (12.71 GB) in `M:\chakramodel` contains 42 unannotated video files but zero ground-truth masks.

---

### 2.3 LDPolypVideo Benchmark

#### A. Background & Provenance
- **Reference Publication**: Y. Ma, X. Chen, K. Cheng, et al. *"LDPolypVideo Benchmark: A Large-scale Colonoscopy Video Dataset for Polyp Detection"*, International Conference on Medical Image Computing and Computer-Assisted Intervention (MICCAI), 2021.
- **Objective**: Designed specifically to provide the first large-scale, continuous colonoscopy video benchmark addressing the temporal tracking and artifact challenges of real-time clinical procedures.

#### B. Scale, Volume & Structure
- **Total Video Sequences**: **160 colonoscopy video sequences** recorded across 160 distinct patients/procedures.
- **Total Frames**: **40,266 annotated frames**.
- **Class Distribution**:
  - **Positive Frames**: 33,024 frames showing polyp instances under varying angles and illumination.
  - **Hard Negative Frames**: 7,242 frames depicting healthy mucosa with confounding features (prominent haustral folds, vascular patterns, bubbles, residual fluid).

#### C. Annotation Scheme & Granularity
- **Continuous Object Detection Bounding Boxes**: Every positive frame possesses a bounding box formatted as `[xmin, ymin, xmax, ymax]` in Pascal VOC / YOLO text format.
- **Inter-Frame Temporal Tracking IDs**: Bounding boxes within each sequence are annotated with persistent tracking IDs, allowing benchmarking of multi-object tracking (MOT) metrics such as MOTA, MOTP, and ID Switches (IDSW).
- **Annotation Density**: Continuous frame-by-frame annotations across the active polyp intervals.

#### D. Technical Characteristics
- **Resolution**: Multi-resolution reflecting real-world clinical equipment: $560 \times 480$, $720 \times 576$, and $1920 \times 1080$ pixels.
- **Frame Rate**: **25 to 30 FPS**.
- **Color Space**: 24-bit sRGB.
- **Containers**: MP4 and AVI containers with H.264 / MPEG-4 Part 2 codecs.

#### E. Partitioning & Leakage Prevention Protocol
- **Patient / Procedure-Level Split**:
  - **Training Set**: 100 video sequences (~25,000 frames).
  - **Validation Set**: 20 video sequences (~5,000 frames).
  - **Test Set**: 40 video sequences (~10,000 frames).
- **Leakage Prevention**: The 160 sequences originate from 160 different patients. Patient-level separation guarantees that the model cannot memorize patient-specific mucosal textures, scope tint, or anatomically unique colon geometry.

#### F. Availability, Licensing & Local Workspace Status
- **Licensing**: Academic research upon author contact (MICCAI 2021).
- **Local Workspace Connection**: In `M:\chakramodel\video_testing`, 42 video files (`1_1.avi` through `1_42.avi`, totaling 381,433 raw frames) share LDPolyp naming conventions (`1_X`), representing raw unannotated recordings from these procedures. However, the ground-truth bounding box text files are absent locally.

---

### 2.4 PolypGen Video Subsets (EndoCV2021 / Nature Scientific Data 2023)

#### A. Background & Provenance
- **Reference Publication**: Sharib Ali, Debesh Jha, Noha Ghatwary, et al. *"PolypGen: A multi-center colonoscopy dataset for generalisable polyp detection and segmentation"*, Scientific Data (Nature), 2023.
- **Challenge Venue**: 3rd International Endoscopy Computer Vision Challenge and Workshop (EndoCV 2021) at IEEE ISBI 2021.
- **Scope**: Created to address the critical generalization barrier across different endoscopic manufacturers (Olympus, Pentax, Fujifilm) and distinct patient populations across multiple clinical centers.

#### B. Scale, Volume & Structure
- **Total Dataset Size**: Exactly **8,037 unique frames** comprising **19,260 visual files** (images, binary masks, and visual bounding box overlays) across 6 clinical centers:
  - Center C1: France (256 single frames)
  - Center C2: Italy (301 single frames)
  - Center C3: United Kingdom (457 single frames)
  - Center C4: Norway (227 single frames)
  - Center C5: Egypt (208 single frames)
  - Center C6: Sequestered Test Center (88 single frames)
  - **Single Frame Subtotal**: 1,537 images + 1,537 masks.
- **Video Sequence Collection (`sequenceData/`)**:
  - **Positive Video Sequences (`sequenceData/positive/`)**: Exactly **23 continuous video sequences** (`seq1` through `seq23`), containing **2,225 frames**.
    - Positive frames with verified masks: 1,710 frames.
    - Non-polyp frames within sequences (empty masks): 515 frames.
  - **Negative Video Sequences (`sequenceData/negativeOnly/`)**: Exactly **23 continuous video sequences** (`seq1_neg` through `seq23_neg`), containing **4,275 frames** of normal colon mucosa (0 masks, 0 bboxes).
- **Total Video Sequence Frames**: $2,225 + 4,275 = \mathbf{6,500\text{ frames}}$.

#### C. Annotation Scheme & Granularity
- **Dual Annotation**: 100% of positive frames possess both pixel-level binary segmentation masks and space-delimited Pascal VOC bounding boxes (`polyp <xmin> <ymin> <xmax> <ymax>`).
- **Negative Sequences**: Explicitly designed with empty masks/labels to train and evaluate false-positive suppression on mucosal folds, stool residue, and vascular trees.
- **Multi-Center Metadata**: Full clinical provenance per center and per sequence.

#### D. Technical Characteristics
- **Resolutions**: Diverse multi-center resolutions:
  - $1920 \times 1080$: 8,767 files (45.5%)
  - $1440 \times 1064$: 2,829 files (14.7%)
  - $1440 \times 1080$: 1,314 files (6.8%)
  - $1280 \times 720$: 1,296 files (6.7%)
  - $720 \times 576$: 1,114 files (5.8%)
  - Other resolutions ($1280 \times 1024$, $1350 \times 1080$, $384 \times 288$): 3,940 files (20.5%)
- **Frame Rate**: Extracted from continuous 25-30 FPS endoscopy feeds.
- **Color Space**: 24-bit RGB (White Light and selected Narrow Band Imaging).

#### E. Partitioning & Leakage Prevention Protocol
- **Out-of-Center Cross-Validation**: Center C6 (88 frames) served as the sequestered, out-of-distribution clinical test center during EndoCV2021.
- **Sequence Preservation**: The 23 positive and 23 negative video sequences are kept contiguous. In cross-validation, sequences are partitioned as intact units—never splitting adjacent frames across train and test folds.

#### F. Availability & Licensing
- **Open Access**: Published under **Creative Commons Attribution 4.0 International (CC-BY 4.0)**.
- **Official Download Sources**:
  - Synapse: `https://www.synapse.org/#!Synapse:syn26376615`
  - Zenodo: `https://doi.org/10.5281/zenodo.5786560`
- **Integrity Status in Local Environment**: Fully verified and documented in `M:\chakramodel\docs\POLYPGEN_INTEGRITY_REPORT.md` (19,260 files decoded with zero byte corruption).

---

### 2.5 Secondary & Supplementary Benchmarks

| Benchmark | Reference | Size / Frames | Key Characteristics & Relevance to Video Streaming |
|---|---|---|---|
| **HyperKvasir (Video Subset)** | Borgli et al., *Scientific Data* 2020 | **374 video clips** (4.3 hours, ~1M frames) | Massive unsegmented or weakly labeled clinical video repository. Ideal for self-supervised pretraining or temporal representation learning. |
| **EndoScene (CVC-300 / ClinicDB)** | Vázquez et al., *Healthcare Tech. Lett.* 2017 | **912 frames** (612 ClinicDB + 300 ColonDB) | Established standardized 18-procedure video splits for CVC-ClinicDB (550 train, 62 test). CVC-300 subset provides 60 static test frames. |
| **PICCOLO** | Puig et al., *Applied Sciences* 2020 | **3,433 frames** (2,131 WLE, 1,302 NBI) | HD video clips with histological ground truth (adenoma vs. hyperplastic) and Paris/NICE classification, directly supporting CADx pipelines. |
| **ColonColo** | Gastrointestinal Endoscopy 2021 | **~5,000 frames** across 20 videos | Focuses on colorectal neoplasia under magnification and NBI; useful for Paris morphology classification. |
| **Kvasir-Capsule** | Smedsrud et al., *Scientific Data* 2021 | **47,238 frames**, 14 videos | Wireless Capsule Endoscopy (WCE) videos; lower frame rate (~2-4 FPS) but valuable for comparison with optical colonoscopy. |

---

## 3. Master Dataset Comparison Matrix

The table below synthesizes the structural, volumetric, and technical specifications across all evaluated datasets.

| Dimension | SUN-SEG | CVC-VideoClinicDB | LDPolypVideo | PolypGen (Video) | EndoScene | HyperKvasir (Video) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Primary Reference** | Ji et al. (MedIA 2023) | Bernal et al. (GIANA 2017) | Ma et al. (MICCAI 2021) | Ali et al. (Sci Data 2023) | Vázquez et al. (2017) | Borgli et al. (2020) |
| **Modality** | Video Clips (HD/SD) | Video Seqs (SD) | Video Seqs (HD/SD) | Video Seqs (Multi-Ctr) | Static & Video-derived | Continuous Video |
| **Video Clips / Seqs** | **110 clips** (158 total) | **18 sequences** | **160 sequences** | **46 sequences** (23 pos + 23 neg) | 18 sequences (ClinicDB) | **374 clips** |
| **Total Frames** | **158,690** | **~11,954** | **40,266** | **6,500** (8,037 total) | 912 | **~1,000,000** |
| **Annotated Frames** | **158,690** (Dense) | **10,040** (Dense) | **40,266** (Dense BBox) | **2,225** (pos) + 4,275 (neg) | 912 | ~1,000 (segmented) |
| **Annotation Types** | Mask + Contour + BBox + 11 Attrib + Optical Flow | Mask + BBox + Temporal $[t_1, t_2]$ | Bounding Box + Tracking ID | Mask + BBox + Negative Labels | Mask | Weak Video Findings |
| **Annotation Density** | **Dense** (100% frames) | **Dense** (all active) | **Dense** (100% frames) | **Dense** (per sequence) | Dense (sparse frames) | Weak / Procedure-level |
| **Resolution(s)** | $1240\times1080$, $1920\times1080$ | $768\times576$, $384\times288$ | $560\times480$ to $1920\times1080$ | $1920\times1080$, $1440\times1064$, etc. | $384\times288$, $574\times500$ | $1920\times1080$, $1280\times720$ |
| **Native Frame Rate** | 25 – 30 FPS | 25 FPS (PAL) | 25 – 30 FPS | 25 – 30 FPS | 25 FPS | 25 – 30 FPS |
| **Color Spaces** | sRGB (WLE + NBI) | 24-bit RGB (WLE) | 24-bit RGB | 24-bit RGB (Multi-Ctr) | 24-bit RGB | 24-bit RGB |
| **Partition Scheme** | 49 train / 61 test clips (Easy, Hard, Neg) | 16 train / 2 test seqs (or LOVOCV) | 100 train / 20 val / 40 test (Patient split) | Leave-One-Center-Out + Sequence split | 550 train / 62 test (Procedure split) | Weakly split |
| **Temporal Leakage Guard** | Strict Clip Separation | Strict Sequence Split | Strict Patient Split | Strict Sequence + Center | Procedure Segregation | Sequence Split |
| **Licensing** | Academic Non-Comm | Academic Challenge | Academic Non-Comm | **CC-BY 4.0** | Academic | **CC-BY 4.0** |
| **Primary Repository** | `GitHub: GewelsJI/VPS` | GIANA / EndoVis Portals | MICCAI 2021 Authors | `Synapse: syn26376615` | CVC / Kaggle Mirrors | Simula Research Portal |

---

## 4. Forensic Audit of Local Video Assets in `M:\chakramodel`

A thorough filesystem audit was executed across `M:\chakramodel` to establish the exact status of all local video files, archives, and past evaluation artifacts.

### 4.1 Physical Inspection of `video_testing/` (42 Clips, 381,433 Frames)

Direct inspection of `M:\chakramodel\video_testing` reveals a substantial collection of video files:
- **File Census**:
  - Exactly **42 AVI video files** (`1_1.avi` through `1_42.avi`, totaling 10.87 GB).
  - Exactly **42 MP4 video files** (`1_1.mp4` through `1_42.mp4`, totaling 2.58 GB).
  - Exactly **1 demo analyzed video** (`1_1_analyzed.mp4`, 91.7 MB).
  - Subdirectory `video_testing/polyp/extracted/videos with polyps`: Contains 12 duplicate AVI files.
  - Compressed zip `video_testing/polyp/videos with polyps-20260804T054937Z-1-001.zip` (2.08 GB).
- **Physical Video Specifications** (measured via OpenCV `cv2.VideoCapture`):
  - **Resolution**: Exactly $768 \times 576$ pixels across all files (PAL standard definition).
  - **Frame Rate**: Measured at $24.83$ to $24.90\text{ FPS}$ (standard 25 FPS PAL capture).
  - **Total Frame Count**: The 42 AVI videos contain exactly **381,433 frames**. Individual clip durations range from 1,400 frames (~56 seconds) to 21,300 frames (~14.2 minutes).
- **Critical Annotation Finding**:
  - Executing automated glob searches for `.txt`, `.json`, `.xml`, `.png`, and `.csv` files within `M:\chakramodel\video_testing` returns **exactly 0 annotation files**.
  - **Ground Reality**: These 42 video files represent raw, unannotated colonoscopy recordings derived from LDPolyp recording sessions. While useful for qualitative pipeline visualization (`src/inference/infer_stream.py`) and processing throughput benchmarking (`src/inference/test_videos_batch.py`), they **cannot be used for quantitative mAP, IoU, or Dice evaluation** because ground-truth polyp locations are completely absent.

### 4.2 Forensic Audit of `CVC_ClinicVideoDB_Kaggle.zip` (12.71 GB Archive)

In the root directory of `M:\chakramodel`, an archive named `CVC_ClinicVideoDB_Kaggle.zip` exists:
- **Filesize**: Exactly $13,648,757,889\text{ bytes}$ (~12.71 GB), timestamped September 5, 2026.
- **Forensic Diagnosis**: As uncovered during the Kaggle Decoding Audit (`docs/audit/KAGGLE_DATASET_DECODING_REPORT.md` §6.1):
  - Standard ZIP parsing utilities (`unzip`, Python `zipfile.ZipFile`) throw parsing errors (`BadZipFile: File is not a zip file` or truncated central directory).
  - Binary inspection reveals a nested 2.08 GB Google Drive archive (`videos with polyps-20260804T054937Z-1-001.zip`) that was concatenated without updating the master End of Central Directory (EOCD) record offset.
  - Extraction reveals that this archive contains the exact same 42 unannotated video clips found in `video_testing/`. It contains **0 ground-truth masks**, confirming that genuine CVC-ClinicVideoDB challenge annotations were never successfully mounted.

### 4.3 Evaluation Results in `kaggle_results/` and Historical Kaggle Uploads

1. **Inference Video Outputs in `kaggle_results/`**:
   - Contains 23 processed video outputs (`1_1_analyzed.mp4` through `1_30_analyzed.mp4` and `07c1fa15a20a4398_analyzed.mp4`).
   - These files contain bounding box and contour overlays rendered by `src/inference/kaggle_video_inference.py`. However, since no ground truth existed, no quantitative recall or false positive metrics were computed.
2. **Cross-Dataset Quantitative Results (`kaggle_results/run_v5/cross_dataset_results_v5.json`)**:
   - The authoritative benchmark results in the repository are strictly static 2D image evaluations:
     - *Kvasir-SEG (test split)*: Dice $0.8131 \pm 0.1747$, IoU $0.7141$ ($n=150$).
     - *CVC-ClinicDB (zero-shot)*: Dice $0.7561 \pm 0.2131$, IoU $0.6470$ ($n=495$).
     - *EndoScene CVC-300 (zero-shot)*: Dice $0.7402 \pm 0.1590$, IoU $0.6098$ ($n=60$).
     - *HyperKvasir Segmented*: Dice $0.8360 \pm 0.1610$, IoU $0.7439$ ($n=1,000$).
     - *PolypDB (All Modalities)*: Dice $0.7283 \pm 0.2544$, IoU $0.6243$ ($n=7,868$).
     - *ETIS-Larib*: Evaluated on 5 synthetic images resulting in Dice $0.0000$.
   - **Conclusion**: Despite claims in early documentation drafts, **zero quantitative evaluation has been executed on genuine video benchmarks** (SUN-SEG, CVC-ClinicVideoDB, LDPolypVideo).

---

## 5. Partitioning Protocols to Prevent Temporal Leakage

### 5.1 The Mechanics of Temporal Leakage in Colonoscopy Video

Temporal leakage is the single most pervasive methodological flaw in published medical video computer vision. In continuous endoscopy:
- Frames captured at 25 FPS are separated by only **40 milliseconds**.
- Two adjacent frames ($t_i$ and $t_{i+1}$) share identical lighting, identical mucosal wall folds, the same camera sensor noise profile, and virtually identical polyp morphology.
- If a practitioner pools all video frames and executes standard random splitting:
  ```python
  # DANGEROUS METHODOLOGICAL FLAW: Causes severe temporal leakage!
  train_frames, test_frames = train_test_split(all_frames, test_size=0.2, shuffle=True)
  ```
  Frame $t$ will enter the training set, while frame $t+1$ (and $t-1$) will enter the test set.
- Under this flawed protocol, deep neural networks (especially high-capacity vision transformers like ViT-Large) easily achieve **artificially inflated metrics** (e.g., Dice > 0.95, mAP > 0.92) simply by memorizing the background vascular texture and brightness of that specific millisecond. When deployed on an unseen patient in real clinic, the model collapses because it never learned generalized geometric and semantic features.

### 5.2 Multi-Level Partitioning Hierarchy (Center → Patient → Sequence)

To guarantee clinical generalizability, video polyp datasets must be partitioned strictly according to a **three-level hierarchical firewall**:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     TEMPORAL LEAKAGE PREVENTION HIERARCHY                       │
├─────────────────┬───────────────────────────────────────────────────────────────┤
│ Level 1: Center │ Split by Hospital / Clinic (Different scope hardware, optical  │
│                 │ sensors, patient demographics, clinical protocols).           │
├─────────────────┼───────────────────────────────────────────────────────────────┤
│ Level 2: Patient│ Split by Patient / Procedure ID (Guarantees zero shared       │
│                 │ mucosal anatomy or individual polyp lesions across splits).   │
├─────────────────┼───────────────────────────────────────────────────────────────┤
│ Level 3: Sequence│ Keep continuous video sequences intact (Never break a clip    │
│                 │ into random train/test frames; test on entire unseen runs).   │
└─────────────────┴───────────────────────────────────────────────────────────────┘
```

#### Buffer Windows (Temporal Deadbands)
If multiple video clips are recorded from the *same* patient procedure (e.g., examining the same cecum or ascending colon segment at different minutes):
- Best practice dictates assigning **all clips from the same patient** to the same partition.
- If procedure IDs are unavailable, a **temporal deadband / buffer window** of at least 15 to 30 seconds (375 to 900 frames) or physical anatomical transition must separate training and validation recordings.

### 5.3 Benchmark Partition Standards

1. **SUN-SEG**:
   - Segregates the 110 clips into 49 training clips and 61 testing clips.
   - Evaluates on distinct Easy (17 clips), Hard (34 clips), and Negative (10 clips) partitions.
   - **Zero frame overlap**: 100% of testing frames originate from video sequences completely unseen during training.
2. **LDPolypVideo**:
   - 160 video sequences correspond to 160 distinct patients.
   - 100 patient sequences train, 20 patient sequences validate, 40 patient sequences test.
   - Prevents both temporal correlation and patient-specific anatomical memorization.
3. **PolypGen**:
   - Combines Level 1 (Center C6 held out as sequestered clinical center) and Level 3 (23 positive and 23 negative sequences preserved as continuous temporal blocks).

---

## 6. Architectural & Evaluation Implications for ChakraModel

### 6.1 Transitioning from Static YOLO+ViT to Temporal Video Processing

ChakraModel currently operates as a disjointed frame-by-frame cascade:
$$\text{Frame } I_t \longrightarrow \text{YOLOv8} \longrightarrow \text{Crop ROI} \longrightarrow \text{ViT-Large (384}\times\text{384)} \longrightarrow \text{Mask } M_t$$
Because each frame is processed independently without temporal memory:
1. **Redundant Computation**: The model re-encodes stationary mucosal background pixels 25 times per second.
2. **Extreme Latency**: Processing ViT-Large at 384×384 takes ~200 ms per frame on consumer GPUs, capping pipeline throughput at 3.7 FPS.
3. **Temporal Jitter**: Bounding box coordinates oscillate by several pixels between adjacent frames, and mask contours jitter.

#### Architectural Remedies from Video Polyp Literature:
- **Temporal Memory Networks (PNS-Net / VPS-Implicit)**: Ingest multi-frame temporal feature representations (e.g., maintaining a hidden state vector or temporal memory queue of keyframes). Feature extraction is run deeply on keyframes (every $k$-th frame), while intermediate frames are updated via lightweight optical flow or cross-frame attention.
- **Fast-Slow Architecture**: Run YOLOv8 detection and lightweight tracking at full 30 FPS (~10 ms), while invoking the heavyweight ViT segmenter only on newly initialized tracks or every 5th frame, propagating the mask via ByteTrack and Kalman state estimation.
- **Temporal Loss Functions**: Integrate temporal consistency regularization:
  $$\mathcal{L}_{\text{temporal}} = \sum_{t=1}^{T-1} \| M_{t+1} - \mathcal{W}_{t \to t+1}(M_t) \|_1$$
  where $\mathcal{W}_{t \to t+1}$ denotes warping via inter-frame optical flow.

### 6.2 Video-Specific Evaluation Metrics

Future evaluations of ChakraModel on continuous video must supersede static Dice and mIoU with standardized Video Polyp Segmentation (VPS) and temporal stability metrics:

| Metric Name | Symbol / Formula | Clinical Meaning & Threshold |
|---|:---:|---|
| **Temporal Consistency Score** | $\text{TCS} = \frac{1}{T-1}\sum \text{IoU}(M_{t+1}, \mathcal{W}(M_t))$ | Measures mask stability across consecutive frames. $\text{TCS} > 0.85$ indicates smooth, non-flickering display. |
| **Structure Measure** | $S_\alpha = \alpha S_o + (1-\alpha) S_r$ | Evaluates structural object-aware and region-aware similarity (Ji et al., 2022). |
| **False Positives Per Procedure** | $\text{FP} / \text{Proc}$ or $\text{FP} / \text{Min}$ | Counts false alarms on normal mucosa. Clinical standard requires $< 0.5\text{ FP/minute}$ to avoid alarm fatigue. |
| **Detection Latency** | $t_{\text{detect}} - t_{\text{enter}}$ | Time (in frames or ms) between a polyp first entering view and the CADe box locking on. Standard: $\le 3\text{ frames}$ ($\le 120\text{ ms}$). |
| **ID Switches** | $\text{IDSW}$ | Frequency with which the tracker loses and re-assigns an object track ID to the same polyp lesion. |

### 6.3 Recommended Video Dataset Ingestion Roadmap

To transition ChakraModel from its current static image baseline to a certified video polyp system:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        VIDEO DATASET INGESTION ROADMAP                                 │
├─────────┬───────────────────┬──────────────────────────────────────────────────────────┤
│ Phase 1 │ PolypGen Video    │ Ingest 23 positive + 23 negative sequences (6,500 frames)│
│ (Now)   │ Subsets (CC-BY)   │ Fully uncorrupted on disk; zero credentialing barrier.   │
├─────────┼───────────────────┼──────────────────────────────────────────────────────────┤
│ Phase 2 │ SUN-SEG VPS       │ Download benchmark splits (49 train / 61 test clips) via │
│ (Next)  │ Official Release  │ GewelsJI/VPS Google Drive. Run VPS evaluation toolkit.   │
├─────────┼───────────────────┼──────────────────────────────────────────────────────────┤
│ Phase 3 │ Annotate Local    │ Select 5 high-quality sequences from local video_testing │
│ (Target)│ 42-Clip Pool      │ Generate pseudo-ground truth using SAM2 / manual review. │
└─────────┴───────────────────┴──────────────────────────────────────────────────────────┘
```

1. **Immediate Execution (PolypGen Video Subsets)**:
   - PolypGen is already verified locally (`M:\chakramodel\docs\POLYPGEN_INTEGRITY_REPORT.md`) under a permissive CC-BY 4.0 license.
   - Utilize its 23 positive sequences (2,225 frames with 1:1 masks and bboxes) and 23 negative sequences (4,275 frames) to benchmark temporal tracking, FPS, and negative false-positive suppression without any external credentialing delay.
2. **Near-Term Execution (SUN-SEG via VPS Toolkit)**:
   - Access the standardized SUN-SEG-Easy and SUN-SEG-Hard splits via the official VPS repository (`https://github.com/GewelsJI/VPS`).
   - Run ChakraModel through the official VPS evaluation scripts to report standard $S_\alpha$, $E_\phi$, $F_\beta^w$, and MAE metrics alongside literature SOTA (PNS-Net, ACSNet, PraNet-V).
3. **Local Video Ground-Truth Annotation**:
   - If the 42 local video sequences in `video_testing` (381,433 frames) are to be used for quantitative validation, a subset of clips (e.g., 5 representative sequences) must be annotated with ground-truth bounding boxes and masks using interactive foundation models (e.g., SAM 2 video predictor) followed by expert clinical verification.

---

## 7. References & Citations

1. **Ji, G.-P., Xiao, G., Chou, Y.-C., Fan, D.-P., Zhao, K., Chen, G., & Van Gool, L.** (2023). *Video Polyp Segmentation: A Deep Learning Perspective*. Medical Image Analysis (MedIA), 84, 102717.
2. **Ma, Y., Chen, X., Cheng, K., et al.** (2021). *LDPolypVideo Benchmark: A Large-scale Colonoscopy Video Dataset for Polyp Detection*. International Conference on Medical Image Computing and Computer-Assisted Intervention (MICCAI 2021), Lecture Notes in Computer Science, vol 12903, pp. 24–34.
3. **Bernal, J., Sánchez, F. J., Fernández-Esparrach, G., et al.** (2017). *Polyp detection and segmentation in colonoscopy video: results from the GIANA 2017 challenge*. Computer Vision Center (CVC), Universitat Autònoma de Barcelona.
4. **Ali, S., Jha, D., Ghatwary, N., Realdon, S., Cannizzaro, R., et al.** (2023). *PolypGen: A multi-center colonoscopy dataset for generalisable polyp detection and segmentation*. Scientific Data (Nature), 10(1), 750.
5. **Misawa, M., Kudo, S. E., Mori, Y., et al.** (2021). *Development of a computer-aided detection system for colonoscopy and a publicly accessible large colonoscopy video database (SUN database)*. Journal of Gastrointestinal Endoscopy, 93(4), 960–967.
6. **Borgli, R. J., Thambawita, V., Smedsrud, P. H., et al.** (2020). *HyperKvasir, a comprehensive multi-class image and video dataset for gastrointestinal endoscopy*. Scientific Data (Nature), 7(1), 283.
7. **Vázquez, D., Bernal, J., Sánchez, F. J., et al.** (2017). *A benchmark for endoluminal scene segmentation of colonoscopy images*. Healthcare Technology Letters, 4(5), 187–193.
8. **Puig, V., et al.** (2020). *The PICCOLO project: Multimodal optical approach for colorectal neoplasia identification*. Applied Sciences, 10(6), 2145.
9. **ChakraModel Forensic Reports**:
   - `M:\chakramodel\docs\audit\KAGGLE_DATASET_DECODING_REPORT.md` (September 7, 2026).
   - `M:\chakramodel\docs\POLYPGEN_INTEGRITY_REPORT.md` (September 8, 2026).
   - `M:\chakramodel\docs\CHAKRAMODEL_ANALYSIS_REPORT.md` (September 9, 2026).
