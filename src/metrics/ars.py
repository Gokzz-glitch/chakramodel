from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class Box:
    class_id: int
    xyxy: Tuple[float, float, float, float]


def _iou_xyxy(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def yolo_to_xyxy(cx: float, cy: float, bw: float, bh: float, width: int, height: int) -> Tuple[float, float, float, float]:
    x1 = (cx - bw / 2.0) * width
    y1 = (cy - bh / 2.0) * height
    x2 = (cx + bw / 2.0) * width
    y2 = (cy + bh / 2.0) * height
    return x1, y1, x2, y2


def load_yolo_boxes(label_path: str | Path, width: int, height: int) -> List[Box]:
    path = Path(label_path)
    if not path.exists():
        return []

    boxes: List[Box] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        class_id = int(float(parts[0]))
        cx, cy, bw, bh = map(float, parts[1:5])
        boxes.append(Box(class_id=class_id, xyxy=yolo_to_xyxy(cx, cy, bw, bh, width, height)))
    return boxes


def greedy_match(predictions: Sequence[Box], ground_truth: Sequence[Box], iou_threshold: float = 0.5):
    candidates = []
    for pi, p in enumerate(predictions):
        for gi, g in enumerate(ground_truth):
            if p.class_id != g.class_id:
                continue
            iou = _iou_xyxy(p.xyxy, g.xyxy)
            if iou >= iou_threshold:
                candidates.append((iou, pi, gi))

    used_p, used_g, matches = set(), set(), []
    for iou, pi, gi in sorted(candidates, reverse=True):
        if pi in used_p or gi in used_g:
            continue
        used_p.add(pi)
        used_g.add(gi)
        matches.append((pi, gi, iou))
    return matches


def detection_summary(predictions: Sequence[Box], ground_truth: Sequence[Box], iou_threshold: float = 0.5) -> dict:
    matches = greedy_match(predictions, ground_truth, iou_threshold=iou_threshold)
    tp = len(matches)
    fp = max(0, len(predictions) - tp)
    fn = max(0, len(ground_truth) - tp)

    precision = tp / len(predictions) if predictions else 0.0
    recall = tp / len(ground_truth) if ground_truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matches": tp,
        "predictions": len(predictions),
        "ground_truth": len(ground_truth),
    }


def artifact_rejection_score(fp_counts_in_artifact_frames: Sequence[int], max_fp_per_frame: int = 1) -> float:
    """
    ARS = 1 - mean(normalized FP on artifact-tagged frames), clipped to [0,1].
    Higher is better.
    """
    if not fp_counts_in_artifact_frames:
        return 0.0
    denom = max(1, max_fp_per_frame)
    norm = [min(max(fp / denom, 0.0), 1.0) for fp in fp_counts_in_artifact_frames]
    return 1.0 - (sum(norm) / len(norm))