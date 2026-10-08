# Handoff Report: Requirement 2 — Recovering Files from Downloads

**From:** `explorer_m1_2_g15`  
**To:** `orchestrator_gen15` (e9d0dc6b-8d4f-4c1a-924e-6152f16b1473) / Implementer Agent  
**Date:** 2026-09-16T04:45:00+05:30  
**Handoff Type:** Hard (Task complete, fully populated)  
**Reference Analysis:** `M:\chakramodel\.agents\explorer_m1_2_g15\analysis.md`  

---

## 1. Observation

Direct observations obtained via filesystem queries, zip inspections, and checksum verifications:

1. **Source Locations & Inventory:**
   - `C:\Users\imgk3\Downloads`: 24 items total (13 Jupyter notebooks, 1 PDF audit, 1 tracking CSV, 1 1.15 GB uncompressed zip archive `om-finalkaggle-upload`, 1 empty directory `anti_fabrication_toolkit_v3_hardened`, 7 personal/system files).
   - `J:\My Drive\downloads`: 951 items (excluding `.venv` and `.git` subtrees). Contains 171 `.ipynb` notebooks, 23 `.zip` archives, 12 `.pth`/`.pt` weights files, 77 `.json` files, 30+ `.csv` files, 48 `.pdf` files.
   - Verified via: `python scan_downloads.py` -> `c_downloads_raw.json` & `j_downloads_raw.json`.

2. **Provenance Artifact for Shipped Weights:**
   - File: `J:\My Drive\downloads\om-krish-4-6 (2).ipynb`
   - File size: 45,879 bytes; SHA256: `6a2f75eecb8fbf2f6375a19113c139f4bd994fa9c3bb45bb957a8525636d9ebe`.
   - Inspection of cell outputs: training runs with 44 batches/epoch over 100 epochs, with the final best validation checkpoint saved at Epoch 54. Arithmetic: 44 batches/epoch × 54 epochs = 2376 batches.
   - Shipped checkpoint `M:\chakramodel\weights\checkpoints\chakra_transformer_best.pth` has `storage 302 (int64) = 2376` (`module.decode_head.1.num_batches_tracked`) and all 312 keys prefixed with `module.` matching DataParallel training observed in the notebook.

3. **Pre-09-05 Clean-Keyed Checkpoint:**
   - Located inside `J:\My Drive\downloads\CHAKRAMODEL_OM_4\chakramodel_weights_PRIVATE.zip`.
   - Entry name: `weights/chakra_transformer_best.pth.bak`.
   - Size: 1,236,830,575 bytes; CRC32: `0xec2c7f47`; timestamp: `2026-08-30 16:27:14`.
   - Matches the description in `M:\chakramodel\checkpoint_analysis.txt` (written 2026-09-04) of an unwrapped 312-key checkpoint before DataParallel wrapping on 2026-09-05.

4. **Extension-less Zip Archive in C:\Users\imgk3\Downloads:**
   - File: `C:\Users\imgk3\Downloads\om-finalkaggle-upload` (1,155,167,936 bytes).
   - Magic bytes: `50 4b 03 04` (`PK\x03\x04`), confirming ZIP format.
   - Integrity: `zipfile.ZipFile.testzip()` completed with output `None` (zero CRC checksum errors).
   - Contains: `weights/chakra_transformer_best.pth` (1,236,836,719 bytes, CRC `0x3aee5cf4`), `weights/best.pt` (6,241,834 bytes, CRC `0x48002f8e`), `Kaggle_ChakraTransformer_Evaluation.ipynb`, and 52 source scripts under `src/`.

5. **12 Missing Universal Evaluation Notebooks:**
   - `C:\Users\imgk3\Downloads` holds 12 evaluation notebooks:
     `ChakraModel_EvalHarness_Kaggle.ipynb` (4,607 B), `ChakraModel_EvalHarness_Kaggle_v4.ipynb` (6,253 B), `ChakraModel_EvalHarness_Kaggle_v5.ipynb` (6,146 B), `ChakraModel_Full_Universal_Evaluation_v9.ipynb` (67,824 B), `chakramodel_v8_corrected.ipynb` (47,516 B), `chakramodel_v9_eval.ipynb` (42,233 B), `ChakraModel_Verified_Eval.ipynb` (40,699 B), `ChakraModel_Verified_Eval_v3.ipynb` (43,075 B), `ChakraModel_Verified_Eval_v4.ipynb` (43,249 B), `ChakraModel_Verified_Eval_v6.ipynb` (47,907 B), `ChakraModel_Verified_Eval_v7.ipynb` (50,848 B), `ChakraModel_Verify_v7.ipynb` (5,853 B).
   - Cross-check against `M:\chakramodel\notebooks` confirmed **0 of these 12 exist in the repository**.

6. **Missing Model Weights:**
   - Checkpoints: `combo2_best.pth` (102,677,499 B, CRC `0x6f9a5b84`), `pranet_kvasir_best.pth` (6,191,937 B, CRC `0xd008a90`).
   - YOLO detectors: `yolo26n.pt` (5,544,453 B, CRC `0x61b5d8d3`), `yolov8n.pt` (6,549,796 B, CRC `0x113a4c91`), `best_of_yolo_newapproach.pt` (6,241,834 B), `best_of_yolo_newapproach2.pt` (6,241,834 B), `best_of_yolo_newapproach3.pt` (6,241,834 B).
   - Cross-check against `M:\chakramodel\weights` confirmed none of these 7 files exist in the repo.

7. **Collision & Corruption Traps:**
   - `J:\My Drive\downloads\CHAKRAMODEL_OM_4\model_output_extracted\model_output.zip` and `output.zip` are 49-byte stub files.
   - Corresponding files in `M:\chakramodel\results\archives\` are healthy archives of size 13,900 bytes and 13,458 bytes. Blind copying would overwrite valid archives with corrupted 49-byte stubs.

8. **Personal & Sensitive Data Identified:**
   - 33 files identified: passport scans (`GOKUL PASSPORT REPORT.pdf`, `RAJASEKAR PASSPORT RECIPT.pdf`, `priya passport report.pdf`), resumes (`Gokul_R_Resume*.pdf/docx`), payment receipts, room bookings, mess fee receipts, calendar invites (`.ics`), and lead generation CSVs with third-party personal data (`CHAKRAMODEL_OM_4\data\leads\corporate_leads.csv`, `researcher_leads.csv`).

---

## 2. Logic Chain

1. **Step 1 (Provenance Verification):**
   - Observation 2 directly links `om-krish-4-6 (2).ipynb` to `chakra_transformer_best.pth` via exact arithmetic (44 × 54 = 2376) and DataParallel multi-GPU key structure.
   - *Inference:* `om-krish-4-6 (2).ipynb` is the authentic training run for the shipped weights. Recovering it into `M:\chakramodel\notebooks\provenance\` resolves the primary provenance gap documented in `DOWNLOADS_INVENTORY.md`.

2. **Step 2 (Key Format Recovery):**
   - Observation 3 confirms `chakra_transformer_best.pth.bak` (dated 2026-08-30) inside `chakramodel_weights_PRIVATE.zip`.
   - *Inference:* This is the unwrapped state_dict from before 2026-09-05. Recovering it provides the clean-keyed baseline required for standalone single-GPU evaluation without requiring `module.` stripping hacks.

3. **Step 3 (Local Downloads Evaluation History):**
   - Observation 5 confirms 12 versioned evaluation notebooks in `C:\Users\imgk3\Downloads` that are missing from the repo.
   - *Inference:* The researcher executed Universal Evaluation iterations (v3 through v9 and Verify v7) on local/Kaggle environments. Recovering them to `M:\chakramodel\notebooks\evaluation\` establishes full auditability of the evaluation timeline.

4. **Step 4 (Safe Recovery Necessity):**
   - Observations 4 and 7 reveal that archives can be extension-less (e.g. `om-finalkaggle-upload`), but can also be 49-byte stubs.
   - *Inference:* A naive file copy or overwrite script would fail to detect the 1.15 GB zip, while destroying 13.5 KB valid archives with 49-byte stubs. Therefore, an archive integrity check (`zipfile.is_zipfile` + `testzip()`) and size-based stub rejection are mandatory before any write.

5. **Step 5 (Privacy Compliance):**
   - Observation 8 shows third-party lead lists and personal identity files in the downloads folder.
   - *Inference:* A regex-based denial filter (Tier 1) must be executed before any inclusion logic to guarantee no private or GDPR-sensitive data enters the project repository.

---

## 3. Caveats

1. **Circumstantial Provenance vs Hash Match:** While `om-krish-4-6 (2).ipynb` matches 44 batches/epoch × 54 epochs = 2376, multi-GPU DataParallel, and save path `/kaggle/working/weights/chakra_transformer_best.pth`, the notebook itself does not print an SHA256 of the output weights. Provenance is strong circumstantial (arithmetic exact), not cryptographic.
2. **Synthetic Data Non-Recovery:** `CHAKRAMODEL_OM_4\data\cvc-300\images\synthetic_*.png` and `etis-larib\images\synth_*.png` were confirmed synthetic/canaries in `DOWNLOADS_INVENTORY.md`. These should NOT be recovered into active benchmark paths.
3. **Google Drive Network Latency:** `J:\My Drive\downloads` is a cloud mount. Scanning or copying large files (e.g., 2.5 GB zip) can be slow or encounter transient network timeouts. Recovery should prioritize local `C:\Users\imgk3\Downloads` files first, followed by targeted single-file reads from `J:\`.

---

## 4. Conclusion

1. **Recovery Feasibility:** 555 Chakramodel-related files across weights, provenance notebooks, universal evaluation harnesses, benchmark JSONs, and audit reports can be safely recovered from downloads into `M:\chakramodel`.
2. **Missing Gaps Closed:**
   - Shipped weights provenance run: `om-krish-4-6 (2).ipynb` -> `notebooks/provenance/`
   - Clean-keyed checkpoint: `chakra_transformer_best.pth.bak` -> `weights/checkpoints/`
   - Universal evaluation suite: 12 notebooks in C:\Downloads -> `notebooks/evaluation/`
   - Missing weights: `combo2_best.pth`, `pranet_kvasir_best.pth`, `yolo26n.pt`, `yolov8n.pt`, `best_of_yolo_newapproach*.pt` -> `weights/`
3. **Safe Architecture Defined:**
   - Two-tier matching engine (Tier 1 Privacy Deny -> Tier 2 Chakramodel Allow).
   - Pre-flight `zipfile.is_zipfile` and `testzip()` validation.
   - Idempotent collision handling (skip identical, reject < 100B stubs, backup existing files as `<dest>.bak_<timestamp>`).
   - Mock weight zip fixture for fast automated testing.

---

## 5. Verification Method

To independently verify the findings and safe recovery pipeline:

1. **Verify Archive Integrity:**
   ```powershell
   python -c "import zipfile; z = zipfile.ZipFile(r'C:\Users\imgk3\Downloads\om-finalkaggle-upload'); assert z.testzip() is None; print('Local 1.15GB zip: VALID')"
   ```
2. **Verify Provenance Arithmetic:**
   ```powershell
   python -c "import json; nb = json.load(open(r'J:\My Drive\downloads\om-krish-4-6 (2).ipynb', encoding='utf-8')); text = str(nb); assert '44/44' in text and 'Epoch 54' in text; print('Batch arithmetic 44*54=2376: VERIFIED')"
   ```
3. **Verify Clean-Keyed Checkpoint in Zip:**
   ```powershell
   python -c "import zipfile; z = zipfile.ZipFile(r'J:\My Drive\downloads\CHAKRAMODEL_OM_4\chakramodel_weights_PRIVATE.zip'); info = z.getinfo('weights/chakra_transformer_best.pth.bak'); assert info.file_size == 1236830575; print('Clean checkpoint 1.236GB: VERIFIED')"
   ```
4. **Verify Mock Weight Test Fixture:**
   ```powershell
   python M:\chakramodel\.agents\explorer_m1_2_g15\test_mock_zip.py
   ```
5. **Verify Recovery Manifest & Collision Detection:**
   ```powershell
   python -c "import json; m = json.load(open(r'M:\chakramodel\.agents\explorer_m1_2_g15\recovery_manifest.json', encoding='utf-8')); print('Total:', len(m), 'Recoverable:', sum(1 for x in m if x['action']=='RECOVER'), 'Quarantined:', sum(1 for x in m if x['action']=='EXCLUDE'))"
   ```

**Invalidation Conditions:**
- If `testzip()` on `om-finalkaggle-upload` fails with CRC error.
- If `om-krish-4-6 (2).ipynb` does not contain 44 batches/epoch and save at Epoch 54.
- If any personal documents (passports, resumes, leads) appear in `recovery_manifest.json` with action `RECOVER`.
