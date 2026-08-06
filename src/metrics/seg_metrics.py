"""
Polyp Segmentation Evaluation Metrics
Implements standard medical image segmentation metrics used in SOTA papers:
  - Dice Similarity Coefficient (DSC)
  - Mean Intersection-over-Union (mIoU)
  - Sensitivity (Recall)
  - Specificity
  - Weighted F-measure (F_beta)
  - Structure Measure (S_alpha) -- Wang et al. ICCV 2017
  - Mean Absolute Error (MAE)
All metrics accept numpy binary arrays (H, W) in range {0,1} or {0,255}.
"""
from __future__ import annotations
import numpy as np


def _binarize(arr: np.ndarray) -> np.ndarray:
    """Ensure mask is boolean {0, 1}."""
    arr = arr.astype(np.float32)
    if arr.max() > 1.0:
        arr = arr / 255.0
    return (arr > 0.5).astype(np.float32)


def dice(pred: np.ndarray, gt: np.ndarray, smooth: float = 1e-6) -> float:
    """Dice Similarity Coefficient (DSC). Range [0, 1], higher is better."""
    p = _binarize(pred).flatten()
    g = _binarize(gt).flatten()
    intersection = np.dot(p, g)
    return float((2.0 * intersection + smooth) / (p.sum() + g.sum() + smooth))


def iou(pred: np.ndarray, gt: np.ndarray, smooth: float = 1e-6) -> float:
    """Intersection-over-Union (Jaccard). Range [0, 1], higher is better."""
    p = _binarize(pred).flatten()
    g = _binarize(gt).flatten()
    intersection = np.dot(p, g)
    union = p.sum() + g.sum() - intersection
    return float((intersection + smooth) / (union + smooth))


def sensitivity(pred: np.ndarray, gt: np.ndarray, smooth: float = 1e-6) -> float:
    """Sensitivity / Recall = TP / (TP + FN). Clinical safety metric."""
    p = _binarize(pred).flatten()
    g = _binarize(gt).flatten()
    tp = np.dot(p, g)
    fn = np.dot(1 - p, g)
    return float((tp + smooth) / (tp + fn + smooth))


def specificity(pred: np.ndarray, gt: np.ndarray, smooth: float = 1e-6) -> float:
    """Specificity = TN / (TN + FP). Avoids unnecessary biopsies."""
    p = _binarize(pred).flatten()
    g = _binarize(gt).flatten()
    tn = np.dot(1 - p, 1 - g)
    fp = np.dot(p, 1 - g)
    return float((tn + smooth) / (tn + fp + smooth))


def weighted_fmeasure(pred: np.ndarray, gt: np.ndarray, beta: float = 1.0, smooth: float = 1e-6) -> float:
    """Weighted F-measure (F_beta). Standard Kvasir-SEG benchmark metric."""
    p = _binarize(pred).flatten()
    g = _binarize(gt).flatten()
    precision = (np.dot(p, g) + smooth) / (p.sum() + smooth)
    recall    = (np.dot(p, g) + smooth) / (g.sum() + smooth)
    beta2 = beta ** 2
    return float(((1 + beta2) * precision * recall) / (beta2 * precision + recall + smooth))


def mae(pred: np.ndarray, gt: np.ndarray) -> float:
    """Mean Absolute Error. Range [0, 1], lower is better."""
    p = _binarize(pred)
    g = _binarize(gt)
    return float(np.mean(np.abs(p - g)))


def _object_score(pred: np.ndarray, gt: np.ndarray, smooth: float = 1e-6) -> float:
    """Object-aware component for Structure Measure."""
    x = pred[gt == 1]
    y = pred[gt == 0]
    if len(x) == 0:
        return 0.0
    o_fg = np.mean(x)
    sigma_fg = np.std(x) + smooth
    o_bg = np.mean(1 - y) if len(y) > 0 else 0.0
    sigma_bg = np.std(y) + smooth if len(y) > 0 else 0.0
    u = o_fg * (1 - sigma_fg) + o_bg * (1 - sigma_bg)
    return float(np.clip(u / 2.0, 0.0, 1.0))


def _region_score(pred: np.ndarray, gt: np.ndarray) -> float:
    """Region-aware component for Structure Measure."""
    p = pred.astype(np.float32)
    g = gt.astype(np.float32)
    cy, cx = np.where(g > 0.5)
    if len(cy) == 0:
        return 0.0
    # Centroid-based quadrant decomposition
    c_y, c_x = int(cy.mean()), int(cx.mean())
    q1 = dice(p[:c_y, :c_x], g[:c_y, :c_x])
    q2 = dice(p[:c_y, c_x:], g[:c_y, c_x:])
    q3 = dice(p[c_y:, :c_x], g[c_y:, :c_x])
    q4 = dice(p[c_y:, c_x:], g[c_y:, c_x:])
    h, w = g.shape
    w1 = float(c_y * c_x) / (h * w)
    w2 = float(c_y * (w - c_x)) / (h * w)
    w3 = float((h - c_y) * c_x) / (h * w)
    w4 = float((h - c_y) * (w - c_x)) / (h * w)
    return w1 * q1 + w2 * q2 + w3 * q3 + w4 * q4


def structure_measure(pred: np.ndarray, gt: np.ndarray, alpha: float = 0.5) -> float:
    """
    Structure Measure (S_alpha). Wang et al., ICCV 2017.
    Evaluates structural similarity to ground-truth annotation.
    Range [0, 1], higher is better.
    """
    p = _binarize(pred)
    g = _binarize(gt)
    if g.sum() == 0:
        return 1.0 if p.sum() == 0 else 0.0
    s_obj = _object_score(p, g)
    s_reg = _region_score(p, g)
    return float(alpha * s_obj + (1 - alpha) * s_reg)


def compute_all_metrics(pred: np.ndarray, gt: np.ndarray) -> dict:
    """
    Compute all segmentation metrics for a single image pair.
    Returns a dict with all metric values.
    """
    return {
        "dice":          dice(pred, gt),
        "iou":           iou(pred, gt),
        "sensitivity":   sensitivity(pred, gt),
        "specificity":   specificity(pred, gt),
        "f_measure":     weighted_fmeasure(pred, gt, beta=1.0),
        "f_beta_half":   weighted_fmeasure(pred, gt, beta=0.5),
        "structure_measure": structure_measure(pred, gt),
        "mae":           mae(pred, gt),
    }


def aggregate_metrics(results: list[dict]) -> dict:
    """
    Aggregates a list of per-image metric dicts into mean and std values.
    Only averages numeric fields; skips string fields like 'image'.
    """
    if not results:
        return {}
    keys = results[0].keys()
    agg = {}
    for k in keys:
        vals = [r[k] for r in results]
        # Only aggregate numeric fields
        try:
            numeric_vals = [float(v) for v in vals]
            agg[k]          = float(np.mean(numeric_vals))
            agg[f"{k}_std"] = float(np.std(numeric_vals))
        except (TypeError, ValueError):
            pass  # skip non-numeric fields (e.g. 'image' filename string)
    return agg
