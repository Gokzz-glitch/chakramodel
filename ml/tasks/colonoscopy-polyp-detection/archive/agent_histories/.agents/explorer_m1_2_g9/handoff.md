# Handoff Report: Metric Replacement (R1) for ChakraModel

**Agent:** Explorer 2 (Milestone 1, Generation 9)  
**Date:** 2026-09-09  
**Working Directory:** `m:\chakramodel\.agents\explorer_m1_2_g9`  
**Parent:** `orchestrator_gen9` (`3c29125b-8d51-40b5-ad4e-3a4853f5fd31`)  
**Type:** Hard Handoff (Investigation Complete)  

---

## 1. Observation

### 1.1 Source Documents Inspected
1. **`docs/HONEST_METRICS.md` (Lines 10–32):**
   - Documents the single source of truth backed by Kaggle v5 evaluation (`kaggle_results/run_v5/cross_dataset_results_v5.json`):
     - Kvasir-SEG (test split, N=150): Dice `0.8131493330001831`, Std `0.17465756833553314`, IoU `0.7141045928001404`
     - HyperKvasir Segmented (N=1000): Dice `0.8359748721122742`, Std `0.16095101833343506`, IoU `0.7439042329788208`
     - CVC-ClinicDB (zero-shot, N=495): Dice `0.7560632228851318`, Std `0.21311913430690765`, IoU `0.6469632983207703`
     - EndoScene CVC-300 (zero-shot, N=60): Dice `0.7402245998382568`, Std `0.15904949605464935`, IoU `0.6098460555076599`
     - PolypDB (All Modalities, N=7868): Dice `0.7283103466033936`, Std `0.25443223118782043`, IoU `0.624253511428833`
     - ETIS-Larib (zero-shot, N=196): Dice `0.0000000000000000`, Std `0.0`, IoU `0.0`
   - Explicitly notes: *"Full dataset experienced catastrophic failure, Dice=0.0000. Only 5-image subset available on Kaggle."*
   - Explicitly retracts: ChakraTransformer C6 Kvasir-SEG 0.9852, CVC-ClinicDB 0.9412, ETIS-Larib 0.8650, ChakraNet-Focal C1 0.9158, Topo-ChakraNet C2 0.9210, AdaBN-ChakraNet C3 0.9610.

2. **`kaggle_results/run_v5/cross_dataset_results_v5.json` (Lines 1–52):**
   - Confirms exact floating-point metrics produced by Kaggle run v5, including precision and recall:
     - Kvasir-SEG: precision `0.8329688310623169`, recall `0.8499649167060852`
     - HyperKvasir: precision `0.8398281335830688`, recall `0.8768253922462463`
     - CVC-ClinicDB: precision `0.7552539706230164`, recall `0.8443913459777832`
     - EndoScene CVC-300: precision `0.6360992789268494`, recall `0.9427413940429688`
     - PolypDB: precision `0.6888580918312073`, recall `0.861095666885376`

3. **`paper/main.tex` (Lines 16, 20, 26, 28–42, 44):**
   - **Line 16:** `Our method achieves a Dice score of 0.9225 on the Kvasir-SEG dataset, outperforming state-of-the-art baselines.`
   - **Line 20:** `...to achieve state-of-the-art polyp segmentation.`
   - **Line 26:** `We evaluated our model on five standard benchmark datasets: Kvasir-SEG, CVC-ClinicDB, CVC-ColonDB, CVC-300, and ETIS.`
   - **Lines 28–42:** Table 1 lists Kvasir-SEG (0.9225, mIoU 0.8743), CVC-ClinicDB (0.9081, mIoU 0.8504), CVC-ColonDB (0.8215, mIoU 0.7359), CVC-300 (0.7949, mIoU 0.6796), ETIS (0.0000, mIoU 0.0000) with dummy MAE `0.0000` across all rows.
   - **Line 44:** `As shown in the table, ChakraModel achieves highly competitive scores, particularly on the Kvasir-SEG dataset (Dice: 0.9225).`

4. **`docs/paper/ChakraModel_Final_Paper.md` (Lines 16, 32, 112–118, 150–158, 171–173, 179–180, 195, 199):**
   - **Line 16:** Version history notes v4.0 citing preliminary metric 0.7304 DSC.
   - **Line 32 (Abstract):** Cites `restoring true test performance to **0.7304 DSC** on the Kvasir-SEG test split.`
   - **Lines 112–118 (Section 4.1):** Reports 10% test split on Kvasir-SEG ($N=100$), lists CVC-ColonDB ($N=380$), omits HyperKvasir and PolypDB.
   - **Lines 150–158 (Table 5.1):** Displays `ChakraTransformer (Initial Fabricated Claim)` with `0.9225 | 0.9081 | 0.8215 | 0.7949`, and `ChakraTransformer (Resolved & Verified)` with `0.7304 | Pending | Pending | Pending`.
   - **Lines 171–173 (Section 5.1):** Cites `0.7304 Mean DSC and 0.6452 Mean IoU` and compares to `0.9225`.
   - **Lines 179–180 (Section 5.3):** Cites `0.7304 DSC` and claims OOD datasets are "*Pending*".
   - **Line 195 (Section 6.1):** Cites `0.7304 DSC`.
   - **Line 199 (Section 6.2):** Cites `0.9225 DSC in-distribution, 0.8215 OOD` and `0.7304 DSC`.

5. **`docs/DATA_FLOW_MAP.md` (Lines 15–33, 138–165):**
   - Explains the forensic lineage:
     - `0.9225`, `0.9081`, `0.8215`, `0.7949`, `0.9814` were produced by `src/evaluate_all.py` slicing only the last 10% tail (`image_paths[-n_test:]`) of sorted files.
     - `0.7304` was produced by early local runs with only 50 images evaluated.
     - `0.8131 ± 0.1747` on Kaggle v5 is the **only** verified, methodologically defensible gold standard on a true held-out 15% permutation test split ($N=150$, seed=42).

---

## 2. Logic Chain

1. **Premise 1 (Single Source of Truth):** `docs/HONEST_METRICS.md` and `kaggle_results/run_v5/cross_dataset_results_v5.json` define the sole authoritative ground-truth metrics for ChakraModel.
2. **Premise 2 (Purging Tail-Slicing & Fabrications):** Any metric derived from `evaluate_all.py`'s 10% tail slicing (0.9225, 0.9081, 0.8215, 0.7949) or early preliminary runs (0.7304) or historical unverified runs (0.9852, 0.9412, 0.8650) must be removed from benchmark tables and replaced with Kaggle v5 metrics.
3. **Premise 3 (Mandate Against Prohibited Strings):** The strings "SOTA", "State of the Art", and "State-of-the-Art" must not appear in any academic claims. `paper/main.tex` contains two instances of "state-of-the-art" (lines 16 and 20) that must be removed.
4. **Premise 4 (ETIS-Larib Transparent Disclosure):** In both `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md`, ETIS-Larib cannot claim positive performance or fabricated scores. The verified result is catastrophic failure (Dice 0.0000 on $N=196$), and local disk holds only 5 synthetic canary files. This must be explicitly disclosed with a dedicated footnote/note.
5. **Premise 5 (CVC-ClinicDB True Metric):** Fabricated scores (0.9412, 0.9081) must be replaced by the verified zero-shot cross-center evaluation score of **0.7561 $\pm$ 0.2131** ($N=495$, mIoU 0.6470).
6. **Premise 6 (Insertion of 0.8131):** The verified in-distribution test metric **0.8131** (specifically `0.8131 ± 0.1747`, mIoU `0.7141`, $N=150$) must be inserted into:
   - `paper/main.tex`: Abstract (L16), Table 1 Kvasir-SEG row (L35), and discussion text (L44).
   - `docs/paper/ChakraModel_Final_Paper.md`: Version history v5.0 (L16), Generator Note (L20), Abstract (L32), Section 4.1 (L113), Table 5.1 row, Section 5.1 recovery text (L171, L173), Section 5.3 generalization text (L179), Section 6.1 What Works (L195), and Section 6.2 What Failed (L199).

---

## 3. Caveats

- **No Caveats Regarding Metric Values:** The numerical values in `docs/HONEST_METRICS.md` match `kaggle_results/run_v5/cross_dataset_results_v5.json` exactly to all significant digits.
- **Hardware/Scope Caveat:** The Kaggle v5 evaluation tested the ViT-Large segmentation core (`ChakraTransformerSegmenter`) with prompt bounding boxes. End-to-end YOLO+ViT streaming video latency (3.7 FPS) remains separate from static image segmentation accuracy.
- **Scope Restriction:** As Explorer 2, this agent does not modify source files directly. The implementer agent must apply the provided exact replacements.

---

## 4. Conclusion & Actionable Replacement Specifications

### 4.1 Specification for `paper/main.tex`

#### Abstract & Introduction Block (Lines 15–21):
```latex
\begin{abstract}
Early detection and accurate segmentation of precancerous polyps is crucial for preventing colorectal cancer. Existing methods often struggle with polyps that have indistinct boundaries or small sizes. We propose ChakraModel, an edge-native hybrid deep learning architecture that combines YOLOv8 detection with Vision Transformer refinement. Evaluated under strict test-set isolation, our method achieves a verified Dice score of 0.8131 $\pm$ 0.1747 and mIoU of 0.7141 on the held-out Kvasir-SEG test split ($N=150$). We evaluate ChakraModel across multiple multi-center benchmark cohorts, demonstrating cross-center generalization (0.8360 $\pm$ 0.1610 Dice on HyperKvasir) and zero-shot transfer (0.7561 $\pm$ 0.2131 Dice on CVC-ClinicDB, 0.7402 $\pm$ 0.1590 Dice on EndoScene CVC-300), while transparently disclosing domain-shift failure on ETIS-Larib.
\end{abstract}

\section{Introduction}
Colorectal cancer (CRC) is one of the leading causes of cancer-related mortality globally. Colonoscopy remains the gold standard for early CRC detection, heavily relying on the gastroenterologist's ability to locate and resect precancerous polyps. In this paper, we introduce ChakraModel, which combines a high-speed detector with a Vision Transformer refinement core, to provide robust, verifiable polyp segmentation with strict evaluation integrity.
```

#### Experiments and Results & Table 1 Block (Lines 25–45):
```latex
\section{Experiments and Results}
We evaluated our model across verified benchmark cohorts from the Kaggle v5 cross-dataset evaluation suite: the held-out test split of Kvasir-SEG, cross-center evaluation on HyperKvasir Segmented, zero-shot transfer on CVC-ClinicDB and EndoScene CVC-300, large-scale multi-modal stress testing on PolypDB, and zero-shot transfer on ETIS-Larib.

\begin{table}[h]
\centering
\caption{Verified Benchmark Performance of ChakraModel Across Datasets (Kaggle v5 Suite)}
\label{tab:honest_metrics}
\begin{tabular}{lcccc}
\toprule
Dataset & Split Method & $N$ & Dice (mean $\pm$ std) & mIoU \\
\midrule
Kvasir-SEG & Held-out Test (15\%) & 150 & 0.8131 $\pm$ 0.1747 & 0.7141 \\
HyperKvasir Segmented & Cross-Center & 1,000 & 0.8360 $\pm$ 0.1610 & 0.7439 \\
CVC-ClinicDB & Zero-Shot & 495 & 0.7561 $\pm$ 0.2131 & 0.6470 \\
EndoScene CVC-300 & Zero-Shot & 60 & 0.7402 $\pm$ 0.1590 & 0.6098 \\
PolypDB (All Modalities) & Multi-Modal & 7,868 & 0.7283 $\pm$ 0.2544 & 0.6243 \\
ETIS-Larib\textsuperscript{*} & Zero-Shot & 196 & 0.0000 $\pm$ 0.0000 & 0.0000 \\
\bottomrule
\end{tabular}
\vspace{1ex}
\begin{minipage}{\linewidth}
\footnotesize \textsuperscript{*}Full ETIS-Larib cohort experienced catastrophic out-of-distribution failure (Dice = 0.0000); local repository copies contained only 5 synthetic canary files.
\end{minipage}
\end{table}

As shown in Table~\ref{tab:honest_metrics}, ChakraModel achieves a verified Dice score of 0.8131 $\pm$ 0.1747 and mIoU of 0.7141 on the held-out Kvasir-SEG test split ($N=150$, seed=42). Cross-center generalization is strong on HyperKvasir (Dice: 0.8360 $\pm$ 0.1610, mIoU: 0.7439). Zero-shot transfer to external cohorts yields 0.7561 $\pm$ 0.2131 on CVC-ClinicDB ($N=495$) and 0.7402 $\pm$ 0.1590 on EndoScene CVC-300 ($N=60$), while multi-modal evaluation on PolypDB ($N=7,868$) achieves 0.7283 $\pm$ 0.2544. However, the model suffers catastrophic out-of-distribution failure on ETIS-Larib (Dice: 0.0000 on $N=196$), demonstrating that zero-shot generalizability does not reliably withstand extreme optical and morphological domain shifts without test-time adaptation.
```

---

### 4.2 Specification for `docs/paper/ChakraModel_Final_Paper.md`

1. **Version History & Generator Note (Lines 12–21):**
   Append v5.0 and update generator note:
   ```markdown
   - **v5.0 (2026-09-09 14:00 UTC+5:30):** Metric Replacement (R1). Integrated single source of truth from Kaggle v5 cross-dataset evaluation suite (Kvasir-SEG test split N=150 DSC 0.8131 ± 0.1747, HyperKvasir Segmented DSC 0.8360 ± 0.1610, CVC-ClinicDB zero-shot DSC 0.7561 ± 0.2131, EndoScene CVC-300 zero-shot DSC 0.7402 ± 0.1590, PolypDB DSC 0.7283 ± 0.2544). Purged all fabricated tail-slice metrics (0.9225, 0.9081, 0.8215, 0.7949) and preliminary metrics (0.7304), and formally documented catastrophic failure on ETIS-Larib (0.0000 DSC).

   > **[GENERATOR NOTE — HONEST REVISION v5.0]**  
   > This revision updates the paper with the single source of truth from `docs/HONEST_METRICS.md` and `kaggle_results/run_v5/cross_dataset_results_v5.json`.
   > The verified in-distribution test performance is **0.8131 ± 0.1747 DSC** (mIoU 0.7141) on Kvasir-SEG ($N=150$, seed=42), with zero-shot transfer of **0.7561 ± 0.2131 DSC** on CVC-ClinicDB ($N=495$) and transparent disclosure of catastrophic failure on ETIS-Larib (0.0000 DSC, $N=196$).
   ```

2. **Abstract (Line 32):**
   Replace preliminary `0.7304 DSC` sentence:
   ```markdown
   Evaluated rigorously under a strict cryptographic anti-fabrication harness, the model initially appeared to suffer from **Catastrophic Mode Collapse** (scoring 0.1835 DSC). However, rigorous root cause analysis revealed this was a **DistributedDataParallel (DDP) serialization defect**—the checkpoint keys were prefixed with `module.`, causing the inference script to silently drop all trained weights and run on random initialization. Upon stripping the prefix, the ViT-Large backbone correctly loaded, resolving the mode collapse and restoring true test performance to **0.8131 ± 0.1747 DSC** (mIoU 0.7141) on the strictly held-out Kvasir-SEG test split ($N=150$, seed=42) in the Kaggle v5 cross-validation benchmark suite. Multi-center evaluation confirms cross-center generalization on HyperKvasir Segmented (0.8360 ± 0.1610 DSC, $N=1,000$), zero-shot cross-domain transfer on CVC-ClinicDB (0.7561 ± 0.2131 DSC, $N=495$) and EndoScene CVC-300 (0.7402 ± 0.1590 DSC, $N=60$), and multi-modal scalability on PolypDB (0.7283 ± 0.2544 DSC, $N=7,868$), while catastrophic failure is transparently documented on ETIS-Larib (0.0000 DSC, $N=196$). This paper transparently documents this near-fatal engineering failure and recovery, offering a stark case study on the dangers of silent failures in deep learning deployment and the absolute necessity of strict weight validation.
   ```

3. **Section 4.1 Datasets (Lines 111–119):**
   Update dataset list to match Kaggle v5:
   ```markdown
   ### 4.1 Datasets
   We evaluated the framework across standard multi-center cohorts from the Kaggle v5 evaluation suite to quantify in-distribution accuracy and zero-shot domain transfer:
   - **Kvasir-SEG**: Primary training and evaluation benchmark (1,000 images). Final metrics reported on a strictly held-out 15% permutation test split ($N=150$, `seed=42`).
   - **HyperKvasir Segmented**: Cross-center in-distribution evaluation cohort ($N=1,000$).
   - **CVC-ClinicDB**: Zero-shot cross-center test cohort ($N=495$ evaluated; strictly excluded from all training phases).
   - **EndoScene CVC-300**: Zero-shot morphology generalization cohort ($N=60$).
   - **PolypDB (All Modalities)**: Large-scale multi-modal stress benchmark ($N=7,868$).
   - **ETIS-Larib**: Evaluated zero-shot ($N=196$) where the model experienced catastrophic failure (Dice = 0.0000); local repository copies contained only 5 synthetic canary files.
   - **LDPolypVideo**: Proposed for future work to evaluate artifact robustness and temporal stability in real-time video context. It was not evaluated in this study.
   ```

4. **Section 5.1 Cross-Dataset Performance & Tables (Lines 144–159):**
   Replace Table 5.1 with verified metrics and add audit lineage:
   ```markdown
   ### 5.1 Cross-Dataset Performance & The Anti-Fabrication Audit

   The full integrated pipeline was evaluated across multi-center benchmark cohorts using the Kaggle v5 evaluation suite (`kaggle_results/run_v5/cross_dataset_results_v5.json`) under strict cryptographic validation and fixed random seed (`seed=42`).

   The definitive cross-dataset results are reported below:

   **Table 5.1: Verified Benchmark Performance of ChakraModel Across Datasets (Kaggle v5 Gold Standard)**

   | Dataset | Evaluation Nature / Split | N (Images) | Dice (mean ± std) | mIoU | Precision | Recall |
   | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
   | **Kvasir-SEG** | Held-Out Test Split (15%) | 150 | **0.8131 ± 0.1747** | 0.7141 | 0.8330 | 0.8500 |
   | **HyperKvasir Segmented** | Cross-Center In-Distribution | 1,000 | **0.8360 ± 0.1610** | 0.7439 | 0.8398 | 0.8768 |
   | **CVC-ClinicDB** | Zero-Shot Transfer | 495 | **0.7561 ± 0.2131** | 0.6470 | 0.7553 | 0.8444 |
   | **EndoScene CVC-300** | Zero-Shot Transfer | 60 | **0.7402 ± 0.1590** | 0.6098 | 0.6361 | 0.9427 |
   | **PolypDB (All Modalities)** | Multi-Modal Stress Benchmark | 7,868 | **0.7283 ± 0.2544** | 0.6243 | 0.6889 | 0.8611 |
   | **ETIS-Larib\*** | Zero-Shot (Catastrophic Failure) | 196 | **0.0000 ± 0.0000** | 0.0000 | 0.0000 | 0.0000 |

   *Source: `kaggle_results/run_v5/cross_dataset_results_v5.json` (Kaggle evaluation pipeline run v5).*  
   *\*Note on ETIS-Larib: The full dataset of 196 clinical images experienced catastrophic out-of-distribution failure with Dice = 0.0000. Local repository copies contained only 5 synthetic canary images (`synth_*.png`), which previously produced ungrounded metrics.*

   **Table 5.2: Metric Provenance and Forensic Audit Lineage**

   | Evaluation Phase / Claim | Kvasir-SEG (DSC) | CVC-ClinicDB (DSC) | ETIS-Larib (DSC) | Forensic Status & Lineage |
   | :--- | :--- | :--- | :--- | :--- |
   | **Historical Claims** | 0.9852 | 0.9412 | 0.8650 | **Retracted:** Unverified scripts; lack of clean splits. |
   | **Truncated Tail Slicing (10%)** | 0.9225 (N=100) | 0.9081 (N=49) | 0.9814 (N=1) | **Invalidated:** Sliced last 10% tail (`[-n_test:]`) in `evaluate_all.py`. |
   | **DDP Serialization Defect** | ~0.1835 | ~0.1835 | ~0.1835 | **Explained:** Missing `module.` prefix strip; 0/312 keys loaded. |
   | **Kaggle v5 Gold Standard** | **0.8131 ± 0.1747** | **0.7561 ± 0.2131** | **0.0000** | **Verified Ground Truth:** Held-out test split ($N=150$, seed=42). |
   ```

5. **Section 5.1 Recovery Text (Lines 167–174):**
   Replace `0.7304` with `0.8131 ± 0.1747` and `0.6452` with `0.7141`.

6. **Section 5.3 Generalization Analysis (Lines 178–180):**
   Replace `0.7304` with `0.8131 ± 0.1747` and quantify external cohorts (CVC-ClinicDB 0.7561, CVC-300 0.7402, HyperKvasir 0.8360, PolypDB 0.7283, ETIS-Larib 0.0000).

7. **Section 6.1 What Works (Lines 193–196):**
   Replace `0.7304 DSC` with `0.8131 ± 0.1747 DSC` ($N=150$).

8. **Section 6.2 What Failed (Lines 198–204):**
   Replace `0.7304 DSC` with `0.8131 ± 0.1747 DSC`, enumerate retracted metrics, and explicitly document ETIS-Larib catastrophic failure.

---

## 5. Verification Method

To independently verify this design and confirm compliance after implementation:

1. **Verify Prohibited Strings:**
   Execute PowerShell command to assert zero matches for prohibited marketing tokens:
   ```powershell
   $files = @("paper\main.tex", "docs\paper\ChakraModel_Final_Paper.md")
   foreach ($f in $files) {
       $content = Get-Content $f -Raw
       foreach ($term in @("SOTA", "State of the Art", "State-of-the-Art")) {
           $matches = [regex]::Matches($content, $term, "IgnoreCase")
           Write-Host "$f - $term : $($matches.Count) matches"
           if ($matches.Count -gt 0) { throw "Prohibited string $term found in $f" }
       }
   }
   ```

2. **Verify Retracted / Fabricated Metric Tokens:**
   Assert zero occurrences of fabricated scores as active claims:
   ```powershell
   foreach ($f in @("paper\main.tex", "docs\paper\ChakraModel_Final_Paper.md")) {
       $content = Get-Content $f -Raw
       foreach ($metric in @("0.9852", "0.9412", "0.8650", "0.9225", "0.9081", "0.8215", "0.7949", "0.7304")) {
           # In paper/main.tex, ALL must be 0.
           # In docs/paper/ChakraModel_Final_Paper.md, they may only appear in the explicit retraction table.
           $count = ([regex]::Matches($content, [regex]::Escape($metric))).Count
           Write-Host "$f - $metric : $count"
       }
   }
   ```

3. **Verify Insertion of "0.8131":**
   ```powershell
   foreach ($f in @("paper\main.tex", "docs\paper\ChakraModel_Final_Paper.md")) {
       $count = ([regex]::Matches((Get-Content $f -Raw), "0\.8131")).Count
       Write-Host "$f contains '0.8131' $count times"
   }
   # Expected: paper/main.tex >= 3; ChakraModel_Final_Paper.md >= 8
   ```

4. **Verify Raw Data Alignment:**
   Inspect `kaggle_results/run_v5/cross_dataset_results_v5.json` and ensure all table entries match keys `Kvasir-SEG (test split)`, `HyperKvasir Segmented`, `CVC-ClinicDB (zero-shot)`, `EndoScene CVC-300 (zero-shot)`, `PolypDB (All Modalities)`, and `ETIS-Larib (zero-shot)`.
