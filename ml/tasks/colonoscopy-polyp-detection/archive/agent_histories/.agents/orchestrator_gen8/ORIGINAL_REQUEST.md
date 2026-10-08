# Original User Request

## 2026-09-09T11:35:46Z

ChakraModel (`M:\chakramodel`) is an 18GB polyp segmentation research repository that has completed Phase 1 forensic discovery. Now execute Phases 2–4: architecture reconstruction, data flow mapping, safe repository restructuring, git operations, and honest README update.

Working directory: M:\chakramodel
Integrity mode: development

## Phase 1 Findings (DO NOT RE-SCAN — use these facts)

- Combo2-5 notebooks FOUND at `notebooks/data/` — untracked, need moving to `notebooks/combos/`
- `src/quick_eval_kvasir.py` FOUND but UNTRACKED (8,958 B) — produced headline evaluation results
- 2 critical JSON results UNTRACKED: `results/corrected_eval_kvasir_seg.json`, `results/final_8_datasets_eval.json`
- `cvc-300/` and `etis-larib/` have only 2 canary/synthetic files — no real data
- `keys.txt` (20KB) is tracked in git with credentials — CRITICAL security issue
- `data/leads/` contains 10 CSV files with researcher contacts — GDPR risk
- `results/sent_emails.txt` (28KB), `college_sent_emails.txt`, `linkedin_contacted.txt` — personal email logs tracked in git
- 8 unpushed commits on local main — public repo frozen since 2026-08-31
- 124 root .py files in iterate-by-copy chains
- `chakra_transformer_best.pth.bak` (1,236 MB) is a clean backup of the checkpoint
- `kaggle_results/cross_dataset_results_v5.json` is the gold-standard result file
- `src/yolov8x.pt` (136 MB) is misplaced in src/ — should be in weights/
- `docs/Gokul_Resume.pdf`, `docs/LOR-NIT.pdf` are personal files in the repo

## Requirements

### R1. Architecture Reconstruction (Winston — Architect role)
Analyze the actual codebase in `M:\chakramodel\src\` and produce `docs/ARCHITECTURE_RECONSTRUCTED.md`:
- Read key source files: `src/chakranet_segmenter.py`, `src/transformer_segmenter.py`, `src/infer_stream.py`, `src/run_all_combos.py`, `src/evaluate_all.py`, `src/quick_eval_kvasir.py`, `src/conformal_calibration.py`, `src/conformal_pipeline/pipeline.py`
- Map the real inference pipeline: YOLO detection → crop → ViT-Large segmentation (312-key checkpoint)
- Document the two different key-stripping paths (which scripts use which loader)
- Map the Combo system (Combo1-6): which have real trained weights (`weights/combo1_best.pth`, `weights/combo2_best.pth`) vs. which are untrained
- Document the conformal prediction pipeline (note the two irreconcilable calibration runs)
- Document the anti-fabrication harness and canary system in `anti_fabrication/`
- Identify dead code in `chakranet_segmenter.py`: RFBBlock, ReverseAttention, BasicConv2d — are they instantiated anywhere?
- Include at least 2 Mermaid diagrams: (1) inference pipeline, (2) training/evaluation data flow
- Save to `M:\chakramodel\docs\ARCHITECTURE_RECONSTRUCTED.md`

### R2. Data Flow Map (Winston — Architect role)
Produce `M:\chakramodel\docs\DATA_FLOW_MAP.md` documenting:
- Which scripts produce which JSON/result files (script → artifact → metric lineage)
- Which scripts load which checkpoints
- Which evaluation scripts have proper train/test splits vs. which do not
- Which scripts are committed vs. untracked
- For every claimed Dice score, document: producing script, checkpoint used, dataset, N_samples, split method
- Include the honest metrics table showing only Kaggle v5 results as defensible

### R3. Repository Restructuring (Amelia — Dev role)
Safely restructure `M:\chakramodel` into this target tree. NEVER DELETE — only move/copy:

```
M:\chakramodel\
├── README.md                    (UPDATE — see R5)
├── CHANGELOG.md
├── FIXES.md
├── LICENSE
├── docs\
│   ├── ARCHITECTURE_RECONSTRUCTED.md   (created in R1)
│   ├── DATA_FLOW_MAP.md                (created in R2)
│   ├── CHAKRAMODEL_ANALYSIS_REPORT.md  (move from root)
│   ├── CHAKRAMODEL_VERSION_HISTORY.md  (move from root)
│   ├── POLYPGEN_INTEGRITY_REPORT.md    (move from root)
│   ├── audit\
│   │   ├── COLAB_EVALUATION_AUDIT_REPORT.md  (move from root)
│   │   └── [other audit reports]
│   └── paper\
│       └── ChakraModel_Final_Paper.md
├── src\
│   ├── models\
│   │   ├── chakranet_segmenter.py
│   │   └── pranet_resnet101.py
│   ├── evaluation\
│   │   ├── evaluate_all.py
│   │   ├── run_corrected_eval.py
│   │   ├── quick_eval_kvasir.py        (currently untracked)
│   │   ├── spot_check_eval.py
│   │   └── verify_minimal.py
│   ├── training\
│   │   ├── train_transformer.py
│   │   └── train_pranet.py
│   ├── detection\
│   │   └── [YOLO pipeline scripts]
│   ├── inference\
│   │   └── infer_stream.py
│   ├── conformal\
│   │   └── [conformal prediction code from src/conformal_pipeline/]
│   ├── anti_fabrication\
│   │   └── [harness scripts]
│   └── utils\
│       └── [shared utilities]
├── notebooks\
│   ├── combos\
│   │   ├── Combo1_ChakraNet_Focal.ipynb
│   │   ├── Combo2_Topo_ChakraNet.ipynb      (MOVE from notebooks/data/)
│   │   ├── Combo3_AdaBN_ChakraNet.ipynb     (MOVE from notebooks/data/)
│   │   ├── Combo4_DiffusionAug_ChakraNet.ipynb  (MOVE from notebooks/data/)
│   │   ├── Combo5_Federated_ChakraNet.ipynb     (MOVE from notebooks/data/)
│   │   └── Combo6_ChakraTransformer.ipynb
│   ├── kaggle\
│   │   ├── Kaggle_Final_Proof_Eval.ipynb
│   │   ├── Kaggle_CrossVal_v5_PATHS_FIXED.ipynb
│   │   └── [other kaggle notebooks]
│   └── colab\
│       └── Colab_ChakraTransformer_Evaluation.ipynb
├── weights\
│   ├── checkpoints\
│   │   ├── chakra_transformer_best.pth
│   │   ├── chakra_transformer_best.pth.bak
│   │   ├── combo1_best.pth
│   │   ├── combo2_best.pth
│   │   └── pranet_kvasir_best.pth
│   ├── yolo\
│   │   ├── best.pt
│   │   ├── yolov8n.pt
│   │   ├── yolo26n.pt
│   │   └── yolov8x.pt          (MOVE from src/)
│   └── calibration\
│       └── conformal_calibration.json
├── results\
│   ├── verified\
│   │   ├── combo1_metrics.json
│   │   ├── corrected_eval_kvasir_seg.json   (annotate with provenance)
│   │   ├── final_8_datasets_eval.json
│   │   └── kaggle_v5\
│   │       └── cross_dataset_results_v5.json
│   ├── historical\
│   │   └── final_5_datasets_eval.json
│   └── README.md               (NEW — explains which results are valid)
├── data\                       (keep as-is, add README noting canary status)
├── scripts\                    (keep as-is)
├── archive\
│   ├── iterate_copies\
│   │   └── [versioned .py chains: build_crossval_v4/v5, sod/sod2, metrics_engine/v2, etc.]
│   ├── one_off\
│   │   └── [other root .py files]
│   └── MANIFEST.md             (NEW — lists each file and its original purpose)
└── .gitignore                  (UPDATED)
```

### R4. Git Operations (Amelia — Dev role)
Execute these git operations IN ORDER. Do NOT push — stage commits only:

1. Update `.gitignore` to add:
   ```
   keys.txt
   data/leads/
   results/sent_emails.txt
   results/college_sent_emails.txt
   results/linkedin_contacted.txt
   docs/Gokul_Resume.pdf
   docs/Gokul_Resume.html
   docs/LOR-NIT.pdf
   .venv/
   __pycache__/
   *.pyc
   *.pth.bak
   ```
2. `git rm --cached keys.txt` — remove from tracking without deleting file
3. `git rm --cached results/sent_emails.txt results/college_sent_emails.txt results/linkedin_contacted.txt` — untrack email logs
4. `git add src/quick_eval_kvasir.py` (or new location after restructure)
5. `git add results/corrected_eval_kvasir_seg.json results/final_8_datasets_eval.json` (or new locations)
6. `git add CHAKRAMODEL_VERSION_HISTORY.md POLYPGEN_INTEGRITY_REPORT.md COLAB_EVALUATION_AUDIT_REPORT.md`
7. Track the Combo2-5 notebooks in their new location `notebooks/combos/`
8. Track `docs/ARCHITECTURE_RECONSTRUCTED.md` and `docs/DATA_FLOW_MAP.md`
9. Create commits with meaningful messages:
   - `security: remove keys.txt and personal data from git tracking`
   - `feat: track critical untracked evaluation scripts and results`
   - `refactor: restructure repo into clean directory tree`
   - `docs: add architecture reconstruction and data flow map`
   - `docs: update README with honest metrics`
10. Do NOT push — leave for user review

### R5. Honest README Update (Mary — Analyst role)
Update `README.md` with:
- Project description: ChakraModel is a polyp segmentation system using YOLO detection + ViT-Large segmentation, trained on Kvasir-SEG
- **Honest metrics table** (Kaggle v5 cross-dataset evaluation, proper test splits):

| Dataset | Dice (mean ± std) | N | Source | Split |
|---------|-------------------|---|--------|-------|
| Kvasir-SEG | 0.8131 ± 0.1747 | 150 | Kaggle v5 | test split |
| HyperKvasir | 0.8360 ± 0.1610 | 1000 | Kaggle v5 | test split |
| PolypDB | 0.7283 ± 0.2544 | 7868 | Kaggle v5 | test split |
| CVC-ClinicDB | 0.7561 ± 0.2131 | 495 | Kaggle v5 | test split |
| CVC-300 | 0.7402 ± 0.1590 | 60 | Kaggle v5 | test split |
| ETIS-Larib | N/A | — | — | No real data evaluated |

- Statement: "ChakraModel is a competent polyp segmenter achieving ~0.73–0.84 Dice across standard benchmarks. It is NOT state-of-the-art; SOTA methods achieve ~0.90+ Dice."
- Acknowledge the DDP serialization bug (module. prefix) and its resolution
- Link to `docs/CHAKRAMODEL_VERSION_HISTORY.md` for the full audit trail
- Remove ALL occurrences of: "New SOTA", "state-of-the-art", "0.9852", "0.9412", "0.8650"
- Architecture section: describe YOLO → crop → ViT-Large pipeline
- Link to `docs/ARCHITECTURE_RECONSTRUCTED.md`

## Acceptance Criteria

### Architecture
- [ ] `docs/ARCHITECTURE_RECONSTRUCTED.md` exists with at least 2 Mermaid diagrams
- [ ] Dead code in `chakranet_segmenter.py` identified by class name (RFBBlock, ReverseAttention, BasicConv2d)
- [ ] Each Combo (1-6) has a clear status: has-trained-weights / no-weights / paper-only
- [ ] Both key-loading paths documented with differences

### Data Flow
- [ ] `docs/DATA_FLOW_MAP.md` exists
- [ ] Every claimed metric has a row: script → JSON → metric value → split method
- [ ] `quick_eval_kvasir.py` lineage documented

### Repository
- [ ] Combo2-5 notebooks exist in `notebooks/combos/` and are git-tracked
- [ ] `src/quick_eval_kvasir.py` (or its new location) is git-tracked (`git ls-files` returns it)
- [ ] `keys.txt` NOT tracked (`git ls-files keys.txt` returns empty)
- [ ] `data/leads/` in `.gitignore`
- [ ] At least 50 root .py files moved to `archive/`
- [ ] `archive/MANIFEST.md` exists listing moved files
- [ ] `results/verified/` directory exists with annotated JSON files
- [ ] `results/README.md` exists explaining which results are valid
- [ ] `src/yolov8x.pt` moved to `weights/yolo/`

### README
- [ ] `README.md` contains the 6-row honest metrics table
- [ ] `README.md` does NOT contain the strings: "SOTA", "0.9852", "0.9412"
- [ ] `README.md` links to `docs/CHAKRAMODEL_VERSION_HISTORY.md`

### Git
- [ ] At least 4 meaningful commits staged (not pushed)
- [ ] `git log --oneline -5` shows descriptive commit messages
- [ ] `git status` shows no untracked critical files (quick_eval_kvasir.py, combo notebooks, audit reports)
