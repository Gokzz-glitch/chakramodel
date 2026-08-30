## 2026-08-29T07:16:18Z
You are Explorer 1 (Dataset Pipeline & Kaggle Runtime Environment).
Your working directory is: m:\chakramodel\.agents\explorer_1
Scope document: m:\chakramodel\PROJECT.md

Objective:
Investigate dataset download sources, extraction methods, and Kaggle runtime environment conventions to create a bulletproof, plug-and-play code cell snippet for downloading and extracting the Kvasir-SEG dataset directly into `/kaggle/working/data/kvasir-seg`.

Tasks:
1. Inspect `src/download_kvasir.py`, `src/download_cvc.py`, `notebooks/`, and other dataset scripts in `m:\chakramodel`.
2. Detail the exact public download URLs (e.g., https://datasets.simula.no/downloads/kvasir-seg.zip or verified fallback mirrors).
3. Design a Python code snippet that:
   - Sets base directory to `/kaggle/working/data/kvasir-seg` (or `./data/kvasir-seg` if run locally).
   - Checks if the dataset already exists.
   - Downloads the dataset zip file with streaming, progress reporting, SSL bypass, and timeout handling.
   - Robustly extracts the zip file and normalizes directory layout to `/kaggle/working/data/kvasir-seg/images/` and `/kaggle/working/data/kvasir-seg/masks/`.
   - Validates that exactly 1,000 images and 1,000 masks exist.
   - Includes a synthetic polyp generator fallback if network is unreachable during offline test runs.
4. Write your full analysis, code snippet, and verification findings to `m:\chakramodel\.agents\explorer_1\analysis.md`.
5. Write your handoff report to `m:\chakramodel\.agents\explorer_1\handoff.md`.
Update `progress.md` in your folder as you work. Send a message to your orchestrator when done.
