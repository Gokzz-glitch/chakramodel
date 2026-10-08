# Architecture & Investigation Analysis: Recovering Files from Downloads

**Agent:** `explorer_m1_2_g15`  
**Working Directory:** `M:\chakramodel\.agents\explorer_m1_2_g15\`  
**Date:** 2026-09-16  
**Status:** Completed Investigation  

---

## 1. Executive Summary & Inventory Overview

A deep, non-destructive investigation was conducted across both local downloads (`C:\Users\imgk3\Downloads`) and Google Drive desktop sync (`J:\My Drive\downloads`), correlated against `M:\chakramodel\DOWNLOADS_INVENTORY.md` and the live codebase at `M:\chakramodel`.

### Key Headline Discoveries:
1. **Critical Provenance Training Notebook Confirmed:**  
   `J:\My Drive\downloads\om-krish-4-6 (2).ipynb` (45,879 bytes, SHA256 `6a2f75eecb8fbf2f6375a19113c139f4bd994fa9c3bb45bb957a8525636d9ebe`).  
   Independent verification confirms 44 batches/epoch × 54 epochs = **2376 batches tracked**, perfectly accounting for `module.decode_head.1.num_batches_tracked = 2376` in the shipped checkpoint. This file must be recovered to `notebooks/provenance/`.
2. **"Lost" Clean-Keyed Checkpoint Recovered:**  
   Inside `J:\My Drive\downloads\CHAKRAMODEL_OM_4\chakramodel_weights_PRIVATE.zip`, the archive holds `weights/chakra_transformer_best.pth.bak` (1,236,830,575 bytes, timestamp `2026-08-30 16:27:14`). This is the pre-09-05 clean-keyed checkpoint described in `checkpoint_analysis.txt` prior to multi-GPU DataParallel wrapping.
3. **Extension-less 1.15 GB Zip in Local Downloads:**  
   `C:\Users\imgk3\Downloads\om-finalkaggle-upload` (1,155,167,936 bytes) is a valid, uncorrupted ZIP archive (`zipfile.testzip()` passed with zero errors). It contains `weights/chakra_transformer_best.pth` (1.24 GB), `weights/best.pt` (6.24 MB), `Kaggle_ChakraTransformer_Evaluation.ipynb`, and 52 source files in `src/`.
4. **12 Missing Universal Evaluation Harness Notebooks in Local Downloads:**  
   `C:\Users\imgk3\Downloads` holds 12 evaluation notebooks (`ChakraModel_EvalHarness_Kaggle*.ipynb`, `ChakraModel_Verified_Eval_v3..v7.ipynb`, `ChakraModel_Full_Universal_Evaluation_v9.ipynb`, `chakramodel_v8_corrected.ipynb`, `chakramodel_v9_eval.ipynb`) created between 2026-09-08 and 2026-09-12. **None of these 12 currently exist in `M:\chakramodel\notebooks`**.
5. **Missing Weights Found in Archives:**  
   `combo2_best.pth` (102,677,499 bytes), `pranet_kvasir_best.pth` (6,191,937 bytes), `yolo26n.pt` (5,544,453 bytes), `yolov8n.pt` (6,549,796 bytes), and three YOLO runs (`best_of_yolo_newapproach*.pt`) exist in downloads but are missing from `M:\chakramodel\weights`.
6. **Collision & Corruption Traps Identified:**  
   Downloads contain 49-byte stub zips (`model_output.zip`, `output.zip`). Blind recovery would overwrite healthy files in `M:\chakramodel\results\archives\` with 49-byte stubs. Safe recovery requires strict size and integrity checks before overwriting.
7. **Strict Privacy Quarantine:**  
   33 files containing sensitive personal identity (passports, resumes, hotel receipts, payment slips) and lead-generation CSVs with third-party personal data (`corporate_leads.csv`, `researcher_leads.csv`) were cataloged and must be permanently excluded from recovery.

---

## 2. Census & Artifact Categorization

Across the two scan sources (excluding `.venv` and `.git` subtrees):
- **C:\Users\imgk3\Downloads**: 24 items (13 notebooks, 1 audit PDF, 1 tracking CSV, 1 1.15 GB zip, 1 empty directory, 7 personal/system files).
- **J:\My Drive\downloads**: 951 items (171 notebooks, 23 zip archives, 12 weights files, 77 JSONs, 30+ CSVs, 48 PDFs, plus markdown architecture guides).

### Comprehensive Breakdown of Identified Chakramodel Artifacts:

| Class | Discovered Artifacts | Key Examples & Metadata | Action & Recovery Target |
|---|---|---|---|
| **Model Weights & Checkpoints** | 14 files / entries | • `chakra_transformer_best.pth` (1.24 GB, CRC `0x3aee5cf4`)<br>• `chakra_transformer_best.pth.bak` (1.24 GB, CRC `0xec2c7f47`, 08-30 clean)<br>• `combo1_best.pth` (102.6 MB, CRC `0xd6dd6eb5`)<br>• `combo2_best.pth` (102.6 MB, CRC `0x6f9a5b84`)<br>• `pranet_kvasir_best.pth` (6.19 MB, CRC `0xd008a90`)<br>• `best.pt` / `yolo_custom_best.pt` (6.24 MB, CRC `0x48002f8e`)<br>• `best_of_yolo_newapproach1..3.pt` (6.24 MB each)<br>• `yolo26n.pt` (5.54 MB), `yolov8n.pt` (6.55 MB) | Recover missing weights (`combo2_best.pth`, `pranet_kvasir_best.pth`, `yolo26n.pt`, `yolov8n.pt`, `best_of_yolo_newapproach*.pt`) to `M:\chakramodel\weights\checkpoints\` and `weights\yolo\`. Keep `chakra_transformer_best.pth.bak` intact. |
| **Provenance Notebooks** | 3 files | • `om-krish-4-6 (2).ipynb` (45,879 bytes, 2376 batches)<br>• `om-krish-4-6 (1).ipynb` (45,910 bytes, 1980 batches)<br>• `om-krish-4-6.ipynb` (clean unexecuted) | Recover to `M:\chakramodel\notebooks\provenance\`. Attach SHA256 checksums in ledger. |
| **Evaluation & Audit Notebooks** | 18 files | • `claudev7.ipynb` & forks (anti-fabrication canary harness)<br>• `crossvali finalrun notebbok downloaded.ipynb`<br>• `ChakraModel_Full_Universal_Evaluation_v9.ipynb`<br>• `ChakraModel_Verified_Eval_v3..v7.ipynb`<br>• `chakramodel_v8_corrected.ipynb`, `chakramodel_v9_eval.ipynb`, `chakramodel_v10_eval.ipynb` | Recover to `M:\chakramodel\notebooks\evaluation\`. |
| **Kaggle Kernel Archive** | 130+ notebooks | • `muruga-perumal (1..7).ipynb`<br>• `notebook75ecf07fa0 (1..4).ipynb`<br>• `notebookb7c036bec1 (1..6).ipynb`<br>• `notebooka0aa0402d8 (1..5).ipynb`<br>• `finalrun-om-4-6.ipynb`, `testingnamashivaya*.ipynb` | Recover to `M:\chakramodel\notebooks\kaggle_archive\`. |
| **Evaluation Results & Logs** | 59 files | • `final_5_datasets_eval comapraion 5 dataset.json`<br>• `cross_dataset_results_v5.json` (in `crossvali (1)result.zip`)<br>• `evaluation_results_20260912_090425.json` & `resource_log_20260912_090317.csv` (in `resultscomaprision successful.zip`)<br>• `verification_verdicts\*.json`<br>• `feature-bytetrack-5.csv` (ByteTrack vs Kalman filter) | Recover to `M:\chakramodel\results\recovered\` and `results\verification_verdicts\`. |
| **Architecture & Docs** | 34 files | • `CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md`<br>• `ChakraModel_Architecture_Explained.md`<br>• `ARCHITECTURE_DEEP_DIVE.md`<br>• `parameter_mapping.txt` | Already present in `M:\chakramodel\docs\`. Recover only non-duplicate/newer versions. |
| **Audit PDFs & Reports** | 29 files | • `ChakraModel_Complete_Audit (1).pdf` (386,974 bytes)<br>• `ChakraModel_Completed_Audit_Report.pdf`<br>• `finalevelauation summary.pdf`<br>• `chakratransformer_COMBO 6 ISSUES.pdf` | Recover to `M:\chakramodel\docs\audit\` and `docs\pdfs\`. |
| **Research Papers** | 16 PDFs | `01_PraNet.pdf` through `16_EndoSLAM.pdf` in `CHAKRAMODEL_OM_4\research_papers\` | Already present in `M:\chakramodel\research_papers\`. Verified identical (`SKIP_IDENTICAL`). |
| **Large Data Archives** | 3 archives | • `CVC_ClinicVideoDB_Kaggle.zip` (13.6 GB)<br>• `ChakraModel_Evaluation_Datasets.zip` (99.3 MB)<br>• `chakramodel_data_scripts.zip` (240.7 MB) | `CVC_ClinicVideoDB_Kaggle.zip` already in repo root (`SKIP_IDENTICAL`). `chakramodel_data_scripts.zip` contains synthetic data (`synth_*`), quarantined from active dataset directory. |

---

## 3. Precise Matching and Filtering Rules

To cleanly separate Chakramodel assets from the user's personal documents, system installers, and unrelated work, the recovery engine must implement a deterministic, two-tiered rule filter.

### Tier 1: Strict Denial & Quarantine Filter (Evaluated First)
If any of these conditions match, the file is immediately **EXCLUDED / QUARANTINED**:

```python
PERSONAL_DENY_PATTERNS = [
    # Personal Identity & Travel Documents
    r"(?i)passport",
    r"(?i)resume",
    r"(?i)profile\.pdf$",
    r"(?i)lor[-_]nit",
    
    # Financial & Transaction Records
    r"(?i)receipt",
    r"(?i)payment",
    r"(?i)booking",
    r"(?i)mess\s*fees",
    r"(?i)bill",
    r"(?i)\.ics$",
    
    # Third-Party Lead Generation & Scraping Data (GDPR/Privacy sensitive)
    r"(?i)leads?",
    r"(?i)corporate_leads",
    r"(?i)researcher_leads",
    r"(?i)russia_moscow",
    r"(?i)priority_\d+.*\.csv$",
    
    # System Installers, Drivers, Executables
    r"(?i)\.(exe|msi|bat|ps1)$",  # except project-specific scripts
    r"(?i)eclipse",
    r"(?i)acer\s*care",
    r"(?i)chatgpt\s*installer",
    r"(?i)chromesetup",
    r"(?i)desktop\.ini$",
    r"(?i)screenshot",
    r"(?i)opus_keyword",
]
```

### Tier 2: Chakramodel Inclusion Filter
If a file passes Tier 1, it is evaluated against the inclusion rules:

1. **Rule 2.1 — Model Weights & Checkpoints:**
   - File extension in `{'.pth', '.pt', '.ckpt', '.onnx', '.weights'}` OR name matches `om-finalkaggle-upload` / `chakra_transformer_best.zip`.
   - Name contains `chakra`, `combo`, `pranet`, `yolo`, `best`, or path is inside a `weights/` directory.
2. **Rule 2.2 — Jupyter Notebooks:**
   - Extension `.ipynb`.
   - Explicit name match: `om-krish*`, `*chakra*`, `*claudev7*`, `*crossvali*`, `*eval*`, `*verify*`, `*muruga*`, `*prrof*`, `*testingnamashivaya*`, `*videotest*`.
   - OR generic Kaggle kernel pattern `notebook[0-9a-f]{10}` where internal cell content contains `"chakra"`, `"polyp"`, `"kvasir"`, `"dice"`, or `"yolo"`.
3. **Rule 2.3 — Evaluation & Metrics Data:**
   - Extension in `{'.json', '.csv'}`.
   - Name or parent dir contains: `eval`, `metric`, `results`, `verdict`, `cross_dataset`, `bytetrack`, `conformal`.
4. **Rule 2.4 — Research Papers & Documentation:**
   - PDFs matching `^\d{2}_.*\.pdf` (numbered literature review papers).
   - PDFs or Markdown files matching `*audit*`, `*architecture*`, `*layer_by_layer*`, `*pitch*`.
5. **Rule 2.5 — Source Code & Toolkits:**
   - `.py` scripts inside `CHAKRAMODEL_OM_4\src\` or matching `anti_fabrication*`.

---

## 4. Destination Mapping Engine

Artifacts must be organized into standard repository locations according to the project layout:

| Artifact Type | Sub-type / Pattern | Target Destination in `M:\chakramodel` |
|---|---|---|
| **Weights** | Transformer / Segmentation (`chakra_*`, `combo*`, `pranet*`) | `weights/checkpoints/<filename>` |
| **Weights** | YOLO Detector (`best.pt`, `yolov8*.pt`, `yolo26n.pt`) | `weights/yolo/<filename>` |
| **Weights** | YOLO Experimental Runs (`best_of_yolo_newapproach*.pt`) | `weights/yolo/archive/<filename>` |
| **Weights** | Calibration parameters (`conformal_calibration.json`) | `weights/calibration/<filename>` |
| **Weights Archive** | Full backup bundles (`chakramodel_weights_PRIVATE.zip`) | `weights/archive/<filename>` |
| **Notebooks** | Shipped weight training provenance (`om-krish-4-6 (2).ipynb`) | `notebooks/provenance/<filename>` |
| **Notebooks** | Training variations (`om-krish-4-6 (1).ipynb`, etc.) | `notebooks/training_runs/<filename>` |
| **Notebooks** | Eval harnesses & Universal audit (`claudev7`, `crossvali`, `v8_corrected`, `v9_eval`, `Universal_Evaluation_v9`) | `notebooks/evaluation/<filename>` |
| **Notebooks** | Kaggle runs & exploratory experiments (`muruga*`, `notebook*`) | `notebooks/kaggle_archive/<filename>` |
| **Results** | Benchmark summaries (`final_5_datasets_eval*.json`, `cross_dataset*.json`) | `results/recovered/benchmarks/<filename>` |
| **Results** | Execution & resource logs (`resource_log*.csv`, `feature-bytetrack-5.csv`) | `results/recovered/logs/<filename>` |
| **Results** | Signed verification outputs (`verification_verdicts/*.json`) | `results/verification_verdicts/<filename>` |
| **Documentation** | Completed audit reports (`ChakraModel_Complete_Audit*.pdf`) | `docs/audit/<filename>` |
| **Documentation** | Presentations & pitch guides (`*.pptx`, pitch PDFs) | `docs/presentations/<filename>` |
| **Documentation** | Markdown guides (`CHAKRAMODEL_LAYER_BY_LAYER_GUIDE.md`) | `docs/<filename>` (if newer than existing) |
| **Research Papers** | Numbered literature PDFs (`01_PraNet*.pdf` .. `16_EndoSLAM*.pdf`) | `research_papers/<filename>` |
| **Tools & Code** | Anti-fabrication toolkit archives (`anti_fabrication_toolkit*.zip`) | `tools/anti_fabrication_toolkit/<filename>` |

---

## 5. Safe Recovery Architecture

To ensure zero risk of data loss, zero accidental overwrites, and robust verification, the recovery pipeline must implement the following safety mechanisms:

```
                  ┌─────────────────────────────────────┐
                  │ Source File in Downloads / J: Drive │
                  └──────────────────┬──────────────────┘
                                     │
                             [Rule Engine Filter]
                                     │
                  ┌──────────────────┴──────────────────┐
                  ▼                                     ▼
          Matches Deny Rule?                   Passes Inclusion?
                  │                                     │
           [YES]  ▼                              [NO]   ▼
         ┌───────────────────┐                ┌───────────────────┐
         │ QUARANTINE/IGNORE │                │   IGNORE/SKIP     │
         │   (No action)     │                │   (No action)     │
         └───────────────────┘                └─────────┬─────────┘
                                                        │ [YES]
                                                        ▼
                                             [Integrity Check]
                                           Is zip / pth intact?
                                           zipfile.testzip() == None?
                                                        │
                                          ┌─────────────┴─────────────┐
                                   [FAIL] ▼                    [PASS] ▼
                                ┌───────────────────┐     [Check Destination]
                                │  FLAG CORRUPTED   │     Does target exist?
                                │   (Abort item)    │                 │
                                └───────────────────┘       ┌─────────┴─────────┐
                                                     [NO]   ▼            [YES]  ▼
                                                   ┌──────────────┐     [Size & Hash Check]
                                                   │ RECOVER FILE │     Are files identical?
                                                   └──────────────┘             │
                                                                         ┌──────┴──────┐
                                                                  [YES]  ▼      [NO]   ▼
                                                               ┌────────────┐ ┌──────────────────┐
                                                               │    SKIP    │ │  CREATE BACKUP   │
                                                               │ IDENTICAL  │ │ target.bak_<ts>  │
                                                               └────────────┘ └────────┬─────────┘
                                                                                       │
                                                                                       ▼
                                                                              ┌──────────────────┐
                                                                              │   RECOVER FILE   │
                                                                              └────────┬─────────┘
                                                                                       │
                                                                                       ▼
                                                                              ┌──────────────────┐
                                                                              │  WRITE MANIFEST  │
                                                                              │ recovery_ledger  │
                                                                              └──────────────────┘
```

### Safety Rules:
1. **Pre-flight Archive Integrity Check:**
   - Before extracting or copying any zip or PyTorch `.pth` checkpoint, run `zipfile.is_zipfile(path)` and verify `zipfile.ZipFile(path).testzip() is None`.
   - If `testzip()` returns a string (corrupted member) or raises `BadZipFile`, recovery for that file MUST be aborted and logged.
2. **Idempotency & Byte-Accurate Collision Check:**
   - If destination file exists, compare `file_size`. If sizes match, compute SHA-256. If SHA-256 matches, log status as `SKIP_IDENTICAL` and do not re-copy.
   - Example verified: `CVC_ClinicVideoDB_Kaggle.zip` (13.6 GB) is identical in downloads and repo root; skipping avoids 13.6 GB of unnecessary disk I/O.
3. **Collision Backup & Stub Protection:**
   - If destination file exists with differing content/size:
     - Check for empty/stub source: if source size is < 100 bytes while destination is a valid archive (e.g. `model_output.zip` 49 bytes vs 13.9 KB), **REJECT SOURCE AS STUB**.
     - If both are valid, create a backup copy of the existing destination: `<dest_path>.bak_<timestamp>`.
     - Copy the recovered file to destination, recording old and new SHA-256 hashes in the ledger.
4. **Automated Test Fixture: Mock Weight Zip:**
   - Testing large 1.25 GB file recovery in automated test suites is impractical and slow.
   - The test harness includes a lightweight mock PyTorch weight zip generator (`test_mock_zip.py`) that creates a valid zip container with `archive/data.pkl`, `.format_version`, and storage tensors (~1 KB), allowing comprehensive unit testing of archive integrity checks, collision handling, and ledger recording in milliseconds.
5. **Dry-Run & Audit Ledger:**
   - All recovery scripts must support `--dry-run` to output planned actions without touching the filesystem.
   - Every execution must write an append-only `recovery_ledger.json` recording timestamp, source path, destination path, size, SHA-256, and status verdict.

---

## 6. Implementation Blueprint for Implementer Agent

The implementer agent can execute recovery using a single modular script `tools/recover_downloads.py` adhering to these specifications:

### Suggested Command-line Interface:
```bash
python tools/recover_downloads.py --dry-run
python tools/recover_downloads.py --category weights --verify
python tools/recover_downloads.py --category provenance --verify
python tools/recover_downloads.py --category evaluation --verify
python tools/recover_downloads.py --all --ledger M:\chakramodel\results\recovery_ledger.json
```

### Priority Phasing:
- **Phase 1 (Critical Provenance & Checkpoints):**
  - Recover `om-krish-4-6 (2).ipynb` -> `notebooks/provenance/`
  - Recover `weights/chakra_transformer_best.pth.bak` (clean-keyed) -> `weights/checkpoints/`
  - Recover missing weights `combo2_best.pth`, `pranet_kvasir_best.pth`, `yolo26n.pt`, `yolov8n.pt`
- **Phase 2 (Evaluation Notebooks & Benchmarks):**
  - Recover 12 evaluation notebooks from `C:\Users\imgk3\Downloads` -> `notebooks/evaluation/`
  - Recover `claudev7.ipynb` and `crossvali finalrun notebbok downloaded.ipynb`
  - Recover `evaluation_results_20260912_090425.json` & `resource_log*.csv`
- **Phase 3 (Audit Documentation & Kaggle Archive):**
  - Recover `ChakraModel_Complete_Audit (1).pdf` -> `docs/audit/`
  - Recover `feature-bytetrack-5.csv` -> `docs/reports/`
  - Recover Kaggle kernel history -> `notebooks/kaggle_archive/`
