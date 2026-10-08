# Technical Analysis Report: Checkpoint Loading & State Dict Prefix Stripping in ChakraNet

**Explorer:** Explorer M1.1 (Gen 4)  
**Date:** 2026-09-08  
**Target Repository:** `m:\chakramodel`  
**Focus Files:** `src/chakranet_segmenter.py`, `weights/chakra_transformer_best.pth`  
**Reference Commit:** `2cac63f7` (and current working tree)

---

## 1. Executive Summary

An investigation was conducted into the checkpoint loading mechanism of `ChakraNet` in `src/chakranet_segmenter.py` and the actual weight tensors stored in `weights/chakra_transformer_best.pth`.

### Key Findings:
1. **Checkpoint Key Count & Structure**: `weights/chakra_transformer_best.pth` contains **312 keys** totaling **309,174,379 parameters** (file size: **1,236,836,719 bytes / 1.15 GB**).
2. **DDP Prefix Confirmation**: **312 out of 312 keys (100%)** are prefixed with `module.`, which is introduced by PyTorch's `DistributedDataParallel` (DDP) during multi-GPU training. Exactly **0 keys** contain `_orig_mod.`.
3. **Decoder Bias & Training Provenance**:
   - `module.decode_head.6.bias` has an exact tensor value of `[-0.011656321585178375]` (shape `torch.Size([1])`, `dtype=torch.float32`).
   - `module.decode_head.1.num_batches_tracked` and `module.decode_head.4.num_batches_tracked` both equal `2376`, proving that the decoder head was actively trained for 2,376 iterations and was not randomly initialized.
4. **Root Cause of Historical Silent Failure**:
   - In commit `2cac63f7`, line 224 executed:
     ```python
     sd = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
     self.model.load_state_dict(sd, strict=False)
     ```
   - Because `module.` was not stripped and `strict=False` was passed, PyTorch silently failed to load all 312 keys. Exactly **310 parameters were missing** and **312 keys were unexpected**. The model ran with random initial weights, causing blank mask outputs and a collapsed DSC score of ~0.1835.
5. **Fixed Implementation Verification**:
   - Current line 224-226 in `src/chakranet_segmenter.py`:
     ```python
     # Strip both DDP 'module.' prefix and torch.compile '_orig_mod.' prefix
     sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
     missing, unexpected = self.model.load_state_dict(sd, strict=False)
     ```
   - Empirical test confirmed: **0 missing keys** and **0 unexpected keys** (312/312 keys matched cleanly).

---

## 2. Checkpoint Inspection (`weights/chakra_transformer_best.pth`)

Direct evaluation was executed on `weights/chakra_transformer_best.pth` with `torch.load(..., map_location='cpu', weights_only=True)`.

### Checkpoint Metadata:
| Property | Value |
| :--- | :--- |
| **Path** | `weights/chakra_transformer_best.pth` |
| **File Size** | 1,236,836,719 bytes (1.15 GB / 1.24 GiB) |
| **Total Parameter Count** | 309,174,379 parameters |
| **Total Keys in Checkpoint** | 312 keys |
| **Keys with `module.` prefix** | 312 (100.0%) |
| **Keys with `_orig_mod.` prefix** | 0 (0.0%) |
| **Trained Batches Tracked** | 2,376 (`module.decode_head.1.num_batches_tracked`, `module.decode_head.4.num_batches_tracked`) |

### Key Names Sample:
- **First 5 Keys:**
  - `module.backbone.cls_token`
  - `module.backbone.pos_embed`
  - `module.backbone.patch_embed.proj.weight`
  - `module.backbone.patch_embed.proj.bias`
  - `module.backbone.blocks.0.norm1.weight`
- **Last 5 Keys:**
  - `module.decode_head.4.running_mean`
  - `module.decode_head.4.running_var`
  - `module.decode_head.4.num_batches_tracked`
  - `module.decode_head.6.weight`
  - `module.decode_head.6.bias`

### Value of `module.decode_head.6.bias`:
- **Tensor representation**: `tensor([-0.0117])`
- **Full precision scalar**: `-0.011656321585178375`
- **Tensor Shape**: `torch.Size([1])`
- **Data Type**: `torch.float32`

This non-zero, learned value confirms that the final `Conv2d(64, 1, kernel_size=3, padding=1)` layer of `decode_head` underwent gradient updates during training.

---

## 3. Detailed Inspection of `src/chakranet_segmenter.py`

### 3.1 Model Architecture Context (`ChakraNetMicroRefiner`)
In `src/chakranet_segmenter.py` (lines 106–136):
- The model architecture wraps a ViT-Large backbone (`vit_large_patch16_384`) with embedding dimension 1024.
- `decode_head` is defined as:
  ```python
  self.decode_head = nn.Sequential(
      nn.ConvTranspose2d(self.embed_dim, 256, kernel_size=4, stride=4), # index 0
      nn.BatchNorm2d(256),                                              # index 1
      nn.ReLU(inplace=True),                                            # index 2
      nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4),             # index 3
      nn.BatchNorm2d(64),                                               # index 4
      nn.ReLU(inplace=True),                                            # index 5
      nn.Conv2d(64, 1, kernel_size=3, padding=1)                        # index 6
  )
  ```
- Thus, parameter keys in the state_dict for this head are named:
  - `decode_head.0.weight`, `decode_head.0.bias`
  - `decode_head.1.weight`, `decode_head.1.bias`, `decode_head.1.running_mean`, `decode_head.1.running_var`, `decode_head.1.num_batches_tracked`
  - `decode_head.3.weight`, `decode_head.3.bias`
  - `decode_head.4.weight`, `decode_head.4.bias`, `decode_head.4.running_mean`, `decode_head.4.running_var`, `decode_head.4.num_batches_tracked`
  - `decode_head.6.weight`, `decode_head.6.bias`

### 3.2 Checkpoint Loading Logic in `ChakraNet.__init__` (lines 219–237)
```python
219:             if weights_path is not None:
220:                 weights_path = Path(weights_path)
221:                 if weights_path.exists():
222:                     # Allow strict=False to handle any _orig_mod prefixes or minor mismatches, but don't swallow completely
223:                     sd = torch.load(weights_path, map_location=self.device)
224:                     # Strip both DDP 'module.' prefix and torch.compile '_orig_mod.' prefix
225:                     sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
226:                     missing, unexpected = self.model.load_state_dict(sd, strict=False)
227:                     if missing:
228:                         print(f"[WARN] ChakraNet: Missing keys in checkpoint ({len(missing)}): {missing[:3]}...")
229:                     if unexpected:
230:                         print(f"[WARN] ChakraNet: Unexpected keys in checkpoint ({len(unexpected)}): {unexpected[:3]}...")
231:                     if not missing and not unexpected:
232:                         print(f"[INFO] ChakraNet: Weights loaded cleanly (strict=True equivalent) from {weights_path}")
233:                 else:
234:                     print(f"[WARN] ChakraNet: Weights path {weights_path} not found")
235:             else:
236:                 print("[WARN] ChakraNet: No weights found. Running with random initialization.")
```

---

## 4. Git Diff Analysis: Before vs. After the Fix

### Diff of `src/chakranet_segmenter.py` around line 224:

```diff
--- a/src/chakranet_segmenter.py (commit 2cac63f7)
+++ b/src/chakranet_segmenter.py (working copy)
@@ -223,6 +223,12 @@ class ChakraNet:
-                    sd = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
-                    self.model.load_state_dict(sd, strict=False)
-                    print(f"[INFO] ChakraNet: Loaded weights from {weights_path}")
+                    # Strip both DDP 'module.' prefix and torch.compile '_orig_mod.' prefix
+                    sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}
+                    missing, unexpected = self.model.load_state_dict(sd, strict=False)
+                    if missing:
+                        print(f"[WARN] ChakraNet: Missing keys in checkpoint ({len(missing)}): {missing[:3]}...")
+                    if unexpected:
+                        print(f"[WARN] ChakraNet: Unexpected keys in checkpoint ({len(unexpected)}): {unexpected[:3]}...")
+                    if not missing and not unexpected:
+                        print(f"[INFO] ChakraNet: Weights loaded cleanly (strict=True equivalent) from {weights_path}")
```

### Contrast Table:
| Aspect | Prior Implementation (`2cac63f7`) | Corrected Implementation (Current) |
| :--- | :--- | :--- |
| **Prefix Handling** | Only stripped `_orig_mod.` | Strips both `module.` and `_orig_mod.` |
| **Result of dict comprehension** | Keys remained e.g. `module.backbone.cls_token` | Keys become `backbone.cls_token` |
| **Missing Model Keys** | **310 / 312** (all model weights & biases) | **0 / 312** |
| **Unexpected Checkpoint Keys** | **312 / 312** (all checkpoint weights dropped) | **0 / 312** |
| **Strictness & Warning** | `strict=False` silently swallowed failure | Diagnostic check logs count of missing & unexpected keys |
| **Model Weight State** | Random initial weights (uninitialized decoder) | Correct learned weights loaded (trained 2376 batches) |

---

## 5. Empirical Test & Verification Results

An empirical test was executed using Python and PyTorch directly on `weights/chakra_transformer_best.pth` and `ChakraNetMicroRefiner`:

```python
# Test script execution summary:
sd = torch.load('weights/chakra_transformer_best.pth', map_location='cpu', weights_only=True)

# 1. OLD LOGIC:
sd_old = {k.replace('_orig_mod.', ''): v for k, v in sd.items()}
missing_old, unexpected_old = model.load_state_dict(sd_old, strict=False)
# Result: Missing count: 310 / 312, Unexpected count: 312 / 312

# 2. NEW LOGIC:
sd_new = {k.replace('module.', '').replace('_orig_mod.', ''): v for k, v in sd.items()}
missing_new, unexpected_new = model.load_state_dict(sd_new, strict=False)
# Result: Missing count: 0 / 312, Unexpected count: 0 / 312
```

In addition:
- Non-missing keys in old logic were only `{'decode_head.1.num_batches_tracked', 'decode_head.4.num_batches_tracked'}`.
- In new logic, all 312 keys matched with 0 missing and 0 unexpected, which is an exact **strict=True equivalent match**.
- In `src/verify_weights_load.py`, forward passes on diverse inputs yielded an output standard deviation of `0.031738` (demonstrating responsive, varied predictions across inputs rather than constant ~0.504 blank mask outputs).

---

## 6. Conclusion

The checkpoint loading bug in `src/chakranet_segmenter.py` line 224 has been verified. The failure was caused by the presence of DDP `module.` prefixes on 100% (312/312) of the keys in `weights/chakra_transformer_best.pth`. The updated key stripping logic in line 225 (`k.replace("module.", "").replace("_orig_mod.", "")`) cleanly loads all 312 weights with zero missing or unexpected keys.
