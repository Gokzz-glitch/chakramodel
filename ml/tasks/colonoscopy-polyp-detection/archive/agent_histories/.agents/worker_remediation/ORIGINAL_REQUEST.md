## 2026-09-09T12:05:42Z

You are the Remediation Software Engineer for ChakraModel Phases 2–4.
Your working directory is: M:\chakramodel\.agents\worker_remediation\
The project repository root is: M:\chakramodel

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

The Forensic Auditor and Reviewers evaluated the Phases 2–4 deliverables and flagged the following specific integrity and execution issues in `M:\chakramodel\.agents\auditor_1\handoff.md` and `M:\chakramodel\.agents\reviewer_1\handoff.md`. Your job is to execute the complete remediation:

### Punch List:

1. **Purge Prohibited String "SOTA" from `README.md`**:
   - Location: `M:\chakramodel\README.md` line 12:
     Currently: `> ChakraModel is a competent polyp segmenter achieving ~0.73–0.84 Dice across standard benchmarks. It is NOT state-of-the-art; SOTA methods achieve ~0.90+ Dice.`
   - Replace line 12 with:
     `> ChakraModel is a competent polyp segmenter achieving ~0.73–0.84 Dice across standard benchmarks. It does not claim state-of-the-art; leading published benchmark methods achieve ~0.90+ Dice.`
   - Verify with `git grep -i "SOTA" README.md` that ZERO instances of the string "SOTA" remain.

2. **Fix Post-Restructuring Runtime Imports and Paths in Evaluation Scripts**:
   Because `chakranet_segmenter.py` was moved to `src/models/chakranet_segmenter.py` and weights to `weights/checkpoints/chakra_transformer_best.pth`:
   - In `src/evaluation/quick_eval_kvasir.py` and `src/quick_eval_kvasir.py`:
     - Ensure `PROJECT_ROOT` resolves to repo root (e.g. `Path(__file__).resolve().parents[2]` for `src/evaluation/`, or `Path(__file__).resolve().parents[1]` for `src/`).
     - Add `str(PROJECT_ROOT / "src")` and `str(PROJECT_ROOT / "src" / "models")` to `sys.path` so that `import chakranet_segmenter` or `from models.chakranet_segmenter import ChakraNetMicroRefiner` works cleanly.
     - Implement dual-path weight resolution:
       ```python
       candidate_weights = [
           PROJECT_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth",
           PROJECT_ROOT / "weights" / "chakra_transformer_best.pth",
       ]
       weights_path = next((p for p in candidate_weights if p.exists()), candidate_weights[0])
       ```
   - In `src/evaluation/run_corrected_eval.py`, `src/evaluation/verify_strict.py`, `src/evaluation/verify_weights_load.py`:
     - Add `str(PROJECT_ROOT / "src")` and `str(PROJECT_ROOT / "src" / "models")` to `sys.path`.
     - Implement the same dual-path weight resolution so weights are found in either `weights/checkpoints/` or `weights/`.
   - In `src/conformal/conformal_calibration.py`:
     - Ensure `sys.path` includes `PROJECT_ROOT` and `PROJECT_ROOT / "src"` so `from chakra_transformer...` or `src.models...` imports resolve.

3. **Add Alias in `src/training/topo_loss.py`**:
   - Add `TopoLoss = TopologicalLoss` to `src/training/topo_loss.py` to maintain backward compatibility with existing tests.

4. **Align Split Note in `results/verified/corrected_eval_kvasir_seg_PROVENANCE.json`**:
   - Update `"split_method"` to:
     `"First 60 images alphabetically (paired[:60]); overlaps with training set"`
     so it is 100% consistent with `docs/DATA_FLOW_MAP.md`.

5. **Test and Verify All Fixes**:
   - Run: `python src/evaluation/quick_eval_kvasir.py` — verify it runs and outputs evaluation results without `ModuleNotFoundError`.
   - Run: `python src/evaluation/verify_minimal.py` — verify PASS.
   - Run: `python src/evaluation/verify_weights_load.py` — verify it finds weights and runs.
   - Run: `python -c "t = open('README.md', encoding='utf-8').read(); assert 'SOTA' not in t, 'SOTA found!'"` — verify clean.

6. **Git Staging**:
   - Stage the modified files (`README.md`, evaluation scripts, `topo_loss.py`, `corrected_eval_kvasir_seg_PROVENANCE.json`).
   - Create a clean local staged commit:
     `git commit -m "fix: resolve post-restructure import paths and purge SOTA token"`
   - DO NOT PUSH!
   - Write your handoff report to `M:\chakramodel\.agents\worker_remediation\handoff.md` and message parent when complete.
