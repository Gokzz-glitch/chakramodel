"""
Kvasir-SEG / CVC-ClinicDB Benchmark Runner for ChakraModel.
Computes Dice, mIoU, Sensitivity, Specificity, F-measure, Structure Measure, MAE.
Usage:
    python src/benchmark_kvasir.py --dataset kvasir-seg
    python src/benchmark_kvasir.py --dataset cvc-clinicdb
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
from pranet_segmenter import PraNetSegmenter
from metrics.seg_metrics import compute_all_metrics, aggregate_metrics

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

DATASET_PATHS = {
    "kvasir-seg":  ("data/kvasir-seg/images",  "data/kvasir-seg/masks"),
    "cvc-clinicdb": ("data/cvc-clinicdb/images", "data/cvc-clinicdb/masks"),
}


def find_mask(masks_dir: Path, stem: str) -> Path | None:
    for ext in IMAGE_EXTS:
        p = masks_dir / (stem + ext)
        if p.exists():
            return p
    return None


def run_benchmark(dataset: str, root: Path, out_dir: Path) -> dict:
    images_rel, masks_rel = DATASET_PATHS[dataset]
    images_dir = root / images_rel
    masks_dir  = root / masks_rel

    if not images_dir.exists():
        print(f"[ERROR] Dataset not found at {images_dir}")
        print(f"  Run: python src/download_kvasir.py first.")
        sys.exit(1)

    image_paths = sorted([p for p in images_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS])
    print(f"\n[BENCHMARK] ChakraModel PraNet on {dataset}")
    print(f"  Images: {len(image_paths)}")
    print(f"  Device: auto (CUDA if available)")

    segmenter = PraNetSegmenter()
    results   = []
    timings   = []
    failed    = 0

    for i, img_path in enumerate(image_paths):
        mask_path = find_mask(masks_dir, img_path.stem)
        if mask_path is None:
            failed += 1
            continue

        img_bgr = cv2.imread(str(img_path))
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if img_bgr is None or gt_mask is None:
            failed += 1
            continue

        # Resize to standard 352x352 for fair comparison with SOTA papers
        h, w = img_bgr.shape[:2]
        img_resized = cv2.resize(img_bgr, (352, 352))

        t0 = time.perf_counter()
        pred_mask, contours, conf = segmenter.segment_roi(img_resized, threshold=0.45)
        t1 = time.perf_counter()
        timings.append((t1 - t0) * 1000)  # ms

        if pred_mask is None:
            pred_mask = np.zeros((352, 352), dtype=np.uint8)

        gt_resized = cv2.resize(gt_mask, (352, 352), interpolation=cv2.INTER_NEAREST)
        metrics = compute_all_metrics(pred_mask, gt_resized)
        metrics["image"]    = img_path.name
        metrics["conf"]     = float(conf)
        metrics["time_ms"]  = timings[-1]
        results.append(metrics)

        if (i + 1) % 50 == 0:
            running_dice = np.mean([r["dice"] for r in results])
            print(f"  [{i+1:4d}/{len(image_paths)}] Running Dice: {running_dice:.4f} | {timings[-1]:.1f}ms/frame")

    agg = aggregate_metrics(results)
    agg["dataset"]         = dataset
    agg["n_images"]        = len(results)
    agg["n_failed"]        = failed
    agg["mean_time_ms"]    = float(np.mean(timings)) if timings else 0.0
    agg["fps"]             = float(1000.0 / agg["mean_time_ms"]) if agg["mean_time_ms"] > 0 else 0.0
    agg["per_image"]       = results

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{dataset}_benchmark.json"
    md_path   = out_dir / f"{dataset}_benchmark.md"
    json_path.write_text(json.dumps(agg, indent=2), encoding="utf-8")

    # Write markdown report
    lines = [
        f"# ChakraModel Benchmark: {dataset}",
        f"",
        f"| Metric | Score |",
        f"|:---|:---:|",
        f"| **Dice (DSC) ↑**           | **{agg['dice']:.4f}** |",
        f"| **mIoU ↑**                 | **{agg['iou']:.4f}** |",
        f"| Sensitivity (Recall) ↑     | {agg['sensitivity']:.4f} |",
        f"| Specificity ↑              | {agg['specificity']:.4f} |",
        f"| F-measure (β=1) ↑          | {agg['f_measure']:.4f} |",
        f"| Weighted F-measure (β=0.5)↑| {agg['f_beta_half']:.4f} |",
        f"| Structure Measure (Sα) ↑   | {agg['structure_measure']:.4f} |",
        f"| MAE ↓                      | {agg['mae']:.4f} |",
        f"| Mean Inference Time        | {agg['mean_time_ms']:.1f} ms/frame |",
        f"| FPS                        | {agg['fps']:.1f} |",
        f"| Images Evaluated           | {agg['n_images']} |",
        f"",
        f"> Results on {dataset} at threshold=0.45, input size 352x352.",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n{'='*55}")
    print(f"  BENCHMARK COMPLETE: {dataset}")
    print(f"{'='*55}")
    print(f"  Dice (DSC):            {agg['dice']:.4f}")
    print(f"  mIoU:                  {agg['iou']:.4f}")
    print(f"  Sensitivity (Recall):  {agg['sensitivity']:.4f}")
    print(f"  Specificity:           {agg['specificity']:.4f}")
    print(f"  F-measure:             {agg['f_measure']:.4f}")
    print(f"  Structure Measure:     {agg['structure_measure']:.4f}")
    print(f"  MAE:                   {agg['mae']:.4f}")
    print(f"  Mean Inference Time:   {agg['mean_time_ms']:.1f} ms")
    print(f"  FPS:                   {agg['fps']:.1f}")
    print(f"{'='*55}")
    print(f"  Report: {md_path}")
    return agg


def main():
    parser = argparse.ArgumentParser(description="ChakraModel Segmentation Benchmark")
    parser.add_argument("--dataset",  default="kvasir-seg", choices=list(DATASET_PATHS.keys()))
    parser.add_argument("--out_dir",  default="outputs/eval")
    args = parser.parse_args()
    root = Path(__file__).parent.parent
    run_benchmark(args.dataset, root, root / args.out_dir)


if __name__ == "__main__":
    main()
