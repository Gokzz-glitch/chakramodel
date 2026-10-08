# Empirical Code & Parameter Challenge Report: `true_docs/`

**Agent**: Challenger 1 (Empirical Code & Parameter Challenger)  
**Date**: 2026-09-07  
**Working Directory**: `m:\chakramodel\.agents\challenger_m4_1`  
**Overall Verdict**: **DOCUMENTATION PASSED EMPIRICAL CHALLENGE** (with 2 minor technical caveats noted)

---

## Challenge Summary

**Overall risk assessment**: **LOW** (Documentation in `true_docs/` is remarkably accurate and rigorously aligned with actual repository artifacts).

The documentation suite in `true_docs/` (`architecture_evolution.md`, `history_and_timeline.md`, `index.md`, `theoretical_claims_vs_code.md`, and `verified_benchmarks_and_metrics.md`) was subjected to adversarial empirical verification against physical weight checkpoints and source code in `m:\chakramodel`.

All five core investigative targets were verified via direct execution of Python test scripts, state dictionary tensor counting, architectural config parsing, and file content inspection:
1. **ChakraTransformer Parameter Count**: Confirmed **309,173,737** weight parameters in `weights/chakra_transformer_best.pth` (rounds to **309.17M** / **309M**).
2. **YOLOv8 Detector Architecture**: Confirmed **YOLOv8n (Nano)** with **3,011,043** parameters in `weights/best.pt`, with `depth_multiple=0.33` and `width_multiple=0.25`. The script `src/train_yolo.py` explicitly instantiates `YOLO("yolov8n.pt")`.
3. **Topological Loss State**: Confirmed **100% disabled** in `src/chakra_transformer/train_transformer.py:L87-90` (`loss = loss_dice`).
4. **ChakraSLAM Status**: Confirmed **100% unimplemented** in `src/`. `src/temporal/tracker.py` is purely a 2D bounding-box smoothing state machine (`ChakraTemporalTracker`). `ARCHITECTURE-SPINE.md:AD-03` explicitly marks ChakraSLAM as `[PROPOSED / FUTURE WORK — NOT IMPLEMENTED]`.
5. **FCBFormer Status**: Confirmed **100% an external LaTeX paper archive** in `fcbformer/` (49 files, all `.tex`, `.bib`, `.bbl`, `.cls`, `.bst`, and figure images; zero executable code).

---

## Detailed Empirical Findings

### 1. ChakraTransformer Parameter Count & Weights Inspection

- **Target Files**: `weights/chakra_transformer_best.pth`, `src/chakra_transformer/transformer_segmenter.py`, `src/chakra_transformer/transformer_segmenter.bak`.
- **Claim Tested**: Is ChakraTransformer actually 309M parameters?
- **Empirical Execution**:
  ```python
  import torch
  ckpt = torch.load('weights/chakra_transformer_best.pth', map_location='cpu')
  sd = ckpt['model_state_dict'] if 'model_state_dict' in ckpt else ckpt
  # Tensor counts
  param_count = sum(p.numel() for k, p in sd.items() if not any(b in k for b in ['running_mean', 'running_var', 'num_batches_tracked']))
  buffer_count = sum(p.numel() for k, p in sd.items() if any(b in k for b in ['running_mean', 'running_var', 'num_batches_tracked']))
  ```
- **Observed Results**:
  - `weights/chakra_transformer_best.pth` file size: **1,236,836,719 bytes** (~1,179.54 MB).
  - Checkpoint tensor count: **312 keys** (all prefixed with `module.`).
  - Trainable weight parameters: **309,173,737** (309.17M).
  - BatchNorm tracking buffers: **642**.
  - Total checkpoint elements: **309,174,379**.
- **Architectural Breakdown**:
  - `timm` Vision Transformer backbone (`vit_large_patch16_384`, 24 blocks, embed_dim=1024, heads=16): **304,715,752 parameters**.
  - Progressive Transpose 2D Decoder head (`decode_head`): **4,457,985 parameters**.
  - Total weights = $304,715,752 + 4,457,985 = \mathbf{309,173,737}$.
- **Technical Caveat (Missing Key)**:
  - In `src/chakra_transformer/transformer_segmenter.py`, line 28 adds a SAM-style prompt encoder: `self.prompt_embedding = nn.Embedding(2, self.embed_dim)` (+2,048 parameters), yielding **309,175,785 parameters**.
  - When loading `weights/chakra_transformer_best.pth` into `ChakraTransformerSegmenter`, PyTorch reports:
    `Missing keys: ['prompt_embedding.weight']`, `Unexpected keys: []`.
  - This proves empirically that `weights/chakra_transformer_best.pth` was trained on the earlier `transformer_segmenter.bak` prior to the prompt embedding addition in commit `55c859b7`.
- **Verdict**: **PASSED**. The claim that ChakraTransformer is a 309M parameter model is verified down to the exact parameter (309,173,737 parameters).

---

### 2. YOLOv8 Detector Architecture & Training Configuration

- **Target Files**: `weights/best.pt`, `src/train_yolo.py`, `outputs/polyp_yolov8x/weights/best.pt`, `yolov8x.pt`.
- **Claim Tested**: Is the fine-tuned detector actually YOLOv8n (nano, ~3.01M params) instead of YOLOv8x?
- **Empirical Execution**:
  ```python
  from ultralytics import YOLO
  yolo = YOLO('weights/best.pt')
  print('Params:', sum(p.numel() for p in yolo.model.parameters()))
  print('YAML:', yolo.model.yaml)
  ```
- **Observed Results**:
  - `weights/best.pt` file size: **6,241,834 bytes** (~5.95 MB).
  - Total parameters: **3,011,043** (3.01M).
  - Total layers: **226**.
  - Classes: `{0: 'polyp'}` (1 class).
  - Architecture configuration: `depth_multiple: 0.33`, `width_multiple: 0.25` (official Ultralytics specification for **YOLOv8n Nano**).
  - `outputs/polyp_yolov8x/weights/best.pt`: Total parameters: **3,011,043**, `depth_multiple: 0.33`, `width_multiple: 0.25`. Contains identical YOLOv8n architecture plus optimizer state (24,485,479 bytes).
  - `src/train_yolo.py`:
    - Line 5 comment: `# Load the pretrained X-Large model (maximum accuracy, hardware not a limit)`
    - Line 6 code: `model = YOLO("yolov8n.pt")`  <-- **Instantiates Nano**
    - Line 15 print: `print("Starting YOLOv8x Training on Colonoscopy Dataset...")`
    - Line 25 argument: `name="polyp_yolov8x"`
  - Upstream `yolov8x.pt` / `src/yolov8x.pt`:
    - File size: **136,890,692 bytes** (~130.55 MB).
    - Total parameters: **68,229,648** (68.23M).
    - Classes: 80 COCO classes (`person`, `bicycle`, `car`...).
    - Zero polyp fine-tuning.
- **Verdict**: **PASSED**. The trained detector is definitively YOLOv8n (3,011,043 params). The directory and script naming `polyp_yolov8x` was an empirical mislabeling, as accurately reported in `true_docs/`.

---

### 3. Topological Loss Training Loop Deactivation

- **Target Files**: `src/chakra_transformer/train_transformer.py:L87-90`, `src/topo_loss.py`, `src/run_topo_ablation.py`.
- **Claim Tested**: Is Topological Loss genuinely disabled in the training loop?
- **Empirical Execution & Code Inspection**:
  - In `src/chakra_transformer/train_transformer.py`:
    - L17: `from topo_loss import TopologicalLoss`
    - L41: `criterion_topo = TopologicalLoss(lam=0.1)`
    - L84-91:
      ```python
      84:             logits = model(imgs)
      85:             loss_dice = criterion_dice(logits, masks)
      86:             
      87:             # Topological Loss is disabled in the main training loop (future work)
      88:             # as it causes extreme slowdowns on 384x384 feature maps.
      89:             loss = loss_dice
      90:             loss.backward()
      91:             optimizer.step()
      ```
  - `criterion_topo` is never invoked in the training iteration; backpropagation is performed strictly on `loss_dice`.
  - Inspection of `src/topo_loss.py:L48-50` reveals why: `gudhi.CubicalComplex` computes persistence on CPU per-sample. On $384 \times 384$ grids (147,456 pixels) with batch size 16, CPU persistence computation froze execution.
  - Inspection of `src/run_topo_ablation.py` confirms that the only working execution of `TopologicalLoss` was on a synthetic $64 \times 64$ toy image (two circles) for 15 iterations.
- **Verdict**: **PASSED**. Topological Loss is genuinely disabled in the actual training loop.

---

### 4. ChakraSLAM Implementation Status

- **Target Files**: `src/temporal/tracker.py`, `ARCHITECTURE-SPINE.md`, and all `src/` modules.
- **Claim Tested**: Is ChakraSLAM genuinely 100% unimplemented in `src/`?
- **Empirical Execution & Code Inspection**:
  - `src/temporal/tracker.py` (`ChakraTemporalTracker`):
    - Dataclass `TrackedObject`: `box: Optional[np.ndarray] = None # [x1, y1, x2, y2]`. Operates exclusively on 2D bounding boxes.
    - Uses 2D IoU (`_compute_iou`), N-of-M confirmation gate (3 of 5 frames), exponential moving average confidence smoothing (`ema_alpha=0.4`), spatial doubt tracking, and hold frames (`max_hold_frames=8`).
    - Contains zero visual odometry, zero camera pose estimation, zero 3D point cloud generation, and zero withdrawal alerting.
  - `ARCHITECTURE-SPINE.md:L43-45`:
    > `### AD-03: Temporal Stability & Tracking (ChakraSLAM) — [PROPOSED / FUTURE WORK — NOT IMPLEMENTED]`  
    > `Status: ⚠ This architectural decision describes a proposed design. As of 2026-09-04, there is no implementation of Endoscopic SLAM or 3D spatial coordinate tracking in src/. ByteTrack 2D temporal tracking is implemented in infer_stream.py; the 3D memory layer is not.`
  - Grep search across `src/` for `slam`, `odometry`, `epipolar`, `pose`, and `point_cloud` confirms zero SLAM code. (The only mention of "slam" is in a paper title in `src/download_papers.py`, and `src/vst_fp/topological_verifier.py` is a mock Conv3d threshold stub).
- **Verdict**: **PASSED**. ChakraSLAM is 100% an unimplemented conceptual proposal; actual production code is the 2D `ChakraTemporalTracker`.

---

### 5. FCBFormer Directory Purpose & Contents

- **Target Files**: `fcbformer/`, `fcbformer_source.tar.gz`.
- **Claim Tested**: Is FCBFormer really only an external LaTeX paper archive in `fcbformer/`?
- **Empirical Inspection**:
  - Directory listing of `fcbformer/`:
    - Total subdirectories: 0
    - Total files: 49
    - LaTeX source files: `main.tex`, `Paper.bib`, `main.bbl`, `llncs.cls`, `splncs04.bst`
    - Paper figure files: 44 images (`FCBformer.png`, `SSFormer.png`, `FCB_feats*.png`, `TB_feats*.png`, `cju*.jpg`, `gt*.jpg`, etc.)
    - Executable code (`.py`, `.sh`, `.c`, `.cpp`, `.pth`, `.pt`): **0 files**
  - Inspection of `fcbformer/main.tex`:
    - Title: *"FCN-Transformer Feature Fusion for Polyp Segmentation"*
    - Authors: Edward Sanderson & Bogdan J. Matuszewski (University of Central Lancashire, UK)
    - Venue: MIUA 2022 / Springer LNCS (arXiv:2205.13867)
  - Root archive `fcbformer_source.tar.gz`: 2,321,666 bytes (the downloaded arXiv tarball).
- **Verdict**: **PASSED**. `fcbformer/` contains no executable model or code; it is purely an unpacked external paper archive used to reference baseline numbers.

---

## Adversarial Challenges & Edge-Case Mining

### Challenge 1 (Low Risk - Checkpoint Loading Discrepancy)
- **Observation**: `weights/chakra_transformer_best.pth` contains 309,173,737 weight parameters, matching `transformer_segmenter.bak`. However, current `src/chakra_transformer/transformer_segmenter.py` adds `self.prompt_embedding = nn.Embedding(2, 1024)` (2,048 parameters = 309,175,785 parameters).
- **Attack Scenario**: Running `model.load_state_dict(sd, strict=True)` using the current class definition crashes with `RuntimeError: Missing key(s) in state_dict: "prompt_embedding.weight"`.
- **Blast Radius**: Anyone running automated tests with `strict=True` will experience a crash unless `strict=False` or `transformer_segmenter.bak` is used.
- **Mitigation**: `true_docs` or code documentation should explicitly note that `weights/chakra_transformer_best.pth` was checkpointed before `prompt_embedding` was merged, requiring `strict=False` when loading.

### Challenge 2 (Low Risk - File Size Discrepancy on Secondary Checkpoints)
- **Observation**: In `true_docs/verified_benchmarks_and_metrics.md:L21`, `outputs/polyp_yolov8x/weights/best.pt` is listed as `24,484,778 bytes`. On disk, the file is `24,485,479 bytes` (difference of 701 bytes). Similarly, `kaggle_bundle/weights/best.pt` is `6,236,259 bytes` (vs `6,241,834 bytes`).
- **Blast Radius**: Trivial (checksum or byte-exact diff tools might flag minor variance; parameter counts of 3,011,043 are 100% identical).
- **Mitigation**: Update byte counts in table to reflect the latest disk state.

---

## Stress Test Results Matrix

| Scenario / Hypothesis | Expected Behavior | Actual Behavior Observed | Pass / Fail |
|:---|:---|:---|:---:|
| **H1**: ChakraTransformer has ~309M parameters | State_dict contains ~309M params | Exactly 309,173,737 weight params + 642 buffers | **PASS** |
| **H2**: Fine-tuned detector is YOLOv8n (3.01M params) | Ultralytics model has 3.01M params, depth=0.33, width=0.25 | Exactly 3,011,043 params, depth=0.33, width=0.25 | **PASS** |
| **H3**: `src/train_yolo.py` trains YOLOv8n | Loads `yolov8n.pt` on line 6 | Loads `yolov8n.pt` despite `polyp_yolov8x` print/name | **PASS** |
| **H4**: Topological Loss is disabled in training | `loss = loss_dice` in `train_transformer.py` | Line 89 sets `loss = loss_dice`, ignores `criterion_topo` | **PASS** |
| **H5**: ChakraSLAM is 100% unimplemented | No 3D SLAM / odometry code in `src/` | Only 2D `ChakraTemporalTracker` exists; spine admits unimplemented | **PASS** |
| **H6**: FCBFormer is only external LaTeX archive | No Python/weights in `fcbformer/` | 49 LaTeX/figure files from Sanderson et al. paper | **PASS** |
| **H7**: Strict checkpoint loading into current model | `strict=True` loads cleanly | `strict=True` fails on missing `prompt_embedding.weight` | **FLAGGED CAVEAT** |

---

## Unchallenged Areas
- Full 50-epoch retraining of ChakraTransformer from scratch was out of scope due to GPU compute and time constraints; verification was performed directly on the trained checkpoint tensors and architecture definitions.
