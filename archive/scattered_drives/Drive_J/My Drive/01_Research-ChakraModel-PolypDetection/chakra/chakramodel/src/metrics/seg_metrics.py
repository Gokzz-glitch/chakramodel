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


def _ssim(p: np.ndarray, g: np.ndarray) -> float:
    if p.size == 0:
        return 0.0
    N = p.size
    x_m = np.mean(p)
    y_m = np.mean(g)
    sigma_x = np.sum((p - x_m) ** 2) / (N - 1 + 1e-5)
    sigma_y = np.sum((g - y_m) ** 2) / (N - 1 + 1e-5)
    sigma_xy = np.sum((p - x_m) * (g - y_m)) / (N - 1 + 1e-5)
    alpha_ = 4 * x_m * y_m * sigma_xy
    beta_ = (x_m**2 + y_m**2) * (sigma_x + sigma_y)
    if alpha_ != 0: return float(alpha_ / (beta_ + 1e-5))
    elif alpha_ == 0 and beta_ == 0: return 1.0
    return 0.0

def _object_score(pred: np.ndarray, gt: np.ndarray) -> float:
    def s_object(x):
        if x.size == 0: return 0.0
        mean = np.mean(x)
        std = np.std(x, ddof=1) if x.size > 1 else 0
        return 2 * mean / (mean**2 + 1 + std + 1e-5)
    gt_mean = np.mean(gt)
    fg_score = s_object(pred[gt == 1]) * gt_mean
    bg_score = s_object((1 - pred)[gt == 0]) * (1 - gt_mean)
    return float(fg_score + bg_score)

def _region_score(pred: np.ndarray, gt: np.ndarray) -> float:
    h, w = gt.shape
    if np.count_nonzero(gt) == 0:
        cy, cx = np.round(h / 2), np.round(w / 2)
    else:
        cy, cx = np.argwhere(gt).mean(axis=0).round()
    cy, cx = int(cy) + 1, int(cx) + 1

    w_lt = cx * cy / (h * w)
    w_rt = cy * (w - cx) / (h * w)
    w_lb = (h - cy) * cx / (h * w)
    w_rb = 1 - w_lt - w_rt - w_lb

    score_lt = _ssim(pred[0:cy, 0:cx], gt[0:cy, 0:cx]) * w_lt
    score_rt = _ssim(pred[0:cy, cx:w], gt[0:cy, cx:w]) * w_rt
    score_lb = _ssim(pred[cy:h, 0:cx], gt[cy:h, 0:cx]) * w_lb
    score_rb = _ssim(pred[cy:h, cx:w], gt[cy:h, cx:w]) * w_rb
    return float(score_lt + score_rt + score_lb + score_rb)

def structure_measure(pred: np.ndarray, gt: np.ndarray, alpha: float = 0.5) -> float:
    """Structure Measure (S_alpha). Wang et al., ICCV 2017."""
    p = _binarize(pred)
    g = _binarize(gt)
    if g.sum() == 0:
        return float(1.0 - np.mean(p))
    if g.sum() == g.size:
        return float(np.mean(p))
    s_obj = _object_score(p, g)
    s_reg = _region_score(p, g)
    return float(np.maximum(0, alpha * s_obj + (1 - alpha) * s_reg))

def s_measure(pred: np.ndarray, gt: np.ndarray, alpha: float = 0.5) -> float:
    return structure_measure(pred, gt, alpha)

def w_fmeasure(pred: np.ndarray, gt: np.ndarray, beta: float = 1.0) -> float:
    p = _binarize(pred)
    g = _binarize(gt)
    if g.sum() == 0:
        if p.sum() == 0:
            return 1.0
        return 0.0
    
    from scipy.ndimage import distance_transform_edt, convolve
    Dst, Idxt = distance_transform_edt(g == 0, return_indices=True)
    
    E = np.abs(p - g)
    Et = np.copy(E)
    Et[g == 0] = Et[Idxt[0][g == 0], Idxt[1][g == 0]]
    
    m, n = 3, 3
    y, x = np.ogrid[-m : m + 1, -n : n + 1]
    h = np.exp(-(x * x + y * y) / (2 * 5 * 5))
    h[h < np.finfo(h.dtype).eps * h.max()] = 0
    sumh = h.sum()
    if sumh != 0:
        h /= sumh
        
    EA = convolve(Et, weights=h, mode="constant", cval=0)
    MIN_E_EA = np.where((g == 1) & (EA < E), EA, E)
    
    B = np.where(g == 0, 2 - np.exp(np.log(0.5) / 5 * Dst), np.ones_like(g))
    Ew = MIN_E_EA * B
    
    TPw = np.sum(g) - np.sum(Ew[g == 1])
    FPw = np.sum(Ew[g == 0])
    
    R = 1 - np.mean(Ew[g == 1])
    P = TPw / (TPw + FPw + 1e-5)
    
    return float(((1 + beta**2) * P * R) / (beta**2 * P + R + 1e-5))

def e_measure(pred: np.ndarray, gt: np.ndarray) -> float:
    p = _binarize(pred)
    g = _binarize(gt)
    if g.sum() == 0:
        return float(1.0 - np.mean(p))
    if g.sum() == g.size:
        return float(np.mean(p))
    
    pred_bin = _binarize(p)
    fg_fg = np.sum((pred_bin == 1) & (g == 1))
    fg_bg = np.sum((pred_bin == 1) & (g == 0))
    bg_fg = np.sum((pred_bin == 0) & (g == 1))
    bg_bg = np.sum((pred_bin == 0) & (g == 0))
    
    gt_size = g.size
    gt_fg_numel = np.sum(g == 1)
    pred_fg_numel = fg_fg + fg_bg
    pred_bg_numel = gt_size - pred_fg_numel
    
    mean_pred_value = pred_fg_numel / gt_size
    mean_gt_value = gt_fg_numel / gt_size
    
    parts_numel = [fg_fg, fg_bg, bg_fg, bg_bg]
    combinations = [
        (1 - mean_pred_value, 1 - mean_gt_value),
        (1 - mean_pred_value, 0 - mean_gt_value),
        (0 - mean_pred_value, 1 - mean_gt_value),
        (0 - mean_pred_value, 0 - mean_gt_value)
    ]
    
    enhanced_matrix_sum = 0.0
    for part_numel, comb in zip(parts_numel, combinations):
        align_matrix_value = 2 * (comb[0] * comb[1]) / (comb[0]**2 + comb[1]**2 + 1e-5)
        enhanced_matrix_value = (align_matrix_value + 1)**2 / 4
        enhanced_matrix_sum += enhanced_matrix_value * part_numel
        
    return float(enhanced_matrix_sum / (gt_size - 1 + 1e-5))


def mean_absolute_error(pred: np.ndarray, gt: np.ndarray) -> float:
    """MAE (Mean Absolute Error) - Simple pixel-level absolute difference."""
    p = _binarize(pred)
    g = _binarize(gt)
    return float(np.mean(np.abs(p - g)))


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
        "s_measure":     s_measure(pred, gt, alpha=0.5),
        "w_fmeasure":    w_fmeasure(pred, gt),
        "e_measure":     e_measure(pred, gt),
        "mean_absolute_error": mean_absolute_error(pred, gt),
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
