# Colonoscopy Polyp Detection

Real-time AI-powered polyp detection and segmentation for colonoscopy video streams.

## Status
![Phase](https://img.shields.io/badge/Phase-Migration%20Complete-green)

## Architecture
- **Model**: PraNet + custom topological loss (topo_loss.py)
- **Inference**: TensorRT-optimized streaming pipeline
- **Export**: ONNX + TensorRT (.engine)
- **Benchmarks**: LeakBench (see `../../evaluation/benchmarks/leakbench/`)

## Structure
```
src/
  app.py                    - Main inference application
  training/train_pranet.py  - Training entry point
  training/topo_loss.py     - Custom topological loss
  inference/infer_stream.py - Real-time streaming inference
  inference/export_tensorrt.py
  detection/train_yolo.py
  data/                     - Data pipeline scripts
tests/                      - 26 adversarial test harnesses
archive/                    - Legacy iterations (kaggle_packaging/, outreach/, etc.)
docs/
```

## Datasets
- `polypdb_candidate_v1` (Kaggle-ready, curated)
- `polyp_segmentation_v1` (Kaggle-ready)
- `fixed_polyp_dataset_v1` (supervised/annotated)
- See `D:\CHAKRA\data\stages\` for full dataset tree

## Evaluation
- LeakBench runs: `D:\CHAKRA\ml\evaluation\benchmarks\leakbench\results\`
- Kaggle notebooks: `D:\CHAKRA\ml\experiments\notebooks\polyp-detection\`

## Key Papers / References
- PraNet: Parallel Reverse Attention Network
- LeakBench: Benchmark for polyp detection data leakage detection
