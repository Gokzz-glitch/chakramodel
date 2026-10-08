from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import cv2

from metrics.ars import Box, detection_summary, load_yolo_boxes
from metrics.tcs import temporal_consistency_score
from temporal.persistence import ArtifactTagger


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def _find_images(images_dir: Path) -> list[Path]:
    candidates = [path for path in sorted(images_dir.rglob("*")) if path.suffix.lower() in IMAGE_EXTENSIONS]
    return candidates


def _sequence_key(stem: str) -> tuple[str, int | None]:
    match = re.match(r"^(.*?)(?:[_-]?)(\d+)$", stem)
    if match:
        return match.group(1), int(match.group(2))
    return stem, None


def _load_frame_boxes(label_dir: Path, image_path: Path) -> tuple[list[Box], tuple[int, int]]:
    image = cv2.imread(str(image_path))
    if image is None:
        return [], (0, 0)
    height, width = image.shape[:2]
    label_path = label_dir / f"{image_path.stem}.txt"
    return load_yolo_boxes(label_path, width, height), (width, height)


def _write_report_markdown(summary: dict, out_path: Path) -> None:
    lines = [
        "# Evaluation Report",
        "",
        f"- Images evaluated: {summary['images_evaluated']}",
        f"- Total predictions: {summary['total_predictions']}",
        f"- Total ground truth boxes: {summary['total_ground_truth']}",
        f"- ARS: {summary['ars']:.4f}",
        f"- TCS: {summary['tcs']:.4f}",
        f"- Precision: {summary['precision']:.4f}",
        f"- Recall: {summary['recall']:.4f}",
        f"- F1: {summary['f1']:.4f}",
        "",
        "## Notes",
        "",
        "ARS is computed from class-aware IoU matches between prediction and ground-truth labels.",
        "TCS is computed from frame-to-frame stability of predictions inside inferred sequences.",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate(images_dir: str | Path, labels_dir: str | Path, predictions_dir: str | Path, out_dir: str | Path, iou_threshold: float = 0.5) -> dict:
    images_path = Path(images_dir)
    labels_path = Path(labels_dir)
    predictions_path = Path(predictions_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    images = _find_images(images_path)
    per_image_rows: list[dict] = []
    sequence_frames: dict[str, list[tuple[int, list[Box]]]] = defaultdict(list)

    total_predictions = 0
    total_ground_truth = 0
    precision_sum = 0.0
    recall_sum = 0.0
    f1_sum = 0.0
    ars_sum = 0.0

    for image_path in images:
        image = cv2.imread(str(image_path))
        if image is None:
            continue

        height, width = image.shape[:2]
        gt_boxes = load_yolo_boxes(labels_path / f"{image_path.stem}.txt", width, height)
        pred_boxes = load_yolo_boxes(predictions_path / f"{image_path.stem}.txt", width, height)

        summary = detection_summary(pred_boxes, gt_boxes, iou_threshold=iou_threshold)
        summary_row = {
            "image": image_path.name,
            **summary,
        }
        per_image_rows.append(summary_row)

        total_predictions += len(pred_boxes)
        total_ground_truth += len(gt_boxes)
        precision_sum += summary["precision"]
        recall_sum += summary["recall"]
        f1_sum += summary["f1"]
        ars_sum += summary["ars"]

        sequence_key, frame_index = _sequence_key(image_path.stem)
        sequence_order = frame_index if frame_index is not None else len(sequence_frames[sequence_key])
        sequence_frames[sequence_key].append((sequence_order, pred_boxes))

    frame_count = len(per_image_rows)
    ordered_sequences = [
        [boxes for _, boxes in sorted(sequence_frames[sequence_key], key=lambda item: item[0])]
        for sequence_key in sorted(sequence_frames.keys())
    ]
    tcs = temporal_consistency_score(ordered_sequences)
    summary = {
        "images_evaluated": frame_count,
        "total_predictions": total_predictions,
        "total_ground_truth": total_ground_truth,
        "precision": precision_sum / frame_count if frame_count else 0.0,
        "recall": recall_sum / frame_count if frame_count else 0.0,
        "f1": f1_sum / frame_count if frame_count else 0.0,
        "ars": ars_sum / frame_count if frame_count else 0.0,
        "tcs": tcs,
        "iou_threshold": iou_threshold,
        "per_image": per_image_rows,
    }

    report_json = out_path / "evaluation_report.json"
    report_md = out_path / "evaluation_report.md"
    report_csv = out_path / "per_image_metrics.csv"

    report_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_report_markdown(summary, report_md)

    with report_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "precision", "recall", "f1", "ars", "matches", "predictions", "ground_truth"])
        writer.writeheader()
        for row in per_image_rows:
            writer.writerow(row)

    tagger = ArtifactTagger(out_path)
    tagger.tag(report_json, "report", "evaluation", "metrics", metadata={"metric": "ars_tcs"})
    tagger.tag(report_md, "report", "evaluation", "markdown")
    tagger.tag(report_csv, "report", "evaluation", "csv")
    tagger.write_manifest()

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate YOLO-style predictions and generate an ARS/TCS report.")
    parser.add_argument("--images_dir", required=True, help="Directory with input images")
    parser.add_argument("--labels_dir", required=True, help="Directory with ground-truth YOLO labels")
    parser.add_argument("--predictions_dir", required=True, help="Directory with predicted YOLO labels")
    parser.add_argument("--out_dir", default="outputs/eval", help="Directory where reports are written")
    parser.add_argument("--iou_threshold", type=float, default=0.5, help="IoU threshold used for matching")
    args = parser.parse_args()

    evaluate(args.images_dir, args.labels_dir, args.predictions_dir, args.out_dir, iou_threshold=args.iou_threshold)
    print(f"Saved evaluation artifacts to {args.out_dir}")


if __name__ == "__main__":
    main()