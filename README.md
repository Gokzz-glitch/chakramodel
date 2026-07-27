# chakramodel

## Train with a profile

- Local:
  - `python src/run_profile.py --profile local`
- Colab:
  - `python src/run_profile.py --profile colab`
- Docker:
  - `python src/run_profile.py --profile docker`

## Inference + evaluation with a profile

`run_infer_eval_profile.py` applies profile thresholds and supports weight fallback in this order:

1. `best.pt`
2. `last.pt`
3. `yolov8n.pt`

If `--weights` is provided and exists, it is used first.

- Local:
  - `python src/run_infer_eval_profile.py --profile local --source data/sample_video.mp4 --weights yolov8n.pt --out outputs/local_demo.mp4 --run_eval --gt_dir data/processed/labels/test --pred_dir outputs/preds/test_labels --images_dir data/processed/images/test --eval_out outputs/eval`
- Colab:
  - `python src/run_infer_eval_profile.py --profile colab --source data/sample_video.mp4 --out outputs/colab_demo.mp4 --run_eval --gt_dir data/processed/labels/test --pred_dir outputs/preds/test_labels --images_dir data/processed/images/test --eval_out outputs/eval_colab`
- Docker:
  - `python src/run_infer_eval_profile.py --profile docker --source data/sample_video.mp4 --out outputs/docker_demo.mp4 --run_eval --gt_dir data/processed/labels/test --pred_dir outputs/preds/test_labels --images_dir data/processed/images/test --eval_out outputs/eval_docker`

## Smoke test

- Quick CLI + eval smoke test:
  - `bash scripts/smoke_infer_eval.sh`
- Optional full inference/eval run (heavier):
  - `RUN_FULL_INFER=1 bash scripts/smoke_infer_eval.sh`