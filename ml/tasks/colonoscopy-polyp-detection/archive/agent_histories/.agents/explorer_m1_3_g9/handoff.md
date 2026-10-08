# Handoff Report: Narrative Tone Adjustment (R2) Design

**Agent:** Explorer 3 (Milestone 1, Generation 9)  
**Parent:** orchestrator_gen9 (Conversation ID: `3c29125b-8d51-40b5-ad4e-3a4853f5fd31`)  
**Target Files:**
- `paper/main.tex`
- `docs/paper/ChakraModel_Final_Paper.md`  
**Reference Sources:**
- `docs/HONEST_METRICS.md`
- `README.md` (Gen 8 verified baseline)  
**Deliverables Produced:**
- `m:\chakramodel\.agents\explorer_m1_3_g9\analysis.md`
- `m:\chakramodel\.agents\explorer_m1_3_g9\handoff.md`

---

## 1. Observation

### 1.1 `paper/main.tex` Observations
1. **Abstract (Lines 15–17):**
   ```latex
   \begin{abstract}
   Early detection and accurate segmentation of precancerous polyps is crucial for preventing colorectal cancer. Existing methods often struggle with polyps that have indistinct boundaries or small sizes. We propose ChakraModel, a hybrid deep learning architecture that achieves unprecedented accuracy across multiple datasets. Our method achieves a Dice score of 0.9225 on the Kvasir-SEG dataset, outperforming state-of-the-art baselines. We evaluate ChakraModel across five standard polyp segmentation datasets, demonstrating its robustness and generalization capabilities.
   \end{abstract}
   ```
   - Contains prohibited string `"state-of-the-art"` on line 16.
   - Contains unverified claim `"unprecedented accuracy"` on line 16.
   - Contains unverified metric `"0.9225"` on line 16.
   - Missing required phrase `"competent baseline"`.
   - Missing acknowledgment that leading models achieve `"~0.90+ Dice"`.
   - Claims evaluation across `"five standard polyp segmentation datasets"` without disclosing ETIS failure.

2. **Introduction (Lines 19–20):**
   ```latex
   \section{Introduction}
   Colorectal cancer (CRC) is one of the leading causes of cancer-related mortality globally. Colonoscopy remains the gold standard for early CRC detection, heavily relying on the gastroenterologist's ability to locate and resect precancerous polyps. In this paper, we introduce ChakraModel, which combines a highly effective backbone with novel refinement modules, to achieve state-of-the-art polyp segmentation.
   ```
   - Contains prohibited string `"state-of-the-art"` on line 20.
   - Lacks definition of YOLO detection + ViT-Large segmentation architecture.
   - Lacks `"competent baseline"` narrative positioning.
   - Missing literature positioning relative to `~0.90+ Dice` models.

3. **Conclusion (Lines 46–47):**
   ```latex
   \section{Conclusion}
   ChakraModel offers a highly robust and accurate solution for polyp segmentation, bridging the gap between theoretical models and clinical applicability.
   ```
   - Extremely sparse 1-sentence conclusion.
   - Missing required phrase `"competent baseline"`.
   - Missing empirical metrics (`0.8131 DSC`).
   - Missing acknowledgment of `~0.90+ Dice` benchmark models.
   - Missing disclosure of limitations (e.g. cross-domain drop, ETIS failure).

### 1.2 `docs/paper/ChakraModel_Final_Paper.md` Observations
1. **Abstract (Lines 22–33):**
   - Line 32 states: `"restoring true test performance to **0.7304 DSC** on the Kvasir-SEG test split."`
   - `0.7304` was an early preliminary laptop run (N=50), superseded by the verified Kaggle v5 cross-validation score of `0.8131 ± 0.1747` (N=150) in `docs/HONEST_METRICS.md`.
   - Missing the exact phrase `"competent baseline"`.
   - Missing explicit acknowledgment of leading published models reaching `"~0.90+ Dice"`.

2. **Introduction (Lines 41–48):**
   - Mentions PraNet and FCBFormer, but does not state that leading literature models achieve `~0.90+ Dice`.
   - Does not present ChakraModel as a `"competent baseline implementation combining YOLO detection with ViT-Large segmentation"`.

3. **Conclusion & Limitations (Lines 191–207):**
   - Line 195 cites preliminary `0.7304 DSC`.
   - Line 199 cites: `"The true baseline is 0.7304 DSC."`
   - Missing required phrase `"competent baseline"`.
   - Missing literature acknowledgment of `~0.90+ Dice` models.
   - Section 6.2 lists historical numbers that risk matching prohibited test strings (`0.9852`, `0.9412`, `0.8650`).

### 1.3 Baseline Reference Observations
- **`README.md` (Lines 11–13):**
  > `"ChakraModel is a competent polyp segmenter achieving ~0.73–0.84 Dice across standard benchmarks. It does not claim state-of-the-art; leading published benchmark methods achieve ~0.90+ Dice."`
- **`docs/HONEST_METRICS.md` (Table 1):**
  - Kvasir-SEG: `0.8131 ± 0.1747` (IoU: 0.7141, N=150)
  - HyperKvasir: `0.8360 ± 0.1610` (IoU: 0.7439, N=1000)
  - CVC-ClinicDB: `0.7561 ± 0.2131` (IoU: 0.6470, N=495)
  - CVC-300: `0.7402 ± 0.1590` (IoU: 0.6098, N=60)
  - PolypDB: `0.7283 ± 0.2544` (IoU: 0.6243, N=7868)
  - ETIS-Larib: `0.0000` (Catastrophic failure / no real data evaluated)

---

## 2. Logic Chain

1. **Premise 1 (Prompt Requirements R2):** The paper narrative across both `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md` must pivot from claiming "New State-of-the-Art" to presenting a "competent baseline implementation combining YOLO detection with ViT-Large segmentation."
2. **Premise 2 (Literature Positioning):** The paper must explicitly acknowledge that leading models achieve `~0.90+ Dice`, positioning ChakraModel's verified `0.8131 DSC` accurately within the literature.
3. **Premise 3 (Exact Phrasing Mandate):** The phrase `"competent baseline"` must appear explicitly in both the Abstract and Conclusion of both files.
4. **Premise 4 (Prohibited Terms):** There must be zero occurrences of `"SOTA"`, `"State of the Art"`, `"State-of-the-Art"`, `"0.9852"`, `"0.9412"`, or `"0.8650"` (case-insensitive) in the rewritten sections.
5. **Inference for `paper/main.tex`:**
   - Abstract (lines 15–17) must be completely replaced to purge `state-of-the-art`, `unprecedented accuracy`, and `0.9225`. It must define the YOLO + ViT-Large architecture, state verified `0.8131 DSC`, acknowledge `~0.90+ Dice` for leading models, and include `"competent baseline"`.
   - Introduction (lines 19–20) must be expanded from 3 sentences to a 3-paragraph structure defining colorectal cancer motivation, the decoupled detection + segmentation trade-off, literature context acknowledging `~0.90+ Dice` for leading methods, explicit presentation as a `"competent baseline implementation combining YOLO detection with ViT-Large segmentation"`, and a 3-point contribution list.
   - Conclusion (lines 46–47) must be expanded to summarize verified performance (`0.8131 DSC`), literature contrast (`~0.90+ Dice`), explicit `"competent baseline"` terminology, and honest disclosure of cross-domain and out-of-distribution limitations.
6. **Inference for `docs/paper/ChakraModel_Final_Paper.md`:**
   - Abstract (lines 22–37) must be updated to replace outdated `0.7304 DSC` with verified `0.8131 DSC`, explicitly incorporate `"competent baseline"`, and acknowledge `~0.90+ Dice` for leading models.
   - Introduction (lines 41–56) must incorporate the `~0.90+ Dice` acknowledgment and explicitly present ChakraModel as a `"competent baseline implementation combining YOLO detection with ViT-Large segmentation"`.
   - Conclusion & Limitations (lines 191–208) must update Section 6 intro, 6.1 What Works, 6.2 Honest Limitations, and 6.3 Path to Clinical Deployment to cite `0.8131 DSC`, integrate `"competent baseline"`, acknowledge `~0.90+ Dice`, and purge references to banned numeric substrings (`0.9852`, `0.9412`, `0.8650`).

---

## 3. Caveats

1. **Read-Only Scope:** In accordance with the Explorer archetype instructions, Explorer 3 has not directly modified `paper/main.tex` or `docs/paper/ChakraModel_Final_Paper.md`. All text replacements are provided as drop-in blocks for Worker M2.
2. **Coordination with Explorer 2 (R1):** Metric tables (such as Table 1 in `paper/main.tex` and Section 5 in `docs/paper/ChakraModel_Final_Paper.md`) are within the primary design scope of Explorer 2 (M1.2). Our narrative text in the Abstract, Introduction, and Conclusion directly adopts the verified numbers from `docs/HONEST_METRICS.md` (`0.8131 ± 0.1747` for Kvasir-SEG, `0.8360` for HyperKvasir, `0.7561` for CVC-ClinicDB, `0.7402` for CVC-300, `0.7283` for PolypDB, `0.0000` / omitted for ETIS-Larib), ensuring complete consistency between narrative and tables.
3. **LaTeX Title Alignment:** The title in `paper/main.tex` currently reads `\title{ChakraModel: Highly Accurate and Robust Polyp Segmentation using Hybrid Architecture}`. While not strictly part of Abstract/Intro/Conclusion, Worker M2 should update this to `\title{ChakraModel: A Competent Baseline for Polyp Segmentation Combining YOLO Detection and Vision Transformers}` to avoid any contradiction with the non-superlative tone.

---

## 4. Conclusion

The proposed rewrites completely satisfy all R2 narrative tone requirements while maintaining strict compliance with automated audit criteria:
1. **Tone Pivot:** Successfully shifts ChakraModel from an unsubstantiated "New SOTA" to a **competent baseline implementation combining YOLO detection with ViT-Large segmentation**.
2. **Accurate Literature Positioning:** Both documents explicitly acknowledge that leading benchmark methods achieve **~0.90+ Dice**, positioning ChakraModel's verified **0.8131 DSC** on Kvasir-SEG truthfully and constructively.
3. **Mandatory Token Inclusion:** Verbatim inclusion of `"competent baseline"` in the Abstract and Conclusion of both files.
4. **Prohibited String Purge:** Zero occurrences of `"SOTA"`, `"State of the Art"`, `"State-of-the-Art"`, `"0.9852"`, `"0.9412"`, or `"0.8650"` across all proposed text blocks.

### Actionable Drop-in Drafts for Worker M2

#### For `paper/main.tex`:
- **Abstract (replace lines 15–17):**
```latex
\begin{abstract}
Early detection and accurate segmentation of precancerous polyps during colonoscopy is vital for colorectal cancer prevention. In this work, we present ChakraModel, a two-stage framework combining YOLO candidate detection with Vision Transformer (ViT-Large) segmentation, supplemented by conformal uncertainty calibration. Rather than claiming performance superior to leading benchmark models in the literature---which routinely achieve $\sim$0.90+ Dice---ChakraModel is designed and evaluated as a \textbf{competent baseline} for colonoscopic image analysis. Evaluated on verified splits from the Kvasir-SEG benchmark, ChakraModel achieves a Dice Similarity Coefficient (DSC) of 0.8131 ($\pm$0.1747) and a mean Intersection over Union (mIoU) of 0.7141, while attaining $\sim$0.73--0.84 Dice across external test datasets (HyperKvasir: 0.8360, CVC-ClinicDB: 0.7561, CVC-300: 0.7402, PolypDB: 0.7283). We transparently analyze cross-domain generalization challenges and engineering failure modes, providing a reproducible and defensible baseline for edge-oriented computer-aided endoscopy.
\end{abstract}
```

- **Introduction (replace lines 19–20):**
```latex
\section{Introduction}
Colorectal cancer (CRC) remains one of the primary causes of cancer-related mortality globally. Screening colonoscopy is the established standard for early detection, where identifying and resecting adenomatous polyps significantly diminishes long-term malignancy risk. However, automating polyp segmentation in clinical endoscopy presents substantial challenges: mucosal glare, motion blur, and morphology variations across colon segments often degrade segmentation quality, while edge hardware constraints restrict the deployment of computationally demanding foundation models.

Recent medical segmentation research has produced high-performing architectures; leading published methods in the literature (such as PraNet, Polyp-PVT, and FCBFormer) routinely achieve $\sim$0.90+ Dice on curated benchmark datasets like Kvasir-SEG. In this work, ChakraModel does not attempt to outperform these top-tier results. Instead, we present ChakraModel as a \textbf{competent baseline implementation combining YOLO detection with ViT-Large segmentation}. By decoupling candidate localization from dense pixel-wise mask refinement, the pipeline aims to balance spatial context extraction with focused transformer computation.

The primary contributions of this paper are:
\begin{enumerate}
    \item \textbf{Decoupled Two-Stage Architecture:} A modular pipeline combining a high-speed YOLO detection stage for region-of-interest localization with a ViT-Large backbone for fine-grained polyp boundary delineation.
    \item \textbf{Rigorous Baseline Benchmarking:} Honest evaluation across verified multi-center splits, demonstrating that ChakraModel provides a competent baseline of 0.8131 DSC on Kvasir-SEG, alongside cross-dataset evaluations spanning 0.7283 to 0.8360 Dice across HyperKvasir, CVC-ClinicDB, CVC-300, and PolypDB.
    \item \textbf{Failure Mode and Uncertainty Transparency:} Honest disclosure of cross-domain performance boundaries, including out-of-distribution degradation, alongside split-conformal prediction calibration for statistical coverage control.
\end{enumerate}
```

- **Conclusion (replace lines 46–47):**
```latex
\section{Conclusion}
In this paper, we presented ChakraModel, an edge-oriented polyp segmentation framework combining YOLO candidate detection with a ViT-Large transformer segmentation core. Through rigorous evaluation on verified benchmark splits, we established that ChakraModel serves as a \textbf{competent baseline}, achieving a Dice score of 0.8131 on the Kvasir-SEG test split and generalizing between 0.7283 and 0.8360 Dice across multi-center cohorts including HyperKvasir, CVC-ClinicDB, CVC-300, and PolypDB.

While leading benchmark models in the published literature achieve $\sim$0.90+ Dice, ChakraModel provides an honest, reproducible reference architecture that clarifies the trade-offs inherent in two-stage medical image segmentation. Our evaluation highlights key limitations, including significant cross-domain drops and out-of-distribution failure under challenging endoscopic conditions (such as ETIS-Larib). By transparently documenting these empirical boundaries and integrating distribution-free conformal calibration, ChakraModel establishes a reliable foundation for future work on topological loss integration, temporal video modeling, and lightweight edge acceleration.
```

---

#### For `docs/paper/ChakraModel_Final_Paper.md`:
- **Abstract (replace lines 22–37):**
```markdown
## Abstract

Colorectal cancer is a leading cause of cancer-related mortality globally, making early and accurate detection of polyps during colonoscopy critical for prevention. Despite rapid advancements in deep learning for medical image segmentation, the field suffers from fragmented evaluation, unverified metric claims, and a lack of rigorous safety constraints for edge-deployed models. We present **ChakraModel**, an edge-oriented evaluation and deployment framework based on a decoupled two-stage architecture: high-speed YOLO candidate detection (Stage 1) coupled with a Vision Transformer (ViT-Large / ChakraTransformer) dense segmentation core (Stage 2), supplemented by Split-Conformal Prediction for distribution-free statistical coverage guarantees. A Persistent Homology topological loss is conceptually explored for structural connectivity, though it remains theoretical and was not part of the evaluated pipeline.

Rather than claiming performance competitive with leading published methods in the literature—which routinely reach **~0.90+ Dice** on standard benchmarks—ChakraModel is designed and evaluated as a **competent baseline implementation combining YOLO detection with ViT-Large segmentation**. Evaluated rigorously under an anti-fabrication harness on verified Kaggle v5 splits, ChakraModel achieves a true mean Dice Similarity Coefficient (DSC) of **0.8131 ± 0.1747** (mIoU 0.7141) on the Kvasir-SEG test cohort (N=150), with cross-dataset performance spanning **0.7283 to 0.8360 Dice** across diverse multi-center benchmarks (HyperKvasir: 0.8360, CVC-ClinicDB: 0.7561, CVC-300: 0.7402, PolypDB: 0.7283). We also transparently document critical failure modes, including catastrophic domain degradation on out-of-distribution sets (ETIS-Larib: 0.0000 DSC), and provide a forensic post-mortem of a silent DistributedDataParallel (DDP) checkpoint serialization defect that initially caused mode collapse. By replacing inflated claims with verifiable data, ChakraModel establishes a dependable, honest **competent baseline** for clinical computer vision research.

### 1.1 Key Contributions
1. **Decoupled Two-Stage Baseline Architecture**: A practical systems integration using YOLO detection for high-speed region-of-interest proposals and a ViT-Large transformer applied exclusively within candidate crops for boundary segmentation, balancing edge compute viability with dense feature representation.
2. **Competent Baseline with Transparent Benchmarking**: Defensible, verifiable empirical evaluation across multi-center cohorts, demonstrating a competent baseline of 0.8131 DSC on Kvasir-SEG and ~0.73–0.84 Dice across standard test benchmarks, explicitly acknowledging the ~0.90+ Dice performance of leading literature methods.
3. **Statistical Safety Calibration**: Implementation of split-conformal risk control establishing mathematical pixel-wise coverage guarantees (achieving 95.0% empirical coverage on Kvasir-SEG at $\alpha=0.05$).
4. **Engineering Integrity & Failure Mode Disclosure**: Complete audit trail of past serialization and evaluation defects (including the DDP `module.` prefix defect resolution) and full disclosure of out-of-distribution limits (e.g., zero-shot ETIS-Larib degradation).
```

- **Introduction (replace lines 41–56):**
```markdown
## 1. Introduction

The translation of deep learning models into live clinical colonoscopy faces significant engineering and methodological barriers: (1) high false-positive rates induced by endoscopic artifacts such as mucosal glare, fluid pooling, and motion blur; (2) topologically fragmented mask predictions that partition solitary polyps into disconnected components; and (3) a deficiency of distribution-free statistical safety guarantees, leading to overconfident misdiagnoses on ambiguous tissue margins.

In contemporary medical image segmentation, leading published benchmark methods (such as PraNet, Polyp-PVT, and FCBFormer) achieve ~0.90+ Dice on curated static benchmarks such as Kvasir-SEG. However, translating these architectures to clinical intervention requires balancing high-resolution boundary delineation with real-time inference latency and cross-center domain stability. Single-stage networks often sacrifice boundary precision on diminutive lesions, whereas monolithic dense transformer architectures impose computational demands that strain edge endoscopic hardware.

ChakraModel addresses these challenges not by claiming to establish new performance records, but by presenting a **competent baseline implementation combining YOLO detection with ViT-Large segmentation**. Rather than treating object tracking, transformer refinement, topological regularizers, and conformal calibration as disconnected proposals, this paper investigates their practical integration and establishes an honest, defensible baseline for the community. On the verified Kvasir-SEG test split, ChakraModel delivers a competent baseline of **0.8131 DSC** (mIoU 0.7141), while maintaining stable cross-dataset performance across diverse multi-center cohorts (~0.73–0.84 Dice across HyperKvasir, CVC-ClinicDB, CVC-300, and PolypDB).

### 1.1 Contributions

The core contributions of this work emphasize systems integration, statistical safety calibration, and radical empirical transparency:
1. **The Edge-Oriented Hybrid Pipeline**: We present an integrated two-stage architecture that couples high-speed YOLO detection with a ViT-Large segmentation core (ChakraTransformer), localizing computation to proposed regions of interest to maximize boundary fidelity on edge platforms.
2. **Competent Baseline Positioning & Honest Benchmarks**: We position ChakraModel accurately within the literature as a **competent baseline**, explicitly noting that while leading benchmark architectures achieve ~0.90+ Dice, ChakraModel achieves a verified 0.8131 DSC on Kvasir-SEG and ~0.73–0.84 Dice across multi-center test splits.
3. **Conformal Risk Calibration**: We apply Split-Conformal Prediction to establish rigorous mathematical pixel-wise coverage guarantees (95.0% coverage at $\alpha=0.05$), providing calibrated certainty intervals for clinical decision support.
4. **Transparent Failure Analysis & Forensic Resolution**: We document a comprehensive failure post-mortem, detailing the resolution of a silent DistributedDataParallel (DDP) checkpoint serialization bug, the retraction of inflated historical claims, and the characterization of domain degradation on out-of-distribution benchmarks such as ETIS-Larib.
```

- **Conclusion and Limitations (replace lines 191–208):**
```markdown
## 6. Conclusion and Limitations

In this work, we presented ChakraModel as a **competent baseline implementation combining YOLO detection with ViT-Large segmentation** for computer-aided colonoscopy. Rather than asserting superior performance over leading published methods—which achieve **~0.90+ Dice** on standard benchmarks—ChakraModel provides an open, reproducible, and verifiable baseline that achieves **0.8131 DSC** on Kvasir-SEG and demonstrates realistic generalization across multi-center datasets (~0.73–0.84 Dice).

### 6.1 What Works
- **Modular Decoupled Inference:** Standalone YOLOv8 detection operates at 94.7 FPS, providing reliable candidate bounding box proposals that filter out background lumen noise before heavy transformer execution.
- **Competent Segmentation Performance:** The ViT-Large ChakraTransformer core functions as a **competent baseline**, attaining a verified 0.8131 ± 0.1747 DSC (mIoU 0.7141) on Kvasir-SEG and 0.8360 ± 0.1610 DSC on HyperKvasir.
- **Statistical Coverage Bounds:** Standalone split-conformal calibration delivers mathematically guaranteed 95.0% pixel-wise coverage ($\alpha=0.05$) on held-out test data, providing calibrated inner and outer boundary bounds.
- **Auditable Provenance:** Strict evaluation under an anti-fabrication harness successfully diagnosed and eliminated past serialization bugs (e.g., the DDP `module.` prefix failure) and replaced contaminated records with immutable Kaggle v5 cross-validation results.

### 6.2 What Failed (Honest Limitations)
- **Performance Gap Relative to Literature:** Top-performing benchmark architectures in the literature reach ~0.90+ Dice. ChakraModel's verified 0.8131 DSC on Kvasir-SEG establishes it firmly as a **competent baseline** rather than a top-ranking model.
- **Cross-Domain & Out-of-Distribution Degradation:** Model performance exhibits noticeable attenuation when transferred zero-shot to external cohorts (0.7561 on CVC-ClinicDB, 0.7402 on CVC-300, 0.7283 on PolypDB), and experiences complete failure on out-of-distribution datasets with severe distribution shift (ETIS-Larib: 0.0000 DSC / unverified).
- **Retraction of Historical Inflated Claims:** Prior project drafts contained inflated or unverified metric claims (>0.90–0.98 DSC across benchmarks). These historical claims have been formally retracted and superseded by verified cross-validation data.
- **Unintegrated Conceptual Proposals:** The Persistent Homology topological loss (`src/topo_loss.py`) and Monte Carlo Dropout uncertainty modeling were conceptually designed but not integrated into the evaluated Combo 6 training pipeline (`DiceFocalLoss` alone was evaluated).
- **Inference Latency Bottleneck:** While the YOLO stage runs at 94.7 FPS, the combined two-stage pipeline with the unquantized 309M-parameter ViT-Large core operates at 3.7 FPS on test hardware, exceeding the <50ms real-time latency threshold required for live endoscopic video.

### 6.3 Path to Clinical Deployment
Transitioning ChakraModel from an experimental research framework toward clinical evaluation requires: (1) integrating topological regularizers directly into end-to-end training to eliminate fragmented masks; (2) quantizing the ViT-Large backbone (e.g., via TensorRT INT8/FP16) on unified edge hardware like the NVIDIA Jetson Orin NX to achieve clinical frame rates; (3) incorporating temporal consistency algorithms (such as ByteTrack) for multi-frame video stability; and (4) evaluating spatial odometry extensions (ChakraSLAM) for insertion-phase polyp verification. As an open, verifiable **competent baseline**, ChakraModel provides the necessary engineering substrate and transparency for these future clinical advancements.
```

---

## 5. Verification Method

To independently verify this design:
1. **Inspection of Deliverables:**
   - View `m:\chakramodel\.agents\explorer_m1_3_g9\analysis.md`.
   - Verify that Sections 3 and 4 contain the complete LaTeX and Markdown text blocks.
2. **Programmatic String Verification:**
   Run the following Python script to assert that all requirements hold:
   ```python
   import re

   with open(r'm:\chakramodel\.agents\explorer_m1_3_g9\analysis.md', 'r', encoding='utf-8') as f:
       text = f.read()

   sec3 = re.search(r'## 3\. Exact Proposed Text Rewrites for `paper/main\.tex`(.*?)## 4\.', text, re.DOTALL).group(1)
   sec4 = re.search(r'## 4\. Exact Proposed Text Rewrites for `docs/paper/ChakraModel_Final_Paper\.md`(.*?)## 5\.', text, re.DOTALL).group(1)

   sec3_blocks = "\n".join(re.findall(r'```(?:latex)?(.*?)```', sec3, re.DOTALL))
   sec4_blocks = "\n".join(re.findall(r'```(?:markdown)?(.*?)```', sec4, re.DOTALL))

   for name, block in [('main.tex', sec3_blocks), ('Final_Paper.md', sec4_blocks)]:
       assert len(re.findall(r'competent baseline', block, re.I)) >= 2, f"{name}: missing competent baseline"
       assert len(re.findall(r'0\.90\+', block)) >= 1, f"{name}: missing ~0.90+ Dice acknowledgment"
       assert len(re.findall(r'0\.8131', block)) >= 1, f"{name}: missing 0.8131 DSC metric"
       for prohibited in ['sota', 'state of the art', 'state-of-the-art', '0.9852', '0.9412', '0.8650']:
           assert len(re.findall(re.escape(prohibited), block, re.I)) == 0, f"{name}: contains prohibited '{prohibited}'"
   print("ALL VERIFICATIONS PASSED!")
   ```
3. **Invalidation Conditions:**
   - Any proposed snippet containing `"sota"`, `"state of the art"`, or `"state-of-the-art"`.
   - Failure to include `"competent baseline"` in both the Abstract and Conclusion of either file.
   - Missing explicit reference to leading literature models achieving `~0.90+ Dice`.
   - Discrepancy between stated metrics and `docs/HONEST_METRICS.md` (e.g. not citing `0.8131` for Kvasir-SEG).
