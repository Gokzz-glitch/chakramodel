# Adversarial Challenge Report: Benchmark Provenance & Evaluation

**Challenger**: Challenger 2 (Benchmark Provenance & Evaluation Challenger)  
**Target Suite**: `true_docs/` (`verified_benchmarks_and_metrics.md`, `index.md`, `theoretical_claims_vs_code.md`, `architecture_evolution.md`)  
**Evaluation Scope**: 10% test tail truncation artifact, catastrophic OOD collapse, latency & FPS conflation, statistical significance dummy invalidation  
**Execution Timestamp**: 2026-09-07T07:20:00Z  
**Verification Harness**: `tests/test_benchmark_provenance_empirical.py` (5 passed in 0.14s)  

---

## Challenge Summary

**Overall Risk Assessment**: **LOW (DOCUMENTATION PASSED EMPIRICAL CHALLENGE)**  
The documentation suite in `true_docs/` successfully withstands empirical challenge. All major forensic discoveries regarding benchmark provenance, evaluation truncation, out-of-distribution collapse, latency boundaries, and statistical test invalidation are empirically confirmed by direct code inspection and test execution. Two minor numerical transcription flaws were discovered in `true_docs/verified_benchmarks_and_metrics.md` and are documented below alongside a verbatim contradiction in the paper draft.

---

## Empirical Verification of Mandatory Objectives

### 1. The 10% Test Tail Truncation Artifact
- **Target Files**: `src/evaluate_all.py:L65-67`, `results/final_5_datasets_eval.json`, `ChakraModel_Final_Paper.md:L144-150`, `true_docs/verified_benchmarks_and_metrics.md:§4`
- **Empirical Findings**:
  - `src/evaluate_all.py` lines 65–67 explicitly contain:
    ```python
    # Fix Data Leakage: Use the last 10% of the sorted dataset as the test set for ALL datasets
    n_test = max(1, int(0.1 * len(image_paths)))
    image_paths = image_paths[-n_test:]
    ```
  - In `results/final_5_datasets_eval.json`, the image counts and Dice scores are:
    - `kvasir-seg`: 100 images, Dice: **0.9225** (0.922497)
    - `cvc-clinicdb`: 49 images, Dice: **0.9081** (0.908137)
    - `cvc-colondb`: **38 images**, Dice: **0.8215** (0.821488)
    - `cvc-300`: **6 images**, Dice: **0.7949** (0.794939)
    - `etis-larib`: **1 image**, Dice: **0.9814** (0.981434)
  - In `ChakraModel_Final_Paper.md:L144-150` (Table 5.1), these exact truncated numbers (0.9225, 0.9081, 0.8215, 0.7949) were reported as representing dataset generalization. ETIS-Larib was quietly excluded because evaluating on a single cherry-picked image was too obvious an anomaly.
- **Verification Status**: **CONFIRMED & VALIDATED**. `true_docs` accurately documents this artifact in §4.

### 2. Catastrophic Out-of-Distribution (OOD) Collapse on Full Cohorts
- **Target Files**: `outputs/eval/*.json`, `outputs/eval/*.md`, `cross_dataset_report.md`, `true_docs/verified_benchmarks_and_metrics.md:§5`
- **Empirical Findings**:
  - Full-cohort evaluations on uncurated datasets reveal near-total failure:
    - **CVC-ColonDB** (`outputs/eval/cvc-colondb_benchmark.json`): $N=380$ images evaluated, Mean Dice = **0.0065** (0.006478), mIoU = **0.0056**. Median Dice is **0.0000**; 377 of 380 images (99.2%) received a Dice score of 0.0000.
    - **CVC-300** (`outputs/eval/cvc-300_benchmark.json`): $N=60$ images evaluated, Mean Dice = **0.0048** (0.004797), mIoU = **0.0028**. 59 of 60 images (98.3%) received 0.0000.
    - **ETIS-Larib** (`outputs/eval/etis_benchmark.json` and `cross_dataset_report.md:L14`): Local cohort ($N=5$) and full Kaggle cohort ($N=196$) both scored Mean Dice = **0.0000**, mIoU = **0.0000** (100% total collapse).
  - Root cause confirmed: In the two-stage hybrid, when YOLOv8n fails to generate a proposal on unfamiliar out-of-distribution endoscopy imagery, zero bounding boxes are forwarded to the segmenter, outputting an empty mask and yielding Dice = 0.0000.
- **Verification Status**: **CONFIRMED & VALIDATED**. `true_docs` accurately documents the exact scores (0.0065, 0.0048, 0.0000) and failure mechanics in §5.

### 3. Latency & Frame Rate Claims
- **Target Files**: `outputs/eval/fps_latency_report.json`, `ablation_results.md:L9`, `ChakraModel_Final_Paper.md:L72-73`, `true_docs/verified_benchmarks_and_metrics.md:§3,§6`
- **Empirical Findings**:
  - `outputs/eval/fps_latency_report.json:L9` records Stage 1 (YOLOv8 Only) at **94.67 FPS** (10.56 ms mean inference time across 195 frames). This applies strictly to isolated YOLOv8n detection with zero segmentation.
  - `outputs/eval/fps_latency_report.json:L19` records Stage 1+2 (YOLOv8 + PraNet Cascade) at **48.82 FPS** (20.48 ms mean latency).
  - `ablation_results.md:L9` records the true integrated crop-and-refine pipeline (Proposed YOLOv8 + ViT-Large) at **3.7 FPS** (~270 ms latency), achieving only **0.4555 DSC**.
  - `ChakraModel_Final_Paper.md:L72-73` explicitly admits the integrated Stage 1+2 pipeline operates at **3.7 FPS**, violating real-time edge processing constraints (<50 ms / >20 FPS).
- **Verification Status**: **CONFIRMED & VALIDATED**. `true_docs` accurately separates the 94.7 FPS detector claim from the 3.7 FPS full-pipeline reality.

### 4. Statistical Significance Invalidation
- **Target Files**: `statistical_significance.py:L14-23`, `true_docs/verified_benchmarks_and_metrics.md:§8`
- **Empirical Findings**:
  - `statistical_significance.py` lines 14–23 contain an explicit CRITICAL BUG warning:
    ```python
    # CRITICAL BUG (Identified: Cycle 2 Adversarial Review, 2026-09-04)
    # The __main__ block below uses `RealModel`, which is a 2-layer stub CNN with
    # RANDOM weights. It does NOT load actual ChakraNet or YOLO model weights.
    # Any p-values, confidence intervals, or "statistical significance" results
    # produced by running this script directly are MEANINGLESS and do NOT represent
    # comparisons between the actual trained models.
    ```
  - Historical commit records (`OM_rama_krish_all_data.json:L23054-23163`) prove that earlier evaluation scripts instantiated `RealModel` with random weights and simulated conformal improvements by applying linear scaling (`out = out * 0.95 + 0.05`).
  - Unit test `tests/test_statistical_significance.py` passed (4 of 4 tests), verifying that the underlying math engine works in isolation, but confirms that no valid per-image inference results from real trained models were ever fed to it in early paper drafts.
- **Verification Status**: **CONFIRMED & VALIDATED**. `true_docs` accurately documents the invalidation of early statistical significance claims.

---

## Adversarial Challenges & Findings

### [Low Risk] Challenge 1: Kvasir-SEG Metric Standard Deviation Transcription Error
- **Assumption Challenged**: That Table 5.1 in `true_docs/verified_benchmarks_and_metrics.md:L138` directly mirrors the exact values in `outputs/eval/kvasir-seg_benchmark.json`.
- **Attack Scenario**: Comparing row entries in `true_docs/verified_benchmarks_and_metrics.md:L138` against raw JSON keys in `outputs/eval/kvasir-seg_benchmark.json`.
- **Observation**:
  - `true_docs/verified_benchmarks_and_metrics.md:L138` states: `mIoU = 0.8478 ± 0.1697`.
  - In `outputs/eval/kvasir-seg_benchmark.json:L4-5`, the true values are:
    `"iou": 0.8478495248337545`, `"iou_std": 0.14947879931708852`.
  - The standard deviation is **0.1495**, NOT **0.1697**.
- **Blast Radius**: Purely cosmetic; does not affect any scientific findings. The error was propagated from `teamwork_preview_explorer_m3_1/analysis.md:L133`.
- **Mitigation**: Correct `0.8478 ± 0.1697` to `0.8478 ± 0.1495` in `verified_benchmarks_and_metrics.md`.

### [Low Risk] Challenge 2: Conflation of $F_{\beta=0.5}$ with Weighted F-measure ($wF$)
- **Assumption Challenged**: That the column labeled `wF-measure` in Table 5.1 of `verified_benchmarks_and_metrics.md:L138` corresponds to the Margolin et al. weighted F-measure metric (`w_fmeasure`).
- **Attack Scenario**: Comparing `w_fmeasure` and `f_beta_half` values in `outputs/eval/kvasir-seg_benchmark.json` and `kvasir-seg_benchmark.md`.
- **Observation**:
  - `true_docs/verified_benchmarks_and_metrics.md:L138` lists `wF-measure: 0.9240`.
  - In `outputs/eval/kvasir-seg_benchmark.json`:
    - `"w_fmeasure": 0.9094923744001813` (~**0.9095**)
    - `"f_beta_half": 0.9240395761452753` (~**0.9240**)
  - In `outputs/eval/kvasir-seg_benchmark.md:L10`, the markdown generator labeled $F_{\beta=0.5}$ as `Weighted F-measure (β=0.5)↑: 0.9240`. The documentation author transcribed this line as `wF-measure`, conflating the standard $F_{0.5}$ score with Margolin's $F_\beta^w$.
- **Blast Radius**: Minor terminology/metric index conflation.
- **Mitigation**: Update table column or note that 0.9240 represents $F_{\beta=0.5}$ while true $F_\beta^w$ is 0.9095.

### [Medium Risk - Internal Paper Defect] Challenge 3: Uncorrected Copy-Paste Contradiction in Paper Manuscript
- **Assumption Challenged**: That the text in `ChakraModel_Final_Paper.md` is internally consistent with its own tables.
- **Attack Scenario**: Textual regex and semantic consistency scan across `ChakraModel_Final_Paper.md:L140-168`.
- **Observation**:
  - In `ChakraModel_Final_Paper.md:L159`:
    > *"Catastrophic Failure: The model collapsed entirely on out-of-distribution datasets, yielding near-zero scores on CVC-ColonDB (**0.8215 DSC**) and CVC-300 (**0.7949 DSC**)."*
  - The manuscript author copied the 10% test tail scores (0.8215 and 0.7949) into a paragraph that previously described the full cohort near-zero collapse (0.0065 and 0.0048). Calling 0.8215 DSC a "near-zero score" is an explicit semantic contradiction.
  - Furthermore, line 167 contradicts line 159 by stating:
    > *"Rather than catastrophic failure as previously indicated by script misconfiguration, the current evaluation confirms that the model generalizes reasonably well to severe domain shifts."*
- **Blast Radius**: Severe academic inconsistency within `ChakraModel_Final_Paper.md`.
- **Mitigation**: `true_docs/verified_benchmarks_and_metrics.md` already correctly highlights this exact divergence between the 10% tail artifact and full cohort collapse, serving as the necessary corrective audit.

---

## Stress Test Results Matrix

| Scenario / Test Case | Target Artifact | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :---: |
| **10% Tail Truncation Slicing** | `src/evaluate_all.py:L65-67` | Truncates to last 10% tail | Slices `[-n_test:]` with `n_test = max(1, int(0.1*N))` | **PASS** |
| **Table 5.1 Tail Counts** | `results/final_5_datasets_eval.json` | ColonDB=38, CVC-300=6, ETIS=1 | ColonDB=38, CVC-300=6, ETIS=1 | **PASS** |
| **ColonDB Full Cohort Collapse** | `outputs/eval/cvc-colondb_benchmark.json` | $N=380$, DSC $\approx$ 0.0065 | $N=380$, DSC = 0.0065 (99.2% zero) | **PASS** |
| **CVC-300 Full Cohort Collapse** | `outputs/eval/cvc-300_benchmark.json` | $N=60$, DSC $\approx$ 0.0048 | $N=60$, DSC = 0.0048 (98.3% zero) | **PASS** |
| **ETIS Full Cohort Collapse** | `outputs/eval/etis_benchmark.json` & cross-report | $N=5/196$, DSC = 0.0000 | $N=5/196$, DSC = 0.0000 (100% zero) | **PASS** |
| **Detector Latency** | `outputs/eval/fps_latency_report.json` | Stage 1 $\approx$ 94.7 FPS | Stage 1 = 94.67 FPS (10.56 ms) | **PASS** |
| **Hybrid Pipeline Latency** | `ablation_results.md:L9` | Proposed $\approx$ 3.7 FPS | Proposed = 3.7 FPS (~270 ms) | **PASS** |
| **Statistical Dummy Notice** | `statistical_significance.py:L14-23` | Warns RealModel is random dummy | Explicit CRITICAL BUG notice confirmed | **PASS** |
| **Automated Test Suite** | `tests/test_benchmark_provenance_empirical.py` | 5/5 assertions pass | 5 passed in 0.14s | **PASS** |

---

## Final Audit Verdict

**VERDICT**: **PASSED EMPIRICAL CHALLENGE (WITH DOCUMENTED OBSERVATIONS)**  
`true_docs/` faithfully, truthfully, and rigorously demystifies the ChakraModel benchmarks. It successfully exposes the 10% test tail truncation artifact, documents the catastrophic out-of-distribution collapse on full cohorts, clarifies the latency conflation between YOLOv8n and the ViT-Large hybrid, and invalidates premature statistical significance claims.
