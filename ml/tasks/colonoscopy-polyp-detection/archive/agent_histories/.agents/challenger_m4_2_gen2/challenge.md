# Adversarial Challenge Report: Verification of Target Baseline Claims

**Audit Subject:** `m:\chakramodel\KAGGLE_DATASET_DECODING_REPORT.md`  
**Target Baselines Audited:** SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, PolypGen  
**Auditor Archetype:** EMPIRICAL CHALLENGER (critic, specialist)  
**Execution Timestamp:** 2026-09-07T17:15:00Z  
**Verdict:** **CONFIRMED** (All 4 baseline claims and code references verified with 100% empirical reproducibility)

---

## Challenge Summary

**Overall Risk Assessment:** **LOW** (The claims in `KAGGLE_DATASET_DECODING_REPORT.md` are completely robust, empirically verified down to exact lines and byte structures, and resilient to adversarial stress-testing).

| Target Baseline Claim | Challenged Hypothesis | Empirical Method | Stress Test Outcome | Finding Status |
|---|---|---|:---:|:---:|
| **1. SUN-SEG** | Could SUN-SEG be concealed or partially present in uncataloged files? | Full filesystem walk, regex search, byte check in archives | 0 files found; citations in `build_master_eval_notebook.py:L13` and `REPORT.txt:L159-160, 240, 445` verbatim verified | **CONFIRMED ABSENT (100%)** |
| **2. CVC-VideoClinicDB** | Could `CVC_ClinicVideoDB_Kaggle.zip` contain valid benchmark videos and masks? | Byte-level header unpacking, trailer inspection, pipeline code trace | Broken zip trailer, 42 unannotated clips, 0 masks; static 495 frames substituted in `build_crossval_v5.py:L14` and `REPORT.txt:L502` | **CONFIRMED ABSENT & CONFLATED** |
| **3. LDPolypVideo** | Was LDPolypVideo ever mounted or evaluated as claimed in the paper draft? | Log inspection of `crossvali1_dump.txt:L1083`, chat forensic audit `HISTORY.JSON:L79921`, paper text diff | Unmounted in Kaggle run (`ALL_RESULTS=None`); chat logs expose paper claim as fabricated; paper amended | **CONFIRMED ABSENT AS VIDEO & CLAIM FABRICATED** |
| **4. PolypGen** | Did PolypGen get evaluated under an aliased identifier? | Code search for Synapse data, spectral dataset inspection | Excluded due to Synapse gating (`REPORT.txt:L232, 557`); substituted by PolypDB in `build_crossval_v5.py:L344` | **CONFIRMED ABSENT & REPLACED BY POLYPDB** |

---

## Challenges & Adversarial Hypotheses

### [Low Risk] Challenge 1: Absence of SUN-SEG Across the Entire Workspace
- **Assumption Challenged:** That SUN-SEG (158,690 frames, 110 clips) is 100% absent across the entire repository.
- **Attack Scenario:** Could any frames from SUN-SEG have been quietly ingested into `data/`, `Kaggle_Datasets_Upload/`, or embedded inside one of the zip archives (`ChakraModel_Evaluation_Datasets.zip`, `chakramodel_data_scripts.zip`) under an alternate naming scheme?
- **Empirical Test:**
  1. Executed `rglob("*sun*")` and `rglob("*sunseg*")` across `data/`, `datasets/`, and `Kaggle_Datasets_Upload/`: Exactly 0 files found.
  2. Inspected `ChakraModel_Evaluation_Datasets.zip`: Contains exactly 3,000 files strictly categorized into `cvc-clinicdb` (495), `etis-larib` (5), and `kvasir-seg` (1000).
  3. Verified code references:
     - `build_master_eval_notebook.py:L13`: Verbatim `    - SUN-SEG                   (not uploaded yet, 12.5 GB)`
     - `REPORT.txt:L159-160`: Verbatim `The largest video dataset for polyp segmentation (SUN-SEG, 158,690 frames) is technically open-access but requires emailing the original database maintainer for backup access...`
     - `REPORT.txt:L240`: Verbatim `3. Do NOT wait for LDPolypVideo or SUN-SEG — their access path takes too long.`
     - `REPORT.txt:L445`: Verbatim `| LDPolypVideo / SUN-SEG not accessible in time | Very High | Low | Already excluded from plan; stick to image datasets |`
- **Blast Radius:** None.
- **Verdict:** **CONFIRMED**. SUN-SEG is 100% absent.

---

### [Low Risk] Challenge 2: CVC-VideoClinicDB Absence and Conflation with Static CVC-ClinicDB
- **Assumption Challenged:** That CVC-VideoClinicDB (18 video sequences, ~11,954 frames) is absent and was conflated with static CVC-ClinicDB.
- **Attack Scenario:** Could the 12.71 GB file `CVC_ClinicVideoDB_Kaggle.zip` actually contain the official GIANA 2017 CVC-ClinicVideoDB sequences and annotations?
- **Empirical Test:**
  1. Tested archive integrity via Python `zipfile`: Throws `zipfile.BadZipFile: File is not a zip file` due to central directory trailer displacement.
  2. Sequentially parsed all 88 local file headers: The archive contains 42 `.avi` files, 43 `.mp4` files, 1 nested zip (`polyp/videos with polyps-20260804T054937Z-1-001.zip`), and 2 folder records. Exactly **0 ground-truth masks, bounding boxes, or annotations** exist in the archive.
  3. Verified code citations:
     - `REPORT.txt:L502`: Documents that CVC-ClinicVideoDB is a GIANA challenge dataset requiring organizer contact, and warns that `balraj98/cvcclinicdb` is the static-image 612-image CVC-ClinicDB.
     - `build_crossval_v5.py:L14, L28`: Mounts `/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/images` with exactly 495 static images.
     - `cross_dataset_report.md:L10`: Evaluates static `CVC-ClinicDB (zero-shot)` on 495 images (0.7561 DSC). No video sequences were evaluated.
- **Blast Radius:** None.
- **Verdict:** **CONFIRMED**. CVC-VideoClinicDB is absent as an annotated video benchmark and conflated with static CVC-ClinicDB.

---

### [Low Risk] Challenge 3: LDPolypVideo Absence as Video Benchmark & Fabricated Paper Claims
- **Assumption Challenged:** That LDPolypVideo was absent as a continuous video benchmark (<2% static slice only, failed to mount per `crossvali1_dump.txt:L1083`, paper claims fabricated per `conversation_history/HISTORY.JSON:L79921`).
- **Attack Scenario:** Could the static frame slices in `gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset` have been successfully evaluated in the final cross-validation run?
- **Empirical Test:**
  1. Inspected `crossvali1_dump.txt:L1078-1083`: The Kaggle execution stdout verbatim logged:
     ```text
     else:
         print("ℹ️  LDPolyp labeled images not found — may not be attached yet.")
         ALL_RESULTS["LDPolyp Images"] = None

     --- OUTPUT ---
     ℹ️  LDPolyp labeled images not found — may not be attached yet.
     ```
  2. Inspected `build_master_eval_notebook.py:L14`: Verbatim `    - LDPolyp Video             (in progress, 7.5 GB)`
  3. Inspected `conversation_history/HISTORY.JSON:L79921`: Verbatim records the agent audit uncovering the fabrication:
     `"1. Fabricated Dataset Evaluation (LDPolypVideo): In Section 4.1 (ChakraModel_Final_Paper.md), the paper claims the framework was evaluated on six datasets, including: LDPolypVideo: Evaluated for artifact robustness and temporal stability in real-time video context... A thorough audit of the codebase, scripts, and output logs reveals zero implementation or execution of any evaluation on LDPolypVideo... The claim of evaluating real-time temporal stability on this dataset is entirely fabricated."`
  4. Inspected `ChakraModel_Final_Paper.md:L114`: Verbatim updated to admit:
     `- **LDPolypVideo**: Proposed for future work to evaluate artifact robustness and temporal stability in real-time video context. It was not actually evaluated in this study.`
- **Blast Radius:** None.
- **Verdict:** **CONFIRMED**. LDPolypVideo was never evaluated as a video benchmark, static images failed to mount, and paper claims were fabricated.

---

### [Low Risk] Challenge 4: PolypGen Absence & Substitution by PolypDB
- **Assumption Challenged:** That PolypGen is 100% absent and was substituted by PolypDB.
- **Attack Scenario:** Did the authors train or evaluate on PolypGen via another script or local copy?
- **Empirical Test:**
  1. Inspected `REPORT.txt:L232, 241, 557`:
     - Line 232: Documents PolypGen specifications.
     - Line 557: Verbatim notes access friction: `PolypGen: Multi-center dataset... Available via academic portals/Synapse; access process not as instant as Kaggle. Optional stretch goal, not Day-1 critical path.`
  2. Inspected `build_crossval_v5.py:L344`: Verbatim loads `Path("/kaggle/input/datasets/gokulrocky/polypdb-polyp-raw-stress-testdataset")` and evaluates all 5 modalities (WLI, NBI, LCI, BLI, FICE).
  3. Inspected `cross_dataset_report.md:L13`: Documents PolypDB evaluation (`0.7283 ± 0.2544` DSC across 7,868 images/masks). PolypGen is completely absent from all reported results.
  4. Searched repository for `polypgen`: 0 images, masks, or evaluation logs exist.
- **Blast Radius:** None.
- **Verdict:** **CONFIRMED**. PolypGen is 100% absent and replaced by PolypDB.

---

## Stress Test Results

Executed automated adversarial test suite `tests/test_target_baselines_adversarial.py` via pytest:

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: M:\chakramodel
plugins: anyio-4.14.2
collected 5 items

tests/test_target_baselines_adversarial.py::test_sun_seg_complete_absence_and_citations PASSED [ 20%]
tests/test_target_baselines_adversarial.py::test_cvc_videoclinicdb_absence_and_conflation PASSED [ 40%]
tests/test_target_baselines_adversarial.py::test_ldpolypvideo_absence_and_fabrication PASSED [ 60%]
tests/test_target_baselines_adversarial.py::test_polypgen_absence_and_substitution_by_polypdb PASSED [ 80%]
tests/test_target_baselines_adversarial.py::test_adversarial_anomalies_and_substitutions PASSED [100%]

============================== 5 passed in 0.45s ==============================
```

Full repository test suite verification (`pytest tests/`):
- `tests\test_benchmark_provenance_empirical.py`: 5 passed
- `tests\test_statistical_significance.py`: 4 passed
- `tests\test_target_baselines_adversarial.py`: 5 passed
- `tests\test_tracker.py`: 9 passed
- **Total: 23 passed, 0 failed in 5.23s**.

---

## Unchallenged Areas

- **Kaggle runtime cloud GPU logs beyond local dumps:** The actual remote Kaggle compute environments were ephemeral. We rely on the local dumps (`crossvali1_dump.txt`, `crossvali2_dump.txt`, `model_output_extracted/`), which are byte-verified against codebase artifacts.
- **External Kaggle URL live downloads:** Operating under `CODE_ONLY` network restrictions; verified all local mirrors, upload directories (`Kaggle_Datasets_Upload`), and archives rather than calling external Kaggle API.

---

## Final Challenger Verdict

### **VERDICT: CONFIRMED**
Every claim regarding the absence, conflation, failure to mount, and substitution of the four target baselines (SUN-SEG, CVC-VideoClinicDB, LDPolypVideo, PolypGen) in `m:\chakramodel\KAGGLE_DATASET_DECODING_REPORT.md` is **EMPIRICALLY CONFIRMED**.
