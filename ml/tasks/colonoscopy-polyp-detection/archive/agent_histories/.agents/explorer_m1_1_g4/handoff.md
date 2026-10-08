# Handoff Report: Explorer M1.1 (Gen 4) — Checkpoint Loading & State Dict Key Analysis

**Author:** Explorer M1.1 (Gen 4)  
**Date:** 2026-09-08  
**Working Directory:** `m:\chakramodel\.agents\explorer_m1_1_g4`  
**Reference Analysis:** `m:\chakramodel\.agents\explorer_m1_1_g4\analysis.md`

---

## 1. Observation

1. **Checkpoint Key Count & Structure**:
   - Running Python inspection on `weights/chakra_transformer_best.pth`:
     ```python
     sd = torch.load('weights/chakra_transformer_best.pth', map_location='cpu', weights_only=True)
     len(sd) # 312
     ```
   - Total keys in checkpoint: **312**
   - Total model parameters represented: **309,174,379**
   - Checkpoint file size: **1,236,836,719 bytes (1.15 GB)**

2. **Prefixes in Checkpoint**:
   - `len([k for k in sd.keys() if k.startswith('module.')])`: **312** (100% of keys)
   - `len([k for k in sd.keys() if '_orig_mod.' in k])`: **0**
   - Sample keys from checkpoint:
     - First key: `'module.backbone.cls_token'`
     - Final keys: `'module.decode_head.6.weight'`, `'module.decode_head.6.bias'`

3. **Value of `module.decode_head.6.bias`**:
   - Exact tensor: `tensor([-0.0117])`
   - Full precision scalar: `-0.011656321585178375`
   - Shape: `torch.Size([1])`
   - Dtype: `torch.float32`
   - Trained batch iterations tracked:
     - `module.decode_head.1.num_batches_tracked`: `tensor(2376)`
     - `module.decode_head.4.num_batches_tracked`: `tensor(2376)`

4. **Implementation in `src/chakranet_segmenter.py`**:
   - **Prior implementation (commit `2cac63f7`, lines 223–226)**:
     ```python
     sd = torch.load(weights_path, map_location=self.device)
     sd = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
     self.model.load_state_dict(sd, strict=False)
     print(f"[INFO] ChakraNet: Loaded weights from {weights_path}")
     ```
   - **Current implementation (working copy, lines 223–232)**:
     ```python
     sd = torch.load(weights_path, map_location=self.device)
     # Strip both DDP 'module.' prefix and torch.compile '_orig_mod.' prefix
     sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
     missing, unexpected = self.model.load_state_dict(sd, strict=False)
     if missing:
         print(f"[WARN] ChakraNet: Missing keys in checkpoint ({len(missing)}): {missing[:3]}...")
     if unexpected:
         print(f"[WARN] ChakraNet: Unexpected keys in checkpoint ({len(unexpected)}): {unexpected[:3]}...")
     if not missing and not unexpected:
         print(f"[INFO] ChakraNet: Weights loaded cleanly (strict=True equivalent) from {weights_path}")
     ```

5. **Empirical Loading Comparison**:
   - Under old logic (`k.replace("_orig_mod.", "")`):
     - `missing_keys`: **310 / 312** (all weights and biases in model uninitialized)
     - `unexpected_keys`: **312 / 312** (all checkpoint weights dropped)
   - Under new logic (`k.replace("module.", "").replace("_orig_mod.", "")`):
     - `missing_keys`: **0 / 312**
     - `unexpected_keys`: **0 / 312** (clean 100% match)

---

## 2. Logic Chain

1. **Observation 1 & 2** show that `weights/chakra_transformer_best.pth` was saved from a PyTorch `DistributedDataParallel` (DDP) training run, which prepended `module.` to every single one of its 312 parameter keys.
2. **Observation 4 (Prior implementation)** shows that `src/chakranet_segmenter.py` originally only stripped `_orig_mod.` (which is added by `torch.compile`), leaving the `module.` prefix intact on all 312 keys (e.g. `module.backbone.cls_token`).
3. **Observation 4 & 5 (Old logic)** show that `load_state_dict(sd, strict=False)` compared the model's native parameter names (e.g. `backbone.cls_token`, `decode_head.6.bias`) against keys starting with `module.`. Because none of the model parameters have the `module.` prefix, PyTorch considered 310 model parameters "missing" and all 312 checkpoint keys "unexpected".
4. Because `strict=False` was passed without checking the returned missing/unexpected lists, the failure was completely silent, leaving the entire model running with random initial weights. This explains why the model output was a constant ~0.504 sigmoid value, yielding a baseline DSC of ~0.1835 on polyp segmentation benchmarks.
5. **Observation 3** confirms that `module.decode_head.6.bias` has a trained, non-zero value (`-0.011656321585178375`) and `num_batches_tracked` is `2376`, proving the weights in the file are valid, trained checkpoint weights rather than corrupted or zeroed tensors.
6. **Observation 4 & 5 (New logic)** demonstrate that stripping `module.` via `k.replace("module.", "").replace("_orig_mod.", "")` and logging `missing` and `unexpected` completely resolves the loading defect, achieving 0 missing keys and 0 unexpected keys (strict=True equivalent loading).

---

## 3. Caveats

- In `src/chakranet_segmenter.py`, `ChakraNetMicroRefiner` specifies `timm.create_model('vit_large_patch16_384', pretrained=True, ...)`. In an offline / airgapped / CODE_ONLY environment without cached Hugging Face weights, `pretrained=True` may attempt to download initial ViT weights before `load_state_dict` overwrites them. While all 312 checkpoint weights overwrite the model, setting `pretrained=False` in offline training/evaluation environments or ensuring timm cache is present is recommended.
- The working copy changes to `src/chakranet_segmenter.py` include TTA (test-time augmentation) and FP16 autocast in addition to line 224; this report specifically examined and verified the checkpoint loading logic.

---

## 4. Conclusion

1. The checkpoint loading bug around line 224 in `src/chakranet_segmenter.py` was conclusively identified and verified.
2. `weights/chakra_transformer_best.pth` contains 312 keys (all 312 prefixed with `module.`).
3. `module.decode_head.6.bias` is confirmed to be `-0.011656` (`-0.011656321585178375`).
4. Stripping `module.` alongside `_orig_mod.` allows 100% of the 312 checkpoint weights to load cleanly into `ChakraNetMicroRefiner` with zero missing and zero unexpected keys.

---

## 5. Verification Method

To independently verify the checkpoint keys, prefix stripping, and exact bias value:

```powershell
# 1. Verify checkpoint keys, module. prefix, and decode_head.6.bias
python -c "import torch; sd = torch.load('weights/chakra_transformer_best.pth', map_location='cpu', weights_only=True); print('Total keys:', len(sd)); print('module. prefix count:', sum(1 for k in sd if k.startswith('module.'))); b = sd['module.decode_head.6.bias']; print('bias value:', b.item(), 'formatted:', f'{b.item():.6f}')"

# 2. Verify state_dict loading match (strict=True equivalent)
python -c "import sys; sys.path.insert(0, 'src'); import torch, timm; from chakranet_segmenter import ChakraNetMicroRefiner; sd = torch.load('weights/chakra_transformer_best.pth', map_location='cpu', weights_only=True); _orig = timm.create_model; timm.create_model = lambda *a, **k: _orig(*a, **{**k, 'pretrained': False}); model = ChakraNetMicroRefiner(channels=24); sd_stripped = {k.replace('module.', '').replace('_orig_mod.', ''): v for k, v in sd.items()}; m, u = model.load_state_dict(sd_stripped, strict=False); print('Missing:', len(m), 'Unexpected:', len(u))"
```

**Expected output:**
- Total keys: `312`
- module. prefix count: `312`
- bias value: `-0.011656321585178375 formatted: -0.011656`
- Missing: `0` Unexpected: `0`
