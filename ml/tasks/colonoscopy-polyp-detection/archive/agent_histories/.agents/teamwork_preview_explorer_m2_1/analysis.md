# ChakraModel Architectural & Theoretical Audit Report

**Auditor:** Explorer 2 (Code Architecture & Theory Auditor)  
**Date:** 2026-09-07  
**Scope:** `m:\chakramodel` codebase, research papers, reports, notebooks, and model checkpoints  
**Objective:** Unflinchingly honest, forensic investigation of the gap between theoretical claims made in research papers, architecture markdown, and project pitch decks versus actual executable implementations.

---

## Executive Summary

A comprehensive architectural audit of the **ChakraModel** repository reveals a dramatic dichotomy between high-level academic/pitch claims and the underlying executable code. 

1. **Topological Loss via Persistent Homology**: Although a persistent homology loss class utilizing the `gudhi` library exists in `src/topo_loss.py`, it was **completely disabled** in the training loop (`src/chakra_transformer/train_transformer.py`) due to crippling CPU execution times (~several minutes per 384×384 image). The earlier "Combo 2" implementation relied on heuristic OpenCV contour area thresholding, which ignored ground truth. In the final paper, the authors conceded that topological loss is strictly a "theoretical proposal / future work" and not part of the evaluated pipeline.
2. **Conformal Calibration & Statistical Safety**: While marketed as providing distribution-free 95% risk-controlling prediction sets with epistemic uncertainty modeling via MC Dropout, the actual runtime implementation in `app.py` and `src/chakranet_segmenter.py` reduces to **deterministic static dual-thresholding** (`prob >= 0.4785` for outer mask, `prob > 0.5542` for inner mask). MC Dropout variance collapsed to zero (`mean_uncertainty = 2.85e-15`) because dropout layers were frozen in evaluation mode in the ViT-Large backbone.
3. **ChakraSLAM / Endo-SLAM**: There is **zero SLAM implementation** in the repository. No visual odometry, camera pose tracking, 3D point cloud generation, or 3D coordinate spatial memory exists. What was branded as "ChakraSLAM" and "temporal persistence" is actually a **2D bounding-box smoothing heuristic** (`src/temporal/tracker.py`) layered over Ultralytics ByteTrack (a rolling N-of-M confirmation window, 8-frame box hold on occlusion, and EMA smoothing).
4. **Hybrid Detection & Crop Degradation**: The initial hybrid pipeline (cropping YOLO bounding boxes and squashing them to 384×384) suffered from a catastrophic "Crop-and-Forward Degradation" bug that dropped Dice scores to ~0.45 DSC. While context padding (50% margin) and letterboxing restored segmentation accuracy to ~0.86–0.92 DSC, executing a 309M parameter ViT-Large per crop throttled the pipeline to **3.7 FPS**, violating real-time clinical requirements (<50ms / >20 FPS) by nearly an order of magnitude.
5. **Federated Learning (Combo 5)**: Represented only by a 76-line standalone utility (`fl_non_iid_partitioner.py`) that samples Dirichlet distributions over mock integer labels, and a deprecated demo notebook running FedAvg across local folders on a toy 3-layer CNN (`SimplePraNet`). It is completely detached from the core production pipeline and absent from the final evaluation.
6. **Production Architecture & SOTA Context**: The actual runtime engine is **YOLOv8n (nano, ~3.2M params, 6.2MB weights, mislabeled as YOLOv8x in training scripts)** coupled with **ChakraTransformer (ViT-Large `vit_large_patch16_384` + 2 transpose-convolution layers, 309.17M params)**, evaluated alongside rule-based geometric Paris classification (`ParisClassifier`). FCBFormer is **not** part of any ensemble; the `fcbformer/` folder is merely the unpacked arXiv LaTeX source of the competing baseline paper by Sandler et al.

---

## Rigorous Claim vs. Code Verification Table

| Claimed Component | Claimed Functionality | Where Mentioned (Paper/MD) | Actual Code Found | Integration Status | Verdict & Technical Analysis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Topological Polyp Loss (TPL)** | Differentiable persistent homology loss enforcing Betti number constraints ($\beta_0=1, \beta_1=0$) in model weight space. | `ChakraModel_Final_Paper.md` (§3.2, §5.5), `ARCHITECTURE-SPINE.md` (§AD-05), `ChakraModel_Project_Journey.md` | `src/topo_loss.py`, `src/chakra_transformer/train_transformer.py` (lines 87–90), `src/run_topo_ablation.py`, `notebooks/deprecated/Combo2_Topo_ChakraNet.ipynb` | **Standalone Prototype / Disabled in Training** | **Aspiration/Concept (Not in production).** Early Combo 2 used `cv2.connectedComponentsWithStats` to zero secondary components without ground truth. `src/topo_loss.py` uses `gudhi.CubicalComplex`, but was disabled in `train_transformer.py` because CPU persistence on 384×384 grids hung training. Paper admits TPL was never evaluated. `oa_topo_loss.json` and `pr_topo_loss.json` are merely literature search JSON dumps. |
| **Conformal Calibration** | Distribution-free uncertainty quantification guaranteeing $\ge 95\%$ coverage ($\alpha=0.05$) via MC Dropout variance and RCPS. | `ChakraModel_Final_Paper.md` (§3.3, §5.4), `conformal_prediction_report.md`, `ARCHITECTURE-SPINE.md` (§AD-04) | `src/conformal_calibration.py`, `conformal_evaluator.py`, `create_conformal_notebook.py`, `src/chakranet_segmenter.py` (lines 393–402), `app.py` | **Standalone Prototype / Degenerated in Pipeline** | **Theoretical / Mocked in Runtime.** MC Dropout variance collapsed to $2.85 \times 10^{-15}$ (frozen dropout in eval mode). In `app.py` and `chakranet_segmenter.py`, conformal calibration reduces to fixed static thresholds (`prob >= 0.4785` and `prob > 0.5542`). `conformal_evaluator.py` only computes standard ECE and Brier score. `create_conformal_notebook.py` uses morphological dilation (`binary_dilation`), not risk-controlling prediction sets. |
| **ChakraSLAM / Endo-SLAM** | Real-time visual odometry / SLAM estimating 3D camera trajectory and logging 3D coordinates of low-confidence polyp detections during insertion for withdrawal verification. | `ARCHITECTURE-SPINE.md` (§AD-03), `ChakraModel_Final_Paper.md` (§1.1, §3.4), `ChakraModel_Pitch_Deck` | `src/temporal/tracker.py`, `temporal_persistence.py`, `src/temporal/persistence.py`, `src/temporal/persistence_filter.py` | **Not Implemented (Pure Fiction)** | **Completely Unimplemented.** Zero SLAM, 3D pose, depth, or point cloud code exists. `ARCHITECTURE-SPINE.md` AD-03 explicitly admits: *"no implementation of Endoscopic SLAM or 3D spatial coordinate tracking in src/"*. `oa_endo_slam.json` is an OpenAlex literature search. The actual implementation is `ChakraTemporalTracker`: 2D ByteTrack box holding (8 frames), rolling window confirmation (3 of 5 frames), and EMA confidence smoothing. |
| **Hybrid Crop / Multi-Stage Detection** | Decoupled 2-stage inference: high-speed YOLO detection proposals refined by ViT-Large inside the bounding box ROI. | `ARCHITECTURE-SPINE.md` (§AD-02), `ChakraModel_Final_Paper.md` (§3.1), `REPORT.txt` | `src/hybrid_refine.py`, `hybrid_crop_validation.py`, `rigorous_hybrid_validation.py`, `src/chakranet_segmenter.py`, `kaggle_hardened_pipeline.py` | **Integrated (Severely Latency-Bottlenecked)** | **Functionally Working but Fails Latency.** Initial implementation (`hybrid_refine.py`) used generic COCO Faster R-CNN. Later YOLO + ViT-Large suffered from severe aspect-ratio squashing ("Crop-and-Forward Degradation", ~0.45 DSC). Fixed with 50% context padding and letterboxing (~0.86–0.92 DSC). However, running 309M param ViT-Large on crops runs at **3.7 FPS**, failing clinical real-time (<50ms) requirements. |
| **Federated Learning (Combo 5)** | Multi-hospital decentralized training (FedAvg) preserving privacy (GDPR/HIPAA) under severe Non-IID Dirichlet domain shifts. | `ChakraModel_Project_Journey.md`, `notebooks/deprecated/Combo5_Federated_ChakraNet.ipynb` | `fl_non_iid_partitioner.py`, `notebooks/deprecated/combo5_federated_colab.py` | **Standalone Prototype (Deprecated)** | **Toy Script / Abandoned.** `fl_non_iid_partitioner.py` is a 76-line utility sampling Dirichlet splits on mock label arrays. `combo5_federated_colab.py` runs FedAvg on a toy 3-layer `SimplePraNet` (ResNet-34 partial) across local folders. Completely absent from `src/`, production runtime, and `ChakraModel_Final_Paper.md`. Deprecated per `ARCHITECTURE-SPINE.md`. |
| **Main Pipeline & Production Architecture** | Unified Edge-Native Hybrid pipeline with YOLOv8x detector + FCBFormer / ChakraTransformer cascade + Paris morphological staging. | `README.md`, `ARCHITECTURE-SPINE.md`, `app.py`, `kaggle_wrapper_v5.ipynb`, `kaggle_wrapper_v6.ipynb` | `app.py`, `src/infer_stream.py`, `src/chakranet_segmenter.py`, `src/paris_classifier.py`, `weights/best.pt`, `weights/chakra_transformer_best.pth` | **Integrated** | **Partially Genuine / Mislabeled Components.** Runtime uses fine-tuned **YOLOv8n (nano, 6.2MB, mislabeled as yolov8x)** + `ChakraNetMicroRefiner` (ViT-Large `vit_large_patch16_384` + 2 transpose-conv layers, 309.17M params). FCBFormer is **not** an ensemble component (`fcbformer/` is the unpacked arXiv LaTeX source of Sandler et al.). `ParisClassifier` is a deterministic rule-based aspect-ratio/solidity heuristic, not ML. |

---

## Detailed Investigation Across 6 Focus Areas

### 1. Topological Loss via Persistent Homology

#### 1.1 The Theoretical Claim
The ChakraModel final paper (§3.2) and architectural documentation assert:
> "By building a cubical complex filtration over the predicted probability map, one could track the birth and death of topological features (components $\beta_0$ and holes $\beta_1$)... dynamically extract the true Betti numbers from the ground truth... force the network to natively learn the correct anatomical topology directly in the weight space."

#### 1.2 Forensic Code Inspection
An inspection of all topological loss code reveals a four-stage evolution:
1. **The Heuristic OpenCV Phase (`Combo2_Topo_ChakraNet.ipynb`, lines 782–830)**:
   ```python
   class TopologicalLoss(nn.Module):
       def _compute_betti_losses(self, prob_map):
           binary = (prob_map.detach() > 0.5).cpu().numpy().astype(np.uint8)
           n_cc, labels_cc, stats_cc, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
           if n_cc > 2:
               # suppresses all components except the largest
   ```
   *Forensic Verdict*: This is **not persistent homology**. It is simple thresholding at 0.5 and heuristic OpenCV connected component suppression. It completely ignores the ground truth target; if the image contains multiple true polyps, it actively penalizes valid detections.
2. **The GUDHI Cubical Complex Implementation (`src/topo_loss.py`, lines 45–97)**:
   A persistent homology module was implemented using the C++/Python `gudhi` library:
   ```python
   prob_np = prob_map.detach().cpu().numpy()
   filtration = (1.0 - prob_np).flatten()
   cc = gudhi.CubicalComplex(dimensions=prob_np.shape, top_dimensional_cells=filtration)
   cc.compute_persistence()
   cofaces = cc.cofaces_of_persistence_pairs()
   ```
3. **The Training Reality (`src/chakra_transformer/train_transformer.py`, lines 84–90)**:
   When the team attempted to train the ViT-Large model with this loss, GUDHI CPU persistence calculations on $384 \times 384$ grids (147,456 cells) froze execution, taking several minutes per single batch. As documented in the commit history and verified in the source:
   ```python
   logits = model(imgs)
   loss_dice = criterion_dice(logits, masks)
   # Topological Loss is disabled in the main training loop (future work)
   # as it causes extreme slowdowns on 384x384 feature maps.
   loss = loss_dice
   loss.backward()
   ```
4. **The Synthetic Ablation Toy (`src/run_topo_ablation.py`)**:
   The only script that executes `TopologicalLoss` is `src/run_topo_ablation.py`, which optimizes an artificial $64 \times 64$ tensor initialized with two synthetic circles against a ground-truth single circle for 15 iterations. No ablation was ever executed on Kvasir-SEG, CVC-ClinicDB, or colonoscopy data.
5. **Search Dumps**: `oa_topo_loss.json` (OpenAlex) and `pr_topo_loss.json` (arXiv) are simply JSON search caches from API calls searching for literature on "topological loss Betti numbers persistent homology".

#### 1.3 Conclusion on Topological Loss
**Topological Loss is an unintegrated research concept.** It was never used to train the production weights (`chakra_transformer_best.pth`).

---

### 2. Conformal Calibration & Statistical Safety

#### 2.1 The Theoretical Claim
The project claims:
- RCPS-style conformal risk control (Bates et al., 2021) with guaranteed 95% pixel-wise coverage ($\alpha=0.05$).
- Epistemic uncertainty modeling via 16 stochastic Monte Carlo Dropout passes ($s^+ = 1 - (\bar{p} + \sigma^2)$).
- Avoidance of false positives on mucosal artifacts and surgical tools.

#### 2.2 Forensic Code Inspection
1. **MC Dropout Variance Collapse**:
   In `results/combo1_metrics.json`, the logged uncertainty is:
   $$\text{mean\_uncertainty} = 2.85 \times 10^{-15}$$
   This is numerically zero. During evaluation, standard PyTorch `model.eval()` freezes all dropout layers. Because `timm` ViT-Large models encapsulate dropout within `DropPath` and internal blocks, running multiple passes through `model.eval()` executes identical deterministic forward passes.
2. **The Calibrated Thresholds (`weights/conformal_calibration.json`)**:
   ```json
   {
     "q_hat_pos": 0.521484375,
     "q_hat_neg": 0.55421875,
     "alpha": 0.05,
     "mc_passes": 16,
     "n_calibration_images": 100
   }
   ```
3. **Runtime Implementation (`src/chakranet_segmenter.py`, lines 393–402)**:
   In the actual inference pipeline and `app.py`:
   ```python
   if conformal and q_hat_pos is not None and q_hat_neg is not None:
       score_pos = 1.0 - prob_resized
       score_neg = prob_resized
       include_pos = (score_pos <= q_hat_pos)
       include_neg = (score_neg <= q_hat_neg)
       outer_mask = include_pos.astype(np.uint8) * 255
       inner_mask = (include_pos & (~include_neg)).astype(np.uint8) * 255
       extras = {"inner": inner_mask, "outer": outer_mask, "unc": None}
   ```
   Substituting `q_hat_pos = 0.521484` and `q_hat_neg = 0.554219`:
   $$\text{outer\_mask} = (\text{prob\_resized} \ge 1.0 - 0.521484) \implies \text{prob} \ge 0.4785$$
   $$\text{inner\_mask} = (\text{prob} \ge 0.4785) \land \neg(\text{prob} \le 0.5542) \implies \text{prob} > 0.5542$$
   Notice that `unc` is hardcoded to `None`. The complex "conformal prediction set" reduces to **static deterministic thresholding at 0.48 and 0.55**.
4. **Notebook Discrepancy (`create_conformal_notebook.py`)**:
   In `create_conformal_notebook.py` (lines 240–245), conformal calibration is attempted via OpenCV morphological dilation:
   ```python
   outer_mask = binary_dilation(inner_mask, iterations=lambda_hat).astype(np.uint8)
   ```
   This is standard morphological dilation, not mathematical prediction set risk control.
5. **Evaluator Reality (`conformal_evaluator.py`)**:
   The script contains only standard binary classification Expected Calibration Error (ECE) and Brier Score calculations on flattened arrays.

#### 2.3 Conclusion on Conformal Calibration
**Conformal Calibration is a standalone prototype that degenerates into static dual-thresholding in production.** The mathematical guarantees of epistemic uncertainty coverage do not hold because MC Dropout was inactive during evaluation.

---

### 3. ChakraSLAM / Endo-SLAM & Temporal Persistence

#### 3.1 The Theoretical Claim
`ARCHITECTURE-SPINE.md` (§AD-03) and `ChakraModel_Final_Paper.md` (§3.4) claim:
> "ChakraSLAM aims to integrate spatial memory by logging the 3D coordinates of low-confidence YOLO predictions... during the insertion phase. Using visual odometry, these coordinates would persist in a spatial memory matrix. During the withdrawal phase, the UI would alert the clinician to re-examine these exact coordinates..."

#### 3.2 Forensic Code Inspection
1. **Complete Absence of SLAM**:
   A comprehensive regex search across all directories (`src/`, `notebooks/`, root) for SLAM terms (`ORB-SLAM`, `visual odometry`, `pose`, `depth`, `camera_matrix`, `solvePnP`, `epipolar`, `bundle adjustment`) reveals **zero SLAM implementation**.
2. **Explicit Internal Concessions**:
   In `ARCHITECTURE-SPINE.md` lines 43–45:
   > "⚠ Status: This architectural decision describes a proposed design. As of 2026-09-04, there is **no implementation** of Endoscopic SLAM or 3D spatial coordinate tracking in `src/`. ByteTrack 2D temporal tracking is implemented in `infer_stream.py`; the 3D memory layer is not."
   In `ChakraModel_Final_Paper.md` line 99:
   > "*Note: This section describes a conceptual extension planned for future work...*"
3. **What Actually Exists (`src/temporal/tracker.py`, `temporal_persistence.py`)**:
   The temporal persistence subsystem is an engineering wrapper around Ultralytics ByteTrack:
   - **`ChakraTemporalTracker`** (`src/temporal/tracker.py`):
     - Tracks 2D bounding boxes across frames using `bytetrack.yaml`.
     - **Confirmation Gate**: Requires detection in $\ge 3$ of the last 5 frames (`confirm_n=3, confirm_m=5`) before confirming an alert.
     - **Occlusion Hold**: Holds the last known 2D box for up to 8 frames (`max_hold_frames=8`) if missed due to brief blur.
     - **EMA Smoothing**: Applies Exponential Moving Average ($\alpha=0.4$) to confidence scores and box coordinates.
     - **Doubt Tracking**: Simply stores the 2D frame index (`doubt_events: List[int]`) where a box had low confidence ($0.25 \le \text{conf} < 0.35$). There are no 3D spatial coordinates.

#### 3.3 Conclusion on ChakraSLAM
**ChakraSLAM is 100% conceptual future work / pitch deck fiction.** The actual executable code is a well-engineered 2D bounding-box smoothing and holding state machine.

---

### 4. Hybrid Crop & Multi-Stage Detection

#### 4.1 Evolution of the Hybrid Concept
1. **Phase 1: Faster R-CNN Refiner (`src/hybrid_refine.py`)**:
   The earliest multi-stage code used YOLO for proposals and torchvision's `fasterrcnn_resnet50_fpn_v2(weights="DEFAULT")` for refinement. Critically, line 31 loaded default COCO weights (trained on 80 common objects like cars, people, and dogs), which was entirely unsuited for polyps.
2. **Phase 2: YOLO + ChakraTransformer (`src/chakranet_segmenter.py`, `hybrid_crop_validation.py`)**:
   The architecture transitioned to YOLOv8 for detection proposals, cropping the detected bounding box and passing it to `ChakraTransformerSegmenter` (ViT-Large).

#### 4.2 The "Crop-and-Forward Degradation" Bug
When the two-stage pipeline was first tested, it suffered severe performance collapse:
- Direct full-image ViT-Large segmentation: **~0.86–0.92 DSC**.
- YOLO cropped-and-forwarded segmentation: **plunged to ~0.45 DSC**.
- **Root Cause**: Bounding box crops were tightly sliced (`frame[y1:y2, x1:x2]`) and resized directly to $384 \times 384$ without aspect-ratio preservation. This distorted non-square polyps and stripped surrounding healthy mucosa context required by the transformer.
- **The Remediation (`hybrid_crop_validation.py`, `rigorous_hybrid_validation.py`)**:
  - Implemented `context_pad_bbox` with `pad_ratio=0.5` (50% margin around box).
  - Implemented `pad_to_square_then_resize` (letterbox padding with reflection or zero fill) and `unletterbox`.
  - Recovered performance back to **~0.866 DSC** on Kvasir-SEG test splits.

#### 4.3 The Clinical Latency Bottleneck
In `rigorous_hybrid_validation.py` (lines 181–220) and `ChakraModel_Final_Paper.md` (§3.1):
- Standalone YOLOv8 detection runs at **94.7 FPS** (latency ~10.5 ms).
- Integrated YOLOv8 + ChakraTransformer pipeline runs at **3.7 FPS** (latency ~270 ms).
- Clinical intervention requires real-time processing at **$<50$ ms ($\ge 20$ FPS)**. The hybrid pipeline is **7× too slow** for live clinical streaming on the evaluation hardware (RTX 3050 Laptop GPU, 4GB VRAM).

#### 4.4 PySODMetrics (`sod.py`, `sod2.py`)
`sod.py` and `sod2.py` are copies of the `PySODMetrics` library implementing standard academic salient object detection metrics ($F_\beta$, $S_\alpha$, $E_\phi$, $\text{wF}$, MAE). They are correctly implemented benchmark utilities.

---

### 5. Federated Learning & Non-IID Partitioner

#### 5.1 The Theoretical Claim
The project journey documents claim multi-hospital federated learning across international centers (Norway, Spain, France) with Dirichlet Non-IID robustness under GDPR/HIPAA compliance.

#### 5.2 Forensic Code Inspection
1. **`fl_non_iid_partitioner.py`**:
   A 76-line utility with a single static method `partition_dirichlet`:
   - It takes an array of dataset indices and mock class labels, samples Dirichlet proportions ($\text{Dir}(\alpha)$), and splits indices into client lists.
   - The test script generates 1000 dummy samples with 70% class 0 and 30% class 1.
   - It does not load or process medical images, does not interface with PyTorch models, and does not execute federated aggregation.
2. **`notebooks/deprecated/combo5_federated_colab.py` / `Combo5_Federated_ChakraNet.ipynb`**:
   - Contains a rudimentary NumPy-based FedAvg simulation across 3 local directory paths (`Hospital_A_Norway`, `Hospital_B_Spain`, `Hospital_C_France`).
   - Uses `SimplePraNet`, a toy network utilizing only the first two stages of ResNet-34 and 3 conv layers (not ViT-Large or full ResNet-101).
   - Moved to `notebooks/deprecated/` and officially abandoned per `ARCHITECTURE-SPINE.md` lines 64–66.
   - Completely omitted from `ChakraModel_Final_Paper.md`.

#### 5.3 Conclusion on Federated Learning
**Federated Learning was an early hackathon concept that was abandoned and never integrated into the core architecture.**

---

### 6. Main Pipeline & Production Architecture

#### 6.1 Weight Inspection & Hardware Reality
An audit of `weights/` and checkpoint keys via `count_params.py` and `inspect_checkpoints.py` reveals:
- **`weights/best.pt`**: File size is **6.2 MB**.
  - This corresponds to **YOLOv8n (nano)**, which has ~3.2M parameters.
  - In `src/train_yolo.py`, line 6 states: `model = YOLO("yolov8n.pt")`, yet the run name was set to `name="polyp_yolov8x"`.
  - The model loaded in `app.py` is YOLOv8n, not YOLOv8x.
- **`weights/chakra_transformer_best.pth`**: File size is **1.23 GB**.
  - Total parameters: **309,174,379 (~309.17M params)**.
  - Architecture: `vit_large_patch16_384` (ImageNet-21k pretrained) + 2 transpose-convolution decode stages.
- **`weights/yolov8x.pt`**: 136.8 MB (87M params), present in root and `src/`, but is the un-finetuned stock COCO pretrained model.

#### 6.2 The FCBFormer Confusion
- A directory named `fcbformer/` exists in the repository root.
- Code review shows that `fcbformer/` is **not** model code or an ensemble component. It contains `main.tex`, `Paper.bib`, `llncs.cls`, and figures (`FCBformer.png`, `cju77t...jpg`) extracted from `fcbformer_source.tar.gz`.
- This is the unpacked arXiv LaTeX source of the 2022 MICCAI paper *"FCBFormer: Fine-Grained Complete Boundary-Aware Transformer for Polyp Segmentation"* by Sandler et al., downloaded to extract comparison tables and metrics for literature benchmarking.

#### 6.3 Paris Morphological Classification (`src/paris_classifier.py`)
Marketed as "automated Paris classification for surgical staging":
- Code inspection reveals it is a **purely handcrafted geometric heuristic** based on bounding box aspect ratio and OpenCV contour circularity/solidity:
  - If $\text{aspect\_ratio} \ge 1.35$ and $\text{solidity} < 0.85 \implies$ **Type 0-Ip (Pedunculated)**
  - If $\text{aspect\_ratio} \le 0.55 \implies$ **Type 0-IIa (Flat Elevated)**
  - Else $\implies$ **Type 0-Is (Sessile)**
  - Physical millimeter sizing is estimated using a hardcoded constant: $\text{diameter} = \text{max}(w, h) \times 0.085\text{ mm}$.
- No deep learning model is used for Paris classification.

#### 6.4 Actual Runtime Execution Flow (`app.py` / `src/infer_stream.py`)
When a user launches `app.py` or `src/infer_stream.py`, the actual execution pipeline is:
1. **Video Ingestion**: Reads frames from webcam or video file.
2. **Quality Gate Filter**: OpenCV heuristics check Laplacian variance ($<80 \implies$ blur) and average brightness ($<30$ or $>220 \implies$ glare/occlusion).
3. **Stage 1 Detection & Tracking**: Runs YOLOv8n with Ultralytics `bytetrack.yaml` tracker (`conf=0.25`).
4. **Temporal State Machine**: `ChakraTemporalTracker` requires 3 detections within 5 frames before confirming a polyp, and persists the box for 8 frames during dropouts with EMA smoothing.
5. **Stage 2 ROI Crop**: Crops the confirmed polyp with 50% context padding and letterbox resizing to $384 \times 384$.
6. **Segmentation**: `ChakraNetMicroRefiner` (ViT-Large) generates the probability map.
7. **Conformal Flag**: If enabled, applies static thresholds (`prob >= 0.4785` and `prob > 0.5542`).
8. **Morphological Classification**: `ParisClassifier` runs aspect-ratio rules to assign a Paris category and recommended resection technique.
9. **Display Overlay**: Draws bounding box, segmentation contour, and Paris badge on the output video stream.

---

## Architectural Synthesis

```
                                CHAKRAMODEL ARCHITECTURE REALITY
                                
   CLAIMED THEORETICAL ARCHITECTURE                    ACTUAL EXECUTABLE CODEBASE
   ────────────────────────────────                    ──────────────────────────
   1. Endoscopic SLAM (3D Tracking)      ───────►      100% UNIMPLEMENTED (0 lines of SLAM code;
                                                       paper admits conceptual future work)
                                                       
   2. Topological Loss (GUDHI Homology)  ───────►      DISABLED IN TRAINING (gudhi.CubicalComplex
                                                       froze CPU; train_transformer.py commented out)
                                                       
   3. Conformal Safety (MC Dropout)      ───────►      DEGENERATED TO STATIC THRESHOLDS (prob >= 0.48,
                                                       prob > 0.55; MC Dropout variance collapsed to 0)
                                                       
   4. Federated Learning (Fed-ChakraNet) ───────►      STANDALONE TOY PROTOTYPE (fl_non_iid_partitioner.py
                                                       samples mock labels; notebook deprecated)
                                                       
   5. YOLOv8x Detector                   ───────►      YOLOv8n (NANO) (weights/best.pt is 6.2MB,
                                                       3.2M params; mislabeled as yolov8x)
                                                       
   6. Real-Time End-to-End Latency       ───────►      3.7 FPS ON EVAL GPU (ViT-Large 309M params
                                                       on crops causes massive latency bottleneck)
```
