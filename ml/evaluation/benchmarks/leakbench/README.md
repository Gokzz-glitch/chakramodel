# LeakBench

Benchmark framework for detecting data leakage in polyp detection models.
Evaluates whether train/test contamination inflates reported metrics.

## Structure
```
analysis/     - Result analysis (build_tidy_csv.py, build_xlsx.py, make_plots.py)
adapters/     - Model adapters (chakraguard.py, endofm_probe.py)
chakraguard/  - ChakraGuard predictor
external_eval/ - External model evaluation
local_tests/  - Smoke tests, latency benchmarks
protocol_gap/ - Protocol gap analysis scripts
results/      - Experiment run results (runs/, runs_e3/, r2-r6/)
```

## Key Scripts
- `aggregate.py`                      - Aggregate results across runs
- `analyze_cascade.py`                - Cascade analysis
- `audit_external_model.py`           - External model auditing
- `analysis/heldout_calibration_chakraguard.py` - Calibration
