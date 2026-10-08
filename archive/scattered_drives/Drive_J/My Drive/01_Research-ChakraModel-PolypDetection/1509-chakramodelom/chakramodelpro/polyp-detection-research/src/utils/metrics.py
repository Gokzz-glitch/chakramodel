"""
metrics.py — Evaluation Metrics for Polyp Segmentation

All metrics are computed from real predictions.
NO hardcoded values. NO simulated results.

Metrics implemented:
  - Dice (F1) coefficient
  - IoU (Jaccard index)
  - F-measure (Fβ²=0.3, community standard for polyp segmentation)
  - Weighted F-measure
  - S-measure (Structural similarity)
  - E-measure (Enhanced alignment)
  - Mean Absolute Error (MAE)

References:
  - Fan et al., PraNet (MICCAI 2020) — Dice, IoU, F-measure, S-measure, E-measure
  - Fan et al., Structure-measure (ICCV 2017) — S-measure definition
  - Fan et al., Enhanced-alignment (IJCAI 2018) — E-measure definition
"""

import numpy as np
import torch
from scipy.ndimage import distance_transform_edt


def dice_coefficient(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    """
    Dice coefficient (F1 score for segmentation).
    
    Args:
        pred: Binary prediction mask (H, W), values in {0, 1}
        gt: Binary ground truth mask (H, W), values in {0, 1}
        eps: Smoothing factor to prevent division by zero
    
    Returns:
        Dice score in [0, 1]
    """
    assert pred.shape == gt.shape, f"Shape mismatch: {pred.shape} vs {gt.shape}"
    pred = pred.astype(np.float32)
    gt = gt.astype(np.float32)
    
    intersection = (pred * gt).sum()
    return float((2.0 * intersection + eps) / (pred.sum() + gt.sum() + eps))


def iou_coefficient(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    """
    Intersection over Union (Jaccard index).
    
    Args:
        pred: Binary prediction mask (H, W), values in {0, 1}
        gt: Binary ground truth mask (H, W), values in {0, 1}
    
    Returns:
        IoU score in [0, 1]
    """
    assert pred.shape == gt.shape
    pred = pred.astype(np.float32)
    gt = gt.astype(np.float32)
    
    intersection = (pred * gt).sum()
    union = pred.sum() + gt.sum() - intersection
    return float((intersection + eps) / (union + eps))


def f_measure(pred: np.ndarray, gt: np.ndarray, beta_sq: float = 0.3,
              eps: float = 1e-6) -> float:
    """
    F-measure with β² = 0.3 (emphasizes precision over recall).
    
    Community standard for polyp segmentation per PraNet/SANet.
    β² = 0.3 is the value used by all competing methods.
    
    Args:
        pred: Continuous prediction map (H, W), values in [0, 1]
        gt: Binary ground truth mask (H, W), values in {0, 1}
        beta_sq: β² weighting factor (0.3 for polyp segmentation)
    
    Returns:
        F-measure score in [0, 1]
    """
    assert pred.shape == gt.shape
    gt = gt.astype(np.float32)
    
    # Adaptive threshold: 2× mean of prediction map
    threshold = 2.0 * pred.mean()
    binary_pred = (pred >= threshold).astype(np.float32)
    
    tp = (binary_pred * gt).sum()
    precision = (tp + eps) / (binary_pred.sum() + eps)
    recall = (tp + eps) / (gt.sum() + eps)
    
    fm = (1 + beta_sq) * precision * recall / (beta_sq * precision + recall + eps)
    return float(fm)


def s_measure(pred: np.ndarray, gt: np.ndarray, alpha: float = 0.5) -> float:
    """
    S-measure (Structure-measure)
    Fan et al., 'Structure-measure: A New Way to Evaluate Foreground Maps' (ICCV 2017)
    
    Args:
        pred: Continuous prediction map (H, W), values in [0, 1]
        gt: Binary ground truth mask (H, W), values in {0, 1}
        alpha: Weight between object and region terms
    
    Returns:
        S-measure score in [0, 1]
    """
    pred = pred.astype(np.float32)
    gt = gt.astype(np.float32)
    
    if gt.max() == 0:  # all zeros
        return 1.0 - float(pred.mean())
    if gt.min() == 1:  # all ones
        return float(pred.mean())
        
    def s_object(p, g):
        fg = p * g
        bg = (1.0 - p) * (1.0 - g)
        u = g.mean()
        
        score_fg = 0.0
        if u > 0:
            x = fg[g == 1].mean()
            sigma_x = fg[g == 1].std()
            score_fg = 2.0 * x / (x**2 + 1.0 + sigma_x**2 + 1e-8)
            
        score_bg = 0.0
        if (1.0 - u) > 0:
            y = bg[g == 0].mean()
            sigma_y = bg[g == 0].std()
            score_bg = 2.0 * y / (y**2 + 1.0 + sigma_y**2 + 1e-8)
            
        return u * score_fg + (1.0 - u) * score_bg

    def s_region(p, g):
        h, w = g.shape
        # Centroid
        x, y = np.where(g > 0)
        cx = int(np.round(x.mean()))
        cy = int(np.round(y.mean()))
        
        cx = max(1, min(cx, h - 2))
        cy = max(1, min(cy, w - 2))
        
        def ssim(p_block, g_block):
            h_b, w_b = p_block.shape
            if h_b * w_b == 0: return 0.0
            x_m, y_m = p_block.mean(), g_block.mean()
            sigma_x2 = p_block.var()
            sigma_y2 = g_block.var()
            sigma_xy = ((p_block - x_m) * (g_block - y_m)).mean()
            
            c1, c2 = 1e-4, 9e-4
            num = (2 * x_m * y_m + c1) * (2 * sigma_xy + c2)
            den = (x_m**2 + y_m**2 + c1) * (sigma_x2 + sigma_y2 + c2)
            return num / den

        w1 = (cx * cy) / (h * w)
        w2 = (cx * (w - cy)) / (h * w)
        w3 = ((h - cx) * cy) / (h * w)
        w4 = ((h - cx) * (w - cy)) / (h * w)

        s1 = ssim(p[:cx, :cy], g[:cx, :cy])
        s2 = ssim(p[:cx, cy:], g[:cx, cy:])
        s3 = ssim(p[cx:, :cy], g[cx:, :cy])
        s4 = ssim(p[cx:, cy:], g[cx:, cy:])

        return w1 * s1 + w2 * s2 + w3 * s3 + w4 * s4

    return alpha * s_object(pred, gt) + (1.0 - alpha) * s_region(pred, gt)


def e_measure(pred: np.ndarray, gt: np.ndarray) -> float:
    """
    E-measure (Enhanced-alignment Measure)
    Fan et al., 'Enhanced-alignment Measure for Binary Foreground Map Evaluation' (IJCAI 2018)
    
    Args:
        pred: Continuous prediction map (H, W), values in [0, 1]
        gt: Binary ground truth mask (H, W), values in {0, 1}
    
    Returns:
        E-measure score in [0, 1]
    """
    pred = pred.astype(np.float32)
    gt = gt.astype(np.float32)
    
    if gt.max() == 0:
        return 1.0 - float(pred.mean())
    if gt.min() == 1:
        return float(pred.mean())
        
    gt_mu = gt.mean()
    pred_mu = pred.mean()
    
    align_gt = gt - gt_mu
    align_pred = pred - pred_mu
    
    align_matrix = 2 * (align_gt * align_pred) / (align_gt**2 + align_pred**2 + 1e-8)
    enhanced_matrix = ((align_matrix + 1) ** 2) / 4
    
    return float(enhanced_matrix.mean())


def weighted_f_measure(pred: np.ndarray, gt: np.ndarray, beta_sq: float = 0.3) -> float:
    """
    Weighted F-measure
    Margolin et al., 'How to evaluate foreground maps?' (CVPR 2014)
    
    Args:
        pred: Continuous prediction map (H, W), values in [0, 1]
        gt: Binary ground truth mask (H, W), values in {0, 1}
        beta_sq: Weighting factor
    
    Returns:
        Weighted F-measure score in [0, 1]
    """
    pred = pred.astype(np.float32)
    gt = gt.astype(np.float32)
    
    if gt.max() == 0:
        return 1.0 - float(pred.mean())
    if gt.min() == 1:
        return float(pred.mean())

    dst = np.minimum(distance_transform_edt(gt), distance_transform_edt(1 - gt))
    weight = np.exp(- (dst ** 2) / (2 * 5 ** 2)) # approximation of standard Gaussian weight
    
    # Calculate precision and recall
    eps = 1e-6
    tp = (weight * np.minimum(pred, gt)).sum()
    precision = tp / (weight * pred).sum() + eps
    recall = tp / (weight * gt).sum() + eps
    
    fm = (1 + beta_sq) * precision * recall / (beta_sq * precision + recall + eps)
    return float(fm)


def mean_absolute_error(pred: np.ndarray, gt: np.ndarray) -> float:
    """
    Mean Absolute Error between predicted probability map and binary GT mask.
    
    Args:
        pred: Continuous prediction map (H, W), values in [0, 1]
        gt: Binary ground truth mask (H, W), values in {0, 1}
    
    Returns:
        MAE in [0, 1] (lower is better)
    """
    assert pred.shape == gt.shape
    return float(np.abs(pred.astype(np.float32) - gt.astype(np.float32)).mean())


class AverageMeter:
    """Tracks running mean of a metric across batches."""
    
    def __init__(self, name: str):
        self.name = name
        self.reset()
    
    def reset(self):
        self.count = 0
        self.total = 0.0
    
    def update(self, value: float, n: int = 1):
        self.total += value * n
        self.count += n
    
    @property
    def avg(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total / self.count
    
    def __repr__(self):
        return f"AverageMeter(name={self.name}, avg={self.avg:.4f}, n={self.count})"


class SegmentationMetrics:
    """
    Collects and reports all segmentation metrics across a dataset.
    
    Usage:
        metrics = SegmentationMetrics()
        for pred, gt in dataloader:
            metrics.update(pred.numpy(), gt.numpy())
        results = metrics.compute()
        print(results)
    """
    
    def __init__(self):
        self.dice = AverageMeter("Dice")
        self.iou = AverageMeter("IoU")
        self.fmeasure = AverageMeter("F-measure")
        self.smeasure = AverageMeter("S-measure")
        self.emeasure = AverageMeter("E-measure")
        self.w_fmeasure = AverageMeter("wF-measure")
        self.mae = AverageMeter("MAE")
    
    def update(self, pred: np.ndarray, gt: np.ndarray, threshold: float = 0.5):
        """
        Update metrics with one prediction-GT pair.
        
        Args:
            pred: Predicted probability map (H, W) in [0, 1]
            gt: Binary ground truth mask (H, W) in {0, 1}
            threshold: Binarization threshold for Dice/IoU
        """
        binary_pred = (pred >= threshold).astype(np.float32)
        
        self.dice.update(dice_coefficient(binary_pred, gt))
        self.iou.update(iou_coefficient(binary_pred, gt))
        self.fmeasure.update(f_measure(pred, gt))
        self.smeasure.update(s_measure(pred, gt))
        self.emeasure.update(e_measure(pred, gt))
        self.w_fmeasure.update(weighted_f_measure(pred, gt))
        self.mae.update(mean_absolute_error(pred, gt))
    
    def compute(self) -> dict:
        """Return dict of all metrics."""
        return {
            "mDice": self.dice.avg,
            "mIoU": self.iou.avg,
            "mF_measure": self.fmeasure.avg,
            "mSmeasure": self.smeasure.avg,
            "mEmeasure": self.emeasure.avg,
            "wFmeasure": self.w_fmeasure.avg,
            "mMAE": self.mae.avg,
            "n_samples": self.dice.count,
        }
    
    def reset(self):
        self.dice.reset()
        self.iou.reset()
        self.fmeasure.reset()
        self.smeasure.reset()
        self.emeasure.reset()
        self.w_fmeasure.reset()
        self.mae.reset()
    
    def __repr__(self):
        results = self.compute()
        return (
            f"Dice={results['mDice']:.4f} | "
            f"IoU={results['mIoU']:.4f} | "
            f"F={results['mF_measure']:.4f} | "
            f"S={results['mSmeasure']:.4f} | "
            f"E={results['mEmeasure']:.4f} | "
            f"wF={results['wFmeasure']:.4f} | "
            f"MAE={results['mMAE']:.4f} | "
            f"n={results['n_samples']}"
        )
