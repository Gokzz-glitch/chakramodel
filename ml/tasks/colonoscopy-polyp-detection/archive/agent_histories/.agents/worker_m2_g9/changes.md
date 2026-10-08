# Changes Made by Worker M2 (Milestone 2, Generation 9)

## Executive Summary
In Milestone 2 (Generation 9), `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md` were thoroughly revised to fulfill Requirements R1 (Metric Replacement) and R2 (Narrative Tone Adjustment) and comply with all strict acceptance criteria.

---

## 1. Requirement R1: Metric Replacement
- **Single Source of Truth Alignment:** All quantitative performance claims across both documents now derive exclusively from `docs/HONEST_METRICS.md` and `kaggle_results/run_v5/cross_dataset_results_v5.json`:
  - **Kvasir-SEG (held-out test split, N=150, seed=42):** Dice = `0.8131 ± 0.1747`, mIoU = `0.7141`, Precision = `0.8330`, Recall = `0.8500`.
  - **HyperKvasir Segmented (cross-center, N=1,000):** Dice = `0.8360 ± 0.1610`, mIoU = `0.7439`, Precision = `0.8398`, Recall = `0.8768`.
  - **CVC-ClinicDB (zero-shot transfer, N=495):** Dice = `0.7561 ± 0.2131`, mIoU = `0.6470`, Precision = `0.7553`, Recall = `0.8444`.
  - **EndoScene CVC-300 (zero-shot transfer, N=60):** Dice = `0.7402 ± 0.1590`, mIoU = `0.6098`, Precision = `0.6361`, Recall = `0.9427`.
  - **PolypDB (All Modalities, N=7,868):** Dice = `0.7283 ± 0.2544`, mIoU = `0.6243`, Precision = `0.6889`, Recall = `0.8611`.
  - **ETIS-Larib (zero-shot transfer, N=196):** Dice = `0.0000 ± 0.0000`, mIoU = `0.0000` (transparently disclosed as catastrophic out-of-distribution failure; noted that local disk contained only 5 synthetic canary files).
- **Purge of Fabricated / Cherry-Picked Metrics:**
  - Removed all instances of tail-slicing metrics: `0.9225`, `0.9081`, `0.8215`, `0.7949`.
  - Removed obsolete/unsupported preliminary metric: `0.7304`.
  - Verified ZERO matches for forbidden tokens: `0.9852`, `0.9412`, `0.8650`.

---

## 2. Requirement R2: Narrative Tone Adjustment
- **Pivot to Competent Baseline:**
  - The narrative across Abstract, Introduction, and Conclusion was systematically rewritten to eliminate claims of "New SOTA", "unprecedented accuracy", or "outperforming baselines".
  - ChakraModel is now explicitly positioned as a **"competent baseline implementation combining YOLO detection with ViT-Large segmentation"**.
  - The phrase `"competent baseline"` appears verbatim in BOTH the Abstract and Conclusion of BOTH `paper/main.tex` and `docs/paper/ChakraModel_Final_Paper.md`.
- **Literature Contextualization:**
  - Both documents explicitly acknowledge that leading published models in the literature (such as PraNet, Polyp-PVT, and FCBFormer) achieve **~0.90+ Dice** on standard benchmarks, providing an accurate, humble, and defensible framing for ChakraModel's 0.8131 DSC.
- **Latency & Edge Feasibility Transparency:**
  - Removed conflicting claims of "solving latency on 4GB edge hardware".
  - Transparently disclosed that while the standalone YOLOv8 detector operates at 94.7 FPS, the full Stage 1+2 hybrid pipeline operates at 3.7 FPS, requiring future quantization and optimization before live clinical deployment.

---

## 3. Specific File Modifications

### 3.1 `paper/main.tex`
- Replaced inflated title with neutral, accurate title: `\title{ChakraModel: A Competent Baseline for Polyp Segmentation Combining YOLO Detection and Vision Transformers}`.
- Rewrote Abstract:
  - Included verbatim phrase `"competent baseline"`.
  - Acknowledged leading models achieve `$\sim$0.90+ Dice`.
  - Included verified 0.8131 DSC ($N=150$) on Kvasir-SEG and external cohort metrics (0.7283 to 0.8360).
  - Disclosed ETIS-Larib catastrophic zero-shot failure (0.0000 DSC) and 3.7 FPS pipeline latency.
- Rewrote Introduction:
  - Positioned as a "competent baseline implementation combining YOLO detection with ViT-Large segmentation".
  - Acknowledged leading literature models reaching $\sim$0.90+ Dice.
  - Enumerated 3 core contributions emphasizing systems integration, baseline benchmarking, and failure mode transparency.
- Corrected Methodology:
  - Replaced obsolete PraNet/ResNet-50 reverse attention description with actual two-stage decoupled architecture (YOLOv8 Stage 1 + ViT-Large Stage 2 + Conformal Prediction Stage 3).
- Updated Results & Table 1:
  - Table 1 replaced with verified 6-row Kaggle v5 benchmark suite.
  - Added footnote on ETIS-Larib explaining catastrophic failure on zero-shot domain transfer and 5 synthetic canary files on local disk.
- Rewrote Conclusion:
  - Included verbatim phrase `"competent baseline"` twice.
  - Acknowledged leading models achieving $\sim$0.90+ Dice.
  - Summarized verified metrics and outlined required future optimizations (quantization on Jetson Orin NX, temporal modeling).

### 3.2 `docs/paper/ChakraModel_Final_Paper.md`
- Added Version History entry v5.0 documenting R1 and R2 revisions.
- Updated Generator Note with verified Kaggle v5 in-distribution and zero-shot transfer metrics.
- Rewrote Abstract:
  - Included verbatim phrase `"competent baseline"` twice.
  - Acknowledged leading literature models reaching **~0.90+ Dice**.
  - Integrated verified 0.8131 DSC on Kvasir-SEG test split ($N=150$) and external benchmarks (0.7283 to 0.8360 Dice).
  - Formally documented catastrophic failure on ETIS-Larib (0.0000 DSC).
- Updated Key Contributions (§1.1) and Introduction (§1):
  - Presented ChakraModel as a **competent baseline implementation combining YOLO detection with ViT-Large segmentation**.
  - Acknowledged literature performance of ~0.90+ Dice.
  - Harmonized latency trade-offs (94.7 FPS standalone vs 3.7 FPS integrated).
- Updated Section 4.1 Datasets:
  - Listed full Kaggle v5 benchmark suite with exact sample counts and split types.
- Updated Section 5 Results and Discussion:
  - Replaced Table 5.1 with verified Kaggle v5 suite.
  - Added Table 5.2 literature comparison table showcasing ~0.90+ Dice reference baselines alongside ChakraModel's competent baseline.
  - Replaced preliminary 0.7304 DSC in recovery and generalization text with verified 0.8131 DSC ($N=150$) and genuine external cohort numbers.
- Rewrote Section 6 Conclusion and Limitations:
  - Section intro explicitly states model is a **competent baseline implementation combining YOLO detection with ViT-Large segmentation** and notes literature ~0.90+ Dice.
  - Subsection 6.1 highlights competent segmentation performance (0.8131 DSC).
  - Subsection 6.2 transparently lists limitations, performance gap relative to literature (~0.90+ Dice), catastrophic failure on ETIS-Larib (0.0000 DSC), latency bottleneck (3.7 FPS), and formally retracts historical inflated claims.
  - Subsection 6.3 concludes with path to clinical deployment as an open, verifiable **competent baseline**.

---

## 4. Verification Results
Run using `m:\chakramodel\.agents\worker_m2_g9\verify_requirements.py`:
- Programmatic scan for forbidden strings (`SOTA`, `State of the Art`, `State-of-the-Art`, `0.9852`, `0.9412`, `0.8650`): **0 matches in both files**.
- Programmatic scan for obsolete/fabricated metrics (`0.9225`, `0.9081`, `0.8215`, `0.7949`, `0.7304`): **0 matches in both files**.
- Programmatic scan for string `"0.8131"`: **Confirmed present in both files (5 times in main.tex, 14 times in Final_Paper.md)**.
- Programmatic scan for verbatim `"competent baseline"`: **Confirmed present in Abstract and Conclusion of both files (6 times in main.tex, 16 times in Final_Paper.md)**.
- Acknowledgment of `~0.90+ Dice` literature benchmark: **Confirmed present in both files**.
- LaTeX syntax validity (matched environments stack LIFO validation): **Passed**.
