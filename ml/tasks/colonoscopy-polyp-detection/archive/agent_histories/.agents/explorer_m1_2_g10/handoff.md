# Handoff Report: Video Datasets for Polyp Detection and Segmentation

**Agent:** Explorer 2 (Video Datasets Analyst)  
**Milestone:** Milestone 1 (Generation 10)  
**Recipient:** Orchestrator (`orchestrator_gen10`, ID: `39578642-3df9-46b1-9513-eea8bc4aa461`)  
**Working Directory:** `M:\chakramodel\.agents\explorer_m1_2_g10`  
**Report Artifact:** `M:\chakramodel\.agents\explorer_m1_2_g10\analysis.md`  
**Date:** September 9, 2026  
**Status:** Hard Handoff (Task Complete)  

---

## 1. Observation

Direct, empirical observations recorded from physical filesystem inspection, code inspection, and command execution across `M:\chakramodel`:

1. **Local Video Assets in `M:\chakramodel\video_testing`**:
   - Directory listing reveals **42 AVI files** (`1_1.avi` to `1_42.avi`, totaling 10.87 GB), **42 MP4 files** (`1_1.mp4` to `1_42.mp4`, totaling 2.58 GB), and 1 demo overlay file (`1_1_analyzed.mp4`, 91.7 MB).
   - Python inspection via OpenCV (`cv2.VideoCapture`) on `M:\chakramodel\video_testing\1_1.avi`:
     `w: 768.0 h: 576.0 fps: 24.874 frames: 5001.0 fourcc: 875967080`
   - Total frames across all 42 AVI videos measured programmatically: **381,433 frames**.
   - Inspection of annotation files across `M:\chakramodel\video_testing` using recursive glob search for `.txt`, `.json`, `.xml`, `.png`:
     `python -c "import glob; print(glob.glob(r'M:\chakramodel\video_testing\**\*.txt', recursive=True))" -> []`
     **Observation**: Exactly **0 ground-truth masks or bounding box annotations exist** for the 42 local video files.
2. **Local Video Archive `M:\chakramodel\CVC_ClinicVideoDB_Kaggle.zip`**:
   - File size: **13,648,757,889 bytes (~12.71 GB)** (Powershell: `Get-Item 'M:\chakramodel\CVC_ClinicVideoDB_Kaggle.zip' | Select-Object Name, Length`).
   - Ground truth status: Audited in `M:\chakramodel\docs\audit\KAGGLE_DATASET_DECODING_REPORT.md` (lines 49, 83, 124, 457):
     > *"The local 12.71 GB archive CVC_ClinicVideoDB_Kaggle.zip contains 42 unannotated video sequences in AVI/MP4 formats, but standard tools cannot read its central directory due to trailer displacement, and it contains 0 ground-truth annotations."*
3. **Forensic Status of Target Video Baselines in the Repository**:
   - `docs/audit/KAGGLE_DATASET_DECODING_REPORT.md` (§1.1, lines 64-70):
     - **SUN-SEG**: 100% ABSENT (0 files, 0 MB). `build_master_eval_notebook.py:L13` documents: *"SUN-SEG not uploaded yet, 12.5 GB"*. `REPORT.txt:L159-160` documents access gating on `amed8k.sundatabase.org` requiring email credentialing.
     - **CVC-VideoClinicDB**: 100% ABSENT as a video evaluation benchmark. Conflated with 2D static benchmark `CVC-ClinicDB` (495 images).
     - **LDPolypVideo**: ABSENT AS A VIDEO BENCHMARK (<2% static frame slice only). Paper draft claims of evaluating real-time temporal stability were confirmed fabricated (`docs/audit/KAGGLE_DATASET_DECODING_REPORT.md:L472-475`).
     - **PolypGen**: 100% ABSENT in Kaggle uploads (substituted with PolypDB 5-modality static pairs).
4. **Verified Status of PolypGen Multi-Center Dataset on Disk**:
   - Documented in `M:\chakramodel\docs\POLYPGEN_INTEGRITY_REPORT.md`:
     - **8,037 unique frames** across **19,260 visual files**, verified with zero byte corruption.
     - Video sequence collection: 23 positive sequences (`seq1` to `seq23`, 2,225 frames: 1,710 positive with masks + 515 empty frames) and 23 negative sequences (`seq1_neg` to `seq23_neg`, 4,275 frames of normal mucosa). Total video sequence frames: **6,500 frames**.
5. **Quantitative Results in Local Evaluation Logs**:
   - `M:\chakramodel\kaggle_results\run_v5\cross_dataset_results_v5.json`:
     Evaluated strictly static 2D image sets: Kvasir-SEG (150 images, Dice 0.8131), CVC-ClinicDB (495 images, Dice 0.7561), EndoScene CVC-300 (60 images, Dice 0.7402), HyperKvasir (1,000 images, Dice 0.8360), PolypDB (7,868 files, Dice 0.7283), and ETIS-Larib (5 synthetic images, Dice 0.0000). Zero quantitative video evaluations were recorded.
6. **Pipeline Video Inference Code**:
   - `src/inference/infer_stream.py` implements a 4-panel stream with OpenCV heuristic artifact rejection (`is_artifact_frame`: Laplacian variance < 80, brightness < 30 or > 220), ByteTrack tracking, and EMA confidence smoothing (`ConfidenceSmoother`), but runs sequentially without multi-frame temporal feature reuse.

---

## 2. Logic Chain

1. **Premise 1 (Clinical Video Disconnect)**: Clinical colonoscopy operates as a continuous stream at 25-30 FPS. Standard static 2D datasets (Kvasir-SEG, CVC-ClinicDB) evaluate isolated, clean, centered frames, failing to represent temporal flickering, motion blur, specular reflections, or false alarm rates on continuous normal mucosa (Obs 1, Obs 5).
2. **Premise 2 (Target Video Datasets Cataloged)**:
   - **SUN-SEG**: 158,690 frames across 110 clips, dense masks, boundary contours, 11 clinical attributes, precomputed optical flow, video-level partition (49 train / 61 test clips). Hosted at `https://github.com/GewelsJI/VPS`.
   - **CVC-VideoClinicDB**: 18 SD sequences (~11,954 frames), dense masks, temporal appearance intervals, 25 FPS PAL, sequence-level partition (16 train / 2 test). GIANA/MICCAI challenge access.
   - **LDPolypVideo**: 160 sequences (40,266 frames: 33,024 positive + 7,242 negative), frame-by-frame bounding boxes with persistent tracking IDs, 25-30 FPS, patient-level partition (100 train / 20 val / 40 test). MICCAI 2021 authors.
   - **PolypGen**: 8,037 frames (6,500 frames in 46 video sequences: 23 positive, 23 negative), dense masks, Pascal VOC bounding boxes, multi-center partition (C1-C5 train, C6 unseen test). CC-BY 4.0 on Synapse (`syn26376615`) and Zenodo.
3. **Premise 3 (Local Workspace Reality)**: Local directory `M:\chakramodel\video_testing` contains 42 video files totaling 381,433 frames (PAL 768x576 at ~25 FPS), but has exactly 0 annotations (Obs 1). Furthermore, `CVC_ClinicVideoDB_Kaggle.zip` is corrupt and contains 0 masks (Obs 2), and Kaggle uploads contained 0% video baselines (Obs 3).
4. **Premise 4 (Temporal Leakage Firewall)**: Random frame-level shuffling across video frames ($t$ and $t+1$ separated by 40 ms) causes massive temporal data leakage, allowing models to memorize background textures. True generalization demands a strict hierarchical firewall: Center-level > Patient/Procedure-level > Sequence-level.
5. **Deduction & Synthesis**: ChakraModel's 3.7 FPS latency bottleneck is exacerbated by processing static frames independently. To transition to a robust video-aware CADe/CADx system, the project must:
   - Immediately leverage PolypGen's 46 video sequences (already verified on disk, CC-BY 4.0).
   - Ingest official SUN-SEG benchmark splits via the VPS toolkit for standard $S_\alpha, E_\phi, F_\beta^w$ comparisons.
   - Employ temporal smoothing, keyframe ViT triggering, and video-level metrics (TCS, detection latency, FP/minute).

---

## 3. Caveats

1. **Network Mode Restriction**: The agent operated under CODE_ONLY network constraints. Live interactive queries to external APIs (Kaggle API, Synapse REST, Zenodo) were not executed. All dataset metadata and URL links are synthesized from local forensic reports (`KAGGLE_DATASET_DECODING_REPORT.md`, `POLYPGEN_INTEGRITY_REPORT.md`), codebase citations, and published peer-reviewed medical imaging literature.
2. **Local Unannotated Video Limitations**: The 42 video files in `video_testing/` (381,433 frames) cannot be used for quantitative mAP, IoU, or Dice benchmark evaluation without annotating ground truth.
3. **Source Code Immutability**: In strict accordance with the prompt's critical constraint, **zero files in `src/` were modified**.

---

## 4. Conclusion

1. **Open-source video polyp benchmarks are clearly defined and structured**: SUN-SEG (158,690 frames, 110 clips, dense masks/boundaries/flow), CVC-VideoClinicDB (18 SD sequences, ~11,954 frames, temporal intervals), LDPolypVideo (160 sequences, 40,266 frames, tracking bboxes), and PolypGen (46 sequences, 6,500 frames, dense masks/bboxes, 6 centers).
2. **Local status reconciled**: Past claims of evaluating video benchmarks in ChakraModel were fabricated or conflated with static subsets; the 42 local test videos (381,433 frames) possess 0 ground-truth annotations.
3. **Actionable path established**: PolypGen's 46 video sequences represent the immediate, fully verified, unencumbered (CC-BY 4.0) video evaluation corpus, while SUN-SEG provides the gold-standard benchmark for formal comparative publication.
4. **Partitioning protocol mandated**: Random frame-level splitting must be strictly prohibited; all video evaluations must use patient/sequence-level segregation to prevent temporal leakage.

---

## 5. Verification Method

To independently verify the observations, measurements, and claims in this report:

1. **Verify Local Video Count, Frame Count, and Resolution**:
   ```powershell
   python -c "import glob, cv2; vids = sorted(glob.glob(r'M:\chakramodel\video_testing\*.avi')); print('Count:', len(vids)); print('Frames:', sum([int(cv2.VideoCapture(v).get(cv2.CAP_PROP_FRAME_COUNT)) for v in vids])); cap = cv2.VideoCapture(vids[0]); print('Res:', cap.get(cv2.CAP_PROP_FRAME_WIDTH), 'x', cap.get(cv2.CAP_PROP_FRAME_HEIGHT), 'FPS:', cap.get(cv2.CAP_PROP_FPS))"
   ```
   *Expected Output*: Count: 42, Frames: 381433, Res: 768.0 x 576.0 FPS: ~24.87.
2. **Verify Absence of Annotations in `video_testing/`**:
   ```powershell
   python -c "import glob; print(glob.glob(r'M:\chakramodel\video_testing\**\*.txt', recursive=True)); print(glob.glob(r'M:\chakramodel\video_testing\**\*.json', recursive=True))"
   ```
   *Expected Output*: `[]` and `[]`.
3. **Verify Size and Timestamp of `CVC_ClinicVideoDB_Kaggle.zip`**:
   ```powershell
   powershell -Command "Get-Item 'M:\chakramodel\CVC_ClinicVideoDB_Kaggle.zip' | Select-Object Name, Length"
   ```
   *Expected Output*: Length: `13648757889`.
4. **Verify Analysis Report Integrity**:
   Inspect `M:\chakramodel\.agents\explorer_m1_2_g10\analysis.md` for complete tables, dataset characteristics, and partitioning protocols.
5. **Verify Zero Changes to `src/`**:
   ```powershell
   git status src/
   ```
   *Expected Output*: Working tree clean (no modified or untracked files in `src/`).
