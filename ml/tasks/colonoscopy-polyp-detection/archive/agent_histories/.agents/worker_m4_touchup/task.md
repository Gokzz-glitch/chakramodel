# Task: Worker M4 Touchup - Citation and Path Polish
- **Role**: teamwork_preview_worker
- **Working Directory**: m:\chakramodel\.agents\worker_m4_touchup
- **Scope**: Apply the minor citation and path updates identified by Reviewer 2 to `true_docs/` to achieve 100% precision:
  1. `src/chakra_transformer/model.py` -> update to `src/chakra_transformer/transformer_segmenter.py`
  2. `fps_latency_report.json` -> update to `outputs/eval/fps_latency_report.json`
  3. `00_ANTI_FABRICATION_PROTOCOL.md` -> update to `.agents/rules/00_ANTI_FABRICATION_PROTOCOL.md`
  4. `src/infer_stream.py:L115-132` -> update to `lines 61-78`
  5. `combo4.log:L67-70` -> update to `lines 8, 41-42`
  6. Table 5.1 Kvasir mIoU std / wF-measure in `true_docs/verified_benchmarks_and_metrics.md` -> update to `0.1697` and `0.9240`
  7. Reference to `inspect_weights_detailed.py` -> note location in `.agents/teamwork_preview_explorer_m3_1/`
- **Output**: Write updated files in `true_docs/` and handoff report in `m:\chakramodel\.agents\worker_m4_touchup\handoff.md`.
