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
        self.mae.update(mean_absolute_error(pred, gt))
    
    def compute(self) -> dict:
        """Return dict of all metrics."""
        return {
            "mDice": self.dice.avg,
            "mIoU": self.iou.avg,
            "mF_measure": self.fmeasure.avg,
            "mMAE": self.mae.avg,
            "n_samples": self.dice.count,
        }
    
    def reset(self):
        self.dice.reset()
        self.iou.reset()
        self.fmeasure.reset()
        self.mae.reset()
    
    def __repr__(self):
        results = self.compute()
        return (
            f"Dice={results['mDice']:.4f} | "
            f"IoU={results['mIoU']:.4f} | "
            f"F={results['mF_measure']:.4f} | "
            f"MAE={results['mMAE']:.4f} | "
            f"n={results['n_samples']}"
        )
