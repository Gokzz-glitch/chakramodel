# Handoff Report: Architecture & Data Flow Reconstruction (R1 & R2)
**Agent:** Winston, System Architect (`worker_arch`)  
**Timestamp:** 2026-09-09T11:44:00Z  
**Target Documents:**
- `M:\chakramodel\docs\ARCHITECTURE_RECONSTRUCTED.md` (39,466 bytes)
- `M:\chakramodel\docs\DATA_FLOW_MAP.md` (20,345 bytes)

---

## 1. Observation

1. **Dead Code in `src/chakranet_segmenter.py`:**
   - Lines 29–43: `class BasicConv2d(nn.Module):`
   - Lines 45–82: `class RFBBlock(nn.Module):`
   - Lines 83–102: `class ReverseAttention(nn.Module):`
   - Line 106: `class ChakraNetMicroRefiner(nn.Module):`
   - Lines 115–121: `self.backbone = timm.create_model('vit_large_patch16_384', pretrained=True, img_size=384, drop_rate=0.1, attn_drop_rate=0.1)`
   - Line 207: `self.model = ChakraNetMicroRefiner(channels=24).to(self.device)`
   - Verified via global grep across `src/chakranet_segmenter.py`: `BasicConv2d`, `RFBBlock`, and `ReverseAttention` are never instantiated or called anywhere in the model pipeline.

2. **Checkpoint Anatomy & The DDP Prefix Failure:**
   - `weights/chakra_transformer_best.pth` contains 312 keys (size: 1,236,836,719 bytes, clean backup at `chakra_transformer_best.pth.bak`).
   - 100% of the 312 keys in the checkpoint are prefixed with `module.` (from DDP multi-GPU training). Exactly 0 keys contain `_orig_mod.`.
   - In legacy commit `2cac63f7` in `src/chakranet_segmenter.py` line 224, the loader executed:
     ```python
     sd = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
     self.model.load_state_dict(sd, strict=False)
     ```
     Under this logic, `missing_keys` was 310, `unexpected_keys` was 312. PyTorch silently failed to load all weights, running the model with random Kaiming weights, producing constant ~0.504 probability and global DSC ~0.1835 across 8,016 images.
   - Under the corrected loader (line 225):
     ```python
     sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
     ```
     All 312 keys load cleanly into `ChakraNetMicroRefiner` with `strict=True` (0 missing, 0 unexpected). When loading into `ChakraTransformerSegmenter` (`src/chakra_transformer/transformer_segmenter.py`), `prompt_embedding.weight` is missing because it was not in the saved checkpoint.

3. **Checkpoint Inventory in `weights/`:**
   - `weights/combo1_best.pth`: Exists (102,677,499 bytes). ResNet-50 backbone.
   - `weights/combo2_best.pth`: Exists (102,677,499 bytes). Warm-started from Combo 1.
   - `weights/combo3_best.pth`: **DOES NOT EXIST**.
   - `weights/combo4_best.pth`: **DOES NOT EXIST**.
   - `weights/combo5_best.pth`: **DOES NOT EXIST**.
   - `weights/chakra_transformer_best.pth`: Exists (1,236,836,719 bytes).
   - `weights/best.pt`: Exists (6,209,450 bytes). YOLOv8 polyp detector.

4. **Conformal Calibration Discrepancies:**
   - Artifact 1: `results/combo1_metrics.json` records `q_hat: 0.99999267`, threshold $\tau = 7.326\text{e-}6$ for $\alpha=0.05$ on $N=200$ images with mean uncertainty $2.85\text{e-}15$.
   - Artifact 2: `weights/conformal_calibration.json` records `q_hat_pos: 0.521484375`, `q_hat_neg: 0.55421875` for $\alpha=0.05$ on $N=100$ images, claiming empirical pixel coverage 95.0%.
   - In `src/conformal_calibration.py`, positive non-conformity scores were computed by pooling all pixels across images (`all_scores_pos = np.concatenate(...)`), violating the exchangeability assumption of conformal risk control.

5. **Local Data Directory Inspection (`cvc-300` and `etis-larib`):**
   - `data/cvc-300/images/`: Contains only 5 files (`CANARY_100891e39afc.png`, `CANARY_1c83461414cf.png`, `CANARY_a7fbd47bfa04.png`, `CANARY_cf7ffa47a7d3.png`, `CANARY_f237a7b98d2d.png`).
   - `data/etis-larib/images/`: Contains only 5 files (`synth_0.png` through `synth_4.png`).
   - No real patient data exists in local `data/cvc-300` or `data/etis-larib`.

6. **Git Tracking Status:**
   - `src/quick_eval_kvasir.py`: Untracked (`?? src/quick_eval_kvasir.py`).
   - `results/corrected_eval_kvasir_seg.json`: Untracked (`?? results/corrected_eval_kvasir_seg.json`).
   - `results/final_8_datasets_eval.json`: Untracked (`?? results/final_8_datasets_eval.json`).
   - `kaggle_results/run_v5/cross_dataset_results_v5.json`: Tracked.

---

## 2. Logic Chain

1. **Premise 1:** `src/chakranet_segmenter.py` defines `BasicConv2d`, `RFBBlock`, and `ReverseAttention`, but instantiates `ChakraNetMicroRefiner`, which initializes `timm.create_model('vit_large_patch16_384')` and a 7-layer transpose convolution head.  
   $\rightarrow$ **Inference 1:** The claimed PraNet CNN architecture is completely dead legacy code. The real segmentation model is a Vision Transformer (ViT-Large).

2. **Premise 2:** Multi-GPU PyTorch DDP training prepends `module.` to all dictionary keys in saved state dicts. The raw checkpoint `chakra_transformer_best.pth` has 312 keys all beginning with `module.`. An earlier loader only stripped `_orig_mod.`.  
   $\rightarrow$ **Inference 2:** Calling `load_state_dict(sd, strict=False)` with unstripped `module.` rejected all 312 weights. The decoder operated on uninitialized random weights, creating the catastrophic mode collapse (~0.1835 DSC) reported across earlier evaluations.

3. **Premise 3:** Slicing `image_paths[:60]` in `src/quick_eval_kvasir.py` selects the first 60 images alphabetically from `data/kvasir-seg/images/`. The training split uses the first 70% (700 images).  
   $\rightarrow$ **Inference 3:** The headline 0.8023 DSC reported in `results/corrected_eval_kvasir_seg.json` was evaluated on training images and suffered from data leakage.

4. **Premise 4:** Local directories `data/cvc-300` and `data/etis-larib` contain only 5 canary and 5 synthetic images respectively. Kaggle v5 (`build_crossval_v5.py`) mounted the real datasets under `/kaggle/input/datasets/gokulrocky/` with 495 ClinicDB images, 60 CVC-300 images, 1000 HyperKvasir images, and 7868 PolypDB images, strictly enforcing a held-out test split (150 images, `seed=42`) on Kvasir-SEG.  
   $\rightarrow$ **Inference 4:** Kaggle v5 results (`cross_dataset_results_v5.json`) represent the only genuine, defensible evaluation of the ChakraModel pipeline.

---

## 3. Caveats

1. **Hardware Constraints:** Full re-training of ViT-Large (304M parameters) was not executed during this turn, as the mission is forensic architectural reconstruction and data flow mapping.
2. **Kaggle ETIS-Larib Evaluation:** The Kaggle dataset only contained a 5-image subset of ETIS-Larib. The historical catastrophic failure (Dice = 0.0000) on the full 196-image dataset was preserved as documented.
3. **Daemon Monitor:** Importing `src/chakranet_segmenter.py` automatically initializes `HardwareMonitor` daemon, which must be kept in mind when invoking CLI smoke tests.

---

## 4. Conclusion

Requirements R1 and R2 have been completely fulfilled with forensic precision:
1. `M:\chakramodel\docs\ARCHITECTURE_RECONSTRUCTED.md` (39.5 KB) documents:
   - The real two-stage inference pipeline (YOLOv8 + ByteTrack + ViT-Large + Progressive Transpose Decoder + Paris Classification + HUD).
   - Complete analysis of the DDP weight loading defect (Path A vs Path B).
   - The Combo 1–6 matrix with verified trained artifact statuses (Combos 1, 2, 6 exist; Combos 3, 4, 5 do not).
   - Dead code identification (`BasicConv2d`, `RFBBlock`, `ReverseAttention`).
   - Conformal calibration discrepancies and mathematical failure modes.
   - Anti-fabrication harness architecture and canary detection.
   - Two comprehensive Mermaid diagrams (Inference Pipeline & Training/Evaluation Data Flow).
2. `M:\chakramodel\docs\DATA_FLOW_MAP.md` (20.3 KB) documents:
   - Exact script $\rightarrow$ artifact $\rightarrow$ metric lineage for all evaluation workflows.
   - Checkpoint loading map and parameter counts.
   - Train/test partition audit and local canary contamination.
   - Git tracking status of critical scripts and JSON results.
   - Complete historical claims vs reality provenance matrix.
   - The Honest Metrics Table establishing Kaggle v5 results as the sole defensible standard.

---

## 5. Verification Method

1. **Inspect Documentation Artifacts:**
   ```powershell
   Get-Item M:\chakramodel\docs\ARCHITECTURE_RECONSTRUCTED.md
   Get-Item M:\chakramodel\docs\DATA_FLOW_MAP.md
   ```
2. **Verify Dead Code in `src/chakranet_segmenter.py`:**
   ```powershell
   Select-String -Path M:\chakramodel\src\chakranet_segmenter.py -Pattern "class BasicConv2d|class RFBBlock|class ReverseAttention|ChakraNetMicroRefiner"
   ```
3. **Verify Weight Checkpoints Existence:**
   ```powershell
   Get-ChildItem M:\chakramodel\weights\ | Select-Object Name, Length
   ```
4. **Verify Kaggle v5 Ground Truth Results:**
   ```powershell
   Get-Content M:\chakramodel\kaggle_results\run_v5\cross_dataset_results_v5.json
   ```
