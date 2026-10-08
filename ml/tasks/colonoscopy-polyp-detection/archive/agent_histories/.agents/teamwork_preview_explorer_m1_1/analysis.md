# Forensic Historical Investigation & Complete Project Timeline of ChakraModel

**Specialist:** Explorer 1 — History & Timeline Specialist  
**Working Directory:** `m:\chakramodel\.agents\teamwork_preview_explorer_m1_1`  
**Investigation Date:** September 7, 2026  
**Status:** Exhaustive Analysis Complete  

---

## 1. Executive Summary

**Core Finding:**  
The ChakraModel project originated on **July 27, 2026** as a fast-paced prototype for the **Tata Centre 36-Hour Hackathon**, conceived to solve temporal video flickering in colonoscopy polyp detection. Over seven weeks, it underwent dramatic transformations: expanding into six fragmented deep learning paradigms (Combos 1–6), enduring a brutal 10-round adversarial GAN audit that uncovered severe engineering pitfalls (cross-dataset collapse, MC Dropout freeze, hallucinated hardware specs), adopting strict anti-fabrication tripwires (`00_ANTI_FABRICATION_PROTOCOL.md`), reframing its academic novelty around systems integration and failure reporting, and ultimately consolidating into a unified **Edge-Native Hybrid Framework (YOLOv8 + ChakraTransformer)**.

---

## 2. Key Participants, Organizations, and Personas

| Participant / Entity | Identifier / Handle / Affiliation | Primary Role & Contribution |
| :--- | :--- | :--- |
| **Gokul** | `Gokzz-glitch`, `gokulrocky` (Kaggle), `310624148027@eec.srmrmp.edu.in` | Lead Full Stack AI Engineer, primary code author, architect of training/eval pipelines and Kaggle notebooks. |
| **Jayasree** | Co-author (`ac883c9d`) | Team member, co-author for paper drafting and clinical validation. |
| **Girupa** | Co-author (`ac883c9d`) | Team member, co-author for paper drafting, slides, and hackathon presentation. |
| **Varsha** | Co-author (`ac883c9d`) | Team member, co-author for paper drafting and documentation. |
| **Tata Centre for Technology and Design** | Institution / Hackathon Organizer | Provided initial hackathon framing (July 28 – August 1, 2026) and institutional affiliation. |
| **ICMR / Patent Mitra** | Hackathon Partner (`PharmInnoQuest 2026`) | IP / patent facilitation partner for Topological Polyp Loss, Conformal Calibration, and Temporal Persistence. |
| **"The Brain Translator"** | Senior Staff Engineer Persona (`25cc0853`) | High-level architectural advisor, code reviewer, and design critic. |
| **Dr. Yamamoto** | CVPR Area Chair Persona (`04ba7367`) | Adversarial discriminator focusing on loss function design, conformal prediction validity, and persistent homology mathematics. |
| **Dr. Kovacs** | IEEE TMI Associate Editor Persona (`41097d2f`) | Adversarial discriminator auditing experimental rigor, data leakage, and out-of-distribution evaluation. |
| **"Om", "Krishna", "Rama"** | Notebook/chat tags (`KRISHNA_OM_$.ipynb`, `OM_rama_krish_convo.md`) | Core collaborative session identities and notebook naming conventions used during team development. |

---

## 3. The Seven Evolutionary Phases

### Phase 1: Genesis & The Tata Centre 36-Hour Hackathon (July 27 – August 1, 2026)
- **Commits:** `2f528801` (July 27, 19:31) → `a0e6f187` (July 29, 00:05)
- **Context:** Prepared for the Tata Centre for Technology and Design 36-Hour Hackathon (`REPORT.txt`, deadline August 1, 2026).
- **Core Motivation:** The literature was bifurcated between high-accuracy frame-wise detectors that flicker in video, and heavy 3D architectures lacking public weights. Real clinical colonoscopy produces severe video artifacts (water washout, specular glare, fecal remnants, motion blur).
- **Architecture Built:**
  1. Single-stage detector: YOLOv8 / YOLO11 fine-tuned on Kvasir-SEG.
  2. Temporal tracking: BoT-SORT / ByteTrack via Ultralytics.
  3. Preprocessing: CLAHE artifact mitigation.
  4. Temporal Persistence Filter: N-frame sliding window to suppress flickering false positives.
  5. User Interface: Gradio dashboard (`app.py`).

### Phase 2: Stage 1 & 2 Cascade AI Architecture (August 3 – August 7, 2026)
- **Commits:** `0e8b5b87` (Aug 3, 09:05) → `abc9a4e2` (Aug 7, 14:12)
- **Core Shift:** Transitioned from pure bounding-box detection to a two-stage clinical cascade:
  - **Stage 1:** YOLOv8 bounding-box detection and ByteTrack tracking.
  - **Stage 2:** PraNet (Parallel Reverse Attention Network with ResNet-101 backbone) for sub-pixel polyp boundary segmentation (`src/pranet_segmenter.py`, `weights/pranet_kvasir_best.pth`).
  - **Clinical Telemetry:** Integrated Paris Classification (polyp morphology) and automated endoscopist telemetry report generation (`src/clinical_report.py`).
  - **Benchmark:** Achieved reported 0.9085 DSC on Kvasir-SEG test cohort.

### Phase 3: Edge Optimization & Hardware Feasibility (August 14 – August 21, 2026)
- **Key Records:** `OM_rama_krish_convo.md` (`da5fa049`, `1d4dee5a`), `start_date.txt` (`2026-08-21`).
- **Context:** 
  - August 14: Interview explanation preparation with e-consystems.com on real-time colonoscopy edge deployment.
  - August 21: Forensic investigation into edge compute hardware: evaluated NVIDIA Jetson Nano @ 50 FPS vs. Jetson Orin NX (16GB unified memory) vs. host RTX 3050 Laptop GPU (4GB VRAM). Marked as project start date for edge-native transformer exploration (`start_date.txt`).

### Phase 4: The Six-Combo Paradigm Exploration & Literature Surge (August 29 – August 31, 2026)
- **Commits:** `9450fb98` (Aug 30, 15:31) → `3ba62e8d` (Aug 31, 15:15)
- **The Six Combos Suite:** Fragmented exploration of six orthogonal deep learning paradigms in standalone Kaggle notebooks:
  1. *Combo 1:* YOLOv8x + PraNet (ResNet-101) + DiceFocalLoss.
  2. *Combo 2:* Topo-ChakraNet (Topological Loss / Betti Number Regularization via Persistent Homology).
  3. *Combo 3:* AdaBN-ChakraNet (Test-Time Adaptive Batch Normalization).
  4. *Combo 4:* DiffusionAug-ChakraNet (ControlNet SD1.5 synthetic polyp generation + MC Dropout quality filter).
  5. *Combo 5:* Fed-ChakraNet (Federated Learning via FedAvg with non-IID partitioner).
  6. *Combo 6:* ChakraTransformer (ViT-Large `vit_large_patch16_384` + Conformal Calibration).
- **Engineering & Automation:**
  - Automated CI pipeline established (`.github/workflows/test.yml`, `ci-pipeline-progress.md`).
  - Continuous improvement autonomous loop (`.bmad-loop/bmad_loop_hook.py`).
  - Repository restructured: clean separation of `src/`, `scripts/`, `docs/`, `data/`, `weights/`.
  - Massive literature extraction: 323 automated subagents extracted PMC research texts, compiling a comprehensive database of 60+ SOTA papers.

### Phase 5: Hackathon Expansion & Architectural Spine Unification (September 1 – September 2, 2026)
- **Key Records:** `OM_rama_krish_convo.md` (`2e0112fc`, `361c09a2`, `ac883c9d`), `ARCHITECTURE-SPINE.md`.
- **Hackathons:** PharmInnoQuest 2026 (Pan-India Healthcare Hackathon, ICMR Patent Mitra IP track) and Data Genesis 2026 (`data-genesis-2k26.vercel.app`).
- **Strategic Pivot:** Adversarial peer-review simulation revealed that presenting six disjointed combos read like an arbitrary, disconnected hyperparameter search that no clinician could run simultaneously.
- **The Solution:** Authored `ARCHITECTURE-SPINE.md`, formally deprecating the standalone combos and consolidating the best components into a single **Edge-Native Hybrid Framework**:
  - Stage 1: Fast YOLOv8 detection & tracking (94.7 FPS).
  - Stage 2: Heavy ChakraTransformer (ViT-Large) applied strictly inside the bounded ROI.
  - Safety Layer: Conformal Prediction (Split-Conformal, 95% coverage).
  - Authors formalized: Gokul, Jayasree, Girupa, Varsha.

### Phase 6: The 10-Round Adversarial GAN Audit & Roadblock Reality Check (September 3 – September 4, 2026)
- **Key Records:** `OM_rama_krish_convo.md` (Sep 3–4), `reviewer_objections.md`, `ChakraModel_Project_Journey.md`, `00_ANTI_FABRICATION_PROTOCOL.md`, commit `6f9c20cd`.
- **Methodology:** A continuous 10-round GAN loop pitting Generators (G1–G3) against Discriminators (Dr. Kovacs IEEE TMI, Dr. Yamamoto CVPR, Clinical reviewer).
- **Major Pitfalls Exposed:**
  1. *Catastrophic Cross-Dataset Drop:* Initial zero-shot evaluation on CVC-ColonDB dropped to 0.006 DSC, CVC-300 to 0.005 DSC, and ETIS-Larib to 0.000 DSC.
  2. *Crop-and-Forward Context Loss:* Naive hard-cropping by YOLO destroyed spatial context (colon walls), causing DSC to plunge from 0.9085 down to 0.4555 DSC. Remedied using context-padded cropping / letterbox padding.
  3. *MC Dropout Variance Collapse:* MC Dropout attention layers remained frozen during evaluation mode, collapsing measured variance to zero ($\sigma^2 = 2.85 \times 10^{-15}$). Retracted "uncertainty-aware" claims, falling back to deterministic split-conformal calibration with verified 95.0% empirical coverage.
  4. *Hallucinated Metrics & Fabricated Outputs:* Audits discovered agents fabricating VRAM specs (claiming 8GB instead of actual 4GB RTX 3050), batch sizes, and p-values. In response, Gokul instituted `00_ANTI_FABRICATION_PROTOCOL.md` (canary tripwires, session nonces, MD5 hash verification).
  5. *Strategic Reframe (Commit `6f9c20cd`):* Reframed paper novelty away from questionable mathematical claims (e.g. conformal calibration novelty) toward systems integration, edge-native deployment, and honest reporting of failure modes ("Honest Revision v2.0").

### Phase 7: Publication Roadmap Execution, Packaging & True Documentation (September 5 – September 7, 2026)
- **Commits:** `55c859b7` (Sep 5, 17:52), `d5807305` (Sep 5, 17:55), `52d97853` (Sep 7, 10:27), `b67bcb1a` (Sep 7, 10:29), `2cac63f7` (Sep 7, 10:31).
- **Milestones:**
  - Executed 5-step publication roadmap: SAM-style prompt embeddings, TopoLoss ablation scripts, MC Dropout fix, heavy Albumentations, and edge latency benchmarks.
  - Built Kaggle-ready video evaluation notebook and packaging script (`ChakraModel_Video_Evaluation_Kaggle.ipynb`, `create_kaggle_zip.py`).
  - Added Mermaid architecture diagrams to `ARCHITECTURE-SPINE.md` and committed all verification assets.
  - Launched the True Documentation multi-agent project (`m:\chakramodel\true_docs/`) to permanently eliminate hallucinated claims and establish code-verified ground truth.

---

## 4. Master Chronological Timeline Matrix

| Date / Timestamp | Project Phase | Key Events & Commit Hashes | Key Participants & Discussions | What Succeeded | What Failed / Blocked / Changed |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **2026-07-27 19:31** | Phase 1: Genesis | Commit `2f528801`: Initial scaffold: ChakraModel baseline + temporal metrics | Gokul (`Gokzz-glitch`, EEC SRM RMP) | Initial codebase, temporal persistence metrics (TCS/ARS). | Baseline frame-wise YOLO still suffers video flicker. |
| **2026-07-27 19:48 – 20:06** | Phase 1: Genesis | Commits `9842e360`, `cdfb78f9`, `e23e679a`, `110c9f1d` | Gokul | Performance profiles for Local, Colab, and Docker; hybrid inference launcher. | Gitignore updated to clean up pycache artifacts. |
| **2026-07-28 22:33 – 23:31** | Phase 1: Genesis | Commits `1fb12e8c`, `2080d3df`: UI, temporal persistence, mask converter, `best.pt` weights | Gokul; Tata Centre 36-Hour Hackathon team | `app.py` Gradio UI launched; `REPORT.txt` landscape synthesized; initial weights committed. | Hardware constraints on local T4/laptop GPU identified. |
| **2026-07-29 00:05** | Phase 1: Genesis | Commit `a0e6f187`: Fix Gradio 6.0 theme deprecation | Gokul | Gradio UI updated to current theme API. | Minor UI deprecation warning resolved. |
| **2026-08-01** | Phase 1: Genesis | Tata Centre 36-Hour Hackathon submission deadline | Gokul, Biomedical engineer, third team member | Prototype delivered: YOLOv8 + ByteTrack + CLAHE + Persistence Filter. | Single-stage detector produces false positives on small sessile polyps. |
| **2026-08-03 09:05** | Phase 2: Cascade AI | Commit `0e8b5b87`: Real-time artifact-aware polyp detection & tracking | Gokul | Video scan scripts, YOLO label generators, artifact-aware tracking. | Need sub-pixel segmentation masks rather than bounding boxes alone. |
| **2026-08-06 14:25 – 17:06** | Phase 2: Cascade AI | Commits `3a25fb67`, `1e6b2ecd`, `fc5885b6`: Stage 1 & 2 Cascade AI, PraNet ResNet-101 weights, Kvasir-SEG benchmark | Gokul | PraNet Reverse Attention integration; Paris classification; automated clinical reports (`src/clinical_report.py`); 0.9085 DSC reported. | PraNet is ResNet-101 based (considered dated by 2024–2026 SOTA reviewers). |
| **2026-08-07 14:12** | Phase 2: Cascade AI | Commit `abc9a4e2`: Resolve merge conflicts | Gokul | Clean repository merge. | Branch divergence resolved. |
| **2026-08-14 19:26** | Phase 3: Hardware Profiling | Conversation `da5fa049` | Gokul; e-consystems.com interview preparation | Clear architectural explanation for edge-based polyp detection. | Identified edge deployment bottlenecks on low-power devices. |
| **2026-08-21 09:49** | Phase 3: Hardware Profiling | Conversation `1d4dee5a`; `start_date.txt` (`2026-08-21`) | Gokul | Edge hardware comparison: Jetson Nano (50 FPS target) vs. Jetson Orin NX vs. RTX 3050 Laptop. | Jetson Nano 4GB too constrained for heavy Vision Transformers. |
| **2026-08-29 12:12** | Phase 4: Six Combos | Conversation `25cc0853` | Gokul; "The Brain Translator" | High-level system architecture critique and plan for multi-paradigm exploration. | Fragmented exploration began across 6 standalone notebooks. |
| **2026-08-30 15:31 – 18:30** | Phase 4: Six Combos | Commits `9450fb98`, `6bae8d1c`, `c838cf3c`, `4561228c` | Gokul | Reorganized repo into `src/`, `scripts/`, `docs/`, `data/`, `weights/`; scaffolded frontend; added transformer track. | Syncing large models from D:\chakramodel and Kaggle caused weight exclusions. |
| **2026-08-30 21:46 – 21:48** | Phase 4: Six Combos | Commits `3dedc11c`, `106443cc`: CI pipeline, ONNX optimization, `bmad-loop` continuous integration | Gokul | GitHub Actions workflow (`.github/workflows/test.yml`); automated `bmad-loop` hook. | Burn-in testing required to catch flaky notebook execution. |
| **2026-08-30 23:31 – 2026-08-31 07:47** | Phase 4: Six Combos | Conversations `c9554b92` → `8266953a` (323 conversations) | Gokul; Automated extraction subagents | Extracted 323 PMC academic papers into standardized 5-part summaries; mapped 60+ SOTA baselines. | High volume of subagent batches required 30–60s rate-limit throttling. |
| **2026-08-31 15:15** | Phase 4: Six Combos | Commit `3ba62e8d`: Reconstruct architecture spine, update index, refactor training | Gokul | Initial `ARCHITECTURE-SPINE.md` drafted; training scripts cleaned. | 6 standalone combos still treated as separate models. |
| **2026-09-01 10:00 – 20:34** | Phase 5: Spine Unification | Conversations `04643688`, `0bcd11c2`, `34a7f322`, `8d715197` | Gokul; PharmInnoQuest 2026 team | Market analysis, pitch deck, IP strategy (ICMR Patent Mitra) for 3 innovations. Simulated harsh MICCAI/TMI reviewer. | Reviewer simulation rejected 6-combo structure as disjointed hyperparameter search. |
| **2026-09-02 19:34 – 23:07** | Phase 5: Spine Unification | Conversations `530bbe49`, `ac883c9d`, `26ac293e` | Gokul, Jayasree, Girupa, Varsha | Data Genesis 2026 hackathon prep; unified paper drafting launched; Kaggle notebook strategy for cloud GPU. | ViT-Large (309.2M params) cannot be trained on local 4GB laptop; Kaggle GPU mandatory. |
| **2026-09-03 01:22 – 12:17** | Phase 6: Adversarial Audit | Conversations `410175bf` → `40bd06a3` (103 conversations) | Generator Squad (G1–G3), Discriminator Squad (D1–D6) | 10-Round continuous GAN loop; hardware monitoring active (`logs/hardware_monitor.log`). | Found `MockEval` returning hardcoded math (`0.88 + 0.01*len`); hard-cropping destroyed colon context (0.9085 -> 0.4555 DSC). |
| **2026-09-04 02:14 – 14:07** | Phase 6: Adversarial Audit | Conversations `41097d2f`, `e2e85fea`; `extract2.txt` | Gokul; Dr. Kovacs; Dr. Yamamoto | Discovered MC Dropout variance collapse ($\sigma^2 = 2.85 \times 10^{-15}$); cross-dataset failure (0.006 DSC). Discussion in Tamil confirming conformal novelty is system-level, not algorithmic. | Realized claiming algorithmic novelty for conformal prediction was fatal to peer review; must reframe. |
| **2026-09-04 14:08** | Phase 6: Adversarial Audit | Commit `6f9c20cd`: Reframe novelty to focus on systems integration and failure reporting | Gokul | "Honest Revision v2.0" of `ChakraModel_Final_Paper.md`; transparent failure reporting adopted as core academic contribution. | Topological Polyp Loss and ChakraSLAM explicitly designated as theoretical future work. |
| **2026-09-04 14:58 – 15:29** | Phase 6: Adversarial Audit | Conversations `191420de` → `80a7101a`; `september1to4afternnon_chat.json` | Gokul; Antigravity agents | Extracted all downloaded Kaggle evaluation notebooks and pitch decks; audited test metrics. | Evaluated Kvasir-SEG test split with RCPS conformal calibration (achieved 95.0% coverage). |
| **2026-09-04 16:00** | Phase 6: Adversarial Audit | `00_ANTI_FABRICATION_PROTOCOL.md` created | Gokul | Implemented canary tripwire images, session nonces, and MD5 hash checks to catch fake terminal outputs. | Prohibited any AI agent from hallucinating unverified numbers. |
| **2026-09-05 17:52** | Phase 7: Roadmap & Packaging | Commit `55c859b7`: Execute 5-step publication roadmap | Gokul | Added SAM-style Prompt Embeddings, TopoLoss Ablation script, MC Dropout fix, heavy Albumentations, Edge Benchmark. | Full multi-dataset retraining remains computationally pending. |
| **2026-09-05 17:55** | Phase 7: Roadmap & Packaging | Commit `d5807305`: Kaggle-ready video inference scripts and notebook | Gokul | `ChakraModel_Video_Evaluation_Kaggle.ipynb` and `create_kaggle_zip.py` built for reproducible video benchmarking. | Video inference runs at 3.7 FPS with full ViT-Large ROI pass (exceeds 50ms latency). |
| **2026-09-07 10:27 – 10:31** | Phase 7: Roadmap & Packaging | Commits `52d97853`, `b67bcb1a`, `2cac63f7` | Gokul | Added Mermaid architecture diagram to `ARCHITECTURE-SPINE.md`, committed all verification harnesses. | Committed ground truth verification framework. |
| **2026-09-07 12:00 – Present** | Phase 7: True Documentation | Teamwork preview multi-agent orchestration (`.agents/orchestrator/`) | Orchestrator, Explorer 1, Explorer 2, Explorer 3 | Launch of `true_docs/` initiative: forensic, verified documentation free of hallucinated claims. | Reconciling discrepancies across early drafts and code reality. |

---

## 5. Forensic Analysis of Roadblocks, Failures, and Architectural Pivots

### 5.1 The "Overfitting to Kvasir-SEG" Trap & Catastrophic Domain Shift
- **Evidence:** `cross_dataset_report.md`, `ChakraModel_Project_Journey.md`, `results/final_5_datasets_eval.json`.
- **Observation:** In-domain training on Kvasir-SEG reached **0.9085 ± 0.0071 DSC** (PraNet) and **0.8131 ± 0.1747 DSC** (ViT-Large standalone test). However, when tested zero-shot on out-of-distribution datasets:
  - CVC-ClinicDB: 0.7561 DSC.
  - CVC-300: 0.7402 DSC (in v5 run; initial unpadded run collapsed to 0.005 DSC).
  - PolypDB (WLI/NBI/LCI/BLI multi-modal stress test): 0.7283 DSC.
  - CVC-ColonDB: 0.8215 DSC (in v5 run; initial unpadded run collapsed to 0.006 DSC).
  - ETIS-Larib: **0.0000 DSC** (Total Generalization Failure).
- **Root Cause Analysis:** Models trained exclusively on Kvasir-SEG overfit to hospital-specific camera sensors, lighting geometry, and mucosal coloration. In ETIS-Larib, diminutive and sessile polyps under unfamiliar endoscopy lighting triggered complete false-negative dropouts.
- **Strategic Pivot:** The team stopped hiding cross-dataset scores, openly published the ETIS-Larib failure, and advocated for Test-Time Adaptation (AdaBN / Combo 3) and synthetic diffusion augmentation (Combo 4) as the clinical roadmap.

### 5.2 The Crop-and-Forward Context Degradation
- **Evidence:** `ChakraModel_Project_Journey.md`, `rigorous_hybrid_validation.py`.
- **Observation:** While Stage 1 YOLOv8 achieved 94.7 FPS, cropping the bounding box and passing it directly into the ChakraTransformer dropped DSC by 45 points—from **0.9085 down to 0.4555 DSC**.
- **Root Cause:** Naive bounding-box cropping stripped away peripheral anatomical context (colon lumen, mucosal walls, fold curvature) that the Vision Transformer self-attention layers relied upon to identify polyp boundaries.
- **Engineering Solution:** Replaced hard-cropping with **letterbox context-padded cropping** (padding bounding boxes with surrounding colon tissue before resizing to 384x384), recovering segmentation performance.

### 5.3 MC Dropout Variance Collapse & Conformal Prediction Fallback
- **Evidence:** `combo4.log` (lines 41–42), `ChakraModel_Final_Paper.md` (§3.3, §5.4).
- **Observation:** In Combo 4, synthetic polyp filtering logged `Accepted Mean Uncertainty: 0.0000 (Max: 0.0000)`. In Combo 6, MC Dropout across 8 passes yielded an empirical variance of $\sigma^2 = 2.85 \times 10^{-15}$.
- **Root Cause:** When `model.eval()` was called, PyTorch set `training=False` on the `timm` ViT-Large backbone, deactivating the dropout masks during forward inference passes.
- **Strategic Pivot:** In the final paper revision, the team explicitly retracted claims of "uncertainty-aware Bayesian conformal prediction" and documented that conformal calibration was executed using deterministic sigmoid thresholds ($q_{hat}$), which verified the **95.0% empirical coverage target** on held-out test data.

### 5.4 Hallucinated Metrics and the Anti-Fabrication Protocol
- **Evidence:** `00_ANTI_FABRICATION_PROTOCOL.md`, `reviewer_objections.md`, `extract2.txt`.
- **Observation:** Synthetic drafting agents had hallucinated hardware specs (claimed 8GB VRAM instead of the actual 4GB RTX 3050 Laptop GPU), batch sizes (claimed 8 instead of 32), and simulated p-values generated by a `MockEval` class.
- **Engineering Solution:** 
  1. Built forensic auditing scripts parsing raw `.log`, `.json`, and state_dict files.
  2. Implemented `00_ANTI_FABRICATION_PROTOCOL.md`: A tripwire module planting synthetic `CANARY_<hex>.png` images with mathematically known Dice scores into dataset folders, generating random session nonces (`VERIFY_NONCE`), and checking that scripts actually execute live inference rather than printing cached text.

### 5.5 Theoretical Claims vs. Implementation Reality
- **Topological Loss via Persistent Homology (TPL):**
  - *Claim:* Mathematically penalizes spurious Betti-0 (disconnected components) and Betti-1 (internal holes) features using cubical complexes.
  - *Reality:* The module exists in `src/topo_loss.py`, but it was **never integrated** into the primary training loop of Combo 6 (which trained using standard `DiceFocalLoss`). The quantitative ablation study (Δ DSC, Δ Betti error) was never run. The paper explicitly marks TPL as a "Theoretical Proposal / Future Work".
- **ChakraSLAM (3D Spatial Memory):**
  - *Claim:* Logs 3D coordinates of low-confidence polyp detections during scope insertion to trigger alerts during withdrawal.
  - *Reality:* Purely conceptual design. As formally verified in `ARCHITECTURE-SPINE.md` (AD-03), there is **zero executable implementation** of Endoscopic SLAM or 3D coordinate tracking in `src/`. Only 2D ByteTrack is implemented in `infer_stream.py`.

---

## 6. Recommendations for the Documentation Authors (`true_docs/`)

1. **Commit to Absolute Transparency on Origins:** Document the dual-origin reality—the codebase started on July 27, 2026 for the Tata Centre 36-Hour Hackathon, while `start_date.txt` (2026-08-21) marks the start of the edge-native transformer exploration.
2. **Feature the 7-Phase Trajectory:** Clearly structure `true_docs/history_and_timeline.md` around the 7 phases established in this report.
3. **Disclose Roadblocks as Core Intellectual Value:** Frame the cross-dataset catastrophe (0.000 ETIS), MC Dropout collapse, and crop-and-forward degradation not as project defects, but as the central scientific lessons of the ChakraModel project.
4. **Enforce the Truth vs. Myth Boundary:**
   - *Verified Ground Truth:* YOLOv8 Stage 1 detection (94.7 FPS), ViT-Large Stage 2 segmentation (0.9225 DSC Kvasir-SEG), Conformal Calibrator deterministic coverage (95.0%), ByteTrack 2D persistence.
   - *Aspirational / Theoretical:* ChakraSLAM 3D spatial memory, Topological Loss integrated training, and MC Dropout epistemic uncertainty.
5. **Honor the Anti-Fabrication Tripwire:** Ensure every metric cited in `true_docs/` can be cross-referenced to a physical commit hash, raw log file (`combo4.log`, `hardware_monitor.log`), or evaluation JSON (`final_5_datasets_eval.json`, `sota_results_clean.json`).
