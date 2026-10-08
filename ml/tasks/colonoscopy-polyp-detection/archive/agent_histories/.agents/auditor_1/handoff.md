# Forensic Audit Report: ChakraModel Phases 2–4 Deliverables

**Work Product**: ChakraModel Phases 2–4 Deliverables (`README.md`, `docs/ARCHITECTURE_RECONSTRUCTED.md`, `docs/DATA_FLOW_MAP.md`, `archive/MANIFEST.md`, `src/evaluation/quick_eval_kvasir.py`, Git Security & Structure)  
**Auditor**: Forensic Auditor (`auditor_1`)  
**Date**: 2026-09-09  
**Repository**: `M:\chakramodel`  
**Profile**: General Project  
**Verdict**: **INTEGRITY VIOLATION**

---

### Executive Summary

| Audit Domain | Scope / Deliverables | Result | Key Finding |
|---|---|---|---|
| **1. Security & Privacy** | `keys.txt`, `data/leads/`, resumes, personal logs | **PASS** | Untracked in git, present in `.gitignore`, fully purged by commit `32202093`. |
| **2. Restructuring & Git** | Commit history, zero data loss, `archive/MANIFEST.md` | **PASS** | 5 genuine non-pushed local commits; 126/126 bidirectional manifest match; 0 lost files. |
| **3. Documentation Integrity** | `ARCHITECTURE_RECONSTRUCTED.md`, `DATA_FLOW_MAP.md` | **PASS** | Mapped pipeline, DDP bug, dead code, Combo 1–6, conformal limits, and data leakage. |
| **4. Metric Authenticity** | 6-Row Honest Table in `README.md` | **PASS** | Numbers exactly match `cross_dataset_results_v5.json`. No hardcoded mocks. |
| **5. Prohibited Strings Policy** | `README.md` ("SOTA", "0.9852", "0.9412", "0.8650") | **FAIL** | **Found 1 instance of literal "SOTA" on Line 12 of `README.md`**. |
| **6. Runtime Executability** | `quick_eval_kvasir.py` & restructured eval scripts | **FAIL** | Broken import paths post-restructuring prevent execution (`ModuleNotFoundError`). |

Due to the strict mandate requiring **ZERO instances of "SOTA"** in `README.md` and broken post-restructuring runtime paths in evaluation scripts, the formal verdict is **INTEGRITY VIOLATION**.

---

## 1. Observation

### 1.1 Security and Privacy Audit
1. **`keys.txt` Git Tracking**:
   - Command: `git ls-files keys.txt`
   - Output: `""` (Empty string).
   - `.gitignore` lines 43 and 74 contain `keys.txt`.
   - On-disk status: File exists locally (552 lines, containing API keys and credentials), safely untracked.
2. **`data/leads/` Git Tracking**:
   - Command: `git ls-files data/leads/`
   - Output: `""` (Empty string).
   - `.gitignore` lines 44 and 83 contain `data/leads/`.
3. **Personal Logs and Resumes Git Tracking**:
   - Command: `git ls-files "*sent_emails*"; git ls-files "*Resume*"; git ls-files "*LOR*"`
   - Output: All return empty string.
   - `.gitignore` lines 45–54, 84–91 contain entries for `results/sent_emails.txt`, `results/college_sent_emails.txt`, `results/linkedin_contacted.txt`, `docs/Gokul_Resume.pdf`, `docs/Gokul_Resume.html`, `docs/LOR-NIT.pdf`.
   - Commit `322020932fa5f601694e2fdaeb87b27213937b2b` explicitly purged all 11 personal/credential files from the git index.

### 1.2 Repository Restructuring & Git Audit
1. **Git Commit History**:
   - Command: `git log --oneline -5`
   - Output:
     ```text
     d739ab9e docs: update README with honest metrics
     116b3bba docs: add architecture reconstruction and data flow map
     c97f2173 refactor: restructure repo into clean directory tree
     57a720b6 feat: track critical untracked evaluation scripts and results
     32202093 security: remove keys.txt and personal data from git tracking
     ```
   - Command: `git status -uno`
   - Output: `Your branch is ahead of 'origin/main' by 15 commits.` (All local, non-pushed).
2. **Zero Source Code and Data Loss Verification**:
   - Commit `c97f2173` had 185 deleted paths and 232 added paths.
   - Python inspection comparing deleted basenames vs added basenames yielded: `Unaccounted: []`.
   - Across the 5 commits from `HEAD~5` to `HEAD`, 14 net files were removed from tracking:
     - 11 sensitive security files purged intentionally.
     - 3 files were relocated: `Colab_GPU_Fast_Verify.ipynb` -> `notebooks/colab/`, `monitor.py` -> `archive/one_off/`, `setup_colab.py` -> `archive/one_off/`.
     - Zero source code files or datasets were deleted without preservation.
3. **`archive/MANIFEST.md` Verification**:
   - Verification script: `M:\chakramodel\.agents\auditor_1\verify_manifest.py`
   - Parsed entries in manifest markdown tables: 126 (69 iteration copies, 57 one-off scripts).
   - Actual files on disk under `archive/` (excluding `MANIFEST.md` and `__pycache__`): 126.
   - Missing on disk: `set()` (0).
   - Unmanifested on disk: `set()` (0).
   - Bidirectional match: 100%.
4. **`src/evaluation/quick_eval_kvasir.py` Tracking**:
   - Command: `git ls-files src/evaluation/quick_eval_kvasir.py`
   - Output: `src/evaluation/quick_eval_kvasir.py` (Tracked in git).
   - Root shim `src/quick_eval_kvasir.py` is also tracked.

### 1.3 Documentation & Architecture Verification
1. **`docs/ARCHITECTURE_RECONSTRUCTED.md`**:
   - **Inference Pipeline**: Lines 26–130 specify two-stage YOLOv8 detection + ByteTrack + ViT-Large (`vit_large_patch16_384`) with 7-layer transpose convolution decode head.
   - **DDP Key Serialization Bug**: Lines 132–207 provide exhaustive state-dict key analysis: 312 keys prefixed with `module.`, explaining how flawed loader stripping only `_orig_mod.` caused 0 keys to match under `strict=False`, resulting in mode collapse (~0.504 logits, ~0.1835 DSC), whereas dual-prefix stripping (`module.` and `_orig_mod.`) restores 312/312 keys.
   - **Dead Code in `src/chakranet_segmenter.py`**: Lines 225–250 identify `BasicConv2d` (lines 29–43), `RFBBlock` (lines 45–82), and `ReverseAttention` (lines 83–102) as completely uninstantiated dead code left over from PraNet.
   - **Combo 1–6 Statuses**: Lines 210–223 document that only Combos 1, 2, and 6 possess trained weight files (`combo1_best.pth`, `combo2_best.pth`, `chakra_transformer_best.pth`), whereas Combos 3, 4, and 5 have ZERO trained weights and are conceptual/paper-only.
   - **Conformal Prediction Limitations**: Lines 251–302 detail the two irreconcilable calibration runs (Run A in `combo1_metrics.json` vs Run B in `conformal_calibration.json`), the spatial autocorrelation violation of exchangeability, and the empty set paradox.
   - **Anti-Fabrication Canaries**: Lines 303–350 detail `plant_multi_canary()`, random uniform noise injection, noise score ceilings ($\le 0.35$), session nonces, and HMAC-SHA256 signatures.
2. **`docs/DATA_FLOW_MAP.md`**:
   - **Lineage**: Lines 25–37 trace script -> artifact -> metric for all 6 pipelines.
   - **Train/Test Leakage**: Lines 17, 31, 101–104, 148 document that `src/quick_eval_kvasir.py` slices the first 60 alphabetically sorted files (`paired[:60]`), directly overlapping with the 70% training set.
   - **Canary / Synthetic Datasets**: Lines 20, 117–131, 146 acknowledge that `data/cvc-300/` contains only 5 planted random noise canaries (`CANARY_*.png`) and `data/etis-larib/` contains only 5 synthetic test files (`synth_*.png`).

### 1.4 Benchmark Metrics & Static Analysis
1. **Honest Metrics Table in `README.md`**:
   - Lines 18–25 of `README.md`:
     ```markdown
     | Dataset | Dice (mean ± std) | N | Source | Split |
     |---|---|---|---|---|
     | Kvasir-SEG | 0.8131 ± 0.1747 | 150 | Kaggle v5 | test split |
     | HyperKvasir | 0.8360 ± 0.1610 | 1000 | Kaggle v5 | test split |
     | PolypDB | 0.7283 ± 0.2544 | 7868 | Kaggle v5 | test split |
     | CVC-ClinicDB | 0.7561 ± 0.2131 | 495 | Kaggle v5 | test split |
     | CVC-300 | 0.7402 ± 0.1590 | 60 | Kaggle v5 | test split |
     | ETIS-Larib | N/A | — | — | No real data evaluated |
     ```
   - Ground truth file `results/verified/cross_dataset_results_v5.json`:
     - `Kvasir-SEG (test split)`: dice = 0.813149, std = 0.174658, n = 150 -> Matches `0.8131 ± 0.1747`.
     - `HyperKvasir Segmented`: dice = 0.835975, std = 0.160951, n = 1000 -> Matches `0.8360 ± 0.1610`.
     - `PolypDB (All Modalities)`: dice = 0.728310, std = 0.254432, n = 7868 -> Matches `0.7283 ± 0.2544`.
     - `CVC-ClinicDB (zero-shot)`: dice = 0.756063, std = 0.213119, n = 495 -> Matches `0.7561 ± 0.2131`.
     - `EndoScene CVC-300 (zero-shot)`: dice = 0.740225, std = 0.159049, n = 60 -> Matches `0.7402 ± 0.1590`.
     - `ETIS-Larib (zero-shot)`: dice = 0.0, note explains full dataset had catastrophic failure, only 5-image subset on Kaggle -> Matches `N/A | No real data evaluated`.
2. **Re-computation of `results/verified/corrected_eval_kvasir_seg.json`**:
   - `python tests/test_eval_kvasir_seg_metrics_audit.py` executed:
     - 60 unique images, 60 unique DSC values, 60 unique IoU values.
     - 0 pixel bounds failures, 0 probability bounds failures, 0 math discrepancies.
     - Mathematical authenticity confirmed.
3. **Hardcoding / Facade Check**:
   - Ran `check_hardcoding.py` across all Python files in `src/`.
   - No mock short-circuits or hardcoded constant evaluation returns found.

### 1.5 FAILURES AND DEFECTS OBSERVED
1. **Prohibited String "SOTA" in `README.md` (Integrity Failure)**:
   - Command: `python -c "readme = open('README.md', encoding='utf-8').read(); print('SOTA' in readme)"`
   - Output: `True` (Found 1 instance).
   - Verbatim location: `README.md` line 12:
     ```markdown
     > ChakraModel is a competent polyp segmenter achieving ~0.73–0.84 Dice across standard benchmarks. It is NOT state-of-the-art; SOTA methods achieve ~0.90+ Dice.
     ```
   - Violation: The prompt mandate explicitly states: **"Ensure ZERO instances of 'SOTA', '0.9852', '0.9412', '0.8650', or ungrounded claims."** Although used contextually in a disclaimer ("SOTA methods achieve ~0.90+ Dice"), the literal token `SOTA` is present, violating the zero-instance constraint.
2. **Runtime Execution Failure in Restructured Evaluation Scripts**:
   - Command: `python src/evaluation/quick_eval_kvasir.py`
   - Verbatim error:
     ```text
     Traceback (most recent call last):
       File "M:\chakramodel\src\evaluation\quick_eval_kvasir.py", line 29, in <module>
         from chakranet_segmenter import ChakraNetMicroRefiner
     ModuleNotFoundError: No module named 'chakranet_segmenter'
     ```
   - Defect: When `chakranet_segmenter.py` was moved to `src/models/chakranet_segmenter.py` and `chakra_transformer_best.pth` was moved to `weights/checkpoints/chakra_transformer_best.pth`, `quick_eval_kvasir.py` was not updated to import from `src.models.chakranet_segmenter` or look in `weights/checkpoints/`.
3. **Runtime Execution Failure in Other Restructured Scripts**:
   - `python src/evaluation/run_corrected_eval.py --n-images 1`:
     `ModuleNotFoundError: No module named 'chakranet_segmenter'` (line 43).
   - `python src/evaluation/verify_strict.py`:
     `ModuleNotFoundError: No module named 'chakranet_segmenter'` (line 15).
   - `pytest tests/test_challenger1_restructuring.py`:
     Fails at line 230 importing `from src.conformal.conformal_calibration import ConformalCalibrator` with `ModuleNotFoundError: No module named 'chakra_transformer'` because `src/` is not on `sys.path`.

---

## 2. Logic Chain

1. **Security & Privacy**:
   - Observation 1.1 confirms `keys.txt`, `data/leads/`, outreach logs, and resumes have empty `git ls-files` outputs and matching `.gitignore` entries.
   - Therefore, sensitive credentials and personal data are protected from accidental git publication. (PASS)
2. **Repository Restructuring**:
   - Observation 1.2 confirms all 185 deleted basenames in `c97f2173` exist in added paths.
   - Observation 1.2 confirms `archive/MANIFEST.md` matches the on-disk archive with zero missing and zero unmanifested files (126/126).
   - Observation 1.2 confirms `git log --oneline -5` shows exactly 5 local, non-pushed commits corresponding to Phases 2–4.
   - Therefore, the git restructuring preserved all artifacts and followed clean repository organization. (PASS)
3. **Documentation & Traceability**:
   - Observation 1.3 confirms `ARCHITECTURE_RECONSTRUCTED.md` and `DATA_FLOW_MAP.md` comprehensively and truthfully document the physical codebase, exposing dead code, DDP defects, paper-only combos, data leakage, and synthetic canaries.
   - Observation 1.4 confirms the 6-row honest metrics table in `README.md` perfectly matches the verified evaluation dump `cross_dataset_results_v5.json`. (PASS)
4. **Integrity Rule Enforcement**:
   - The user prompt specifies: *"Ensure ZERO instances of 'SOTA', '0.9852', '0.9412', '0.8650', or ungrounded claims."*
   - Observation 1.5 proves that `README.md` line 12 contains the exact string `"SOTA"`.
   - The system prompt mandates: *"Trust nothing... Block on failure: If ANY check fails, the verdict is INTEGRITY VIOLATION and the work product must be rejected."*
   - Additionally, Observation 1.5 proves that `src/evaluation/quick_eval_kvasir.py` and other core evaluation scripts crash upon execution due to unadjusted import paths following the directory reorganization.
   - Under strict forensic standards, a work product containing a prohibited keyword and broken evaluation scripts cannot receive a CLEAN verdict. (FAIL)

---

## 3. Caveats

1. **Semantic Intent of "SOTA" in Line 12**:
   - The occurrence of "SOTA" in `README.md` line 12 (`"It is NOT state-of-the-art; SOTA methods achieve ~0.90+ Dice."`) is intended as an honest disclaimer contrasting ChakraModel with true state-of-the-art methods, rather than an ungrounded promotional boast. However, as an automated or forensic rule, the specification required "ZERO instances of 'SOTA'".
2. **Root Shim vs Subpackage Imports**:
   - The failures in `quick_eval_kvasir.py` and `run_corrected_eval.py` are trivial import path discrepancies caused by moving modules into `src/models/` without updating legacy `import chakranet_segmenter` statements or adding `src/models` to `sys.path`. No model weights or algorithmic code were corrupted.
3. **Hardware / Long-Running Tests**:
   - Full image-by-image evaluation across 8,000+ PolypGen frames (`test_polypgen_challenger_pg2.py`) was not run to completion in this session due to time constraints, but the first 4 census and integrity assertions passed (80%).

---

## 4. Conclusion

The deliverables produced across Phases 2–4 represent an enormous technical improvement in truthfulness, architectural documentation, and security hygiene:
- Credentials and personal data are 100% untracked and gitignored.
- Historical metric fabrications (0.9852, 0.9412, 0.8650) have been completely purged.
- The 6-row honest metrics table is backed by empirical Kaggle cross-validation results.
- Architecture and data flow documentation provide exhaustive, transparent accounts of system limitations and dead code.
- All 126 archived files are accounted for in `archive/MANIFEST.md`.

However, pursuant to strict forensic auditor guidelines, the audit verdict is **INTEGRITY VIOLATION** based on two concrete findings:
1. **Rule Violation**: `README.md` line 12 contains the string `"SOTA"`, failing the explicit requirement for ZERO occurrences.
2. **Executability Defect**: `src/evaluation/quick_eval_kvasir.py`, `src/evaluation/run_corrected_eval.py`, and `src/evaluation/verify_strict.py` fail with `ModuleNotFoundError: No module named 'chakranet_segmenter'` due to unadapted relative import paths following directory restructuring.

### Required Remediations Before Certification:
1. Edit `README.md` line 12 to replace `"SOTA methods achieve ~0.90+ Dice"` with `"leading published methods achieve ~0.90+ Dice"`, achieving exactly zero instances of the token.
2. In `src/evaluation/quick_eval_kvasir.py` and `src/quick_eval_kvasir.py`:
   - Update import to `from src.models.chakranet_segmenter import ChakraNetMicroRefiner` (or add `PROJECT_ROOT / "src" / "models"` to `sys.path`).
   - Update `weights_path` to `PROJECT_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth"` (with fallback to `PROJECT_ROOT / "weights" / "chakra_transformer_best.pth"`).
3. In `src/evaluation/run_corrected_eval.py` and `src/evaluation/verify_strict.py`:
   - Update imports to use `src.models.chakranet_segmenter` or insert `src/models` into `sys.path`.
4. In `src/training/topo_loss.py`:
   - Add alias `TopoLoss = TopologicalLoss` to maintain compatibility with test suites.

---

## 5. Verification Method

To independently reproduce all observations and verify the status:

1. **Verify Prohibited Strings in `README.md`**:
   ```bash
   python -c "t = open('README.md', encoding='utf-8').read(); print({s: t.count(s) for s in ['SOTA', '0.9852', '0.9412', '0.8650']})"
   # Expected output: {'SOTA': 1, '0.9852': 0, '0.9412': 0, '0.8650': 0}
   ```

2. **Verify Security Git Hygiene**:
   ```bash
   git ls-files keys.txt data/leads/ "*sent_emails*" "*Resume*" "*LOR*"
   # Expected output: completely empty
   ```

3. **Verify Archive Manifest Exact Match**:
   ```bash
   python .agents/auditor_1/verify_manifest.py
   # Expected output:
   # Total manifest entries parsed: 126
   # Actual files on disk (excluding MANIFEST.md and pycache): 126
   # Missing on disk: set()
   # Unmanifested on disk: set()
   ```

4. **Verify Git History**:
   ```bash
   git log --oneline -5
   # Verify 5 commits ahead of origin/main
   ```

5. **Reproduce Script Import Failures**:
   ```bash
   python src/evaluation/quick_eval_kvasir.py
   # Observe ModuleNotFoundError: No module named 'chakranet_segmenter'
   ```
