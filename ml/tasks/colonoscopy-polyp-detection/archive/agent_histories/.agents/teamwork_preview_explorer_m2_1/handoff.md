# Handoff Report: ChakraModel Code Architecture & Theory Audit

**Author:** Explorer 2 (Code Architecture & Theory Auditor)  
**Assigned Working Directory:** `m:\chakramodel\.agents\teamwork_preview_explorer_m2_1`  
**Date:** 2026-09-07  
**Type:** Hard Handoff (Task Complete)

---

## 1. Observation

Direct observations from source code, configuration files, model weights, and logs in `m:\chakramodel`:

1. **Topological Loss (Persistent Homology)**:
   - In `src/chakra_transformer/train_transformer.py` (lines 87–90):
     ```python
     # Topological Loss is disabled in the main training loop (future work)
     # as it causes extreme slowdowns on 384x384 feature maps.
     loss = loss_dice
     loss.backward()
     ```
   - In `notebooks/deprecated/Combo2_Topo_ChakraNet.ipynb` (lines 799–824), the earlier topological loss used `cv2.connectedComponentsWithStats` to zero out secondary components above threshold 0.5 without referencing the ground truth.
   - In `src/run_topo_ablation.py`, the only executable ablation of `TopologicalLoss` runs on a single synthetic $64 \times 64$ tensor with two artificial circles vs one target circle for 15 iterations.
   - In `ChakraModel_Final_Paper.md` (lines 87, 173):
     > "⚠ Limitation: As noted in our honest failure documentation, this Topological Polyp Loss (TPL) is strictly a theoretical proposal/future work and was **not** implemented or part of the evaluated ChakraModel pipeline."
   - `oa_topo_loss.json` and `pr_topo_loss.json` are OpenAlex and arXiv JSON literature search query dumps.

2. **Conformal Calibration & Uncertainty Quantification**:
   - In `results/combo1_metrics.json`, the recorded uncertainty is `mean_uncertainty = 2.85e-15` (effectively zero).
   - In `weights/conformal_calibration.json`, the calibrated thresholds are `"q_hat_pos": 0.521484375` and `"q_hat_neg": 0.55421875`.
   - In `src/chakranet_segmenter.py` (lines 393–402):
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
     This mathematically simplifies to static deterministic thresholding at `prob >= 0.4785` (outer) and `prob > 0.5542` (inner), with `unc = None`.
   - In `create_conformal_notebook.py` (line 241), the prediction band is generated using `binary_dilation(inner_mask, iterations=lambda_hat)`.
   - In `conformal_evaluator.py`, only classification ECE and Brier score are implemented.

3. **ChakraSLAM / Endo-SLAM**:
   - In `ARCHITECTURE-SPINE.md` (lines 43–45):
     > "Status: ⚠ This architectural decision describes a proposed design. As of 2026-09-04, there is **no implementation** of Endoscopic SLAM or 3D spatial coordinate tracking in `src/`. ByteTrack 2D temporal tracking is implemented in `infer_stream.py`; the 3D memory layer is not."
   - In `ChakraModel_Final_Paper.md` (line 99):
     > "*Note: This section describes a conceptual extension planned for future work...*"
   - In `src/temporal/tracker.py`, `ChakraTemporalTracker` implements a 2D bounding-box smoothing and holding state machine (`confirm_n=3, confirm_m=5, max_hold_frames=8`, EMA smoothing $\alpha=0.4$) on top of Ultralytics ByteTrack.

4. **Hybrid Detection & Crop Degradation**:
   - In `src/hybrid_refine.py` (line 31), the early pipeline loaded `fasterrcnn_resnet50_fpn_v2(weights="DEFAULT")`, which uses generic COCO weights.
   - In `hybrid_crop_validation.py` and `rigorous_hybrid_validation.py`, tight cropping without aspect-ratio preservation caused Dice scores to collapse to ~0.45. Adding 50% context padding and letterboxing restored Dice to ~0.866.
   - In `rigorous_hybrid_validation.py` (line 219) and `ChakraModel_Final_Paper.md` (§3.1, line 73), standalone YOLO runs at 94.7 FPS, but the integrated YOLO + ViT-Large crop pipeline runs at **3.7 FPS**.
   - `sod.py` and `sod2.py` are copies of the standard `PySODMetrics` evaluation library.

5. **Federated Learning (Combo 5)**:
   - `fl_non_iid_partitioner.py` is a 76-line utility demonstrating Dirichlet sampling on mock labels.
   - `notebooks/deprecated/combo5_federated_colab.py` runs FedAvg on a toy 3-layer `SimplePraNet` across 3 local directory paths.
   - It is absent from `src/`, production inference, and the final paper.

6. **Main Pipeline & Production Weights**:
   - In `src/train_yolo.py` (lines 6, 25), the script initializes `model = YOLO("yolov8n.pt")` while setting the name to `polyp_yolov8x`.
   - `weights/best.pt` is 6,241,834 bytes (6.2 MB), corresponding to YOLOv8n (nano, ~3.2M params), not YOLOv8x (136.8 MB, ~87M params).
   - `weights/chakra_transformer_best.pth` is 1.23 GB, containing 309,174,379 parameters (`vit_large_patch16_384` + 2 transpose-conv layers).
   - `fcbformer/` contains the unpacked arXiv LaTeX source and figures of Sandler et al. (2022). It is not part of any model ensemble.
   - In `src/paris_classifier.py`, Paris classification is implemented via handcrafted geometric rules on aspect ratio and contour circularity/solidity.

---

## 2. Logic Chain

1. **Topological Loss**:
   - *Premise*: Theoretical claims assert that persistent homology constrains network weights during training.
   - *Evidence*: In `train_transformer.py` line 89, `loss = loss_dice` explicitly bypasses `criterion_topo`. In `Combo2_Topo_ChakraNet.ipynb`, only OpenCV thresholding was used. In `run_topo_ablation.py`, only a toy synthetic tensor is tested.
   - *Deduction*: Topological loss was never used to train the production weights, and the paper's admission that it is strictly theoretical future work is accurate.

2. **Conformal Calibration**:
   - *Premise*: Theoretical claims assert distribution-free 95% coverage with epistemic uncertainty modeling via MC Dropout.
   - *Evidence*: `results/combo1_metrics.json` records variance of $2.85 \times 10^{-15}$ because dropout was frozen in evaluation mode. In `src/chakranet_segmenter.py` lines 393–402, `extras["unc"]` is `None`, and the code performs simple boolean checks against fixed floats $1 - 0.521484 = 0.4785$ and $0.5542$.
   - *Deduction*: The runtime implementation does not model uncertainty or calculate adaptive prediction sets; it performs static dual-thresholding of a single deterministic forward pass.

3. **ChakraSLAM**:
   - *Premise*: Claims state a visual odometry SLAM backend logs 3D coordinates of polyp detections for withdrawal re-inspection.
   - *Evidence*: Zero SLAM, camera pose, or 3D coordinate code exists anywhere in the repository. `ARCHITECTURE-SPINE.md` lines 43–45 and `ChakraModel_Final_Paper.md` line 99 directly admit this. `src/temporal/tracker.py` contains only 2D bounding box temporal smoothing on top of ByteTrack.
   - *Deduction*: ChakraSLAM is 100% conceptual future work / pitch deck narrative.

4. **Production Architecture & SOTA Baselines**:
   - *Premise*: Project mentions YOLOv8x and FCBFormer in proximity to the pipeline.
   - *Evidence*: `weights/best.pt` is 6.2MB (YOLOv8n). `fcbformer/` contains `main.tex` and `Paper.bib` from Sandler et al. `app.py` loads `weights/best.pt` and `weights/chakra_transformer_best.pth`.
   - *Deduction*: The actual runtime pipeline is YOLOv8n + ViT-Large ChakraTransformer + 2D ByteTrack + rule-based ParisClassifier. FCBFormer was merely an external academic baseline used for benchmark comparisons.

---

## 3. Caveats

1. **Hardware Specificity**: The 3.7 FPS measurement for the full hybrid pipeline was benchmarked on an NVIDIA GeForce RTX 3050 Laptop GPU (4GB VRAM). The authors propose deployment on an NVIDIA Jetson Orin NX (16GB unified memory). While Jetson Orin NX has more memory, ViT-Large (309M parameters) will still exhibit severe compute bottlenecks without TensorRT FP16/INT8 optimization.
2. **Dataset Scarcity**: Real video evaluations on CVC-ClinicVideoDB were limited because challenge access was gated, leading the team to evaluate on LDPolypVideo and static datasets.
3. **Adversarial Audit Context**: The repository contains extensive internal documentation from a multi-agent adversarial audit loop (Generator vs. Discriminator in `OM_rama_krish_all_data.json`), which successfully forced the final paper (`ChakraModel_Final_Paper.md`) to retract many inflated claims prior to this audit.

---

## 4. Conclusion

The ChakraModel repository is a compelling hybrid engineering pipeline comprising a fine-tuned **YOLOv8n detector**, a **309M parameter ViT-Large segmenter**, and a **2D temporal persistence smoothing filter** with rule-based morphological staging. 

However, all advanced theoretical research claims — specifically **Persistent Homology Topological Loss**, **Uncertainty-Aware Conformal Risk Control**, **Endoscopic SLAM 3D tracking**, and **Federated Learning** — are either:
- **Completely Unimplemented** (ChakraSLAM / 3D tracking);
- **Disabled in Training** due to compute/CPU bottlenecks (Topological Loss);
- **Degenerated into Static Heuristics** in production (Conformal Prediction $\to$ dual static thresholds at 0.48 and 0.55; Paris Classification $\to$ bounding box aspect ratio rules); or
- **Abandoned Prototypes** (Federated Learning Dirichlet partitioner).

Furthermore, while the context-padding fix successfully resolved the "Crop-and-Forward Degradation" bug, executing a 309M parameter Vision Transformer on cropped ROIs runs at **3.7 FPS**, directly contradicting real-time clinical feasibility claims.

---

## 5. Verification Method

To independently verify all findings in this report, execute the following commands in PowerShell from `m:\chakramodel`:

1. **Verify Topological Loss is Disabled in Training**:
   ```powershell
   Get-Content src\chakra_transformer\train_transformer.py | Select-String -Pattern "loss_topo|disabled in the main training loop" -Context 2
   ```
   *Expected Output*: Displays lines 87–90 showing `# Topological Loss is disabled in the main training loop (future work)` and `loss = loss_dice`.

2. **Verify Conformal Calibration Reduces to Static Thresholding**:
   ```powershell
   Get-Content src\chakranet_segmenter.py | Select-String -Pattern "if conformal and q_hat_pos" -Context 10
   Get-Content weights\conformal_calibration.json
   ```
   *Expected Output*: Displays `score_pos = 1.0 - prob_resized` with `q_hat_pos = 0.521484` and `extras = {"inner": inner_mask, "outer": outer_mask, "unc": None}`.

3. **Verify ChakraSLAM is Documented as Unimplemented**:
   ```powershell
   Get-Content ARCHITECTURE-SPINE.md | Select-String -Pattern "AD-03" -Context 6
   ```
   *Expected Output*: Displays *"Status: ⚠ ... no implementation of Endoscopic SLAM or 3D spatial coordinate tracking in src/"*.

4. **Verify YOLO Checkpoint is Nano (not X-Large)**:
   ```powershell
   (Get-Item weights\best.pt).Length / 1MB
   Get-Content src\train_yolo.py | Select-String -Pattern "yolov8n.pt" -Context 2
   ```
   *Expected Output*: File size is ~5.95 MB (6,241,834 bytes), and `src/train_yolo.py` loads `yolov8n.pt`.

5. **Verify FCBFormer is LaTeX Source, not Code**:
   ```powershell
   Get-ChildItem fcbformer | Select-Object Name
   ```
   *Expected Output*: Shows `main.tex`, `Paper.bib`, `llncs.cls`, `FCBformer.png`.
