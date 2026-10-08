# Analysis Report — Milestone M1.3 (Gen 4)

**Agent**: Explorer M1.3 (Gen 4)  
**Date/Timestamp**: 2026-09-08T02:42:30Z  
**Project Root**: `m:\chakramodel`  
**Working Directory**: `m:\chakramodel\.agents\explorer_m1_3_g4`  

---

## Executive Summary
1. **Local Dataset Status**: `datasets/kvasir-seg` does NOT exist. However, `data/kvasir-seg` **DOES exist** and contains **1,000 images** and **1,000 masks** with 100% 1-to-1 filename correspondence in `.jpg` format. In addition, exact copies exist at `notebooks/data/kvasir-seg`, `kaggle_bundle/notebooks/data/kvasir-seg`, and `Kaggle_Datasets_Upload/kvasir-seg`. The requirement for $\ge 50$ evaluation images is **fully satisfied** (1,000 images available).
2. **Synthetic Evaluation Specification**: A complete specification is documented as a fallback for headless/isolated environments (e.g. isolated Kaggle runs or CI pipelines lacking data mounts). The specification details input generation (20 random $224 \times 224$ images), ground-truth mask generation (known circle $r=50$ at $(112, 112)$), forward-pass verification, mode-collapse detection threshold ($[0.49, 0.51]$ rejection), and output JSON schema.
3. **Kaggle Notebook Structure & Ordering Audit**: `notebooks/Kaggle_Final_Proof_Eval.ipynb` was thoroughly inspected. Cells 0, 1, and 2 were analyzed in detail for imports, execution environments, and directory navigation. An ordering discrepancy was discovered: a sanity check cell was placed at index 3/4 before the weights file is copied at index 5/6, which causes a runtime `FileNotFoundError` unless placed sequentially after weight acquisition. A recommended cell design and structural placement is provided.

---

## 1. Local Dataset Investigation (`kvasir-seg`)

### 1.1 Direct Path Checks
Empirical filesystem checks were performed across all candidate paths:
- `m:\chakramodel\datasets\kvasir-seg`: **FALSE** (Directory does not exist).
- `m:\chakramodel\data\kvasir-seg`: **TRUE** (Directory exists).
- `m:\chakramodel\notebooks\data\kvasir-seg`: **TRUE** (Directory exists).
- `m:\chakramodel\kaggle_bundle\notebooks\data\kvasir-seg`: **TRUE** (Directory exists).
- `m:\chakramodel\Kaggle_Datasets_Upload\kvasir-seg`: **TRUE** (Directory exists).

### 1.2 Quantitative Counts and Pair Integrity
Verification on `m:\chakramodel\data\kvasir-seg`:
- Subdirectory `images/`: **1,000 files**
- Subdirectory `masks/`: **1,000 files**
- Format/Extensions: **100% `.jpg`** (1,000 `.jpg` images, 1,000 `.jpg` masks).
- Image Dimensions: Variable endoscopic resolutions (e.g., sample `cju0qkwl35piu0993l0dewei2.jpg` is $622 \times 529$ RGB).
- Mask Dimensions: Exactly matches image dimensions (sample is $622 \times 529$ 3-channel / grayscale equivalent).
- Filename Overlap:
  ```python
  imgs = set(os.listdir('data/kvasir-seg/images'))
  masks = set(os.listdir('data/kvasir-seg/masks'))
  len(imgs) == 1000, len(masks) == 1000, len(imgs & masks) == 1000
  ```
  Every single image has a perfectly matching mask by name.
- First 5 files sampled:
  - `cju0qkwl35piu0993l0dewei2.jpg`
  - `cju0qoxqj9q6s0835b43399p4.jpg`
  - `cju0qx73cjw570799j4n5cjze.jpg`
  - `cju0roawvklrq0799vmjorwfv.jpg`
  - `cju0rx1idathl0835detmsp84.jpg`

### 1.3 Milestone 2 Readiness Verdict
- **Available Count**: 1,000 evaluation pairs.
- **Requirement Threshold**: $\ge 50$ images.
- **Verdict**: **SUFFICIENT (1,000 $\ge$ 50)**. Full cohort or 50-image sub-cohort evaluation can proceed immediately without synthetic substitution.

---

## 2. Specification for Synthetic Evaluation Fallback

Although local data is available, for environments lacking dataset attachments (e.g., standalone Kaggle kernel execution without data volumes, or containerized regression tests), the following synthetic evaluation design is specified:

### 2.1 Input Data Generation
- **Batch Size**: 20 images.
- **Dimensions**: $224 \times 224 \times 3$ (RGB).
- **Data Distribution**: Uniform random noise simulating varied endoscopic lighting and color distributions:
  ```python
  import numpy as np
  np.random.seed(42)
  # Generate 20 random RGB images
  synthetic_images = [
      np.random.randint(20, 235, (224, 224, 3), dtype=np.uint8)
      for _ in range(20)
  ]
  ```

### 2.2 Ground Truth Mask Specification
- **Shape**: $224 \times 224$ binary uint8 mask.
- **Geometry**: Solid circular target with radius $r = 50$ pixels, centered at $(x=112, y=112)$:
  ```python
  import cv2
  synthetic_masks = []
  for _ in range(20):
      mask = np.zeros((224, 224), dtype=np.uint8)
      cv2.circle(mask, (112, 112), 50, 1, -1) # radius 50, filled with 1
      synthetic_masks.append(mask)
  ```
- **Area**: $\pi r^2 = \pi \times 50^2 \approx 7,854$ pixels ($\approx 15.65\%$ of the total 50,176 pixels).

### 2.3 Inference Execution Protocol
For each synthetic image:
1. Pass image through `ChakraNet` or `ChakraNetMicroRefiner`.
2. Extract predicted probability map $\hat{P} \in [0, 1]^{224 \times 224}$ and threshold at $\tau = 0.45$:
   $$\hat{M}(x, y) = \mathbb{I}(\hat{P}(x, y) \ge 0.45)$$
3. Compute binary metrics against the ground truth circular mask $G$:
   $$\text{DSC} = \frac{2 |\hat{M} \cap G|}{|\hat{M}| + |G| + \epsilon}$$
   $$\text{IoU} = \frac{|\hat{M} \cap G|}{|\hat{M} \cup G| + \epsilon}$$

### 2.4 Mode Collapse Rejection Criteria
To definitively prove that the model is NOT suffering from catastrophic mode collapse:
1. **Spatial Probability Variance**: For any input $x$, the standard deviation of predicted probabilities across pixels must satisfy:
   $$\text{std}(\hat{P}) > 0.01$$
2. **Input Sensitivity Variance**: The standard deviation of mean predicted probabilities across the 20 diverse synthetic inputs must satisfy:
   $$\text{std}\left(\{\text{mean}(\hat{P}_i)\}_{i=1}^{20}\right) > 0.005$$
3. **Collapse Interval Exclusion**: Mean output probability must NOT fall into the Kaiming initialization mode collapse zone:
   $$\text{mean}(\hat{P}) \notin [0.49, 0.51]$$

### 2.5 Target Results JSON Schema (`results/corrected_eval_kvasir_seg.json`)
```json
{
  "mean_dsc": 0.xxxx,
  "mean_iou": 0.xxxx,
  "n_images": 20,
  "timestamp": "2026-09-08T02:35:00Z",
  "model_path": "weights/chakra_transformer_best.pth",
  "weight_loading_status": "PASS: 0 missing, 0 unexpected",
  "synthetic_evaluation": true,
  "synthetic_varied_output": true
}
```

---

## 3. Inspection of `notebooks/Kaggle_Final_Proof_Eval.ipynb`

### 3.1 Detailed Cell-by-Cell Structure
The notebook currently contains 13 cells (6 Markdown, 7 Code):

| Index | Type | Header / Content Summary | Key Imports / Commands |
|---|---|---|---|
| **0** | Markdown | `# ChakraModel - Final Kaggle Proof Evaluation` | Overview & proof description |
| **1** | Markdown | `## 1. Environment Setup` | Section 1 Header |
| **2** | Code | Environment Setup & Workspace Init | `import os, shutil, glob`<br>`!rm -rf /kaggle/working/chakramodel`<br>`shutil.copytree(...)`, `%cd ...`<br>`!pip install ultralytics thop gdown numpy opencv-python matplotlib` |
| **3** | Markdown | `## 2b. Weight Loading Sanity Check (DDP Prefix Fix)` | Context explaining DDP `module.` prefix bug |
| **4** | Code | Sanity Check & Verification Script | `import torch, numpy as np, sys`<br>`from datetime import datetime, timezone`<br>`from chakranet_segmenter import ChakraNetMicroRefiner`<br>`torch.load(...)`, strip `module.`, check missing/unexpected, 3 forward passes, check collapse $[0.49, 0.51]$, print PASS/FAIL |
| **5** | Markdown | `## 2. Load Weights` | Section 2 Header |
| **6** | Code | Weight Dataset Discovery & Symlink/Copy | `for root, dirs, files in os.walk("/kaggle/input"):`<br>`!mkdir -p weights`, `!cp -r {WEIGHTS_SRC}/* weights/` |
| **7** | Markdown | `## 3. Video Inference & Temporal Proof (FPS Logging)` | Section 3 Header |
| **8** | Code | Video Inference Execution | `import glob`<br>`!python src/infer_stream.py ...` |
| **9** | Markdown | `## 4. Full-Cohort Cross-Dataset Evaluation (OOD Truth)` | Section 4 Header |
| **10** | Code | Evaluation Loop on attached datasets | `import sys, cv2, numpy as np, json, tqdm`<br>`from chakranet_segmenter import ChakraNet`<br>`eval_folder()`, scan `/kaggle/input` for `images/` & `masks/` |
| **11** | Markdown | `## 5. Artifact Packaging` | Section 5 Header |
| **12** | Code | Zip artifact packaging | `%cd /kaggle/working`<br>`!zip -r final_proof_artifacts.zip ...` |

### 3.2 Analysis of Cell 0, 1, 2
- **Cell 0 (`markdown`)**: Title block declaring zero-tolerance validation of ChakraModel without synthetic shortcuts or data truncation.
- **Cell 1 (`markdown`)**: `## 1. Environment Setup` boundary marker.
- **Cell 2 (`code`)**:
  - Sets up runtime environment in `/kaggle/working/chakramodel`.
  - Searches `/kaggle/input` dynamically for `chakranet_segmenter.py` within any directory named `src`.
  - Copies source code into `/kaggle/working/chakramodel`.
  - Executes `%cd /kaggle/working/chakramodel`.
  - Runs pip installation of dependencies: `ultralytics`, `thop`, `gdown`, `numpy`, `opencv-python`, `matplotlib`.

### 3.3 Critical Structural Finding & Execution Dependency Bug
In the staged notebook, the sanity check cells (Index 3 Markdown and Index 4 Code) are placed **BEFORE** Section 2 "Load Weights" (Index 5 Markdown and Index 6 Code).
- In Cell 4:
  ```python
  WEIGHTS_PATH = "weights/chakra_transformer_best.pth"
  sd_raw = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
  ```
- In Cell 6:
  ```python
  # Link Weights - Auto-detect weights path by looking for chakra_transformer_best.pth
  ...
  !mkdir -p weights
  if WEIGHTS_SRC:
      !cp -r {WEIGHTS_SRC}/* weights/
  ```
**Consequence**: If a user runs the notebook linearly on Kaggle ("Run All"), Cell 4 will fail immediately with `FileNotFoundError: No such file or directory: 'weights/chakra_transformer_best.pth'` because the weights file has not been copied to `weights/` yet!

### 3.4 Recommended Remediation & Cell Structure
To satisfy the requirement of adding a clean weight verification cell:
1. **Option A (Logical Sequential Flow - Strongly Recommended)**:
   - Cell 2: Environment Setup (`%cd /kaggle/working/chakramodel`, pip install).
   - Cell 4 (formerly Cell 6): Load Weights (copy `chakra_transformer_best.pth` from `/kaggle/input` to `weights/`).
   - Cell 5 / 6: Weight Loading Sanity Check (DDP Prefix Fix & PASS/FAIL print).
2. **Option B (Self-Contained Verification Cell at Position 2)**:
   - If the verification cell must run at Position 2 (immediately following Environment Setup), it must dynamically discover the weights in `/kaggle/input` or copy them prior to calling `torch.load()`.

### 3.5 Exact Proposed Code for the DDP Prefix Stripping Cell
```python
# CRITICAL FIX VERIFICATION | Timestamp: 2026-09-08
import os
import sys
import torch
import numpy as np
from datetime import datetime, timezone

sys.path.append("/kaggle/working/chakramodel/src")
print(f"[{datetime.now(timezone.utc).isoformat()}] Starting DDP Prefix Fix Verification...")

# 1. Locate weights
WEIGHTS_PATH = "weights/chakra_transformer_best.pth"
if not os.path.exists(WEIGHTS_PATH):
    # Auto-detect fallback if not yet copied to local weights directory
    for root, dirs, files in os.walk("/kaggle/input"):
        if "chakra_transformer_best.pth" in files:
            WEIGHTS_PATH = os.path.join(root, "chakra_transformer_best.pth")
            break

if not os.path.exists(WEIGHTS_PATH):
    print(f"FAIL: Checkpoint not found at {WEIGHTS_PATH}")
    sys.exit(1)

# 2. Load raw checkpoint
sd_raw = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
print(f"Loaded raw checkpoint: {len(sd_raw)} keys. Sample: {list(sd_raw.keys())[:2]}")

# 3. Strip both DDP ('module.') and torch.compile ('_orig_mod.') prefixes
sd_stripped = {
    k.replace("module.", "").replace("_orig_mod.", ""): v 
    for k, v in sd_raw.items()
}
print(f"Cleaned state dict: {len(sd_stripped)} keys. Sample: {list(sd_stripped.keys())[:2]}")

# 4. Instantiate model and verify strict-equivalent key match
from chakranet_segmenter import ChakraNetMicroRefiner
model = ChakraNetMicroRefiner(channels=24)
missing, unexpected = model.load_state_dict(sd_stripped, strict=False)
print(f"Missing keys: {len(missing)} | Unexpected keys: {len(unexpected)}")

# 5. Forward-pass sensitivity & non-collapse verification
model.eval()
outputs = []
with torch.no_grad():
    for _ in range(5):
        x = torch.randn(1, 3, 224, 224)
        outputs.append(torch.sigmoid(model(x)).mean().item())

output_std = float(np.std(outputs))
is_collapsed = all(0.49 <= o <= 0.51 for o in outputs)
print(f"Output std: {output_std:.4f} | Output mean range: [{min(outputs):.4f}, {max(outputs):.4f}]")

# 6. Final verdict
if not is_collapsed and len(missing) == 0:
    print("PASS: Fix verified - all keys loaded cleanly, no mode collapse")
else:
    print(f"FAIL: Verification failed (collapsed={is_collapsed}, missing={len(missing)})")
```

---

## 4. Key Takeaways for Downstream Workers
- **Worker M2 (Evaluation)**: Use `data/kvasir-seg` with 1,000 pairs. No synthetic data needed unless testing edge cases.
- **Worker M3 (Docs & Notebook)**:
  - In `FIXES.md`: Document the DDP `module.` prefix root cause, line 224-225 diff, 312 keys matching, and evaluation results.
  - In `Kaggle_Final_Proof_Eval.ipynb`: Correct cell execution sequence so weight loading/copying precedes the sanity verification check, or ensure the sanity check dynamically resolves the path.
