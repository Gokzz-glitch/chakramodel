"""
Inference Speed & Latency Benchmarker for ChakraModel.
Measures:
  - Stage 1 FPS: YOLOv8 only (full-frame detection)
  - Stage 1+2 FPS: YOLOv8 + PraNet (cascade pipeline)
  - GPU VRAM usage (MB)
  - Mean per-frame inference time (ms)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

def _try_gpu_mem() -> float:
    """Returns GPU memory used in MB, or -1 if unavailable."""
    try:
        import torch
        assert torch.cuda.is_available(), "CUDA is required for FPS benchmarking!"
        return torch.cuda.memory_allocated() / 1024**2
    except Exception:
        pass
    return -1.0


def benchmark_stage1(model_path: str, test_video: str, n_frames: int = 200, img_size: int = 640) -> dict:
    """Benchmark Stage 1: YOLOv8 detection only."""
    from ultralytics import YOLO
    model = YOLO(model_path)
    model.fuse()

    cap = cv2.VideoCapture(test_video)
    if not cap.isOpened():
        return {"error": f"Could not open {test_video}"}

    timings = []
    for i in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
        if not ret:
            break
        t0 = time.perf_counter()
        _ = model(frame, imgsz=img_size, verbose=False, conf=0.20)
        t1 = time.perf_counter()
        timings.append((t1 - t0) * 1000)

    cap.release()
    timings = timings[5:]  # skip warmup
    return {
        "stage": "Stage 1 (YOLOv8 Only)",
        "n_frames": len(timings),
        "mean_ms": float(np.mean(timings)),
        "std_ms":  float(np.std(timings)),
        "min_ms":  float(np.min(timings)),
        "max_ms":  float(np.max(timings)),
        "fps":     float(1000.0 / np.mean(timings)),
        "gpu_mem_mb": _try_gpu_mem(),
    }


def benchmark_stage2(model_path: str, test_video: str, n_frames: int = 200, img_size: int = 640) -> dict:
    """Benchmark Stage 1+2: YOLOv8 + PraNet cascade."""
    from ultralytics import YOLO
    from pranet_segmenter import PraNetSegmenter

    model     = YOLO(model_path)
    model.fuse()
    segmenter = PraNetSegmenter()

    cap = cv2.VideoCapture(test_video)
    if not cap.isOpened():
        return {"error": f"Could not open {test_video}"}

    timings_total = []
    timings_seg   = []

    for i in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
        if not ret:
            break

        t0 = time.perf_counter()
        results = model(frame, imgsz=img_size, verbose=False, conf=0.20)
        t1 = time.perf_counter()

        boxes = []
        if results and results[0].boxes is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()

        ts = time.perf_counter()
        for box in boxes[:1]:  # segment first detection only (most clinical use case)
            x1, y1, x2, y2 = [int(v) for v in box]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
            if x2 > x1 and y2 > y1:
                roi = frame[y1:y2, x1:x2]
                segmenter.segment_roi(roi, threshold=0.45)
        te = time.perf_counter()

        t2 = time.perf_counter()
        timings_total.append((t2 - t0) * 1000)
        timings_seg.append((te - ts) * 1000)

    cap.release()
    timings_total = timings_total[5:]
    timings_seg   = timings_seg[5:]

    return {
        "stage": "Stage 1+2 (YOLOv8 + PraNet Cascade)",
        "n_frames": len(timings_total),
        "mean_ms":      float(np.mean(timings_total)),
        "std_ms":       float(np.std(timings_total)),
        "min_ms":       float(np.min(timings_total)),
        "max_ms":       float(np.max(timings_total)),
        "fps":          float(1000.0 / np.mean(timings_total)),
        "seg_mean_ms":  float(np.mean(timings_seg)),
        "gpu_mem_mb":   _try_gpu_mem(),
    }


def print_latency_table(s1: dict, s2: dict):
    print("\n" + "="*65)
    print("  CHAKRAMODEL INFERENCE SPEED BENCHMARK")
    print("="*65)
    hdr = f"  {'Stage':<35} {'FPS':>6}  {'Mean(ms)':>9}  {'VRAM(MB)':>9}"
    print(hdr)
    print("-"*65)
    if "fps" in s1:
        print(f"  {s1['stage']:<35} {s1['fps']:>6.1f}  {s1['mean_ms']:>9.2f}  {s1['gpu_mem_mb']:>9.1f}")
    if "fps" in s2:
        print(f"  {s2['stage']:<35} {s2['fps']:>6.1f}  {s2['mean_ms']:>9.2f}  {s2['gpu_mem_mb']:>9.1f}")
        if "seg_mean_ms" in s2:
            print(f"  {'  of which: PraNet only':<35} {'':>6}  {s2['seg_mean_ms']:>9.2f}")
    print("="*65)


def main():
    parser = argparse.ArgumentParser(description="ChakraModel Inference Speed Benchmark")
    parser.add_argument("--video",      required=True, help="Test video file path")
    parser.add_argument("--model",      default="yolov8n.pt")
    parser.add_argument("--n_frames",   type=int, default=200)
    parser.add_argument("--out_dir",    default="outputs/eval")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    out  = root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    print("[Stage 1] Benchmarking YOLOv8 only...")
    s1 = benchmark_stage1(args.model, args.video, args.n_frames)

    print("[Stage 1+2] Benchmarking YOLOv8 + PraNet cascade...")
    s2 = benchmark_stage2(args.model, args.video, args.n_frames)

    print_latency_table(s1, s2)

    report = {"stage1": s1, "stage2": s2}
    json_path = out / "fps_latency_report.json"
    md_path   = out / "fps_latency_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# ChakraModel Inference Speed Report",
        "",
        "| Stage | FPS | Mean (ms) | VRAM (MB) |",
        "|:---|:---:|:---:|:---:|",
    ]
    for s in [s1, s2]:
        if "fps" in s:
            lines.append(f"| {s['stage']} | {s['fps']:.1f} | {s['mean_ms']:.2f} | {s['gpu_mem_mb']:.1f} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[SAVED] {md_path}")


if __name__ == "__main__":
    main()
