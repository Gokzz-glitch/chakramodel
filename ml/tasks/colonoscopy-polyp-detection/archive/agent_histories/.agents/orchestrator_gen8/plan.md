# Execution Plan: ChakraModel Phases 2–4

## Objectives
Execute requirements R1–R5 for ChakraModel repository:
- **R1: Architecture Reconstruction** (`docs/ARCHITECTURE_RECONSTRUCTED.md`)
  - Inference pipeline mapping (YOLO detection -> crop -> ViT-Large segmentation)
  - Key-stripping paths documented
  - Combo system status (Combo1-6 weights vs untrained)
  - Conformal prediction pipeline documentation
  - Anti-fabrication & canary documentation
  - Dead code analysis in `chakranet_segmenter.py` (RFBBlock, ReverseAttention, BasicConv2d)
  - >=2 Mermaid diagrams
- **R2: Data Flow Map** (`docs/DATA_FLOW_MAP.md`)
  - Script -> artifact -> metric lineage
  - Checkpoint mapping
  - Train/test split hygiene
  - Lineage of `quick_eval_kvasir.py`
  - Honest metrics table highlighting Kaggle v5 defensible results
- **R3: Repository Restructuring**
  - Move files safely (NEVER delete)
  - Relocate Combo2-5 notebooks to `notebooks/combos/`
  - Move 50+ root .py files to `archive/` (categorized into `iterate_copies/` and `one_off/`)
  - Create `archive/MANIFEST.md`
  - Create `results/verified/` and `results/README.md`
  - Move `src/yolov8x.pt` to `weights/yolo/`
  - Move root documentation & audit reports to `docs/` and `docs/audit/`
- **R4: Git Operations**
  - Update `.gitignore` with credentials, leads, personal logs/resumes
  - `git rm --cached` keys.txt, sent_emails, etc.
  - Stage critical untracked scripts and evaluation results
  - Create at least 4 meaningful staged commits (DO NOT PUSH)
- **R5: Honest README Update**
  - 6-row honest metrics table (Kaggle v5 results)
  - Remove all SOTA claims and inflated metrics (0.9852, 0.9412, etc.)
  - Architecture explanation and links to reconstructed docs and version history
- **Milestone 4: Verification & Audit**
  - Reviewer verification of all acceptance criteria
  - Challenger verification of git status, file moves, and metrics consistency
  - Forensic Auditor integrity check

## Milestones & Dispatch Plan
1. **Worker 1 (Architect)**: `teamwork_preview_worker` in `.agents/worker_arch/`
   - Scope: R1 (`docs/ARCHITECTURE_RECONSTRUCTED.md`) and R2 (`docs/DATA_FLOW_MAP.md`)
2. **Worker 2 (Dev)**: `teamwork_preview_worker` in `.agents/worker_dev/`
   - Scope: R3 (Repository Restructuring) and R4 (Git Operations) and R5 (Honest README Update)
3. **Reviewer / Challenger / Auditor**:
   - Verify all acceptance criteria
   - Binary veto on integrity
