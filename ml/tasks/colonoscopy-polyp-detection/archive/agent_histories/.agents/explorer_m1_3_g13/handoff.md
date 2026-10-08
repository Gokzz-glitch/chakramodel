# Unified Architecture Handoff Report: YOLO Detection Head, End-to-End Data Flow, and Parameter Mapping

**Document ID:** `M:\chakramodel\.agents\explorer_m1_3_g13\handoff.md`  
**Author:** Explorer 3 (Gen 13) — Architecture & Data Flow Specialist  
**Working Directory:** `M:\chakramodel\.agents\explorer_m1_3_g13`  
**Workspace:** `M:\chakramodel`  
**Parent Orchestrator:** `M:\chakramodel\.agents\orchestrator_gen13`  
**Date:** 2026-09-10  
**Handoff Type:** Hard (Task Complete)  

---

## 1. Observation

### 1.1 YOLO Detection Engine Inspection
- **Training Configuration (`src/detection/train_yolo.py`):**
  - Line 6: `model = YOLO("yolov8n.pt")`
  - Line 9: `data_yaml = r"M:\chakramodel\dataset_yolo\dataset.yaml"`
  - Lines 16–29: `model.train(data=data_yaml, epochs=30, imgsz=640, batch=32, workers=8, device=0, amp=True, project=r"M:\chakramodel\outputs", name="polyp_yolov8n")`
- **Live Video Streaming Invocation (`src/app.py` & `src/inference/infer_stream.py`):**
  - `src/app.py`, line 40: `weights_path = r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt"`
  - `src/inference/infer_stream.py`, line 10: `from ultralytics import YOLO`
  - `src/inference/infer_stream.py`, line 249: `model = YOLO(model_path)`
  - `src/inference/infer_stream.py`, line 306: `results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=conf_thresh, verbose=False)[0]`
- **Physical Weight Inspection (`weights/yolo/best.pt`):**
  - Evaluated via PyTorch introspection:
    - Total Parameters: **3,011,043** (Trainable: 3,011,027; DFL non-trainable: 16).
    - Layers 0–9 (CSPDarknet Backbone): Conv and C2f layers downsampling to P3 ($80 \times 80 \times 64$), P4 ($40 \times 40 \times 128$), P5 ($20 \times 20 \times 256$) + SPPF ($k=5$). Backbone params: **1,272,656**.
    - Layers 10–21 (PAN-FPN Neck): Top-down upsampling and bottom-up downsampling with C2f modules. Neck params: **986,880**.
    - Layer 22 (Anchor-Free Decoupled Head `Detect`):
      - Bounding box regression branch `cv2`: Conv(3x3) $\rightarrow$ Conv(3x3) $\rightarrow$ Conv2d(1x1, 64) for $4 \times 16$ DFL bins across P3, P4, P5.
      - Classification branch `cv3`: Conv(3x3) $\rightarrow$ Conv(3x3) $\rightarrow$ Conv2d(1x1, 1) for polyp class logit across P3, P4, P5.
      - Distribution Focal Loss `dfl`: Conv2d(16, 1, 1, bias=False) integration layer.
      - Total anchor grid cells: $80 \times 80$ (6,400) + $40 \times 40$ (1,600) + $20 \times 20$ (400) = **8,400 anchor points**.
      - Head params: **751,507**.
      - Raw head output tensor shape: $[B, 5, 8400]$ ($4$ box coordinates $[x, y, w, h] + 1$ class confidence).
      - Post-NMS output tensor shape: $[B, N, 6]$ where $N \le 300$, columns: $[x_1, y_1, x_2, y_2, \text{confidence}, \text{class\_id}]$.

### 1.2 Detection-to-Segmentation Coupling Inspection
- **Cascaded RoI Crop Pipeline (`src/inference/infer_stream.py`):**
  - Lines 163–176: YOLO detection parsing and track updating:
    ```python
    boxes = results.boxes.xyxy.cpu().numpy()
    track_ids = results.boxes.id.int().cpu().numpy()
    confs = results.boxes.conf.cpu().numpy()
    display_tracks = tracker.update(frame_detections)
    ```
  - Lines 190–204: Bounding box crop extraction and patch segmentation:
    ```python
    x1, y1, x2, y2 = map(int, track.box)
    roi_crop = frame[y1:y2, x1:x2]
    if track.state == "DETECTING" and roi_crop.size > 0:
        mask, contours, seg_conf, _ = chakranet_seg.segment_roi(roi_crop)
        track.mask = mask
        paris_info = paris_clf.analyze_polyp((x1, y1, x2, y2), mask=mask, contour=contours[0] if contours else None)
    ```
  - Lines 212–218: Mask resizing and alpha overlay on full frame:
    ```python
    p4 = chakranet_seg.overlay_mask_on_frame(p4, (x1, y1, x2, y2), mask, color=mask_color, alpha=0.40)
    ```
- **Feature Prompt Injection Alternative (`src/chakra_transformer/transformer_segmenter.py`):**
  - Lines 26–28:
    ```python
    self.prompt_embedding = nn.Embedding(2, self.embed_dim)
    ```
  - Lines 73–89:
    ```python
    prompt_mask = torch.zeros((B, grid_h, grid_w), dtype=torch.long, device=x.device)
    # Scale box coordinates to 24x24 grid:
    px1 = max(0, int(x1 * grid_w / W))
    py1 = max(0, int(y1 * grid_h / H))
    px2 = min(grid_w, int(x2 * grid_w / W))
    py2 = min(grid_h, int(y2 * grid_h / H))
    prompt_mask[b, py1:py2, px1:px2] = 1
    prompt_feats = self.prompt_embedding(prompt_mask).permute(0, 3, 1, 2)
    features = features + prompt_feats
    ```

### 1.3 Segmentation Body Model Inspection
- **Primary Production Segmenter (`ChakraNetMicroRefiner` in `src/models/chakranet_segmenter.py`):**
  - Lines 115–132:
    - Backbone: `timm.create_model('vit_large_patch16_384', pretrained=True, img_size=384, drop_rate=0.1, attn_drop_rate=0.1)` $\rightarrow$ **304,715,752 parameters** (includes 1,025,000 parameter classifier stub).
    - Decode Head:
      - `[0] ConvTranspose2d(1024, 256, k=4, s=4)`: 4,194,560 params
      - `[1] BatchNorm2d(256)`: 512 params
      - `[2] ReLU(inplace=True)`: 0 params
      - `[3] ConvTranspose2d(256, 64, k=4, s=4)`: 262,208 params
      - `[4] BatchNorm2d(64)`: 128 params
      - `[5] ReLU(inplace=True)`: 0 params
      - `[6] Conv2d(64, 1, k=3, p=1)`: 577 params
      - Subtotal Decode Head: **4,457,985 parameters**.
    - Model Total: **309,173,737 parameters** (312 tensors / 309,174,379 parameters with positional tokens in checkpoint).
- **Secondary CNN Segmenter (`PraNetResNet101` in `src/models/pranet_resnet101.py`):**
  - ResNet-101 Backbone (`enc0`–`enc4`): **23,508,032 parameters**.
  - Receptive Field Blocks (`rfb1`–`rfb4`): **1,784,448 parameters**.
  - Parallel Partial Decoder (`ppd_conv` + `ppd_out`): **83,089 parameters**.
  - Reverse Attention Modules (`ra1`–`ra4`): **169,548 parameters**.
  - PraNet Total: **25,545,117 parameters**.

### 1.4 Architectural Documentation Cross-Reference
- `docs/CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md`:
  - Documents exact 312 checkpoint keys, the DDP serialization flaw (`module.` prefix), the 16 decode_head keys, dead weight classifier head (~1.03M params), the OOM CPU fallback race condition, and the lack of skip connections (16x coarse bottleneck).
  - Highlights §1.2 / §5.4: Cascaded pipeline Dice (0.4555) was lower than standalone YOLO box Dice (0.685).
- `docs/ARCHITECTURE_RECONSTRUCTED.md`:
  - Confirms dead code status of `BasicConv2d`, `RFBBlock`, and `ReverseAttention` in `chakranet_segmenter.py` (lines 29–102).
  - Details Path A (flawed loader, 0/312 loaded, mode collapse) vs Path B (corrected dual-prefix strip `module.` and `_orig_mod.`, 312/312 loaded).
- `docs/DATA_FLOW_MAP.md` & `docs/HONEST_METRICS.md`:
  - Retracts 0.9852 (Kvasir), 0.9412 (ClinicDB), 0.8650 (ETIS).
  - Establishes Kaggle Run v5 as the sole gold-standard benchmark: Kvasir-SEG (N=150): **0.8131 ± 0.1747 DSC**, HyperKvasir (N=1000): **0.8360 ± 0.1610 DSC**, PolypDB (N=7868): **0.7283 ± 0.2544 DSC**.

---

## 2. Logic Chain

1. **Detection Head Execution Chain:**
   - Input frame $[H, W, 3]$ enters YOLOv8. CSPDarknet extracts multiscale features at P3 ($80 \times 80$), P4 ($40 \times 40$), P5 ($20 \times 20$).
   - PAN-FPN neck aggregates top-down semantics and bottom-up localization.
   - Decoupled anchor-free heads evaluate 8,400 spatial points, predicting $4 \times 16$ DFL bins (regression) and $1$ class logit (polyp probability).
   - Softmax integration over DFL bins decodes continuous $[x, y, w, h]$ coordinates, yielding tensor $[B, 5, 8400]$.
   - NMS suppresses redundant overlapping boxes, yielding detection tensor $[B, N, 6]$.
2. **Temporal Stabilization Chain:**
   - Raw detections are passed to ByteTrack Kalman filtering to estimate velocity and maintain object ID continuity.
   - `ChakraTemporalTracker` enforces a 3-of-5 frame confirmation gate to eliminate single-frame false positives, smooths confidence scores via EMA ($\alpha=0.4$), and holds lost detections for up to 8 frames with monotonic confidence decay ($0.85 \times \text{conf}$).
   - Laplacian variance ($< 80$) and intensity thresholding ($< 30$ or $> 220$) detect endoscopic motion blur, blood, or fecal occlusion, vetoing spurious candidate detections.
3. **Coupling Mechanism Chain:**
   - *Cascaded RoI Extraction (Mechanism A, Deployed):* Bounding box coordinates $[x_1, y_1, x_2, y_2]$ are clipped and sliced directly from the video frame (`roi_crop = frame[y1:y2, x1:x2]`). `letterbox_pad` embeds the crop into a square $384 \times 384$ canvas without aspect-ratio distortion. The ViT-Large segmenter processes this high-resolution patch, and `unletterbox` restores the probability map to native coordinates before alpha-blending onto the live frame.
   - *Prompt Injection (Mechanism B, Defined):* Full-frame images enter ViT-Large, producing feature map $[B, 1024, 24, 24]$. A binary spatial mask at $24 \times 24$ is embedded via `nn.Embedding(2, 1024)` and added to features. However, because checkpoint `chakra_transformer_best.pth` has 312 keys (trained without prompt embeddings), this layer cannot be used with existing weights.
4. **Segmentation Body Execution Chain:**
   - In ViT-Large, input $[1, 3, 384, 384]$ is projected into 576 patch tokens ($16 \times 16$ stride 16) + 1 CLS token $\rightarrow [1, 577, 1024]$.
   - 24 Transformer encoder blocks apply multi-head self-attention (16 heads) and MLP expansions (4096 hidden dimension).
   - CLS token is stripped, and patch tokens are reshaped to $[1, 1024, 24, 24]$.
   - Transpose convolutions progressively upscale features: $[1, 1024, 24, 24] \rightarrow [1, 256, 96, 96] \rightarrow [1, 64, 384, 384] \rightarrow [1, 1, 384, 384]$ logits.
5. **Post-Processing & Risk Control Chain:**
   - 3-way test-time augmentation (original, horizontal flip, brightness $\times 1.1$) averages predicted probabilities.
   - Conformal prediction bounds are generated using non-conformity scores with epistemic variance.
   - Morphological aspect ratio and contour curvature are evaluated by `ParisClassifier` to render Paris staging badges (Type I-p, I-s, II-a, II-b/c).

---

## 3. Caveats

1. **Prompt Embedding Checkpoint Incompatibility:** While `src/chakra_transformer/transformer_segmenter.py` defines SAM-style prompt embeddings, production checkpoint `weights/chakra_transformer_best.pth` does not contain `prompt_embedding.weight`. Loading this checkpoint into `ChakraTransformerSegmenter` requires `strict=False` and leaves prompt embeddings uninitialized.
2. **Conformal Inference Sign Discrepancy:** While `src/conformal/conformal_calibration.py` correctly specifies that variance must be added to non-conformity scores, `src/models/chakranet_segmenter.py` (lines 343–344) still inlines the legacy formula (`1.0 - (prob + variance)`), introducing a sign flip that invalidates theoretical coverage guarantees during live inference.
3. **Training Data Unrecoverability:** The training log for the run that produced checkpoint `weights/chakra_transformer_best.pth` (`num_batches_tracked = 2376`) is absent from the repository. The exact composition of the multi-dataset training corpus cannot be independently confirmed.
4. **Local Canary Datasets:** `data/cvc-300/` contains 5 uniform noise canary files, and `data/etis-larib/` contains 5 synthetic test images. No local evaluation on these directories produces valid clinical metrics.

---

## 4. Conclusion

1. **Unified Architecture Established:**
   - ChakraModel's true operational architecture is a two-stage cascaded hybrid: **YOLOv8n detector** ($3,011,043$ params) + **ByteTrack / ChakraTemporalTracker** $\rightarrow$ **RoI letterbox cropper** ($384 \times 384$) $\rightarrow$ **ViT-Large ChakraTransformerSegmenter** ($309,173,737$ params) with a 7-layer transpose-convolution decoder $\rightarrow$ **TTA / Conformal Bounds / Paris Staging HUD**.
   - The secondary CNN architecture is **PraNet ResNet-101** ($25,545,117$ params) with RFB, PPD, and Reverse Attention.
2. **Mermaid Diagrams Designed:**
   - Complete high-level clinical cascade pipeline Mermaid diagram designed for `docs/ARCHITECTURE_DEEP_DIVE.md`.
   - Complete tensor flow Mermaid diagram tracking exact tensor shapes $[B, C, H, W]$ across every single layer designed and validated.
3. **Parameter Mapping Specification Designed:**
   - Full PyTorch `summary()` style structure specified with exact layer names, shapes, parameter counts, and memory footprints for `docs/parameter_mapping.txt`.

---

## 5. Verification Method

To independently verify all observations and parameter counts:

1. **Verify YOLOv8 Parameters & Layers:**
   ```powershell
   python -c "from ultralytics import YOLO; yolo = YOLO('weights/yolo/best.pt'); print('Total:', sum(p.numel() for p in yolo.model.parameters())); [print(f'Layer {i}: {type(m).__name__}, params: {sum(p.numel() for p in m.parameters())}') for i, m in enumerate(yolo.model.model)]"
   ```
   *Expected:* Total = `3011043`, Layers 0–9 = `1272656`, Layers 10–21 = `986880`, Layer 22 = `751507`.

2. **Verify ViT-Large ChakraNetMicroRefiner Parameters & Layers:**
   ```powershell
   python -c "import sys; sys.path.insert(0, 'M:/chakramodel'); from src.models.chakranet_segmenter import ChakraNetMicroRefiner; m = ChakraNetMicroRefiner(); print('Total:', sum(p.numel() for p in m.parameters())); print('Backbone:', sum(p.numel() for p in m.backbone.parameters())); print('Decode head:', sum(p.numel() for p in m.decode_head.parameters()))"
   ```
   *Expected:* Total = `309173737`, Backbone = `304715752`, Decode Head = `4457985`.

3. **Verify PraNet ResNet-101 Parameters & Layers:**
   ```powershell
   python -c "import sys; sys.path.insert(0, 'M:/chakramodel'); from src.models.pranet_resnet101 import PraNetResNet101; m = PraNetResNet101(); print('Total:', sum(p.numel() for p in m.parameters()))"
   ```
   *Expected:* Total = `25545117`.

4. **Verify Clean Checkpoint Weight Loading:**
   ```powershell
   python src/evaluation/verify_minimal.py
   ```
   *Expected:* All 312/312 keys match, 0 missing, 0 unexpected, runs in < 10 seconds.
