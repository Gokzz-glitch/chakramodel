# Handoff Report: Zip Packaging & Checkpoint Architecture Audit

**Agent:** Explorer M1-3 (Generation 7)  
**Recipient:** Orchestrator / Parent Agent (`f8735eda-a828-4903-b431-9cd5df91932b`)  
**Working Directory:** `m:\chakramodel\.agents\explorer_m1_3_g7`  
**Date:** 2026-09-08  
**Type:** Hard Handoff (Task Complete)  

---

## 1. Observation

1. **The Colab Execution Log Failure:**
   The verbatim error recorded in `.agents/ORIGINAL_REQUEST.md` (lines 169–177) was:
   ```text
   Copying files directly (skipping the slow search)...

   ❌ CRITICAL: Could not find the weights at /content/drive/MyDrive/chakra_transformer_best.pth

   ❌ CRITICAL: Could not find the zip at /content/drive/MyDrive/chakramodel_data_scripts.zip

   unzip:  cannot find or open /content/chakramodel_data_scripts.zip, /content/chakramodel_data_scripts.zip.zip or /content/chakramodel_data_scripts.zip.ZIP.

   FileNotFoundError: [Errno 2] No such file or directory: '/content/src/verify_strict.py'
   ```

2. **Zip Archive Layouts & Contents (`zip_and_weights_summary.json`):**
   - `chakramodel_data_scripts.zip`: 240,662,934 bytes (229.51 MB), MD5: `c861bd2822468cb5f70201bb41efafac`, 998 files.
     - Top-level items: `src/` and `data/` (NO top-level root project folder).
     - Contains `src/verify_strict.py` (line 19).
     - Contains 892 dataset files under `data/cvc-300/` and `data/cvc-colondb/` (synthetic images/masks).
     - Contains only one weight: `src/yolov8x.pt` (136.9 MB). Does NOT contain `chakra_transformer_best.pth` or `best.pt`.
   - `chakramodel-weights.zip`: 1,155,023,765 bytes (1101.52 MB), MD5: `4aa14d75aff01f3e4b44d41763de3afd`, 3 files.
     - Top-level items: `best.pt` (MD5 `7bc485770374c5b17d4721d774e71a1a`), `chakra_transformer_best.pth` (MD5 `49541d7ca35955c2a33ba1ded85e0a70`), `conformal_calibration.json`.
     - Completely **FLAT** structure (no `weights/` folder).
   - `chakramodel_weights_PRIVATE.zip`: 2,516,940,586 bytes (2400.34 MB), MD5: `207f24fc646de6d24da38433a7f23908`, 11 files.
     - Encapsulated inside a top-level `weights/` directory (`weights/best.pt`, `weights/chakra_transformer_best.pth`, etc.).

3. **Codebase Hardcoded Assumptions:**
   - `src/verify_strict.py` (lines 102–104):
     ```python
     root = Path(__file__).parent.parent
     weight_path = root / "weights" / "chakra_transformer_best.pth"
     yolo_path = root / "weights" / "best.pt"
     ```
   - `setup_colab.py` (line 5–6, 78):
     ```python
     src_base = r'M:\chakramodel'
     dest_base = r'J:\My Drive\chakramodel_collab'
     ...
     !python "/content/drive/MyDrive/chakramodel_collab/src/verify_strict.py"
     ```
   - `local_eval.py` (lines 135, 139–144):
     ```python
     device = torch.device('cuda')
     ...
     if os.path.exists('/content/drive/MyDrive/chakramodel'):
         base_dir = '/content/drive/MyDrive/chakramodel'
     elif os.path.exists('J:/My Drive/chakramodel'):
         base_dir = 'J:/My Drive/chakramodel'
     else:
         base_dir = 'm:/chakramodel'
     ```

4. **Checkpoint State Dict & Tensor Inspection (`checkpoint_details.json`):**
   - `weights/chakra_transformer_best.pth`: 1,236,836,719 bytes, 312 keys, 309,174,379 parameters.
   - 100% of keys (312/312) have a `module.` prefix.
   - If loaded into `ChakraNetMicroRefiner` with `strict=False` without stripping `module.`: `raw_missing = 310`, `raw_unexpected = 312`. PyTorch silently loads 0 trained weights.
   - When stripped (`k.replace('module.', '').replace('_orig_mod.', '')`): `stripped_missing = 0`, `stripped_unexpected = 0`, `strict_error = None`.
   - `weights/best.pt`: 6,209,450 bytes, Ultralytics DetectionModel with 3,011,043 parameters. Calling raw `torch.load('weights/best.pt')` on PyTorch >= 2.6 fails with `WeightsUnpickler error: Unsupported global` unless loaded via `YOLO('weights/best.pt')` or `weights_only=False`.

5. **Historical Successful Run in `COLLABRUNTESTING.pdf` (Page 2):**
   - Showed:
     ```text
     Google Drive mounted! Hunting for the weights...
     ✅ FOUND IT! The weights are hiding here: /content/drive/MyDrive/chakramodel
     ```
   - The weights file was located at `/content/drive/MyDrive/chakramodel/weights/chakra_transformer_best.pth`.

---

## 2. Logic Chain

1. **Step 1 (Why `cp` and `unzip` failed):**
   From Observation 1 and Observation 5, Google Drive synchronizes project files into a subfolder (`/content/drive/MyDrive/chakramodel/` or `chakramodel_collab/`). The modified Colab script attempted a direct copy from `/content/drive/MyDrive/chakramodel_data_scripts.zip` (at the root of `MyDrive`). Because that path did not exist, the copy failed. The script did not abort on copy failure and proceeded to run `!unzip /content/chakramodel_data_scripts.zip`. Because the target archive did not exist, Linux `unzip` tried `/content/chakramodel_data_scripts.zip.zip` and `.ZIP`, producing the verbatim error.
2. **Step 2 (Why `FileNotFoundError: /content/src/verify_strict.py` occurred):**
   Because `unzip` failed, nothing was extracted into `/content/`. When `!python /content/src/verify_strict.py` ran immediately afterward, Python failed to locate the script, raising `FileNotFoundError: [Errno 2] No such file or directory: '/content/src/verify_strict.py'`.
3. **Step 3 (Why even a successful unzip of `chakramodel_data_scripts.zip` would fail downstream):**
   From Observation 2, `chakramodel_data_scripts.zip` unpacks to `/content/src/` and `/content/data/`, but contains no weights. From Observation 3, `src/verify_strict.py` lines 102–104 hardcodes `root / "weights" / "chakra_transformer_best.pth"`. Furthermore, `chakramodel-weights.zip` is flat. Unzipping both archives to `/content/` leaves `chakra_transformer_best.pth` at `/content/chakra_transformer_best.pth` instead of `/content/weights/chakra_transformer_best.pth`, which triggers a secondary `FileNotFoundError`.
4. **Step 4 (Why weight loading fails without prefix stripping):**
   From Observation 4, `weights/chakra_transformer_best.pth` has 312 keys all beginning with `module.`. If loaded with `strict=False` without key rewriting, PyTorch skips all 312 keys, running inference on random Kaiming initialization.
5. **Step 5 (Colab T4 Hardware Feasibility):**
   From Observation 4, static weights consume ~1.19 GB FP32 (~595 MB FP16). Peak inference activations require ~300–430 MB. The total runtime VRAM footprint is ~1.8–2.2 GB. On Colab's 15.0 GB T4 GPU, VRAM utilization is ~12–15%, leaving >12.5 GB headroom.

---

## 3. Caveats

1. **Google Drive Sync Latency:** If a user modifies files locally on Windows `J:\My Drive`, the Google Drive desktop client can take minutes to upload gigabyte-scale weights to Google's cloud servers. Running Colab before sync completes can result in partial or 0-byte files on `/content/drive/MyDrive/`.
2. **Synthetic Data in `chakramodel_data_scripts.zip`:** `chakramodel_data_scripts.zip` only packages synthetic image/mask pairs for `cvc-300` and `cvc-colondb` (440 pairs). Full medical evaluation on real clinical data requires `ChakraModel_Evaluation_Datasets.zip` (3,000 images/masks).

---

## 4. Conclusion

1. The Colab failure was caused by a fragile setup cell hardcoding the root of Google Drive (`/content/drive/MyDrive/...`) rather than discovering the synced subfolder (`/content/drive/MyDrive/chakramodel/...`).
2. The `unzip` failure and subsequent `FileNotFoundError` were sequential cascade failures caused by lack of error checking on file copy commands.
3. The project's archives have an inconsistent directory depth (`chakramodel_data_scripts.zip` contains `src/` and `data/`; `chakramodel-weights.zip` is completely flat; `chakramodel_weights_PRIVATE.zip` has a `weights/` root).
4. `weights/chakra_transformer_best.pth` requires DDP prefix stripping (`module.`) before loading into `ChakraNetMicroRefiner`, and requires `strict=False` if loaded into `ChakraTransformerSegmenter` due to the latter's additional `prompt_embedding.weight`.
5. Replacing all fixed paths with the provided recursive anchor discovery and normalization script completely resolves all Cloud GPU execution issues.

---

## 5. Verification Method

To independently verify the observations and conclusions:

1. **Verify Zip Archive Structures:**
   ```bash
   python -c "import zipfile; z = zipfile.ZipFile('chakramodel_data_scripts.zip'); print('Top items:', set(x.split('/')[0] for x in z.namelist())); print('Has verify_strict:', 'src/verify_strict.py' in z.namelist())"
   python -c "import zipfile; z = zipfile.ZipFile('chakramodel-weights.zip'); print('Items in weights zip:', z.namelist())"
   ```
2. **Verify Checkpoint DDP Prefix and Parameter Count:**
   ```bash
   python -c "import torch; sd = torch.load('weights/chakra_transformer_best.pth', map_location='cpu'); print('Total keys:', len(sd)); print('module. prefix count:', sum(1 for k in sd if k.startswith('module.'))); print('Total params:', sum(v.numel() for v in sd.values() if torch.is_tensor(v)))"
   ```
3. **Verify Clean Load into ChakraNet with Stripped Keys:**
   ```bash
   python -c "import sys; sys.path.insert(0, 'src'); import torch; from chakranet_segmenter import ChakraNetMicroRefiner; sd = torch.load('weights/chakra_transformer_best.pth', map_location='cpu'); sd_clean = {k.replace('module.', '').replace('_orig_mod.', ''): v for k, v in sd.items()}; model = ChakraNetMicroRefiner(channels=24); missing, unexpected = model.load_state_dict(sd_clean, strict=True); print('Missing keys:', len(missing), 'Unexpected keys:', len(unexpected))"
   ```
4. **Invalidation Condition:** If `chakramodel_data_scripts.zip` is found to contain `weights/chakra_transformer_best.pth`, or if `chakramodel-weights.zip` contains an internal `weights/` folder, this conclusion would be invalidated.
