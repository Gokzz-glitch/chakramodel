#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python src/hybrid_refine.py --help >/dev/null
python src/run_infer_eval_profile.py --help >/dev/null

TMP_DIR="$(mktemp -d /tmp/chakramodel-smoke-XXXXXX)"
export TMP_DIR
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/images" "$TMP_DIR/labels" "$TMP_DIR/preds" "$TMP_DIR/eval"

python - <<'PY'
from pathlib import Path
import os
import cv2
import numpy as np

root = Path(os.environ["TMP_DIR"])
img = np.zeros((64, 64, 3), dtype=np.uint8)
cv2.imwrite(str(root / "images" / "frame_0001.jpg"), img)
(root / "labels" / "frame_0001.txt").write_text("0 0.5 0.5 0.25 0.25\n", encoding="utf-8")
(root / "preds" / "frame_0001.txt").write_text("0 0.5 0.5 0.25 0.25\n", encoding="utf-8")
PY

python src/eval_pipeline.py \
  --images_dir "$TMP_DIR/images" \
  --labels_dir "$TMP_DIR/labels" \
  --predictions_dir "$TMP_DIR/preds" \
  --out_dir "$TMP_DIR/eval" \
  --iou_threshold 0.5

test -f "$TMP_DIR/eval/evaluation_report.json"
test -f "$TMP_DIR/eval/evaluation_report.md"
test -f "$TMP_DIR/eval/per_image_metrics.csv"

if [[ "${RUN_FULL_INFER:-0}" == "1" ]]; then
  if [[ ! -f "data/sample_video.mp4" ]]; then
    echo "Skipping full run: data/sample_video.mp4 not found"
    exit 0
  fi
  python src/run_infer_eval_profile.py \
    --profile local \
    --source data/sample_video.mp4 \
    --out "$TMP_DIR/local_demo.mp4" \
    --run_eval \
    --gt_dir "$TMP_DIR/labels" \
    --pred_dir "$TMP_DIR/preds" \
    --images_dir "$TMP_DIR/images" \
    --eval_out "$TMP_DIR/eval_full"
fi

echo "Smoke test passed."
