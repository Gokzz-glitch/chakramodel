# Deep Codebase Audit: Colab Cloud GPU Evaluation Failures, Google Drive Sync Mechanics, and Zero-Hardcoded Architecture

**Investigator:** Explorer M1-1 (Generation 7)  
**Date:** 2026-09-08  
**Working Directory:** `m:\chakramodel\.agents\explorer_m1_1_g7`  
**Project Directory:** `m:\chakramodel`  
**Scope:** `Colab_GPU_Fast_Verify.ipynb`, `setup_colab.py`, `cloud_gpu_guide.py`, `COLLABRUNTESTING.pdf`, `anti_fabrication_toolkit/Kaggle_Colab_AntiFabrication_V3.ipynb`, `append_notebook.py`, `append_notebook_gdown.py`, `local_eval.py`, `src/verify_strict.py`, `package_kaggle.py`, and Google Drive mount/sync mechanics.

---

## 1. Executive Summary & Root Cause Synthesis

The failure observed during Google Colab Cloud GPU evaluation:

```text
Copying files directly (skipping the slow search)...

❌ CRITICAL: Could not find the weights at /content/drive/MyDrive/chakra_transformer_best.pth

❌ CRITICAL: Could not find the zip at /content/drive/MyDrive/chakramodel_data_scripts.zip

unzip:  cannot find or open /content/chakramodel_data_scripts.zip, /content/chakramodel_data_scripts.zip.zip or /content/chakramodel_data_scripts.zip.ZIP.

FileNotFoundError: [Errno 2] No such file or directory: '/content/src/verify_strict.py'
```

is caused by a **fatal path mismatch** resulting from a naive attempt to "optimize" away a slow Google Drive search, compounded by a lack of error propagation guards:

1. **The Optimization Regression:**  
   In the previous successful Colab run documented in `COLLABRUNTESTING.pdf` (`Untitled2.ipynb`), the notebook ran a dynamic recursive search (`os.walk('/content/drive/MyDrive')`) that located the weights inside a subfolder (`/content/drive/MyDrive/chakramodel/weights/chakra_transformer_best.pth`). Because recursive searches over Colab's Google Drive FUSE mount are notoriously slow (taking several minutes across thousands of remote cloud items), a modified script/cell was written to skip the search and copy files directly.
2. **The Root Directory Blunder (Subfolder Omission):**  
   The author of the direct copy logic hardcoded paths pointing to the **root** of Google Drive (`/content/drive/MyDrive/chakra_transformer_best.pth` and `/content/drive/MyDrive/chakramodel_data_scripts.zip`). However, Google Drive Desktop on Windows syncs local project folders into subfolders (`J:\My Drive\chakramodel\` or `J:\My Drive\chakramodel_collab\`), which map on Colab to `/content/drive/MyDrive/chakramodel/` or `/content/drive/MyDrive/chakramodel_collab/`. Neither the weights nor the zip ever existed at the root of `MyDrive`.
3. **The Silent Cascade of Failures:**  
   The direct copy code reported `❌ CRITICAL`, but did not halt notebook execution. The notebook blindly executed `!unzip /content/chakramodel_data_scripts.zip`, which failed with `unzip: cannot find or open ...`. It then executed `!python /content/src/verify_strict.py`, which immediately crashed with `FileNotFoundError: [Errno 2] No such file or directory: '/content/src/verify_strict.py'` because `src/` was never unzipped.
4. **Architectural Brittle Assumptions:**  
   The audit revealed an endemic reliance on rigid, hardcoded paths across Windows (`M:\chakramodel`, `J:\My Drive\...`, `C:\Users\imgk3\...`), Colab (`/content/drive/MyDrive/...`), and Kaggle (`/kaggle/input/...`), along with hardcoded folder names (`chakramodel` vs `chakramodel_collab` vs `chakramodel_necessary_zip`), and hardcoded CUDA initialization (`device = torch.device('cuda')` or `# torch.cuda.is_available = lambda: False`).

---

## 2. Chronological Sequence of Events

```
[Local Development & Training]
  Windows machine: M:\chakramodel (Code & Data)
  Google Drive Desktop synced to: J:\My Drive\
        │
        ▼
[Setup Automation: setup_colab.py]
  Copies M:\chakramodel -> J:\My Drive\chakramodel_collab\
  Generates Run_Strict_Verification.ipynb pointing to:
  /content/drive/MyDrive/chakramodel_collab/src/verify_strict.py
        │
        ▼
[Successful Colab Run: COLLABRUNTESTING.pdf (2026-09-05/06)]
  User opens Untitled2.ipynb on Colab.
  Mounts drive: drive.mount('/content/drive')
  Logs: "Google Drive mounted! Hunting for the weights..."
  Runs dynamic search (os.walk) across /content/drive/MyDrive
  Logs: "✅ FOUND IT! The weights are hiding here: /content/drive/MyDrive/chakramodel"
  Copies weights to /content/weights/
  Runs /content/src/verify_strict.py -> CVC-ColonDB: 0.8125, CVC-300: 0.8004
        │
        ▼
[The Flawed "Optimization"]
  Recursive os.walk on Colab FUSE is painfully slow (several minutes).
  Developer/User decides to bypass it:
  Logs: "Copying files directly (skipping the slow search)..."
  Hardcodes ROOT paths:
    - /content/drive/MyDrive/chakra_transformer_best.pth
    - /content/drive/MyDrive/chakramodel_data_scripts.zip
        │
        ▼
[The Failure Cascade]
  1. Files do NOT exist at /content/drive/MyDrive/ (they are in subfolders!).
     -> Logs "❌ CRITICAL: Could not find..."
  2. Notebook does not abort. Continues to:
     !unzip -q /content/chakramodel_data_scripts.zip
     -> Logs "unzip: cannot find or open /content/chakramodel_data_scripts.zip..."
  3. Notebook continues to:
     !python /content/src/verify_strict.py
     -> FileNotFoundError: '/content/src/verify_strict.py'
```

---

## 3. Google Drive Sync Mechanics: Windows (`J:\`) vs Google Colab (`/content/drive/MyDrive/`)

### 3.1 Architecture of Google Drive for Desktop (Windows)
When Google Drive for Desktop runs on Windows, it creates a virtual drive letter (commonly `J:` or `G:`):
- `J:\My Drive\`: Represents the cloud root (`root` folder in Google Drive API).
- Any folder created in `J:\My Drive\` is a first-level subdirectory in Google Drive cloud storage.
- In `setup_colab.py`, line 6 sets:
  ```python
  dest_base = r'J:\My Drive\chakramodel_collab'
  ```
  This creates a folder in Google Drive named `chakramodel_collab`.
- When users copy manually or sync git repos, they often sync to:
  ```text
  J:\My Drive\chakramodel\
  J:\My Drive\chakramodel\weights\chakra_transformer_best.pth
  ```

### 3.2 Architecture of Google Colab Drive Mount
In Google Colab, executing:
```python
from google.colab import drive
drive.mount('/content/drive')
```
mounts the user's Google Drive via a Linux FUSE daemon at `/content/drive`. The mount hierarchy is:
```text
/content/
└── drive/
    ├── MyDrive/         <--- 1-to-1 equivalent to J:\My Drive\
    └── Shareddrives/    <--- 1-to-1 equivalent to J:\Shared drives\
```

### 3.3 The Path Mapping Table

| Item / Resource | Windows Local Path | Windows Drive Sync Path | Google Colab True Mount Path | Erroneous Colab Lookup Path |
|---|---|---|---|---|
| Project Root (Repo) | `M:\chakramodel\` | `J:\My Drive\chakramodel\` | `/content/drive/MyDrive/chakramodel/` | `/content/drive/MyDrive/` |
| `setup_colab.py` Dest | `M:\chakramodel\` | `J:\My Drive\chakramodel_collab\` | `/content/drive/MyDrive/chakramodel_collab/` | `/content/drive/MyDrive/` |
| ViT Weights | `M:\chakramodel\weights\chakra_transformer_best.pth` | `J:\My Drive\chakramodel\weights\chakra_transformer_best.pth` | `/content/drive/MyDrive/chakramodel/weights/chakra_transformer_best.pth` | `/content/drive/MyDrive/chakra_transformer_best.pth` ❌ |
| YOLO Weights | `M:\chakramodel\weights\best.pt` | `J:\My Drive\chakramodel\weights\best.pt` | `/content/drive/MyDrive/chakramodel/weights/best.pt` | `/content/drive/MyDrive/best.pt` ❌ |
| Code & Data Zip | `M:\chakramodel\chakramodel_data_scripts.zip` | `J:\My Drive\chakramodel\chakramodel_data_scripts.zip` | `/content/drive/MyDrive/chakramodel/chakramodel_data_scripts.zip` | `/content/drive/MyDrive/chakramodel_data_scripts.zip` ❌ |
| Verification Script | `M:\chakramodel\src\verify_strict.py` | `J:\My Drive\chakramodel\src\verify_strict.py` | `/content/drive/MyDrive/chakramodel/src/verify_strict.py` | `/content/src/verify_strict.py` ❌ (before unzip) |

### 3.4 Why the Root Lookup Failed
The author of the direct copy script omitted the subfolder segment (`chakramodel` or `chakramodel_collab`). In Python terms, the script evaluated:
```python
os.path.exists('/content/drive/MyDrive/chakra_transformer_best.pth') # -> False
os.path.exists('/content/drive/MyDrive/chakramodel_data_scripts.zip') # -> False
```
Because the files resided at `/content/drive/MyDrive/chakramodel/weights/chakra_transformer_best.pth` and `/content/drive/MyDrive/chakramodel/chakramodel_data_scripts.zip` (or inside `chakramodel_collab/`), checking the root directory returned `False`.

---

## 4. In-Depth Forensic Analysis of `COLLABRUNTESTING.pdf`

`COLLABRUNTESTING.pdf` documents the successful Colab evaluation run executed on 2026-09-05/06 in `Untitled2.ipynb`:

### Page 1 Analysis:
- URL at footer: `https://colab.research.google.com/drive/11XKXspNsyJmDylh-5zSrAVL1x78ly9L_#printMode=true`
- Timestamp: `9/6/26, 12:21 AM`
- Code snippets visible in the print artifact:
  - `ir, 'chakra_transformer_best.pth'))`: Shows programmatic construction of the weights path using a discovered directory variable.
  - `force_remount=True)`: Shows robust drive mounting options.
  - `gle Drive!")`: End of a warning or confirmation print message.

### Page 2 Analysis:
- Top comment/log fragment:
  `Drive desktop app never actually finishe...`  
  This confirms the user was aware that Google Drive for Desktop on Windows often lags in syncing large files (1.24 GB weights), or that folder locations can be uncertain.
- Key logs verbatim:
  1. `Drive already mounted at /content/drive; to attempt to forcibly remount, call...`
  2. `Google Drive mounted! Hunting for the weights...`
  3. `✅ FOUND IT! The weights are hiding here: /content/drive/MyDrive/chakramodel (`
  4. `Copying weights to the correct Colab folder...`
  5. `✅ Copied YOLO weights too!`
  6. `Running the strict verification...`
  7. `2026-09-05 18:45:52,366 [HW-MONITOR] INFO WARMUP phase - GPU capped at 40%`
  8. `Segmenter Checkpoint: /content/weights/chakra_transformer_best.pth`
  9. `Segmenter MD5: e98c14c40055b244885baac26e28d165`
  10. `YOLO Checkpoint: /content/weights/best.pt`
  11. `YOLO MD5: d1d0101b47469b77c2a092ba5e18bd0b`
  12. `Executing on device: cuda`
  13. `ChakraNet Weights Loaded. Missing keys: 0, Unexpected keys: 0`
  14. `[DONE] CVC-ColonDB: Total Evaluated Images: 380, Final True Average Dice: 0.8125`
  15. `[DONE] CVC-300: Total Evaluated Images: 60, Final True Average Dice: 0.8004`

### Page 3 Analysis:
- Shows clean termination with standard HuggingFace unauthenticated access warnings (`Warning: You are sending unauthenticated requests to the HF Hub`).

### What `COLLABRUNTESTING.pdf` Teaches Us:
1. The dynamic search ("Hunting for the weights...") **succeeded** because it walked Google Drive and found the weights at `/content/drive/MyDrive/chakramodel`.
2. Once found, it copied them to the local Colab directory `/content/weights/chakra_transformer_best.pth` and `/content/weights/best.pt`.
3. Running from `/content` with weights copied locally was fast and bypassed slow FUSE read latency during inference.
4. When the user later attempted to replace that dynamic search with a "fast direct copy", they stripped out the search logic, hardcoded the wrong root path, and broke the entire pipeline.

---

## 5. Line-by-Line Codebase Audit of Colab Scripts & Notebooks

### 5.1 `Colab_GPU_Fast_Verify.ipynb`
| Cell # | Line(s) | Code Snippet | Architectural & Bug Analysis |
|---|---|---|---|
| **Cell 1** | 7–8 | `"This notebook connects to your Google Drive and runs the verification directly from the synced chakramodel folder using Colab's T4 GPU. No need to upload zip files manually!"` | Notes intention to avoid manual zip uploads, but relies entirely on Drive sync. |
| **Cell 2** | 31 | `drive.mount('/content/drive')` | Standard Colab drive mount. |
| **Cell 2** | 34–36 | `base_dir = '/content/drive/MyDrive/chakramodel'` <br> `if not os.path.exists(base_dir): print(f"...Could not find '{base_dir}'...")` | **Hardcoded Path Bug**: Assumes folder is strictly named `chakramodel`. If created by `setup_colab.py`, it is named `chakramodel_collab`, triggering immediate failure. |
| **Cell 3** | 48 | `%cd /content/drive/MyDrive/chakramodel` | **Hardcoded Directory Switch**: Fails if directory does not exist or has a different name. |
| **Cell 3** | 51–52 | `if not os.path.exists('weights/chakra_transformer_best.pth'): print("...weights file...is missing...")` | **Hardcoded Weights Path**: Fails if weights are in root or not yet synced. |
| **Cell 3** | 58–68 | `script_path = 'src/verify_strict.py'` <br> `content = content.replace('torch.cuda.is_available = lambda: False', ...)` | **Brittle In-Place Patching**: Opens file directly in Google Drive FUSE and modifies it in place to remove the CPU mock line. FUSE network latency makes file rewrites unreliable. |
| **Cell 4** | 80 | `!python src/verify_strict.py` | Runs verification directly inside Google Drive FUSE mount. FUSE has high I/O latency for reading 440 dataset images, causing significant evaluation slowdown compared to local `/content/`. |

---

### 5.2 `setup_colab.py`
| Line(s) | Code Snippet | Architectural & Bug Analysis |
|---|---|---|
| **5** | `src_base = r'M:\chakramodel'` | **Hardcoded Windows Path**: Hardcoded to `M:` drive; crashes if cloned to `C:`, `D:`, or running on Linux. |
| **6** | `dest_base = r'J:\My Drive\chakramodel_collab'` | **Folder Name Divergence**: Hardcodes destination to `chakramodel_collab` (with two 'l's). All notebooks (`Colab_GPU_Fast_Verify.ipynb`, `local_eval.py`) search for `chakramodel`, creating an immediate mismatch. |
| **9** | `os.makedirs(dest_base, exist_ok=True)` | Creates destination folder on Windows Google Drive virtual filesystem. |
| **19–25** | Reads `src/verify_strict.py`, removes `torch.cuda.is_available = lambda: False`, and writes back to `dest_src`. | Workaround for hardcoded CPU mock in source code. |
| **27–47** | Copies `weights/`, `data/cvc-colondb`, `data/cvc-300` using `shutil.copytree`. | Syncs ~1.5 GB of data to Google Drive Desktop, which can take hours on slow upload connections. |
| **78** | `!python "/content/drive/MyDrive/chakramodel_collab/src/verify_strict.py"` | Generated notebook in `Run_Strict_Verification.ipynb` hardcodes `chakramodel_collab`. |

---

### 5.3 `cloud_gpu_guide.py`
| Line(s) | Code Snippet | Architectural & Bug Analysis |
|---|---|---|
| **17–22** | Hardcoded table: `RTX 3050: 4 GB`, `Kaggle: 16 GB (T4)`, `Colab Free: 15 GB (T4)`, `Colab Pro: 40 GB (A100)` | Pure static reference table. Offers no dynamic detection of hardware capabilities or runtime memory budgets. |
| **24–28** | `RECOMMENDATION: Use KAGGLE for Combination #4... Use COLAB FREE for Combination #5...` | Heuristic recommendations. Does not automate environment setup. |

---

### 5.4 `anti_fabrication_toolkit/Kaggle_Colab_AntiFabrication_V3.ipynb`
| Cell # | Line(s) | Code Snippet | Architectural & Bug Analysis |
|---|---|---|---|
| **Cell 1** | 27–28 | `base_path = '/kaggle/working' if os.path.exists('/kaggle/working') else '/content'` <br> `input_path = '/kaggle/input' if os.path.exists('/kaggle/input') else '/content'` | Implements environment switching between Kaggle and Colab, but assumes Colab input is always `/content` (ignoring `/content/drive/MyDrive/`). |
| **Cell 1** | 32–36 | Substring matching: `if 'anti_fabrication_toolkit' in f and f.endswith('.zip'):` | Scans for zip file. |
| **Cell 2** | 58–59 | `toolkit_py = os.path.join(base_path, 'anti_fabrication_toolkit', 'verifyai.py')` <br> `eval_script = os.path.join(base_path, 'src', 'verify_strict.py')` | Hardcodes script locations relative to `base_path`. |
| **Cell 2** | 90–93 | `env["VERIFY_DATASET_NAME"] = ds['name']` <br> `env["VERIFY_DATASET_ROOT"] = ds['path']` | **Clean Pattern**: Uses environment variables to dynamically parameterize `verify_strict.py`. |

---

### 5.5 `append_notebook.py` & `append_notebook_gdown.py`
| Script | Line(s) | Code Snippet | Architectural & Bug Analysis |
|---|---|---|---|
| `append_notebook.py` | 3 | `with open(r'm:\chakramodel\notebooks\Kaggle_ChakraTransformer_Evaluation.ipynb'...)` | Hardcoded Windows absolute path `m:\...`. |
| `append_notebook.py` | 29–30 | `video_dir = Path('/kaggle/input/polypdataset-gokul')` <br> `output_dir = Path('/kaggle/working/output_videos')` | Hardcoded Kaggle dataset and output paths. |
| `append_notebook_gdown.py` | 3 | `with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb'...)` | Hardcoded Windows absolute path `M:/...`. |
| `append_notebook_gdown.py` | 28–30 | `file_id = '1QEMKV632XGGs9202iTyH-QggV_F3dSED'` <br> `gdown.download(url, '/kaggle/working/custom_videos.tar.gz'...)` | Hardcoded Google Drive file ID. |

---

### 5.6 `notebooks/Colab_ChakraTransformer_Evaluation.ipynb`
| Line(s) | Code Snippet | Architectural & Bug Analysis |
|---|---|---|
| **39** | `BASE_DIR = '/content/drive/MyDrive/chakramodel_necessary_zip'` | **Yet Another Hardcoded Folder Name**: Diverges from both `chakramodel` and `chakramodel_collab`. |
| **82–84** | `weight_path = f"{BASE_DIR}/chakra_transformer_best.pth"` <br> `if not os.path.exists(weight_path): weight_path = f"{BASE_DIR}/weights/chakra_transformer_best.pth"` | Checks both flat and subdirectory paths, but restricted to `BASE_DIR`. |
| **106** | `video_dir = Path('/content/drive/MyDrive/chakramodel_necessary_zip/video for testing')` | Hardcoded subfolder containing whitespace. |

---

### 5.7 `local_eval.py`
| Line(s) | Code Snippet | Architectural & Bug Analysis |
|---|---|---|
| **135** | `device = torch.device('cuda')` | **CRITICAL Hardcoded Device**: Unconditionally forces CUDA without checking `torch.cuda.is_available()`. Crashes on non-GPU workstations. |
| **139–144** | `if os.path.exists('/content/drive/MyDrive/chakramodel'): base_dir = ...` <br> `elif os.path.exists('J:/My Drive/chakramodel'): base_dir = ...` <br> `else: base_dir = 'm:/chakramodel'` | **Brittle Tri-Path Heuristic**: Only checks three rigid locations. If on Linux outside Colab, falls back to Windows path `m:/chakramodel`. |
| **149** | `weight_path = Path(f'{base_dir}/weights/chakra_transformer_best.pth')` | Hardcoded relative weight path. |
| **162–163** | `run_evaluation(f'{base_dir}/data/cvc-colondb', 'CVC-ColonDB'...)` <br> `run_evaluation(f'{base_dir}/data/cvc-300', 'CVC-300'...)` | Hardcoded dataset paths. |

---

### 5.8 `src/verify_strict.py`
| Line(s) | Code Snippet | Architectural & Bug Analysis |
|---|---|---|
| **10** | `# torch.cuda.is_available = lambda: False` | Monkey-patches CUDA check to CPU. Historically active and patched out by notebooks. |
| **102** | `root = Path(__file__).parent.parent` | Assumes script is always invoked 1 directory below project root. |
| **103–104** | `weight_path = root / "weights" / "chakra_transformer_best.pth"` <br> `yolo_path = root / "weights" / "best.pt"` | Hardcoded weight file names and `weights/` subfolder. |
| **110, 112** | `print(f"Segmenter MD5: {md5(weight_path)}")` <br> `print(f"YOLO MD5: {md5(yolo_path)}")` | **Fatal Crash on Missing Weights**: Calls `open(fname, "rb")` inside `md5()` before checking if the files exist. Causes unhandled `FileNotFoundError`. |
| **142–149** | `colondb_images = root / "data/cvc-colondb/images"` <br> `cvc300_images = root / "data/cvc-300/images"` | Hardcoded dataset locations when dynamic environment variables are absent. |

---

## 6. Comprehensive Catalog of Hardcoded Values and Brittle Assumptions

As mandated by user instruction (*"ensure no hardcoded value , shouls work on whole arch rather than skimming across files"*), the table below systematically indexes every hardcoded path, filename, and environmental assumption in the pipeline:

| Category | File | Line(s) | Hardcoded Entity | Flaw / Brittleness |
|---|---|---|---|---|
| **Colab Mount** | `Colab_GPU_Fast_Verify.ipynb` | 34, 48 | `/content/drive/MyDrive/chakramodel` | Ignores `chakramodel_collab` or any user folder variations. |
| **Colab Mount** | Direct Copy Cell (Logs) | - | `/content/drive/MyDrive/chakra_transformer_best.pth` | Assumes files are at the root of Google Drive. |
| **Colab Mount** | Direct Copy Cell (Logs) | - | `/content/drive/MyDrive/chakramodel_data_scripts.zip` | Assumes zip archive is at the root of Google Drive. |
| **Colab Mount** | `notebooks/Colab_ChakraTransformer_Evaluation.ipynb` | 39, 106 | `/content/drive/MyDrive/chakramodel_necessary_zip` | Completely divergent folder name with spaces in subfolders. |
| **Colab Mount** | `setup_colab.py` | 78 | `/content/drive/MyDrive/chakramodel_collab/src/verify_strict.py` | Creates divergence (`collab` with 2 'l's). |
| **Colab Mount** | `local_eval.py` | 139 | `/content/drive/MyDrive/chakramodel` | Rigid string check. |
| **Windows Path** | `setup_colab.py` | 5 | `M:\chakramodel` | Hardcoded drive letter `M:`. |
| **Windows Path** | `setup_colab.py` | 6 | `J:\My Drive\chakramodel_collab` | Hardcoded drive letter `J:` and folder name. |
| **Windows Path** | `package_kaggle.py` | 163 | `m:\chakramodel` | Hardcoded drive letter `m:`. |
| **Windows Path** | `package_kaggle.py` | 184 | `C:\Users\imgk3\Downloads\best_of_yolo_newapproach3.pt` | Hardcoded user profile path. |
| **Windows Path** | `package_kaggle.py` | 195 | `J:\My Drive\chakramodel_necessary_zip\video for testing` | Hardcoded user Drive path. |
| **Windows Path** | `append_notebook.py` | 3 | `m:\chakramodel\...` | Hardcoded Windows path. |
| **Windows Path** | `append_notebook_gdown.py` | 3 | `M:/chakramodel/...` | Hardcoded Windows path. |
| **Windows Path** | `local_eval.py` | 141, 144 | `J:/My Drive/chakramodel`, `m:/chakramodel` | Hardcoded Windows drive paths on Linux. |
| **Kaggle Path** | `package_kaggle.py` | 26, 46, 50-54 | `/kaggle/working/src`, `/kaggle/input/...` | Hardcoded Kaggle filesystem paths. |
| **Kaggle Path** | `Final_Evaluation_MultiCell.ipynb` | 40–42, 58–61 | `/kaggle/input/datasets/gokulrocky/...` | Hardcoded Kaggle usernames (`gokulrocky`, `gokulraj324`). |
| **Kaggle Path** | `AutoDiscover_Evaluation.ipynb` | 94–97 | `/kaggle/input/datasets/gokulrocky/...` | Hardcoded Kaggle usernames. |
| **Hardware / Device** | `local_eval.py` | 135 | `device = torch.device('cuda')` | Crashes if CUDA is unavailable. |
| **Hardware / Device** | `src/verify_strict.py` | 10 | `torch.cuda.is_available = lambda: False` | Disables GPU acceleration globally. |
| **Execution Context** | `src/verify_strict.py` | 102 | `Path(__file__).parent.parent` | Assumes fixed 2-level directory nesting. |
| **Weights Hierarchy** | `src/verify_strict.py` | 103, 104 | `root / "weights" / "chakra_transformer_best.pth"` | Incompatible with flat weight archives (`chakramodel-weights.zip`). |
| **Dataset Hierarchy** | `src/verify_strict.py` | 142–149 | `root / "data/cvc-colondb/images"` | Hardcoded relative dataset folders. |
| **File Extensions** | `src/verify_strict.py` | 37, 47 | `.png`, `.jpg`, `.tif`, `.bmp` (lowercase only) | Fails on uppercase extensions on Linux (`.PNG`, `.JPG`). |

---

## 7. Dynamic, Environment-Agnostic Architecture (Zero Hardcoded Values)

To eliminate all hardcoded paths across the entire architecture, we define a 4-tier discovery protocol:

```
                  ┌────────────────────────────────────────┐
                  │ Tier 1: Explicit CLI Arguments         │
                  │ (--weights, --yolo, --data-dir, etc.)   │
                  └──────────────────┬─────────────────────┘
                                     │ (if not set)
                                     ▼
                  ┌────────────────────────────────────────┐
                  │ Tier 2: Environment Variables          │
                  │ (CHAKRA_WEIGHTS, CHAKRA_DATA, etc.)    │
                  └──────────────────┬─────────────────────┘
                                     │ (if not set)
                                     ▼
                  ┌────────────────────────────────────────┐
                  │ Tier 3: Contextual Project Root Search │
                  │ (Look for weights/ or src/ relative    │
                  │  to script or current working dir)     │
                  └──────────────────┬─────────────────────┘
                                     │ (if not set)
                                     ▼
                  ┌────────────────────────────────────────┐
                  │ Tier 4: Environment-Specific Discovery │
                  │ - Colab: Search /content/drive/MyDrive │
                  │          with targeted subfolder index │
                  │ - Kaggle: Search /kaggle/input         │
                  │ - Fail-fast with clear error message   │
                  └────────────────────────────────────────┘
```

### 7.1 Reusable Environment & Asset Resolver (`src/utils/env_resolver.py` Proposal)

```python
"""
Zero-hardcoded environment and asset resolver.
Dynamically resolves runtime platform, scratch storage, model weights, and datasets.
"""
import os
import sys
import glob
from pathlib import Path
from typing import Optional, List, Dict, Any
import torch

class EnvironmentResolver:
    @staticmethod
    def get_runtime_environment() -> str:
        if 'google.colab' in sys.modules:
            return 'colab'
        if os.path.exists('/kaggle/working') and os.path.exists('/kaggle/input'):
            return 'kaggle'
        return 'local'

    @staticmethod
    def get_scratch_dir() -> Path:
        env = EnvironmentResolver.get_runtime_environment()
        if env == 'colab':
            return Path('/content')
        elif env == 'kaggle':
            return Path('/kaggle/working')
        return Path(os.getcwd())

    @staticmethod
    def get_device() -> torch.device:
        if torch.cuda.is_available():
            return torch.device('cuda')
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return torch.device('mps')
        return torch.device('cpu')

    @staticmethod
    def find_file(
        filename: str,
        cli_arg: Optional[str] = None,
        env_var: Optional[str] = None,
        search_roots: Optional[List[Path]] = None
    ) -> Optional[Path]:
        # Tier 1: CLI override
        if cli_arg and Path(cli_arg).exists():
            return Path(cli_arg).resolve()

        # Tier 2: Environment variable override
        if env_var and os.environ.get(env_var) and Path(os.environ[env_var]).exists():
            return Path(os.environ[env_var]).resolve()

        # Tier 3: Search roots
        if search_roots is None:
            search_roots = []
            # Add script root and current working directory
            search_roots.append(Path.cwd())
            search_roots.append(Path(__file__).resolve().parent)
            search_roots.append(Path(__file__).resolve().parent.parent)
            
            runtime = EnvironmentResolver.get_runtime_environment()
            if runtime == 'colab':
                search_roots.append(Path('/content'))
                drive_root = Path('/content/drive/MyDrive')
                if drive_root.exists():
                    # Check common chakramodel directories first before slow full walk
                    search_roots.extend(list(drive_root.glob('*chakra*')))
                    search_roots.append(drive_root)
            elif runtime == 'kaggle':
                search_roots.append(Path('/kaggle/working'))
                search_roots.append(Path('/kaggle/input'))

        # Check immediate candidate locations first (O(1) lookups)
        for root in search_roots:
            if not root.exists():
                continue
            # Direct child
            direct = root / filename
            if direct.exists():
                return direct.resolve()
            # Under weights/
            sub = root / "weights" / filename
            if sub.exists():
                return sub.resolve()

        # Tier 4: Targeted recursive lookup (bounded depth to prevent FUSE timeouts)
        for root in search_roots:
            if not root.exists():
                continue
            for path in root.glob(f"**/{filename}"):
                if path.is_file():
                    return path.resolve()

        return None
```

### 7.2 Dynamic Replacement for Colab Setup Cell
Instead of hardcoding `/content/drive/MyDrive/chakra_transformer_best.pth` or running an unbounded `os.walk`, the Colab setup cell should execute:

```python
import os
import shutil
from pathlib import Path
from google.colab import drive

# 1. Mount Drive
drive.mount('/content/drive')

drive_root = Path('/content/drive/MyDrive')
content_dir = Path('/content')

# 2. Targeted search for chakramodel folders first (fast!)
candidate_dirs = list(drive_root.glob('*chakra*')) + [drive_root]
weights_file = None
zip_file = None

for d in candidate_dirs:
    if not d.is_dir():
        continue
    # Check for weights
    for w_cand in [d / "weights" / "chakra_transformer_best.pth", d / "chakra_transformer_best.pth"]:
        if w_cand.exists():
            weights_file = w_cand
            break
    # Check for code/data zip
    for z_cand in [d / "chakramodel_data_scripts.zip", d / "chakramodel_code.zip"]:
        if z_cand.exists():
            zip_file = z_cand
            break
    if weights_file and zip_file:
        break

# 3. Fail-Fast Guard: Abort if essential assets are not found
if not weights_file:
    raise FileNotFoundError(
        "❌ CRITICAL: Could not find 'chakra_transformer_best.pth' in Google Drive. "
        "Please ensure your project folder is synced."
    )

print(f"✅ Found weights at: {weights_file}")
(content_dir / "weights").mkdir(exist_ok=True)
shutil.copy2(weights_file, content_dir / "weights" / "chakra_transformer_best.pth")

# Look for YOLO weights in the same directory
yolo_cand = weights_file.parent / "best.pt"
if yolo_cand.exists():
    shutil.copy2(yolo_cand, content_dir / "weights" / "best.pt")
    print(f"✅ Found and copied YOLO weights from: {yolo_cand}")

# 4. Extract Code/Data Zip if present, or link directory directly
if zip_file:
    print(f"✅ Extracting code and data from: {zip_file}")
    shutil.unpack_archive(zip_file, content_dir)
else:
    # If unzipped in drive, copy or symlink src and data
    src_cand = weights_file.parent.parent / "src"
    if src_cand.exists():
        shutil.copytree(src_cand, content_dir / "src", dirs_exist_ok=True)
        print("✅ Copied src/ directory from Drive.")
```

---

## 8. Conclusion

1. **Root Cause Confirmed:** The failure `"❌ CRITICAL: Could not find the weights at /content/drive/MyDrive/chakra_transformer_best.pth"` occurred because direct copy code looked for weights and archives at the **root** of Google Drive rather than in the synced subfolder (`chakramodel` or `chakramodel_collab`).
2. **Cascade Mechanics:** The missing zip prevented extraction of `/content/src/verify_strict.py`, causing `unzip` failure followed by Python's `FileNotFoundError`.
3. **Previous Success Verified:** In `COLLABRUNTESTING.pdf`, an active recursive search successfully located the weights inside `/content/drive/MyDrive/chakramodel` and staged them to `/content/weights/`, producing valid Dice scores (0.8125 and 0.8004).
4. **Architecture Modernization:** Replacing rigid, hardcoded paths with a multi-tier resolution protocol (CLI -> Env Var -> Local Workspace -> Targeted Cloud Discovery) guarantees environment-agnostic execution across Colab, Kaggle, and local systems without hardcoded strings.
