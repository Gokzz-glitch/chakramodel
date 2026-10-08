# Plan — Orchestrator Gen 7: Colab Cloud GPU Evaluation Audit

## Mission Objective
Conduct an exhaustive, line-by-line codebase audit of `chakramodel` to identify the exact root causes of failures observed during model evaluation on Google Colab Cloud GPU (as evidenced in the provided execution logs), trace each log message directly to code lines and filesystem assumptions, and deliver a comprehensive markdown audit report with exact proposed fixes (REPORT ONLY, zero source code modifications).

## Audit Scope & Key Areas
1. **Colab Log Line Tracing**:
   - `Copying files directly (skipping the slow search)...`
   - `❌ CRITICAL: Could not find the weights at /content/drive/MyDrive/chakra_transformer_best.pth`
   - `❌ CRITICAL: Could not find the zip at /content/drive/MyDrive/chakramodel_data_scripts.zip`
   - `unzip: cannot find or open /content/chakramodel_data_scripts.zip, /content/chakramodel_data_scripts.zip.zip or /content/chakramodel_data_scripts.zip.ZIP.`
   - `FileNotFoundError: [Errno 2] No such file or directory: '/content/src/verify_strict.py'`
2. **Setup, Notebooks & Packaging Scripts Audit**:
   - `Colab_GPU_Fast_Verify.ipynb`, `AutoDiscover_Evaluation.ipynb`, `Bulletproof_Evaluation.ipynb`, `Final_Evaluation_MultiCell.ipynb`, etc.
   - `setup_colab.py`, `cloud_gpu_guide.py`, `append_notebook.py`, `append_notebook_gdown.py`, `package_kaggle.py`, etc.
   - Zip files and packaging logic: `chakramodel_data_scripts.zip`, `chakramodel-weights.zip`, `chakramodel_weights_PRIVATE.zip`, etc.
3. **Evaluation Script Execution Flow & Path Resolution**:
   - `src/verify_strict.py`, `local_eval.py`, `verify_best_pt.py`, `src/verify_weights_load.py`.
   - Windows backslashes (`\`) vs Linux forward slashes (`/`), absolute paths (`/content/...`) vs relative paths (`./src/...` or `src/...`), working directory context (`os.getcwd()`), Drive mounting paths (`/content/drive/MyDrive/...` vs `/content/drive/MyDrive/Colab Notebooks/...`).
4. **Weight Loading Logic & Environment Differences**:
   - Key matching, DDP prefix (`module.`), GPU device mapping (`map_location`), CPU vs CUDA tensor operations.
5. **Systemic Elimination of Hardcoded Values Across Architecture**:
   - Catalog all hardcoded paths (`/content/drive/MyDrive/...`, `/content/...`, `m:/...`, `J:/...`), fixed filenames, and environmental assumptions.
   - Design dynamic, environment-agnostic solutions (dynamic root resolution, recursive discovery, CLI flags/env vars) for the entire architecture.
6. **Concrete Proposed Fixes**:
   - Step-by-step code and configuration fixes for notebook cells, packaging scripts, and evaluation execution commands.

## Milestone Plan

### Milestone 1: Multi-Track Exploration & Code Analysis
- **Track 1 (Explorer 1)**: Colab Notebooks & Setup Automation (`Colab_GPU_Fast_Verify.ipynb`, `setup_colab.py`, `cloud_gpu_guide.py`, `append_notebook*.py`). Find where the log lines originated, how Google Drive is mounted, where files are expected, and why `chakramodel_data_scripts.zip` and `chakra_transformer_best.pth` were not found.
- **Track 2 (Explorer 2)**: Evaluation Execution & Path Resolution (`src/verify_strict.py`, `local_eval.py`). Trace line-by-line how `/content/src/verify_strict.py` is invoked, how zip archives extract files (nested folders vs flat files), working directory changes (`%cd` vs `cd` vs Python cwd), and why `FileNotFoundError: '/content/src/verify_strict.py'` occurs.
- **Track 3 (Explorer 3)**: Weight Packaging & Checkpoint Architecture. Examine `chakramodel-weights.zip`, `chakramodel_data_scripts.zip`, actual weights file naming (`chakra_transformer_best.pth` vs `chakra_best_weights.pth` vs `best.pth`), file sizes, directory tree within zips, and state_dict structures.

### Milestone 2: Report Drafting (Worker)
- Aggregate Explorer findings into `m:\chakramodel\COLAB_EVALUATION_AUDIT_REPORT.md`.
- Structure:
  1. Executive Summary & Root Cause Matrix
  2. Line-by-Line Colab Execution Log Decomposition
  3. Codebase Analysis of Setup, Packaging & Drive Mounting
  4. Line-by-Line Audit of Evaluation Scripts (`local_eval.py`, `src/verify_strict.py`)
  5. Cross-Platform & Environment Discrepancies (Windows vs Colab Linux)
  6. Concrete, Production-Grade Proposed Fixes (Notebook cells, scripts, paths)
  7. Verification Checklist & Action Plan

### Milestone 3: Review, Empirical Stress-Test & Forensic Audit
- **Reviewer 1**: Validate technical accuracy, line number references, code citations, and logic flow against actual files.
- **Reviewer 2**: Validate proposed fixes, ensuring they completely resolve all 5 logged failures without introducing new regressions.
- **Challenger 1**: Verify zip packaging structures and path extraction behavior (simulate zip layout and path resolution).
- **Challenger 2**: Verify weight loading logic and evaluate alternative path scenarios.
- **Forensic Auditor**: Verify zero source code modifications and audit integrity.

### Milestone 4: Gate Synthesis & Sentinel Notification
- Verify all pass criteria.
- Notify Sentinel with final status and report summary.
