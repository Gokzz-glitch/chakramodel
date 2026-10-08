# Comprehensive Forensic Audit & Metrics Remediation Analysis
**Document:** `analysis.md`  
**Target Files:** `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md`  
**Auditor:** Explorer 1 (Milestone 1, Generation 9)  
**Date:** 2026-09-09  
**Ground Truth Reference:** `docs/HONEST_METRICS.md` and `kaggle_results/run_v5/cross_dataset_results_v5.json`

---

## 1. Executive Summary

This forensic investigation performed an exhaustive line-by-line inspection of both paper manuscripts in the ChakraModel repository:
1. `paper/main.tex` (50 lines, LaTeX manuscript)
2. `docs/paper/ChakraModel_Final_Paper.md` (236 lines, Markdown manuscript v4.0)

### Key Findings
1. **`paper/main.tex` is completely compromised by obsolete, fabricated, and hyperbolic claims**:
   - Contains prohibited strings: `"state-of-the-art"` (lines 16, 20).
   - Contains prohibited superlatives: `"unprecedented accuracy"` (line 16), `"highly competitive scores"` (line 44), `"highly robust and accurate solution"` (line 47).
   - Contains fabricated metrics: Kvasir-SEG Dice `0.9225` and mIoU `0.8743` (lines 16, 35, 44); CVC-ClinicDB Dice `0.9081` and mIoU `0.8504` (line 36); CVC-ColonDB Dice `0.8215` and mIoU `0.7359` (line 37); CVC-300 Dice `0.7949` and mIoU `0.6796` (line 38); placeholder `0.0000` MAE across all rows.
   - Contains ETIS-Larib Dice `0.0000` presented without context, obscuring catastrophic zero-shot domain failure.
   - Describes an obsolete architecture: claims a "ResNet-50 backbone with specialized Reverse Attention modules" (line 23, PraNet clone) rather than the actual Edge-Native Hybrid (YOLOv8 + ViT-Large ChakraTransformer).
   - **Recommendation**: Complete rewrite of `paper/main.tex` to align with the honest, reconstructed Edge-Native architecture and verified Kaggle v5 metrics.

2. **`docs/paper/ChakraModel_Final_Paper.md` (v4.0) represents substantial progress toward transparency, but retains obsolete intermediate metrics and uncoordinated claims**:
   - Contains obsolete/unsupported metric **`0.7304 DSC`** (and companion **`0.6452 IoU`**) on lines 16, 32, 156, 171, 173, 179, 195, and 199. As established in `DOWNLOADS_INVENTORY.md` §3.4 and `docs/HONEST_METRICS.md`, this intermediate metric has no backing verifiable artifact; the genuine single source of truth is the Kaggle run_v5 benchmark (**0.8131 DSC**, **0.7141 IoU** on N=150 held-out test split).
   - In Table 5.1 (lines 150–156), CVC-ClinicDB, CVC-ColonDB, and CVC-300 are left as `*Pending*`, ignoring that `docs/HONEST_METRICS.md` and `kaggle_results/run_v5/cross_dataset_results_v5.json` already contain cryptographically verified zero-shot evaluations: **CVC-ClinicDB (0.7561 DSC, N=495)** and **CVC-300 (0.7402 DSC, N=60)**.
   - ETIS-Larib is stated on line 117 as "Excluded from evaluation due to missing clinical source data", which omits the verified zero-shot evaluation on N=196 images in Kaggle run_v5 that demonstrated catastrophic domain collapse (**0.0000 DSC**), as well as the historical retraction of the fabricated 0.8650 claim.
   - Contains latency/edge feasibility contradictions: line 35 claims "solving the heavy-transformer latency problem on strict 4GB edge hardware budgets" and line 52 claims "achieve real-time latency on edge hardware", directly contradicted by line 77 ("The integrated Stage 1+2 pipeline runs at 3.7 FPS... severely violates the <50ms latency bound") and line 202 (309M parameter ViT-Large fatally bottlenecks 4GB VRAM).
   - Displays sample size discrepancies across sections: N=100 (line 113) vs N=50 (line 158) vs N=60 (`results/corrected_eval_kvasir_seg.json`) vs N=150 (`docs/HONEST_METRICS.md`).
   - Contains duplicate section headers: `## 5. Results and Discussion` (line 142) and `## 5. Experimental Results and Analysis` (line 160).

---

## 2. Ground Truth Reference Benchmark

The single source of truth for all metric reporting is defined in `docs/HONEST_METRICS.md` and verified in `kaggle_results/run_v5/cross_dataset_results_v5.json`:

| Dataset | Evaluation Method | N (Images) | Dice Score (Mean ± Std) | IoU / mIoU | Precision | Recall | Status |
|---|---|---|---|---|---|---|---|
| **Kvasir-SEG** | test split | 150 | 0.8131 ± 0.1747 | 0.7141 | 0.8330 | 0.8500 | **Verified Genuine** |
| **HyperKvasir Segmented** | benchmark | 1000 | 0.8360 ± 0.1610 | 0.7439 | 0.8398 | 0.8768 | **Verified Genuine** |
| **CVC-ClinicDB** | zero-shot | 495 | 0.7561 ± 0.2131 | 0.6470 | 0.7553 | 0.8444 | **Verified Genuine** |
| **EndoScene CVC-300** | zero-shot | 60 | 0.7402 ± 0.1590 | 0.6098 | 0.6361 | 0.9427 | **Verified Genuine** |
| **PolypDB (All Modalities)** | benchmark | 7868 | 0.7283 ± 0.2544 | 0.6243 | 0.6889 | 0.8611 | **Verified Genuine** |
| **ETIS-Larib** | zero-shot | 196 | 0.0000 ± 0.0000 | 0.0000 | 0.0000 | 0.0000 | **Catastrophic Failure** |

### Retracted / Fabricated Metrics Inventory (Never to be cited as genuine)
- **0.9852** (ChakraTransformer C6 on Kvasir-SEG — unverifiable, contaminated)
- **0.9412** (ChakraTransformer C6 on CVC-ClinicDB — unverifiable; true zero-shot is 0.7561)
- **0.8650** (ChakraTransformer C6 on ETIS-Larib — unverifiable; true zero-shot is 0.0000)
- **0.9225** (ChakraModel on Kvasir-SEG — fabricated legacy metric)
- **0.9081** (ChakraModel on CVC-ClinicDB — fabricated legacy metric)
- **0.8215** (ChakraModel on CVC-ColonDB — fabricated legacy metric)
- **0.7949** (ChakraModel on CVC-300 — inflated legacy metric)
- **0.7304 / 0.6452** (ChakraTransformer on Kvasir-SEG N=50 — unsupported intermediate prose metric)

---

## 3. Exhaustive Itemized Audit of `paper/main.tex`

`paper/main.tex` consists of 50 lines. The table below catalogs every violation, classification, and precise remediation.

| Line | Category | Existing Verbatim Code / Text | Defect Description | Required Remediation |
|---|---|---|---|---|
| **9** | Superlative / Inflation | `\title{ChakraModel: Highly Accurate and Robust Polyp Segmentation using Hybrid Architecture}` | "Highly Accurate and Robust" is an unsubstantiated superlative given 0.0000 ETIS score and 3.7 FPS latency. | Replace with neutral title: `\title{ChakraModel: An Edge-Native Hybrid Framework for Clinical Polyp Segmentation with Conformal Guarantees}` |
| **16** | Superlative Claim | `...achieves unprecedented accuracy across multiple datasets.` | Prohibited superlative claim ("unprecedented accuracy"). | Remove superlative; replace with objective statement of evaluation and bounds. |
| **16** | Fabricated Metric | `Our method achieves a Dice score of 0.9225 on the Kvasir-SEG dataset...` | Prohibited fabricated metric `0.9225`. | Replace with verified Kaggle v5 metric: `Dice score of 0.8131 (IoU 0.7141) on the Kvasir-SEG test split (N=150)`. |
| **16** | Prohibited String & Superlative | `...outperforming state-of-the-art baselines.` | Contains prohibited string `"state-of-the-art"` (case-insensitive) and unsupported superiority claim. | Replace with honest comparison: `achieving competent baseline performance while operating below real-time clinical thresholds`. |
| **16** | Generalization Inflation | `We evaluate ChakraModel across five standard polyp segmentation datasets, demonstrating its robustness and generalization capabilities.` | Misleading claim of "robustness and generalization" given complete failure on ETIS-Larib (Dice 0.0000). | State transparently: `evaluating cross-dataset generalization across multi-center benchmarks, identifying significant domain degradation on challenging zero-shot targets.` |
| **20** | Prohibited String | `...to achieve state-of-the-art polyp segmentation.` | Contains prohibited string `"state-of-the-art"`. | Replace with: `...to evaluate decoupled edge-native detection and transformer-based segmentation with conformal uncertainty bounds.` |
| **20** | Unsubstantiated Claim | `...combines a highly effective backbone with novel refinement modules...` | Vague promotional language ("highly effective", "novel"). | Replace with factual description: `combines a YOLOv8 detection stage with a ViT-Large segmentation core`. |
| **23** | Architecture Mismatch | `ChakraModel uses a ResNet-50 backbone with specialized Reverse Attention modules. The features are aggregated and refined across multiple stages. We apply comprehensive data augmentation and train using a combined Dice and BCE loss.` | Fundamental architectural error: Describes Combo 1 / PraNet baseline (ResNet-50 + Reverse Attention), not the actual ChakraModel (YOLOv8 + ViT-Large Combo 6). | Rewrite Methodology to document the two-stage decoupled architecture (YOLOv8 stage 1, ViT-Large stage 2) and `DiceFocalLoss`. |
| **26** | Inaccurate Benchmark List | `We evaluated our model on five standard benchmark datasets: Kvasir-SEG, CVC-ClinicDB, CVC-ColonDB, CVC-300, and ETIS.` | Lists CVC-ColonDB and ETIS without provenance context. | Update dataset list to match verified Kaggle v5 suite: Kvasir-SEG, HyperKvasir, CVC-ClinicDB, CVC-300, PolypDB, and ETIS-Larib. |
| **30–42** | Fabricated Table (Table 1) | Whole `\begin{table}...\end{table}` block | Table contains entirely fabricated/inflated numbers (0.9225, 0.9081, 0.8215, 0.7949), unexplained 0.0000 for ETIS, and 0.0000 MAE placeholders. | Replace Table 1 with the verified Kaggle v5 benchmark results from `docs/HONEST_METRICS.md`. |
| **35** | Fabricated Metric | `Kvasir-SEG & 0.9225 & 0.8743 & 0.0000 \\` | Fabricated Dice `0.9225`, fabricated mIoU `0.8743`, dummy MAE `0.0000`. | Replace with: `Kvasir-SEG (test, N=150) & 0.8131 & 0.7141 & -- \\` |
| **36** | Fabricated Metric | `CVC-ClinicDB & 0.9081 & 0.8504 & 0.0000 \\` | Fabricated Dice `0.9081`, fabricated mIoU `0.8504`, dummy MAE `0.0000`. | Replace with verified zero-shot: `CVC-ClinicDB (zero-shot, N=495) & 0.7561 & 0.6470 & -- \\` |
| **37** | Fabricated Metric | `CVC-ColonDB & 0.8215 & 0.7359 & 0.0000 \\` | Fabricated Dice `0.8215`, mIoU `0.7359`. | Replace with verified benchmark or mark unverified/omitted from v5 suite. |
| **38** | Inflated Metric | `CVC-300 & 0.7949 & 0.6796 & 0.0000 \\` | Inflated Dice `0.7949`, mIoU `0.6796`. | Replace with verified zero-shot: `CVC-300 (zero-shot, N=60) & 0.7402 & 0.6098 & -- \\` |
| **39** | Unexplained Failure | `ETIS & 0.0000 & 0.0000 & 0.0000 \\` | Dice 0.0000 listed without context or clinical explanation. | Annotate clearly: `ETIS-Larib (zero-shot, N=196) & 0.0000 & 0.0000 & -- (Catastrophic domain failure)` |
| **44** | Fabricated Metric & Superlative | `As shown in the table, ChakraModel achieves highly competitive scores, particularly on the Kvasir-SEG dataset (Dice: 0.9225).` | "Highly competitive scores" and fabricated metric `0.9225`. | Replace with: `As shown, ChakraModel achieves a Dice score of 0.8131 on Kvasir-SEG, while showing zero-shot domain transfer drop on CVC-ClinicDB (0.7561) and complete collapse on ETIS-Larib (0.0000).` |
| **47** | Superlative & Inaccurate Claim | `ChakraModel offers a highly robust and accurate solution for polyp segmentation, bridging the gap between theoretical models and clinical applicability.` | Exaggerated conclusion ("highly robust and accurate", "bridging the gap") contradicted by 3.7 FPS latency and ETIS failure. | Replace with honest conclusion: `ChakraModel demonstrates a functional decoupled hybrid framework, but its 3.7 FPS processing speed and out-of-distribution sensitivity indicate that substantial optimization is required before clinical deployment.` |

---

## 4. Exhaustive Itemized Audit of `docs/paper/ChakraModel_Final_Paper.md`

`docs/paper/ChakraModel_Final_Paper.md` consists of 236 lines. The table below catalogs all occurrences of obsolete metrics, discrepancies, superlative statements, and required remediations.

| Line | Category | Existing Verbatim Text | Defect Description | Required Remediation |
|---|---|---|---|---|
| **16** | Obsolete Metric | `- **v4.0 (2026-09-08 09:40 UTC+5:30):** Root cause resolution... Fix applied and true metrics (0.7304 DSC) evaluated.` | Cites obsolete unverified metric `0.7304 DSC`. | Update to: `Fix applied and verified metrics evaluated (0.8131 DSC on Kvasir-SEG test split N=150, Kaggle run v5).` |
| **18–20** | Context Note | `> **[GENERATOR NOTE — HONEST REVISION v4.0]** ... True evaluation results are now integrated.` | Mentions integration of v4.0 metrics (which was 0.7304). | Update note to state that v5 verified multi-dataset metrics are now integrated. |
| **32** | Obsolete Metric | `...restoring true test performance to **0.7304 DSC** on the Kvasir-SEG test split.` | Cites obsolete metric `0.7304 DSC`. | Replace with: `...restoring verified test performance to **0.8131 DSC** (IoU 0.7141) on the Kvasir-SEG test split (N=150, Kaggle run v5).` |
| **35** | Unsupported Claim / Contradiction | `...solving the heavy-transformer latency problem on strict 4GB edge hardware budgets.` | Directly contradicted by line 77 (measured 3.7 FPS violates real-time latency) and line 202 (309M parameter model fatally bottlenecks 4GB VRAM). | Replace with honest phrasing: `...evaluating the architectural trade-offs of region-of-interest transformer execution, while acknowledging that the current 3.7 FPS throughput does not yet meet real-time edge constraints.` |
| **52** | Unsupported Claim / Contradiction | `...We present a novel architecture that combines YOLOv8 tracking with ChakraTransformer segmentation to achieve real-time latency on edge hardware.` | Claim of achieving "real-time latency" is contradicted by measured 3.7 FPS (~270ms/frame) in §3.1. | Replace with: `...We analyze an architecture combining YOLOv8 detection with ChakraTransformer segmentation, evaluating latency bottlenecks and edge deployment requirements.` |
| **62** | ETIS-Larib Context | `While these models achieve high performance on source datasets, they often suffer catastrophic degradation on harder, out-of-distribution datasets such as ETIS-Larib.` | Mention of ETIS-Larib degradation is factually aligned, but needs explicit cross-reference to the 0.0000 zero-shot result. | Retain as clinical motivation and cross-reference §4.1 / §5.1. |
| **76–77** | Latency Transparency | Standalone YOLOv8 runs at 94.7 FPS, but integrated pipeline runs at **3.7 FPS** (violating <50ms). | This is honest transparency; must be preserved and harmonized with contributions (§1.1). | Preserve as the benchmark truth; remove conflicting claims in lines 35 and 52. |
| **100** | Sample Size Discrepancy | `Empirical pixel-wise coverage on the Kvasir-SEG test cohort (N=100 images) was **95.0%**...` | States N=100 images for Kvasir-SEG test cohort, whereas verified Kaggle v5 split is N=150. | Reconcile sample size citation to N=150 or explain calibration cohort breakdown. |
| **113** | Split Size Discrepancy | `- **Kvasir-SEG**: Primary training set (1,000 images). Final metrics reported on 10% held-out test split (N=100).` | Discrepancy: Kaggle run v5 uses N=150 (15% test split), not N=100. | Update to: `Final metrics reported on held-out test split (N=150, Kaggle v5).` |
| **117** | ETIS-Larib Inconsistency | `- **ETIS-Larib**: Excluded from evaluation due to missing clinical source data (only synthetic fallbacks available).` | Contradicts `HONEST_METRICS.md` and `cross_dataset_results_v5.json`, where zero-shot evaluation on N=196 images was executed and scored 0.0000 DSC. | Update to: `- **ETIS-Larib**: Evaluated zero-shot (N=196 images, Kaggle v5), exhibiting catastrophic domain transfer failure (Dice 0.0000). Historical claim of 0.8650 is formally retracted.` |
| **150–156** | Table 5.1 Deficiencies | Entire Cross-Dataset Comparison Table | Contains fabricated numbers (0.9225, 0.9081, 0.8215, 0.7949), obsolete number (0.7304), and leaves CVC-ClinicDB and CVC-300 as `*Pending*`. | Replace row 156 with verified Kaggle v5 metrics across all tested datasets. See Section 6 for exact table. |
| **154** | Fabricated Baseline Listing | `| **ChakraTransformer (Initial Fabricated Claim)** | *0.9225* | *0.9081* | *0.8215* | *0.7949* |` | Accurately labels them as fabricated, but should also clarify the retraction of 0.9852 (Kvasir), 0.9412 (CVC-ClinicDB), and 0.8650 (ETIS-Larib) from the early README. | Add note or row explicitly documenting retracted README metrics. |
| **156** | Obsolete Metric & Pending Status | `| **ChakraTransformer (Resolved & Verified)** | **0.7304** | *Pending* | *Pending* | *Pending* |` | Cites unsupported `0.7304`; marks CVC-ClinicDB and CVC-300 as `*Pending*` when genuine v5 numbers (0.7561 and 0.7402) are available. | Update row to: `Kvasir-SEG: 0.8131`, `CVC-ClinicDB: 0.7561`, `CVC-ColonDB: Not in v5`, `CVC-300: 0.7402`, `ETIS-Larib: 0.0000`. |
| **158** | Source & Sample Inconsistency | `*Source: results/corrected_eval_kvasir_seg.json via verifiable harness on N=50 images (Kvasir-SEG test split).*` | Inconsistent: `results/corrected_eval_kvasir_seg.json` in repo contains N=60 (Dice 0.80225); true source of truth is `kaggle_results/run_v5/cross_dataset_results_v5.json` (N=150, Dice 0.8131). | Update source citation to `kaggle_results/run_v5/cross_dataset_results_v5.json` (N=150). |
| **160** | Duplicate Header | `## 5. Experimental Results and Analysis` | Line 142 already declared `## 5. Results and Discussion`. | Consolidate under a single Section 5 header hierarchy. |
| **171** | Obsolete Metric | `- Evaluation on the true held-out Kvasir-SEG test split (seed=42) yielded a genuine **0.7304 Mean DSC** and **0.6452 Mean IoU**.` | Obsolete metric from untracked/unsupported notebook prose. | Update to: `yielded a verified **0.8131 Mean DSC** and **0.7141 Mean IoU** on N=150 test images (Kaggle run v5).` |
| **173** | Obsolete Metric & Fabrication Ref | `While 0.7304 DSC is lower than the initial fabricated claim of 0.9225...` | Refers to `0.7304 DSC`. | Update to: `While the verified 0.8131 DSC is lower than the initial fabricated claim of 0.9225...` |
| **179** | Obsolete Metric & False Pending | `The genuine 0.7304 DSC on Kvasir-SEG demonstrates that the model generalizes to held-out test data... True zero-shot performance bounds on OOD datasets (CVC-ClinicDB) will be quantified in subsequent runs now that the pipeline is verified.` | Claims 0.7304 and claims CVC-ClinicDB evaluation is future work, ignoring completed Kaggle v5 run (0.7561 DSC). | Update to report verified CVC-ClinicDB zero-shot score (0.7561 DSC, 0.6470 IoU, N=495). |
| **182** | Sample Size Discrepancy | `Empirical pixel-wise coverage on the Kvasir-SEG test cohort is **95.0%** (N=100 images)...` | Discrepancy with N=150 test split in Kaggle v5. | Reconcile N=100 vs N=150 split citation. |
| **195** | Obsolete Metric | `- The ChakraTransformer effectively learns segmentation boundaries, achieving a genuine 0.7304 DSC once the DDP serialization defect was resolved.` | Cites `0.7304 DSC`. | Replace with: `achieving a verified 0.8131 DSC on the Kvasir-SEG test split (N=150).` |
| **199** | Obsolete Metric | `- **Fabricated Baselines:** The previous metrics (0.9225 DSC in-distribution, 0.8215 OOD) were fabricated artifacts of flawed evaluation scripts. The true baseline is 0.7304 DSC.` | Cites `0.7304 DSC` as true baseline. | Replace with: `The true verified baseline is 0.8131 DSC (Kvasir-SEG) and 0.7561 DSC (CVC-ClinicDB zero-shot).` |

---

## 5. Metric Reconciliation Matrix

The following table provides the cross-comparison between past claims, intermediate unverified numbers, and the cryptographically backed ground truth:

| Dataset | Split Type | N Images | Earliest Claim (README / main.tex) | Intermediate Claim (v4.0 Paper) | Verified Ground Truth (`HONEST_METRICS.md`) | Discrepancy Status |
|---|---|---|---|---|---|---|
| **Kvasir-SEG** | Test split | 150 | 0.9852 / 0.9225 | 0.7304 (N=50) | **0.8131 ± 0.1747** (IoU: 0.7141) | Earlier 0.9852/0.9225 fabricated; 0.7304 unsupported intermediate; 0.8131 verified. |
| **HyperKvasir** | Benchmark | 1000 | Unreported in main.tex | Unreported in paper | **0.8360 ± 0.1610** (IoU: 0.7439) | Verified; omit or add to expanded multi-center table. |
| **CVC-ClinicDB** | Zero-shot | 495 | 0.9412 / 0.9081 | *Pending* | **0.7561 ± 0.2131** (IoU: 0.6470) | 0.9412/0.9081 fabricated; paper left as *Pending*; 0.7561 verified. |
| **CVC-300** | Zero-shot | 60 | 0.7949 | *Pending* | **0.7402 ± 0.1590** (IoU: 0.6098) | 0.7949 inflated; paper left as *Pending*; 0.7402 verified. |
| **PolypDB** | All modalities | 7868 | Unreported in main.tex | Unreported in paper | **0.7283 ± 0.2544** (IoU: 0.6243) | Verified massive-scale benchmark; provides strong evidence of generalization bound. |
| **ETIS-Larib** | Zero-shot | 196 | 0.8650 / 0.0000 | "Excluded" | **0.0000 ± 0.0000** (IoU: 0.0000) | 0.8650 fabricated; 0.0000 is genuine catastrophic failure on zero-shot domain transfer. |
| **CVC-ColonDB** | Zero-shot | 380 | 0.8215 | *Pending* | Not in v5 run | 0.8215 fabricated; must be marked as not evaluated in clean v5 suite. |

---

## 6. Proposed Remediation Blueprints

### 6.1 Replacement Blueprint for `paper/main.tex`

The file `paper/main.tex` should be replaced with a clean, defensible LNCS manuscript. Below is the proposed drop-in replacement content:

```latex
\documentclass[runningheads]{llncs}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{amsmath}
\usepackage{multirow}

\begin{document}

\title{ChakraModel: An Edge-Native Hybrid Framework for Clinical Polyp Segmentation with Conformal Risk Bounds}
\author{Anonymous Authors}
\institute{Anonymous Institute}

\maketitle

\begin{abstract}
Early detection and reliable segmentation of precancerous colorectal polyps during colonoscopy is critical for effective clinical intervention. However, clinical translation is hindered by high false-positive rates on mucosal artifacts, severe domain degradation across endoscope centers, and an absence of formal statistical guarantees on prediction uncertainty. We present ChakraModel, an edge-native hybrid framework that decouples real-time polyp tracking (via YOLOv8) from heavy-weight Vision Transformer segmentation (via a ViT-Large ChakraTransformer) applied selectively to bounded Regions of Interest. We integrate distribution-free Split-Conformal Prediction to establish rigorous mathematical pixel-wise coverage guarantees. Evaluated across multi-center benchmark datasets under an adversarial evaluation protocol, ChakraModel achieves a Dice Similarity Coefficient (DSC) of 0.8131 and IoU of 0.7141 on the Kvasir-SEG test split (N=150). Zero-shot transfer evaluation reveals genuine domain generalization bounds: 0.7561 DSC on CVC-ClinicDB (N=495), 0.7402 DSC on CVC-300 (N=60), and catastrophic failure (0.0000 DSC) on ETIS-Larib (N=196). We transparently report architectural profiling showing that while standalone detection operates at 94.7 FPS, the full hybrid pipeline operates at 3.7 FPS, highlighting the remaining engineering gap before edge deployment.
\end{abstract}

\section{Introduction}
Colorectal cancer (CRC) remains one of the primary causes of cancer-related mortality globally. Screening colonoscopy is the clinical standard for identifying precancerous polyps. Despite rapid progress in deep learning architectures for polyp segmentation, significant barriers impede real-world deployment: extreme out-of-distribution performance drops across clinical sites, high inference latency on edge compute devices, and overconfident uncalibrated mask predictions. In this work, we present an empirical evaluation of ChakraModel, focusing on rigorous, verifiable cross-dataset evaluation and conformal risk calibration.

\section{Methodology}
ChakraModel employs a decoupled two-stage architecture:
\begin{enumerate}
    \item \textbf{Stage 1: Real-Time Detection:} A YOLOv8 detector operates continuously on full endoscopic frames (running at 94.7 FPS standalone) to localize suspicious regions and eliminate non-informative lumen background.
    \item \textbf{Stage 2: ROI Transformer Segmentation:} Upon confirmed detection, the cropped Region of Interest is normalized and processed by a ViT-Large backbone (\texttt{vit\_large\_patch16\_384}) with progressive upsampling decoders to extract dense boundaries.
    \item \textbf{Stage 3: Conformal Risk Calibration:} We apply split-conformal calibration with non-conformity thresholding to yield conservative inner and liberal outer masks satisfying a $1-\alpha \ge 0.95$ coverage guarantee.
\end{enumerate}

\section{Experiments and Results}
We evaluate ChakraModel on verified benchmark splits from Kaggle evaluation run v5. Table~\ref{tab:results} reports empirical performance across in-distribution test splits and out-of-distribution zero-shot transfers.

\begin{table}[h]
\centering
\caption{ChakraModel Empirical Performance across Multi-Center Datasets (Kaggle v5 Verified Suite)}
\label{tab:results}
\begin{tabular}{lccccc}
\toprule
Dataset & Evaluation Type & N (Images) & Dice Score & IoU & Precision \\
\midrule
Kvasir-SEG & Held-Out Test & 150 & 0.8131 $\pm$ 0.1747 & 0.7141 & 0.8330 \\
HyperKvasir & Benchmark & 1000 & 0.8360 $\pm$ 0.1610 & 0.7439 & 0.8398 \\
CVC-ClinicDB & Zero-Shot Transfer & 495 & 0.7561 $\pm$ 0.2131 & 0.6470 & 0.7553 \\
EndoScene CVC-300 & Zero-Shot Transfer & 60 & 0.7402 $\pm$ 0.1590 & 0.6098 & 0.6361 \\
PolypDB (All Modalities) & Multi-Center & 7868 & 0.7283 $\pm$ 0.2544 & 0.6243 & 0.6889 \\
ETIS-Larib & Zero-Shot Transfer & 196 & 0.0000 $\pm$ 0.0000 & 0.0000 & 0.0000 \\
\bottomrule
\end{tabular}
\end{table}

As documented in Table~\ref{tab:results}, ChakraModel exhibits robust in-distribution performance (0.8131 DSC on Kvasir-SEG) and acceptable zero-shot transfer to CVC-ClinicDB (0.7561 DSC). However, it suffers complete catastrophic failure on ETIS-Larib (0.0000 DSC), demonstrating severe vulnerability to certain clinical optical distributions. Furthermore, while the YOLOv8 detector runs at 94.7 FPS, the full Stage 1+2 pipeline operates at 3.7 FPS, confirming that further quantization and optimization are mandatory for real-time edge translation.

\section{Conclusion}
We have presented an honest empirical evaluation of ChakraModel. By eliminating inflated metric claims and documenting both zero-shot degradation and latency constraints, this study provides an authentic baseline for safety-critical clinical segmentation research.

\end{document}
```

### 6.2 Remediation Blueprints for `docs/paper/ChakraModel_Final_Paper.md`

The following specific text modifications are required for `docs/paper/ChakraModel_Final_Paper.md`:

1. **Lines 16 & 32 (Abstract & History):**
   - *Target:* `restoring true test performance to **0.7304 DSC** on the Kvasir-SEG test split.`
   - *Replacement:* `restoring verified test performance to **0.8131 DSC** and **0.7141 IoU** on the Kvasir-SEG test split (N=150, Kaggle run v5).`

2. **Lines 35 & 52 (Contributions):**
   - *Target:* `solving the heavy-transformer latency problem on strict 4GB edge hardware budgets.`
   - *Replacement:* `characterizing the latency trade-offs of ROI-based transformer execution, where the full pipeline operates at 3.7 FPS on evaluation hardware.`
   - *Target:* `to achieve real-time latency on edge hardware.`
   - *Replacement:* `to profile edge deployment feasibility and quantify latency bottlenecks.`

3. **Line 117 (Datasets - ETIS-Larib):**
   - *Target:* `- **ETIS-Larib**: Excluded from evaluation due to missing clinical source data (only synthetic fallbacks available).`
   - *Replacement:* `- **ETIS-Larib**: Evaluated zero-shot (N=196 images, Kaggle v5), exhibiting catastrophic domain transfer failure (Dice 0.0000). The historical unverified claim of 0.8650 is formally retracted.`

4. **Lines 150–156 (Table 5.1):**
   - *Target Table:*
   ```markdown
   | Model / Architecture | Kvasir-SEG (DSC) | CVC-ClinicDB (DSC) | CVC-ColonDB (DSC) | CVC-300 (DSC) |
   | :--- | :--- | :--- | :--- | :--- |
   | PraNet (ViT-Large, 2020) Baseline | 0.8990 | 0.8990 | 0.7120 | 0.8710 |
   | PolypMamba (2025) | 0.9350 | 0.9480 | 0.8030 | 0.9160 |
   | **ChakraTransformer (Initial Fabricated Claim)** | *0.9225* | *0.9081* | *0.8215* | *0.7949* |
   | **ChakraTransformer (DDP Bug / Mode Collapse)** | ~0.1835 | ~0.1835 | ~0.1835 | ~0.1835 |
   | **ChakraTransformer (Resolved & Verified)** | **0.7304** | *Pending* | *Pending* | *Pending* |
   ```
   - *Replacement Table:*
   ```markdown
   | Model / Architecture | Kvasir-SEG (DSC) | CVC-ClinicDB (DSC) | CVC-300 (DSC) | ETIS-Larib (DSC) |
   | :--- | :--- | :--- | :--- | :--- |
   | PraNet (2020) Published Baseline | 0.8990 | 0.8990 | 0.8710 | 0.6280 |
   | PolypMamba (2025) Reference | 0.9350 | 0.9480 | 0.9160 | 0.7820 |
   | **ChakraTransformer (Retracted / Fabricated Claim)** | *0.9852 / 0.9225* | *0.9412 / 0.9081* | *0.7949* | *0.8650* |
   | **ChakraTransformer (DDP Weight Bug / Mode Collapse)** | ~0.1835 | ~0.1835 | ~0.1835 | ~0.1835 |
   | **ChakraTransformer (Kaggle v5 Verified Suite)** | **0.8131 ± 0.1747** (N=150) | **0.7561 ± 0.2131** (N=495) | **0.7402 ± 0.1590** (N=60) | **0.0000 ± 0.0000** (N=196) |
   ```

5. **Line 158 (Source citation):**
   - *Target:* `*Source: results/corrected_eval_kvasir_seg.json via verifiable harness on N=50 images (Kvasir-SEG test split).*`
   - *Replacement:* `*Source: kaggle_results/run_v5/cross_dataset_results_v5.json via verified evaluation pipeline (Kaggle run v5).*`

6. **Lines 171, 173, 179, 195, 199:**
   - Replace all assertions of `0.7304 Mean DSC` and `0.6452 Mean IoU` with verified Kaggle v5 metrics (`0.8131 Mean DSC`, `0.7141 Mean IoU` on N=150).
   - In line 179, replace the claim that CVC-ClinicDB evaluation is pending with the verified zero-shot finding (0.7561 DSC, 0.6470 IoU across N=495 images).

---

## 7. Conclusion

This audit provides an unambiguous, line-by-line roadmap for reforming both manuscripts. All fabricated, inflated, and obsolete numbers have been mapped to their exact locations, and concrete replacement blueprints have been established strictly adhering to the single source of truth in `docs/HONEST_METRICS.md`.
