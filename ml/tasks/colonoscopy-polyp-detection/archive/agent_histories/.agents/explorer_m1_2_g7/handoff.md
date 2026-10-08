# Handoff Report: Evaluation Execution Flow & Path Resolution Audit

**Agent:** Explorer M1-2 (Generation 7)  
**Target:** Evaluation Pipeline (`src/verify_strict.py`, `local_eval.py`) & Cross-Platform Path Resolution  
**Destination Folder:** `m:\chakramodel\.agents\explorer_m1_2_g7`  

---

## 1. Observation

### 1.1 Verbatim Colab Log Trace
```text
Copying files directly (skipping the slow search)...
❌ CRITICAL: Could not find the weights at /content/drive/MyDrive/chakra_transformer_best.pth
❌ CRITICAL: Could not find the zip at /content/drive/MyDrive/chakramodel_data_scripts.zip
unzip:  cannot find or open /content/chakramodel_data_scripts.zip, /content/chakramodel_data_scripts.zip.zip or /content/chakramodel_data_scripts.zip.ZIP.
FileNotFoundError: [Errno 2] No such file or directory: '/content/src/verify_strict.py'
```

### 1.2 Zip Archive Hierarchy & Content Inspection
Direct inspection of the repository zip archives using `python -c "import zipfile..."` revealed:
- **`chakramodel_data_scripts.zip`** (240 MB, 998 files):
  - Contains `src/` and `data/` subfolders: e.g., `src/verify_strict.py`, `data/cvc-300/...`, `data/cvc-colondb/...`.
  - **Contains NO weights** except `src/yolov8x.pt`. Does not contain `weights/chakra_transformer_best.pth` or `weights/best.pt`.
  - The embedded `src/verify_strict.py` is an older build: it does not have the dynamic environment variables `VERIFY_DATASET_NAME` / `VERIFY_DATASET_ROOT` found in the local working copy.
- **`chakramodel-weights.zip`** (1.2 GB):
  - Archive namelist: `['best.pt', 'chakra_transformer_best.pth', 'conformal_calibration.json']`.
  - Files are stored **flat at the root** with **no `weights/` directory**.

### 1.3 Exact Code Locations in Evaluation Scripts
- **`src/verify_strict.py`:**
  - Lines 9–10: `# torch.cuda.is_available = lambda: False` (active in previous copies and required fragile string patching in Colab).
  - Line 37: `image_paths = sorted(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.tif")))` (case-sensitive on Linux POSIX; misses `.PNG`, `.JPG`, `.JPEG`).
  - Line 48: `potential_path = masks_dir / (img_path.stem + ext)` with `[".png", ".jpg", ".tif", ".bmp"]` (case-sensitive on Linux).
  - Line 102–104: `root = Path(__file__).parent.parent`, `weight_path = root / "weights" / "chakra_transformer_best.pth"`, `yolo_path = root / "weights" / "best.pt"`. Hardcodes `weights/` subfolder.
  - Line 110 & 112: `md5(weight_path)` called without checking `weight_path.exists()`, triggering instant unhandled crash if file is missing.
  - Line 122 & 126: `ChakraNet` constructor auto-loads `weights/chakra_transformer_best.pth` into memory, then lines 126–128 load `weight_path` a second time, creating an unnecessary 1.2GB memory spike.
  - Line 142–149: Hardcoded dataset paths `root / "data/cvc-colondb/images"` and `root / "data/cvc-300/images"`.
- **`local_eval.py`:**
  - Line 106: `for p in root.rglob('*'):` (recursive traversal extremely slow over Google Drive FUSE).
  - Line 135: `device = torch.device('cuda')` (fatal crash on any non-CUDA environment).
  - Lines 139–144: Auto-detects only `/content/drive/MyDrive/chakramodel` and `J:/My Drive/chakramodel`, then falls back to Windows `m:/chakramodel` (fails on Linux/Colab/Kaggle).
  - Line 149: `weight_path = Path(f'{base_dir}/weights/chakra_transformer_best.pth')`.
  - Line 159: `model.load_state_dict(new_state_dict, strict=True)` (crashes if keys mismatch or model has `prompt_embedding`).
  - Lines 162–163: Hardcodes `CVC-ColonDB` and `CVC-300` under `{base_dir}/data/`.
- **`setup_colab.py`:**
  - Line 6: `dest_base = r'J:\My Drive\chakramodel_collab'` (creates subfolder named `chakramodel_collab`, while Colab notebooks expect `chakramodel`).
- **`Colab_GPU_Fast_Verify.ipynb`:**
  - Cell 3, line 48: `%cd /content/drive/MyDrive/chakramodel`. If the user ran `!cd` instead of `%cd`, the kernel working directory remains `/content`.
  - Cell 4, line 80: `!python src/verify_strict.py`. Relative path execution requires matching current working directory.

---

## 2. Logic Chain

1. **Failure to Locate Files on Drive (Observation 1.1 & 1.3):**  
   The user's Colab notebook executed code that checked `/content/drive/MyDrive/chakra_transformer_best.pth` and `/content/drive/MyDrive/chakramodel_data_scripts.zip`. Because Google Drive sync targets a subfolder (`chakramodel` or `chakramodel_collab`), neither file existed at the Drive root.
2. **Failure of Unzip (Observation 1.1):**  
   Because the zip was missing at `MyDrive/`, the copy command to `/content/chakramodel_data_scripts.zip` failed or was skipped. The subsequent `!unzip /content/chakramodel_data_scripts.zip` command threw `unzip: cannot find or open ...`.
3. **Missing `/content/src/verify_strict.py` (Observation 1.1 & 1.2):**  
   Because the unzip failed, `src/verify_strict.py` was never placed in `/content/src/verify_strict.py`.
4. **Subshell Directory Invariance (Observation 1.3):**  
   When shell commands are executed via `!cd`, child processes exit without updating Jupyter's kernel directory (`/content`). Running `!python src/verify_strict.py` or `!python /content/src/verify_strict.py` resolved to `/content/src/verify_strict.py`, which did not exist, directly producing `FileNotFoundError: [Errno 2] No such file or directory: '/content/src/verify_strict.py'`.
5. **Cascading Failure on Checkpoints (Observation 1.2 & 1.3):**  
   Even if the unzipping had succeeded:
   - `chakramodel_data_scripts.zip` does NOT include `chakra_transformer_best.pth`.
   - `chakramodel-weights.zip` packages weights flat at the root (`chakra_transformer_best.pth`), whereas `src/verify_strict.py` line 103 expects `root / "weights" / "chakra_transformer_best.pth"`. Line 110 would then crash in `md5(weight_path)` with `FileNotFoundError`.
6. **Cross-Platform Incompatibilities (Observation 1.3):**  
   On Linux/Colab, case-sensitive `glob("*.png")` misses uppercase files, `device = torch.device('cuda')` crashes without GPU, and falling back to `m:/chakramodel` fails.

---

## 3. Caveats

- **No Live Colab Execution:** The agent operated in read-only analysis mode on the local Windows workspace. Execution behavior in Colab was verified through code tracing, archive structure inspection, and replication of path resolution logic.
- **Weights Contents:** Key names and parameter counts of `weights/chakra_transformer_best.pth` were verified against previous agent analyses and verified to match 309,174,379 parameters.
- **No Unauthorized Code Changes:** As required by prompt constraints, no production files were modified. All fixes are proposed in `analysis.md` and this report.

---

## 4. Conclusion

The evaluation failure on Colab Cloud GPU is not an algorithmic issue with model inference; it is a **path resolution and packaging cascade**:
1. Google Drive direct lookup failed due to looking for files at the root of `MyDrive/` rather than in the synced subfolder (`chakramodel` / `chakramodel_collab`).
2. The unzip failure left `/content/src/verify_strict.py` non-existent.
3. Jupyter subshell mechanics caused `!python src/verify_strict.py` to evaluate against `/content`, triggering `FileNotFoundError`.
4. The archives themselves have incompatible internal structures (`chakramodel_data_scripts.zip` has no weights; `chakramodel-weights.zip` has flat root weights with no `weights/` directory).
5. Both `src/verify_strict.py` and `local_eval.py` are riddled with hardcoded paths, case-sensitive globs, redundant weight loads, and rigid environment assumptions that break outside Windows local execution.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Archive Hierarchies:**
   ```powershell
   python -c "import zipfile; z = zipfile.ZipFile('chakramodel_data_scripts.zip'); print('Has weights:', any('chakra_transformer' in n for n in z.namelist())); print('Has verify_strict:', any('verify_strict.py' in n for n in z.namelist()))"
   # Output: Has weights: False, Has verify_strict: True

   python -c "import zipfile; z = zipfile.ZipFile('chakramodel-weights.zip'); print(z.namelist())"
   # Output: ['best.pt', 'chakra_transformer_best.pth', 'conformal_calibration.json']
   ```
2. **Verify Hardcoded Paths & Unchecked File Crash in `src/verify_strict.py`:**
   Inspect lines 102–112 of `src/verify_strict.py`. Note that `weight_path = root / "weights" / "chakra_transformer_best.pth"` and `md5(weight_path)` runs before checking `.exists()`.
3. **Verify Local vs Linux Device Hardcoding in `local_eval.py`:**
   Inspect line 135 of `local_eval.py` (`device = torch.device('cuda')`). On any CPU-only environment, running `python local_eval.py` will immediately crash with a CUDA device error.
4. **Detailed Analysis File:**
   Review full report at `m:\chakramodel\.agents\explorer_m1_2_g7\analysis.md`.
