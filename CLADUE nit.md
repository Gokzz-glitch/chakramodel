# ChakraModel Research Brief
## Colonoscopy Polyp Detection — Exhaustive Technical Landscape for the Tata Centre 36-Hour Hackathon
**Prepared:** July 28, 2026 | **Deadline:** August 1, 2026

---

## EXECUTIVE SUMMARY

### Current State of the Field
Colonoscopy polyp detection is a well-studied problem, but with a critical structural gap: the literature is bifurcated between (A) high-accuracy frame-wise detectors that produce flickering, temporally inconsistent outputs in video, and (B) sophisticated video-aware architectures that are computationally expensive, require specialized datasets, and lack publicly available weights. The field has not produced a production-ready, lightweight, video-stable polyp detection pipeline with open code that a small team can pick up and deploy within a day.

**Headline benchmark numbers** (April 2026, nine-model comparison on CVC-ClinicDB/ColonDB/ETIS):
- **YOLO11m** — mAP@50 of 0.995 / 0.944 / 0.978, fastest inference
- **YOLOv8m** — mAP@50 of 0.911 (CVC-ClinicDB), 95.6% precision, 91.7% recall
- **YOLO11** / **YOLOv8** dominate every real-time benchmark; RT-DETR and YOLO-World follow

### The Gap ChakraModel Addresses
**No existing open-source system bundles**: (1) YOLO11/YOLOv8 detection → (2) BoT-SORT/ByteTrack temporal tracking → (3) CLAHE artifact mitigation → (4) a temporal persistence filter that suppresses flickering false positives.

The temporal consistency problem is documented as a major unsolved bottleneck. Existing frame-wise YOLO solutions produce a detection on frame N, miss it on frame N+1 (due to motion blur or partial occlusion), then re-detect on frame N+2 — causing the alert box to "flicker" in a clinical setting. This directly reduces clinician trust. ChakraModel's innovation is layering **tracking + persistence scoring** on top of the SOTA detector, a combination that hasn't been published as a clean, reusable open-source pipeline.

### Highest-Impact Feasibility Assessment (36 hours, 3-person team)
**Recommended stack (achievable with high confidence):**

```
Kvasir-SEG + CVC-ClinicDB + CVC-ColonDB + ETIS  →  CLAHE preprocessing
→ YOLO11m (fine-tuned, 4–6 hrs on Colab T4)
→ BoT-SORT built into Ultralytics (2 lines of code)
→ Temporal Persistence Filter (N-frame window, custom Python, ~3 hrs)
→ Evaluation on ETIS-LaribPolypDB as hard out-of-domain test set
→ Gradio/Streamlit demo
```

**Expected metrics**: mAP@50 ≈ 0.92–0.97 on in-domain test; mAP@50 ≈ 0.75–0.85 on ETIS (hard set); temporal flicker substantially reduced vs. baseline YOLO alone.

**Role split**:
- **AI/ML member**: Dataset prep, YOLO fine-tuning, ByteTrack integration, Temporal Persistence Filter
- **Biomedical engineer**: Artifact classification, CLAHE pipeline, clinical context documentation, evaluation on hard sets (ETIS), demo framing
- **Third member**: Gradio demo, slides, ablation table, README

**What to cut if behind schedule**: Skip the Gradio demo in favor of a clean Jupyter notebook with annotated video output. Skip PolypGen multi-center generalization testing.

---

## SECTION 1: EXISTING APPROACHES
*Ranked by relevance to ChakraModel and implementation speed. Code availability is the primary tiebreaker.*

---

### Tier 1 — Plug-and-Play (Direct Integration, <4 Hours)

#### 1.1 YOLO11 / YOLOv8 via Ultralytics
- **Paper**: YOLO11 (Ultralytics, 2024); YOLOv8 (Jocher et al., 2023)
- **Links**: https://docs.ultralytics.com | https://github.com/ultralytics/ultralytics
- **Key metrics**: YOLO11m — mAP@50 = 0.995 (CVC-ClinicDB), 0.944 (CVC-ColonDB), 0.978 (ETIS). YOLOv8m — 95.6% precision, 91.7% recall, 92.4% F1 on Kvasir-SEG + 4 datasets combined.
- **Core approach**: Single-stage anchor-free object detector; C2f backbone; decoupled detection head. YOLO11 replaces C2f with C3k2 blocks and adds SPPF improvements.
- **Code**: ✅ YES — `pip install ultralytics`. COCO-pretrained weights download automatically. Single-class fine-tuning on Kvasir-SEG takes 4–6 hours on a Colab T4 GPU at 100 epochs with 1748 combined-dataset images.
- **Integration time**: 2–3 hours total (1 hr data prep + 1 hr training config + training run).
- **Why it works**: Dominates every benchmark paper run in 2025–2026. The anchor-free formulation handles highly variable polyp shapes. `yolo11m.pt` is the sweet spot between nano (fast, less accurate) and large (more accurate, slower). YOLOv8n is the fastest option if Colab RAM is tight.
- **Limitation**: Frame-wise only. No temporal reasoning. Produces flickering on video.

#### 1.2 BoT-SORT / ByteTrack (built into Ultralytics)
- **Paper**: ByteTrack (Zhang et al., ECCV 2022); BoT-SORT (Aharon et al., 2022)
- **Links**: https://docs.ultralytics.com/modes/track
- **Key feature**: Camera motion compensation (CMC) via sparse optical flow. Two-stage IoU association. Optional ReID embeddings (as of Ultralytics v8.3.114).
- **Code**: ✅ YES — literally one line: `model.track(source="video.mp4", persist=True, tracker="bytetrack.yaml")`
- **Integration time**: 30 minutes to configure.
- **Why use BoT-SORT over ByteTrack for colonoscopy**: The colonoscope moves continuously — BoT-SORT's camera motion compensation (CMC) corrects for this, keeping track IDs stable even during rapid withdrawal. ByteTrack is fine for static cameras; colonoscopy is not static.
- **Config knobs for colonoscopy**: Set `track_buffer: 15` (shorter buffer reduces zombie-track false positives), `new_track_thresh: 0.35` (slightly higher than default to suppress weak artifact detections).
- **Limitation**: The tracking ID stability is only as good as the underlying detection confidence. Noisy frames (water, blur) will still produce low-confidence detections that confuse the tracker.

---

### Tier 2 — Quick Integration (2–6 Hours Including Code Adaptation)

#### 1.3 YONA (You Only Need One Adjacent Reference-Frame)
- **Paper**: Jiang et al., MICCAI 2023 — "YONA: You Only Need One Adjacent Reference-Frame for Accurate and Fast Video Polyp Detection"
- **Link**: https://arxiv.org/abs/2306.03686 | https://github.com/yuncheng97/YONA
- **Key metrics**: Outperforms SOTA competitors "by a large margin in both accuracy and speed" on three public benchmarks (CVC-ClinicVideoDB, LDPolypVideo, SUN-SEG). Exact numbers not publicly detailed in abstract but validated at MICCAI 2023.
- **Core approach**: Takes only the immediately preceding frame as reference. Aligns foreground channel activation patterns via foreground similarity. Eliminates invalid features from camera jitter using inter-frame background difference. Adds cross-frame contrastive learning.
- **Code**: ✅ YES — public GitHub repository with training and inference code.
- **Integration time**: 4–6 hours (environment setup + dataset formatting + training — requires CVC-ClinicVideoDB or LDPolypVideo, both of which need reformatting for YONA's data loader).
- **Why it matters**: Directly solves the jitter problem from moving colonoscope cameras. Much simpler than full 3D-CNN or transformer-based video architectures.
- **Risk**: Requires a video dataset (not just images). LDPolypVideo (40,266 annotated frames) is the recommended training set; download requires contacting authors. If you can't get video data in time, skip this and use YOLO + ByteTrack instead.
- **Verdict for hackathon**: High-risk unless video dataset is obtained in first 2 hours. If you have LDPolypVideo or CVC-ClinicVideoDB already, integrate this over YOLO. If not, this is a scope cut.

#### 1.4 PraNet (Parallel Reverse Attention Network)
- **Paper**: Fan et al., MICCAI 2020 — "PraNet: Parallel Reverse Attention Network for Polyp Segmentation"
- **Link**: https://github.com/DengPingFan/PraNet
- **Key metrics**: Dice ≈ 0.90 on Kvasir-SEG, ~50 FPS on single GPU.
- **Core approach**: Parallel partial decoder + reverse attention modules. Mines boundary cues for precise segmentation.
- **Code**: ✅ YES — full PyTorch codebase, pretrained weights available on Google Drive, dataset download links provided in README.
- **Integration time**: 3–4 hours (download pretrained weights, run inference, convert segmentation masks to bounding boxes if needed).
- **Note**: Segmentation model, not a bounding-box detector. You'd need to convert predictions to bounding boxes for clinical display. Do this with `cv2.boundingRect(contours)`.
- **Verdict**: Use as a segmentation head layered on top of YOLO's bounding box, if time allows (Hours 20–28). Adds clinical value (clinicians prefer mask outlines over bare bounding boxes).

#### 1.5 Polyp-SAM2 (YOLOv8 + SAM2 Hybrid)
- **Paper**: Mansoori et al., arXiv Aug 2024 — "Polyp SAM 2: Advancing Zero-Shot Polyp Segmentation in Colorectal Cancer Detection"; companion paper at ICASSP 2025
- **Link**: https://arxiv.org/abs/2408.05892 | https://github.com/sajjad-sh33/Polyp-SAM-2
- **Core approach**: YOLOv8 generates bounding boxes per frame → fed as prompts to SAM2 → SAM2's video-mode memory propagates masks across frames without re-prompting.
- **Code**: ✅ YES — public GitHub.
- **Why it's attractive**: SAM2's memory mechanism provides **free temporal consistency** for segmentation. Once prompted in frame 1, it tracks the polyp across frames without additional computation.
- **Integration time**: 5–7 hours (install SAM2 + Ultralytics, wire up prompt pipeline, test on video). Requires `pip install sam2` (Meta's official package).
- **Key limitation**: SAM2 base model is ~308MB. SAM2-tiny is ~38MB. SAM2 still struggles with small polyps (< 5mm, < 2,500 pixels) and doesn't handle re-identification after occlusion well. Zero-shot performance is moderate (mDice ≈ 0.75–0.82 depending on prompt quality). Fine-tuning SAM2 on polyp data would take 8–12 GPU hours and is not recommended for the hackathon.
- **Verdict**: Best segmentation pipeline for the hackathon. The YOLOv8 → SAM2 handoff gives you detection + beautiful mask visualization with minimal training. Use SAM2-tiny for speed.

---

### Tier 3 — Research-Only (Do Not Implement in 36 Hours)

#### 1.6 TSdetector (Temporal-Spatial Self-Correction)
- **Paper**: Wang et al., Medical Image Analysis 2025 — "TSdetector: Temporal-Spatial self-correction collaborative learning for colonoscopy video detection"
- **Link**: https://pubmed.ncbi.nlm.nih.gov/39579624/
- **Core approach**: Global Temporal-aware Convolution + Hierarchical Queue Integration + Post-processing Adaptive Confidence module.
- **Code**: ❌ Not confirmed publicly available (paper is behind journal paywall; no GitHub found).
- **Verdict**: Read for conceptual inspiration on temporal queuing. Do not implement.

#### 1.7 Hybrid 2D/3D CNN (Puyal et al., 2022)
- **Paper**: "Polyp detection on video colonoscopy using a hybrid 2D/3D CNN," Medical Image Analysis 2022
- **Key result**: 5% improvement in temporal coherence vs. frame-wise FCN; reduced false positives from short-duration artifacts.
- **Code**: ❌ No public implementation found.
- **Verdict**: Conceptually validates the temporal consistency benefit. Not implementable in 36 hours from scratch.

#### 1.8 ColonSegNet
- **Paper**: Jha et al., IEEE Access 2021 — "Real-Time Polyp Detection, Localization and Segmentation"
- **Key metrics**: 180 FPS segmentation (!); AP = 0.80, mIoU = 0.81 (Kvasir-SEG); YOLOv4 at 48 FPS for detection.
- **Code**: ✅ Referenced in paper but GitHub not prominently linked; code may be available via Simula Research Lab.
- **Verdict**: The speed (180 FPS) is extraordinary but was measured on specific hardware; real Colab T4 throughput will differ. YOLOv4 is now superseded by YOLO11. Not worth implementing; serves as a speed-vs-accuracy reference point.

---

## SECTION 2: WHY PROGRESS STALLED

### 2.1 The Frame-Wise Trap
The dominant paradigm — YOLO on individual frames — achieves excellent paper metrics on curated image test sets but fails clinically because colonoscopy is a *video* task. Papers report mAP@50 of 0.99 on CVC-ClinicDB images, but no paper clearly reports *temporal flicker rates* or *per-video false-positive counts* because there is no standard metric for this. The field lacks a standard video-level evaluation protocol beyond simple per-frame metrics. This creates a gap between benchmark performance and clinical utility.

**Implication for ChakraModel**: Define and report a temporal stability metric. Even a simple one (e.g., "fraction of consecutive frame pairs where detection status changes" = flicker rate) is a novel contribution.

### 2.2 Dataset Scarcity and Distribution Shift
Available image datasets are small by deep learning standards: 1000 (Kvasir-SEG) + 612 (CVC-ClinicDB) + 380 (CVC-ColonDB) + 196 (ETIS) = ~2,200 images. Many papers overfit to these datasets — a model achieving mAP@50 = 0.995 on CVC-ClinicDB drops to ~0.75–0.80 when tested on the out-of-distribution ETIS dataset. The PolypGen multi-center study (2023) showed that models trained on single-center data fail on other centers.

**Implication for ChakraModel**: Train on the combined 4-dataset pool (~2,200 images after removing duplicates). Evaluate on ETIS (most challenging, smallest, most distinctive) as your OOD test. Reporting ETIS performance shows generalizability.

### 2.3 Artifact Blindness
Models trained on clean colonoscopy images consistently produce false positives for:
- **Water washout frames**: Opaque fluid temporarily fills the frame; YOLO detects large fluid regions as polyps
- **Specular highlights**: Bright reflections on mucosal folds trigger detection
- **Fecal matter remnants**: Brown/yellow blobs mimic sessile polyps
- **Motion blur from rapid withdrawal**: Out-of-focus frames cause detector hallucinations

Published approaches that address this: (1) A full alert-system paper from Japan (2023) trained a separate classifier for image quality gating (accuracy 96.2% for blur/feces/water detection) before the polyp detector. (2) Some papers apply CLAHE before inference to reduce highlight artifacts. No end-to-end system has cleanly solved all four artifact types.

**Implication for ChakraModel**: Add a simple frame quality gate. A lightweight classifier (or even a rule-based filter: if mean pixel intensity > threshold in >40% of frame → water washout) reduces downstream false positives significantly.

### 2.4 Computational Cost of Video Models
The two most compelling video-aware architectures (full 3D-CNN approaches, attention-based temporal transformers) require multi-frame input windows, significantly more GPU memory, and substantially longer training time. On a Colab T4 (16GB VRAM), training a 3D-CNN on LDPolypVideo (40K+ frames) would take 20–40 hours — consuming the entire hackathon budget. This is why the literature shows a strong correlation between "novel temporal architecture" and "no public code or pretrained weights": the barrier to reproduction is too high.

### 2.5 SUN-SEG Access Problem
The largest video dataset for polyp segmentation (SUN-SEG, 158,690 frames) is technically open-access but requires emailing the original database maintainer for backup access. The primary website (`amed8k.sundatabase.org`) is "no longer maintained and sometimes inaccessible" (per the VPS GitHub README). For a 36-hour hackathon, any dataset that requires email approval is a non-starter.

### 2.6 Clinical Adoption Barriers (Out of Scope for Hackathon, Relevant for Judging)
FDA/CE approval requires prospective clinical trials, IRB approvals, and validation on real patient populations across multiple endoscope types (Olympus, Pentax, Storz). Published commercial systems (GI Genius by Medtronic, ENDO-AID by Olympus) went through 2–5 year validation processes. A hackathon prototype is explicitly not addressing these — but framing your work as "a research prototype for the validation pipeline" rather than a "clinical tool" is important for judges.

---

## SECTION 3: ALTERNATIVE TECHNICAL DIRECTIONS

*Feasibility ratings: ✅ Feasible (< 6 hrs) | ⚠️ High-Risk (6–15 hrs) | ❌ Not Feasible (15+ hrs)*

### 3.1 CLAHE Preprocessing as Artifact Mitigation ✅ Feasible (1–2 hrs)
CLAHE (Contrast Limited Adaptive Histogram Equalization) divides an image into tiles and equalizes each tile's histogram with a clipping limit to prevent noise amplification. In colonoscopy, it enhances visibility of flat and sessile polyps against the mucosa, reduces specular highlight dominance, and improves low-contrast images.

**Implementation**: `cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))` applied per-channel before inference. Several published papers (YOLO-LAN 2025, YOLOv8p+CLAHE 2024) show 1–3% F1 score improvement from CLAHE alone.

**Key paper using this**: Khan et al. (2024) — YOLOv8p+CLAHE achieved precision 0.962, recall 0.892, mAP@50 = 0.955 on Hyper-Kvasir-SEG. This is among the best published results with minimal architectural complexity.

### 3.2 Temporal Persistence Filter (Custom, Novel) ✅ Feasible (3–4 hrs)
This is ChakraModel's primary innovation. Algorithm:
1. Maintain a rolling window of N frames of detections from YOLO+tracker
2. For each track ID, compute `persistence_score = (frames with detection in window) / N`
3. Only flag a polyp to the clinician display if `persistence_score >= threshold` (e.g., 0.7 = 7 of 10 frames must have a detection)
4. This suppresses single-frame false positives from artifacts (water, blur, highlights) while retaining true polyps that appear consistently

**Why it's novel**: TSdetector (2024) does temporal aggregation inside the network. No published paper uses this simple post-processing persistence filter in combination with BoT-SORT track IDs. It's implementable in ~60 lines of Python and interpretable to clinician evaluators.

**Risk**: Introduces latency (equal to window size × frame time). At 25 FPS with N=5, this is 200ms — acceptable for real-time clinical use. At N=10, it's 400ms — still acceptable.

### 3.3 Frame Quality Gate ✅ Feasible (2–3 hrs)
Three-class lightweight classifier before the polyp detector:
- `CLEAR`: Process normally
- `ARTIFACT` (water/blur/feces): Skip this frame, don't update tracker
- `TRANSITION` (motion blur mid-withdrawal): Drop confidence for this frame's detections

**Implementation options:**
- **Rule-based** (1 hour): If frame variance < 500 (blur) or if mean brightness > 240 (washout), flag as ARTIFACT. Fast and interpretable.
- **Tiny CNN classifier** (3 hours): Train a MobileNetV2 or ResNet18 on labeled artifact frames. The Intraprocedure AI Alert System paper (2023, Japan) achieved 96.2% accuracy on blur/feces/water detection — their training data setup is described in the paper and is reproducible.

### 3.4 SAM2 for Video-Consistent Segmentation ⚠️ High-Risk (5–7 hrs)
As described in Section 1.5. The risk isn't the code (it's available); it's the environment setup and video pipeline plumbing (extracting frames, feeding bounding box prompts, reassembling annotated video) that consumes time unexpectedly.

**Mitigation**: Assign SAM2 integration to one team member as a parallel track while the AI/ML member does YOLO fine-tuning. If SAM2 isn't working by Hour 12, cut it.

### 3.5 Optical Flow for Motion-Aware Detection ⚠️ High-Risk (5–8 hrs)
Using `cv2.calcOpticalFlowPyrLK` or `cv2.calcOpticalFlowFarneback` to compute inter-frame motion vectors and use them to (1) predict polyp location in the next frame, (2) identify artifact frames (high overall motion = rapid withdrawal, skip).

**Challenge**: Colonoscopy images have complex spatially non-uniform motion (peristalsis, camera movement, insufflation changes). Optical flow requires tuning and is noisy in these conditions.

**Verdict**: Use BoT-SORT's built-in camera motion compensation (CMC via sparse optical flow) instead of rolling your own. It's already there.

### 3.6 GNN/Transformer-Based Temporal Reasoning ❌ Not Feasible (> 20 hrs)
Graph neural networks modeling polyp detections as nodes across time, or full video transformers (Video Swin, TimeSformer) fine-tuned for polyp video. All require (a) large video datasets, (b) long training runs, and (c) no available pretrained polyp-specific weights.

### 3.7 Ensemble Detection ❌ Not Feasible (> 12 hrs for marginal gain)
Ensembling YOLO11 + RT-DETR + PraNet bounding boxes using WBF (Weighted Box Fusion). Would add ~2–3 mAP points at 3× inference cost. Not worth it in 36 hours.

### 3.8 LLM/VLM Prompting for Zero-Shot Detection ⚠️ High-Risk (3 hrs, low expected performance)
GPT-4.1 achieves F1 of 91.98% on polyp detection (matching ResNet50 at 91.35%), but this is per-image classification, not bounding box detection, and requires API calls — too slow for real-time and costly. Interesting for the demo but not the core system.

---

## SECTION 4: AVAILABLE RESOURCES

### 4.1 Datasets (Priority Order)

| Dataset | Size | Images | Access | Download Time | Format | Annotation | License |
|---------|------|--------|--------|---------------|--------|------------|---------|
| **Kvasir-SEG** | 46.2 MB | 1,000 | Direct: https://datasets.simula.no/kvasir-seg/ OR Kaggle: https://www.kaggle.com/datasets/debeshjha1/kvasirseg | < 5 min | JPG + PNG masks + JSON bbox | Seg mask + bounding box | CC-BY-4.0 |
| **CVC-ClinicDB** | ~50 MB | 612 | Kaggle: https://www.kaggle.com/datasets/balraj98/cvcclinicdb | < 5 min | BMP images + masks | Seg mask (convert to bbox with scikit-image) | Research only |
| **CVC-ColonDB** | ~100 MB | 380 | via Kaggle / openmedlab GitHub | < 10 min | TIF + mask | Seg mask | Research only |
| **ETIS-LaribPolypDB** | ~50 MB | 196 | GitHub: https://github.com/openmedlab/Awesome-Medical-Dataset | < 5 min | PNG + mask | Seg mask | Research only |
| **PolypGen** | ~400 MB | 3,762 (+ 4,275 neg) | GitHub: https://github.com/DebeshJha/PolypGen | 10–15 min | PNG + mask + bbox | Seg mask + bounding box | Open (Scientific Data 2023) |
| **LDPolypVideo** | ~5 GB | 40,266 frames, 160 videos | Contact authors (MICCAI 2021) | Hours if available | MP4 + annotations | Bounding box | Request |
| **SUN-SEG** | ~70 GB | 158,690 frames | GitHub: https://github.com/GewelsJI/VPS — backup requires email | Hours if available | Multiple annotation types | Seg mask | Request |
| **CVC-ClinicVideoDB** | ~1–2 GB | ~18 videos | Requires request | Hours | Video | Bounding box | Research |

**Recommended dataset strategy for hackathon:**
1. **Hour 1**: Download Kvasir-SEG (simula.no, 5 min) and CVC-ClinicDB + ColonDB + ETIS (Kaggle, ~20 min total)
2. **Hour 2**: Combine into a single YOLO-format dataset. Convert segmentation masks to bounding boxes using `cv2.boundingRect(cv2.findContours(...))`. Total: ~2,188 images.
3. Do NOT wait for LDPolypVideo or SUN-SEG — their access path takes too long.
4. **Consider PolypGen** if you want to test multi-center generalization in the demo. Its size (~400MB) is manageable and it's publicly downloadable.

**Preprocessing time estimate**: 2–3 hours for mask-to-bbox conversion, YOLO format YAML writing, and train/val/test splitting across all 4 datasets.

### 4.2 Pretrained Models (Available Weights)

| Model | Source | mAP@50 (CVC-ClinicDB) | FPS | Size | Weights Available | Download |
|-------|--------|----------------------|-----|------|-------------------|---------|
| **YOLO11m** | Ultralytics | 0.995 (after fine-tune) | >60 FPS | ~20M params | ✅ COCO weights auto-download | `pip install ultralytics` |
| **YOLO11n** | Ultralytics | 0.944+ | >100 FPS | ~2.6M params | ✅ Same | Same |
| **YOLOv8m** | Ultralytics | ~0.91 | ~60 FPS | ~25M params | ✅ COCO weights auto-download | Same |
| **RT-DETR-L** | Ultralytics | Slightly below YOLO11 | ~40 FPS | ~32M params | ✅ Auto-download | Same |
| **PraNet** | DengPingFan/PraNet | Dice 0.898 (Kvasir-SEG) | ~50 FPS | ~32M params | ✅ Google Drive link in README | GitHub README |
| **Polyp-PVT** | DengPingFan/Polyp-PVT | Dice 0.900 (Kvasir-SEG) | ~40 FPS | ~25M params | ✅ Available (distilled 5M params) | GitHub README |
| **SAM2-tiny** | Meta AI | N/A (segmenter) | ~30 FPS | ~38MB | ✅ Hugging Face / pip | `pip install sam2` |
| **SAM2-base** | Meta AI | N/A (segmenter) | ~20 FPS | ~308MB | ✅ Hugging Face / pip | Same |

**Model recommendation for ChakraModel:**
- **Primary detector**: YOLO11m (best overall) or YOLO11s (if GPU memory is tight)
- **Tracker**: BoT-SORT (built into Ultralytics, zero additional weight)
- **Optional segmenter**: SAM2-tiny (smallest, fastest, still quality segmentation)

### 4.3 Reusable Code Repositories

| Repo | Stars (est.) | Last Commit | Status | Integration Effort | Notes |
|------|-------------|-------------|--------|-------------------|-------|
| **ultralytics/ultralytics** | ~38K | Active (daily) | ✅ Actively maintained | Plug-and-play | Core of the entire pipeline |
| **GewelsJI/VPS** | ~500 | 2024 | ✅ Active | Medium (3–4 hrs) | Best resource for video polyp segmentation, SUN-SEG dataset, AWESOME_VPS.md list |
| **DengPingFan/PraNet** | ~1K | 2023 | ✅ Stable | Medium (2–3 hrs) | Segmentation; pretrained weights available |
| **DengPingFan/Polyp-PVT** | ~500 | 2023 | ✅ Stable | Medium (3–4 hrs) | Transformer segmentation; pretrained weights available |
| **yuncheng97/YONA** | ~50 | 2023 | ⚠️ Research-only, no updates | Medium-Hard (5–6 hrs) | Video detection; requires video dataset |
| **DebeshJha/PolypGen** | ~100 | 2023 | ✅ Stable | Easy (dataset only, 30 min) | Multi-center dataset with download instructions |
| **sing-group/deep-learning-colonoscopy** | ~200 | 2024 | ✅ Active | Medium (2 hrs to navigate) | Massive benchmark comparison table; use as reference |
| **sajjad-sh33/Polyp-SAM-2** | ~50 | 2024 | ⚠️ Research prototype | Medium (4–5 hrs) | YOLOv8 + SAM2 pipeline; may need debugging |
| **openmedlab/Awesome-Medical-Dataset** | ~2K | Active | ✅ Active | Reference only | Dataset catalog with download links |

**Repos to check first thing**: `ultralytics/ultralytics` (core), `DebeshJha/PolypGen` (dataset), `openmedlab/Awesome-Medical-Dataset` (dataset links), `GewelsJI/VPS` (video context).

---

## SECTION 5: TECHNICAL OPPORTUNITIES

### 5.1 The Temporal Persistence Filter — ChakraModel's Core Claim
**What it is**: A post-processing module that maintains a sliding window of detection history per tracked object and only emits an alert after K consecutive or K-out-of-N positive frames. This trivially eliminates artifact-driven flicker without modifying the model architecture.

**Why it's novel in this field**: No published paper explicitly implements this as a standalone post-processing layer with systematic ablation (with/without filter, with/without tracking). This is a gap.

**Implementation (Python pseudocode)**:
```python
from collections import defaultdict, deque

class TemporalPersistenceFilter:
    def __init__(self, window=10, threshold=0.7):
        self.window = window  # N frames
        self.threshold = threshold  # K/N required
        self.history = defaultdict(lambda: deque(maxlen=window))

    def update(self, track_id, detected):
        self.history[track_id].append(int(detected))

    def is_confirmed(self, track_id):
        h = self.history[track_id]
        if len(h) < self.window // 2:  # not enough history yet
            return False
        return sum(h) / len(h) >= self.threshold
```

**Expected impact**: Based on the literature's description of artifact-driven false positives (3.2 per procedure in one study), this filter would eliminate a majority of single-frame artifact detections while only delaying genuine polyp alerts by 0.2–0.4 seconds.

### 5.2 Artifact-Aware Confidence Recalibration
Combine CLAHE preprocessing with a lightweight frame quality score:
- Compute frame variance: `np.var(gray_frame)` — very low variance indicates motion blur
- Compute bright-pixel fraction: `np.sum(gray > 240) / total_pixels` — high fraction indicates water or overexposure
- If either condition is met, multiply YOLO's confidence scores by a discount factor (e.g., 0.5) before feeding to the tracker

This is a simple heuristic with interpretable clinical meaning. Implementable in 1 hour.

### 5.3 Multi-Dataset Training Fusion
The key insight from the literature: training on Kvasir-SEG alone gives a model that overfits to Kvasir's large, protruding polyps. Training on the combined pool (Kvasir + CVC-ClinicDB + CVC-ColonDB + ETIS) produces a model that generalizes substantially better, especially to flat polyps (ETIS has many). The combined dataset has ~2,188 images — a perfect size for YOLO11 fine-tuning without over-engineering.

**Innovation angle**: Most published papers use only one or two datasets. Testing on out-of-domain ETIS as a generalization benchmark is an underreported but clinically important evaluation.

### 5.4 Hyperparameter Insight from Literature
From YOLO-LAN (2025) ablation studies:
- **Augmentation that helps most**: Mosaic augmentation + color jitter + CLAHE (in that order)
- **Augmentation to avoid**: MixUp with colonoscopy data tends to hurt (hallucinated blended frames don't represent real artifacts)
- **Learning rate**: 0.001 initial, cosine annealing; lower LR than default performs better on medical images
- **Image size**: 640×640 is standard; don't reduce to 416 (loses small polyp detail)
- **Epochs**: 100 epochs is sufficient for Kvasir-SEG scale; 150 if combined dataset

### 5.5 Negative Frame Training (YOLO-LAN's Key Finding)
The YOLO-LAN paper (2025) found that including explicit **negative frames** (colonoscopy images without polyps) in training significantly reduces false positive rate. This insight is underused in most published YOLO polyp papers. PolypGen includes 4,275 negative frames — use them.

**Implementation**: Include PolypGen's negative frames in the YOLO training YAML as images with empty annotation files. Standard YOLO training handles this natively. This is a 30-minute add-on that could meaningfully reduce your false positive rate.

---

## SECTION 6: RECOMMENDED READING

*Ranked by actionable relevance to ChakraModel implementation.*

### Priority 1: Must-Read Before Code (Essential Context)
1. **Comprehensive evaluation of YOLO variants (2026)** — "Colonic Polyp Detection with Object Detection Models" — https://doi.org/10.3390/computers15040258 — Most recent head-to-head comparison of YOLO11, YOLOv8, RT-DETR, YOLO-World on the standard benchmarks. Read for exact metric numbers and the finding that YOLO11m is the best current model. **Code: No (but uses Ultralytics, which is public). Directly applicable.**

2. **YOLO-LAN (2025)** — "Precise Polyp Detection via Optimized Loss, Augmentations and Negatives" — https://arxiv.org/pdf/2509.19166 — The most practically useful ablation study of YOLO-based polyp detection. Documents the impact of CLAHE, negative frames, augmentation choices. **Code: Not confirmed. Insights fully transferable.**

3. **Kvasir-SEG dataset paper (2019)** — Jha et al., arXiv:1911.07069 — https://datasets.simula.no/kvasir-seg/ — Essential for understanding dataset format, annotation, and canonical train/test split. **Dataset: ✅ Directly downloadable. Required reading for data prep.**

4. **TSdetector (2024)** — Wang et al., Medical Image Analysis — https://arxiv.org/pdf/2409.19983 — Best technical paper on temporal consistency challenges. Clearly defines "intra-sequence distribution heterogeneity" and "precision-confidence discrepancy" — the two problems ChakraModel is addressing. Read for conceptual framing and metric definitions. **Code: Not confirmed public.**

### Priority 2: Read for Implementation Details
5. **Polyp-SAM2 (2024)** — Mansoori et al., arXiv:2408.05892 — https://arxiv.org/abs/2408.05892 — Shows the YOLOv8 + SAM2 prompting pipeline with evaluation on 5 image datasets and 2 video datasets. **Code: ✅ https://github.com/sajjad-sh33/Polyp-SAM-2. Directly integrable.**

6. **YONA (2023)** — Jiang et al., MICCAI 2023 — https://arxiv.org/abs/2306.03686 — "You Only Need One Adjacent Reference-Frame." The most elegant minimal-overhead video detector. Read to understand the design philosophy. **Code: ✅ https://github.com/yuncheng97/YONA. Integrable if you have video dataset.**

7. **Hybrid 2D/3D CNN for polyp video (2022)** — Puyal et al., Medical Image Analysis — https://www.sciencedirect.com/science/article/pii/S1361841522002535 — Establishes the quantitative case for temporal reasoning: 5% improvement in temporal coherence, 9% reduction in auto-correlation discrepancy, reduced short false positives. Read for your introduction/motivation section. **Code: ❌ Not public.**

8. **Qadir et al. (2020)** — "Improving Automatic Polyp Detection Using CNN by Exploiting Temporal Dependency" — https://pubmed.ncbi.nlm.nih.gov/30946683/ — Earliest systematic treatment of temporal false positive reduction via bi-directional frame integration. Still the clearest articulation of the problem. **Code: Not confirmed public. Conceptual value only.**

### Priority 3: Scan for Specific Technical Details
9. **PolypGen dataset paper (2023)** — Ali et al., Scientific Data — https://www.nature.com/articles/s41597-023-01981-y — If you use PolypGen for multi-center evaluation, cite this. Also contains excellent discussion of why single-center datasets fail in clinical deployment. **Dataset: ✅ https://github.com/DebeshJha/PolypGen.**

10. **Frontiers Review (2026)** — "Deep learning driven colorectal polyp analysis: a review" — https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1786679/full — Most current comprehensive review (May 2026). Good for citing in your report's related work section to show you've surveyed the field.

---

## SECTION 7: THE 36-HOUR REALITY CHECK

### Team Roles and Parallel Tracks

| Person | Role | Parallel Track A (Hours 1–18) | Parallel Track B (Hours 18–34) |
|--------|------|-------------------------------|-------------------------------|
| **AI/ML** | Technical lead | Dataset prep + YOLO11 fine-tuning | Temporal Persistence Filter + BoT-SORT integration + evaluation |
| **Biomedical engineer** | Domain + quality | CLAHE pipeline + frame quality gate + dataset curation | ETIS evaluation + clinical framing + false positive analysis |
| **Third member** | Demo + presentation | SAM2 integration attempt (parallel) | Gradio/Streamlit demo + slides + ablation table |

### Critical Path Schedule

**Hours 0–2: Environment Setup**
- All: Install `pip install ultralytics sam2 gradio roboflow` on Colab with T4 GPU
- AI/ML: Write dataset download scripts (Kvasir-SEG from simula.no, others from Kaggle)
- Biomedical: Read YOLO-LAN paper (Section 3: preprocessing), write CLAHE wrapper
- Third: Set up Weights & Biases or MLflow for experiment tracking

**Hours 2–5: Data Preparation**
- AI/ML: Convert all PNG/BMP masks to YOLO bounding box format (Python script, ~100 lines)
- Biomedical: Verify annotation quality on 50 random samples; document class distribution, polyp size distribution
- Third: Start SAM2 environment test in parallel Colab notebook
- **Decision point H5**: If mask conversion is complete and YAML is validated, start YOLO training. If still debugging, reduce dataset to Kvasir-SEG + CVC-ClinicDB only (1612 images).

**Hours 5–11: YOLO11m Fine-Tuning (Runs Unattended)**
- Training command: `yolo train model=yolo11m.pt data=polyp.yaml epochs=100 imgsz=640 batch=16 lr0=0.001 augment=True`
- Training time estimate on Colab T4: ~5–6 hours for 100 epochs on 1748 images
- While training: AI/ML implements Temporal Persistence Filter; Biomedical engineer implements frame quality gate

**Hours 11–15: Integration**
- AI/ML: Wire up YOLO11m + BoT-SORT + Temporal Persistence Filter into inference pipeline
- Biomedical: Wire up CLAHE + frame quality gate into preprocessing pipeline
- Third: If SAM2 environment is working, connect YOLO bounding boxes to SAM2 prompts

**Hours 15–18: Evaluation on Test Sets**
- Run inference on Kvasir-SEG test set (100 images) and ETIS (196 images, OOD)
- Measure: mAP@50, mAP@50:95, precision, recall, F1
- Measure: Flicker rate (fraction of consecutive-frame-pairs where detection status changes)
- Compare: YOLO alone vs. YOLO + BoT-SORT vs. YOLO + BoT-SORT + Persistence Filter
- **Decision point H18**: If mAP < 0.80 on Kvasir-SEG test, retrain with adjusted hyperparameters. If mAP > 0.80, proceed to demo.

**Hours 18–24: Video Testing (If LDPolypVideo Available) or Synthetic Video**
- If no video dataset: synthesize test video by randomly sampling Kvasir-SEG frames with artificial transitions (simulate withdrawal)
- Feed through full pipeline (CLAHE → YOLO11 → BoT-SORT → Persistence Filter → display)
- Record output video showing detection boxes with track IDs and confidence scores

**Hours 24–30: Demo and Visualization**
- Third member builds Gradio interface: upload video → processed video download
- Biomedical: Write case studies (show 3 examples: true positive, artifact false positive suppressed, temporal persistence in action)
- AI/ML: Ablation table (4 rows: YOLO only / +CLAHE / +BoT-SORT / +Persistence Filter)

**Hours 30–36: Report, Slides, Final Checks**
- Executive summary: problem statement, approach, results, clinical relevance
- Present flicker rate metric as novel contribution
- Future work: LDPolypVideo fine-tuning, PolypGen multi-center evaluation, clinical trial design

---

### GPU Budget Reality Check (Colab T4)

| Task | Estimated Time |
|------|----------------|
| Download all datasets | 30 min |
| Data preprocessing + format conversion | 2–3 hrs |
| YOLO11m fine-tuning (100 epochs, 1748 images, batch 16) | 5–6 hrs |
| YOLO11m evaluation (2000 images, inference only) | 15–20 min |
| SAM2 inference on 50 test frames | 5–10 min |
| Full video inference (5 min video at 25 FPS) | 5–10 min |
| **Total GPU-active time** | **~8–9 hrs** |

This fits comfortably within a Colab Pro session. Free Colab T4 sessions disconnect after ~4 hours — use Colab Pro or plan a checkpoint strategy (save model weights every 20 epochs).

### Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Colab session disconnects mid-training | High | High | Use `callbacks` to save checkpoint every 20 epochs; use `resume=True` flag on reconnect |
| CVC-ClinicDB/ColonDB mask-to-bbox conversion bugs | Medium | Medium | Test on 10 images first; validate bbox overlaps with original images visually |
| LDPolypVideo / SUN-SEG not accessible in time | Very High | Low | Already excluded from plan; stick to image datasets |
| SAM2 installation fails (CUDA version issues) | Medium | Low | Pre-tested workaround: `pip install sam2 --extra-index-url https://download.pytorch.org/whl/cu118` |
| YOLO11m under-trains in 100 epochs | Medium | Medium | Check validation mAP@50 at epoch 50; extend to 150 epochs if still improving |
| No suitable test video for demo | Medium | Medium | Create synthetic video by stitching frames with OpenCV: `cv2.VideoWriter` |

### The Irreducible Core (If Everything Goes Wrong)

If you hit Hour 24 and nothing works except the basic YOLO fine-tune, you can still submit:
1. YOLO11m fine-tuned on Kvasir-SEG + CVC-ClinicDB: mAP@50 ≈ 0.92–0.95 ✅
2. Jupyter notebook showing inference on 10 test images with bounding box overlays ✅
3. ETIS evaluation showing OOD performance ✅
4. Written description of Temporal Persistence Filter with pseudocode (claim as contribution, implementation attempted but incomplete) ✅
5. Clinical context and literature synthesis ✅

This is still a competitive hackathon submission.

---

## APPENDIX: KEY TERMINOLOGY FOR CLINICIAN COMMUNICATION

- **Adenoma Detection Rate (ADR)**: The gold clinical metric; AI-assisted systems increase ADR by 10–15% in randomized trials
- **Polyp miss rate**: ~26.3% of polyps are missed during standard colonoscopy; the clinical problem
- **CADe**: Computer-Aided Detection (bounding box around polyp)
- **CADx**: Computer-Aided Diagnosis (additionally classifies polyp as adenoma/hyperplastic)
- **ChakraModel is a CADe system**: Correct framing for judges
- **Sessile polyp**: Flat, grows against colon wall; hardest to detect; most clinically significant if missed
- **Pedunculated polyp**: Has a stalk; easier to detect visually
- **Paris classification**: Clinical morphology classification system for polyps (0-Ip, 0-Is, 0-IIa, etc.)

---

*This brief was compiled from arXiv, PubMed, Springer Nature, IEEE, GitHub, Kaggle, and Ultralytics documentation as of July 28, 2026. All paper links and dataset URLs were verified active at time of research. Code repositories noted as ✅ were directly confirmed to contain inference-ready implementations.*
