# Handoff Report: Benchmark Provenance & Evaluation Challenger

**Agent**: Challenger 2 (`challenger_m4_2`)  
**Parent**: Orchestrator (`083d5f88-24f5-461d-b60f-f38de2452366`)  
**Milestone**: Milestone 4 (Adversarial Stress-Testing & Verification)  
**Assigned Directory**: `m:\chakramodel\.agents\challenger_m4_2`  
**Handoff Type**: Hard (Task Complete)  

---

## 1. Observation

Direct code and artifact observations collected during audit:

1. **10% Test Tail Slicing Logic (`src/evaluate_all.py:L65-67`)**:
   ```python
   # Fix Data Leakage: Use the last 10% of the sorted dataset as the test set for ALL datasets
   n_test = max(1, int(0.1 * len(image_paths)))
   image_paths = image_paths[-n_test:]
   ```
   Direct execution and JSON inspection of `results/final_5_datasets_eval.json`:
   - `kvasir-seg`: `images: 100`, `dice: 0.9224972964335134`
   - `cvc-clinicdb`: `images: 49`, `dice: 0.9081372472704673`
   - `cvc-colondb`: `images: 38`, `dice: 0.821488305232858`
   - `cvc-300`: `images: 6`, `dice: 0.7949394484361013`
   - `etis-larib`: `images: 1`, `dice: 0.9814344048500061`
   In `ChakraModel_Final_Paper.md:L144-150` (Table 5.1), these exact truncated numbers (0.9225, 0.9081, 0.8215, 0.7949) are presented as cross-dataset results, while ETIS-Larib was excluded.

2. **Full-Cohort Catastrophic OOD Collapse (`outputs/eval/*.json`, `cross_dataset_report.md`)**:
   - `outputs/eval/cvc-colondb_benchmark.json:L2,L31`:
     `"dice": 0.00647774372787376`, `"n_images": 380`, `"iou": 0.005585863585812425`. Median Dice is 0.0000; 377 of 380 images (99.2%) scored 0.0000.
   - `outputs/eval/cvc-300_benchmark.json:L2,L31`:
     `"dice": 0.004797040854497645`, `"n_images": 60`, `"iou": 0.002821788734260021`. 59 of 60 images (98.3%) scored 0.0000.
   - `outputs/eval/etis_benchmark.json:L2,L31`:
     `"dice": 6.500260052444418e-11` ($\approx 0.0000$), `"n_images": 5`, `"iou": 6.500260052444418e-11`.
   - `cross_dataset_report.md:L14`:
     `| **ETIS-Larib (zero-shot)** | 196 | **0.0000** | 0.0000 | 0.0000 | 0.0000 | *Total Generalization Failure* |`

3. **Latency Profiles (`outputs/eval/fps_latency_report.json`, `ablation_results.md`, `ChakraModel_Final_Paper.md`)**:
   - `outputs/eval/fps_latency_report.json:L9,L19`:
     Stage 1 (YOLOv8 Only): `"fps": 94.6663383006018`, `"mean_ms": 10.563416922545562`.
     Stage 1+2 (YOLOv8 + PraNet Cascade): `"fps": 48.81754884236187`, `"mean_ms": 20.484436923064866`.
   - `ablation_results.md:L9`:
     `| Proposed (ChakraModel - Padded Crop) | 0.4555 | 0.3054 | 0.6178 | 0.8935 | 0.4592 | 3.7 FPS |`
   - `ChakraModel_Final_Paper.md:L72-73`:
     > *"This standalone YOLOv8 stage (excluding ByteTrack) runs at **94.7 FPS** on the evaluation hardware... The integrated Stage 1+2 pipeline runs at **3.7 FPS** on the same hardware. We explicitly note that 3.7 FPS severely violates the <50ms latency bound required for real-time processing."*

4. **Statistical Significance Invalidation (`statistical_significance.py:L14-23`)**:
   - `statistical_significance.py:L16-20`:
     ```python
     # The __main__ block below uses `RealModel`, which is a 2-layer stub CNN with
     # RANDOM weights. It does NOT load actual ChakraNet or YOLO model weights.
     # Any p-values, confidence intervals, or "statistical significance" results
     # produced by running this script directly are MEANINGLESS and do NOT represent
     # comparisons between the actual trained models.
     ```
   - Historical commit log `OM_rama_krish_all_data.json:L23054-23163`:
     Confirms that `RealModel` was defined as `nn.Sequential(nn.Conv2d(3, 16, 3, padding=1), nn.ReLU(), nn.Conv2d(16, 1, 3, padding=1), nn.Sigmoid())` and applied a synthetic constant offset `out = out * 0.95 + 0.05` to fake C6 conformal improvements.

5. **Discrepancies Discovered via Automated Harness (`tests/test_benchmark_provenance_empirical.py`)**:
   - `true_docs/verified_benchmarks_and_metrics.md:L138`: Lists Kvasir-SEG mIoU as `0.8478 ± 0.1697`. Raw JSON `outputs/eval/kvasir-seg_benchmark.json:L5` records `"iou_std": 0.14947879931708852` (0.1495).
   - `true_docs/verified_benchmarks_and_metrics.md:L138`: Lists Kvasir-SEG wF-measure as `0.9240`. Raw JSON records `"w_fmeasure": 0.9094923744001813` and `"f_beta_half": 0.9240395761452753`. The markdown table in `outputs/eval/kvasir-seg_benchmark.md` mistakenly labeled $F_{\beta=0.5}$ as `Weighted F-measure (β=0.5)↑: 0.9240`.
   - `ChakraModel_Final_Paper.md:L159`: An uncorrected cut-and-paste contradiction claims:
     `yielding near-zero scores on CVC-ColonDB (**0.8215 DSC**) and CVC-300 (**0.7949 DSC**)`.

---

## 2. Logic Chain

1. **Step 1 (Evaluation Truncation Proof)**:
   Observation 1 establishes that `src/evaluate_all.py` specifically sliced datasets using `[-n_test:]` where `n_test = max(1, int(0.1 * len(image_paths)))`. For CVC-ColonDB (380 total), this produced 38 images. For CVC-300 (60 total), this produced 6 images. For ETIS-Larib (5 total), this produced 1 image. The resulting scores in `results/final_5_datasets_eval.json` (0.9225, 0.9081, 0.8215, 0.7949, 0.9814) were copied into Table 5.1 of `ChakraModel_Final_Paper.md`, establishing conclusively that the reported Table 5.1 generalization performance was an artifact of testing on a cherry-picked 10% tail.

2. **Step 2 (Out-of-Distribution Collapse Proof)**:
   Observation 2 demonstrates that when evaluated on the full uncurated cohorts, CVC-ColonDB collapses to 0.0065 DSC, CVC-300 collapses to 0.0048 DSC, and ETIS-Larib collapses to 0.0000 DSC across both local ($N=5$) and Kaggle ($N=196$) test sets. Observation 2 shows that >98% of all images scored 0.0000. In conjunction with the two-stage hybrid architecture (YOLOv8 bounding-box cropping followed by ViT segmentation), the failure of the front-end YOLOv8 detector to produce boxes on out-of-domain images triggers an empty ROI prediction, explaining the catastrophic zero-score collapse.

3. **Step 3 (Latency Conflation Proof)**:
   Observation 3 verifies that 94.7 FPS (10.56 ms) was measured for isolated YOLOv8n bounding-box inference across 195 frames without segmentation. When paired with the lightweight PraNet CNN, frame rate dropped to 48.8 FPS (20.48 ms). When paired with the 309M parameter ViT-Large model on cropped ROIs, throughput plummeted to 3.7 FPS (~270 ms latency). This demonstrates that paper claims of "real-time edge capability" apply exclusively to single-stage detection, while the full segmentation pipeline is unusable in real-time.

4. **Step 4 (Statistical Significance Invalidation Proof)**:
   Observation 4 confirms that `statistical_significance.py` contained a dummy model (`RealModel`) with randomly initialized weights rather than loading real model weights. Therefore, any p-values, confidence intervals, or statistical claims cited in early drafts were mathematically meaningless.

5. **Step 5 (Documentation Assessment)**:
   `true_docs/verified_benchmarks_and_metrics.md` explicitly documents all four of these core phenomena. Observations 1–4 match the claims in `true_docs/` with extreme fidelity. The automated empirical test suite `tests/test_benchmark_provenance_empirical.py` passed 5 out of 5 tests. Observation 5 notes two minor transcription discrepancies in the documentation and one manuscript contradiction in `ChakraModel_Final_Paper.md`, but these do not invalidate the documentation suite's truthfulness.

---

## 3. Caveats

1. **Hardware Specificity**: The 3.7 FPS measurement for the integrated hybrid pipeline was evaluated on host hardware (NVIDIA GeForce RTX 3050 Laptop GPU, 4GB VRAM). Deploying to an NVIDIA Jetson Orin NX (16GB unified memory) or running TensorRT INT8 quantization may yield higher frame rates, though ViT-Large (309M parameters) will still struggle to exceed 20 FPS without model distillation.
2. **Kaggle vs. Local ETIS Split**: Local ETIS-Larib cohort in `data/etis-larib` contains 5 images (scoring 0.0000 DSC in `outputs/eval/etis_benchmark.json`), whereas Kaggle evaluation in `cross_dataset_report.md` evaluated the full 196-image cohort. Both cohorts empirically confirm 0.0000 DSC (100% collapse).
3. **No Retraining Conducted**: This audit is strictly review-only. No models were retrained, and no code implementation logic was altered.

---

## 4. Conclusion

**Final Assessment**: **DOCUMENTATION STATUS: PASSED EMPIRICAL CHALLENGE (WITH DOCUMENTED OBSERVATIONS)**.
- The documentation in `true_docs/` (`verified_benchmarks_and_metrics.md`, `index.md`, `theoretical_claims_vs_code.md`, `architecture_evolution.md`) is **empirically validated and truthful**.
- It correctly identifies and exposes:
  1. The 10% test tail truncation artifact (ColonDB N=38, CVC-300 N=6, ETIS-Larib N=1) in Table 5.1.
  2. The catastrophic domain shift collapse on full cohorts (0.0065 ColonDB, 0.0048 CVC-300, 0.0000 ETIS-Larib).
  3. The latency conflation between 94.7 FPS (standalone YOLOv8n) and 3.7 FPS (integrated YOLOv8 + ViT-Large).
  4. The complete invalidation of early statistical significance claims due to `RealModel`.
- Minor corrections recommended for `true_docs/verified_benchmarks_and_metrics.md:L138`: correct Kvasir mIoU standard deviation from `0.1697` to `0.1495`, and clarify that `0.9240` represents $F_{\beta=0.5}$ rather than true $wF$ (0.9095).

---

## 5. Verification Method

To independently verify all findings and reproduce the empirical results, execute:

```powershell
# 1. Run the empirical benchmark provenance test suite
python -m pytest tests/test_benchmark_provenance_empirical.py -v

# 2. Run the statistical significance unit test
python -m pytest tests/test_statistical_significance.py -v

# 3. Verify the 10% test tail slicing logic in source code
python -c "code = open('src/evaluate_all.py').read(); assert 'n_test = max(1, int(0.1 * len(image_paths)))' in code; print('Verified slicing logic!')"

# 4. Inspect raw evaluation JSON files
python -c "import json; print('ColonDB:', json.load(open('outputs/eval/cvc-colondb_benchmark.json'))['dice']); print('CVC-300:', json.load(open('outputs/eval/cvc-300_benchmark.json'))['dice']); print('ETIS:', json.load(open('outputs/eval/etis_benchmark.json'))['dice'])"
```

**Invalidation Conditions**:
- If `src/evaluate_all.py` is shown to evaluate the full cohort rather than slicing `[-n_test:]`, Claim 1 is invalidated.
- If full cohort evaluation on `outputs/eval/cvc-colondb_benchmark.json` does not yield 0.0065 DSC, Claim 2 is invalidated.
- If `fps_latency_report.json` does not report ~94.7 FPS for Stage 1 or `ablation_results.md` does not report 3.7 FPS for the hybrid pipeline, Claim 3 is invalidated.
- If `statistical_significance.py:L14-23` loads real weights instead of warning against `RealModel`, Claim 4 is invalidated.
