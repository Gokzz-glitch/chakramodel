"""
Association weights & dynamic thresholds for BoT-SORT / ByteTrack tracking matching.
"""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class TrackingWeightsConfig:
    """Configuration weights for IoU, Mahalanobis, and appearance affinity."""
    conf_high: float = 0.60
    conf_low: float = 0.15
    iou_weight: float = 0.70
    reid_weight: float = 0.30
    proximity_threshold: float = 0.50


class AssociationCostCalculator:
    """Calculates association matrix combining IoU and feature distances."""

    def __init__(self, config: TrackingWeightsConfig = TrackingWeightsConfig()):
        self.config = config

    def compute_iou_cost(self, atracks: list, btracks: list) -> np.ndarray:
        """Computes IoU distance matrix (1 - IoU)."""
        if len(atracks) == 0 or len(btracks) == 0:
            return np.empty((len(atracks), len(btracks)))

        cost_matrix = np.zeros((len(atracks), len(btracks)), dtype=np.float32)
        for i, a in enumerate(atracks):
            for j, b in enumerate(btracks):
                # Calculate Intersection over Union
                ax1, ay1, aw, ah = a.bbox.x_center - a.bbox.width / 2, a.bbox.y_center - a.bbox.height / 2, a.bbox.width, a.bbox.height
                bx1, by1, bw, bh = b.bbox.x_center - b.bbox.width / 2, b.bbox.y_center - b.bbox.height / 2, b.bbox.width, b.bbox.height

                inter_x1 = max(ax1, bx1)
                inter_y1 = max(ay1, by1)
                inter_x2 = min(ax1 + aw, bx1 + bw)
                inter_y2 = min(ay1 + ah, by1 + bh)

                inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
                union_area = (aw * ah) + (bw * bh) - inter_area
                iou = inter_area / (union_area + 1e-6)

                cost_matrix[i, j] = 1.0 - iou
        return cost_matrix

    def fuse_score_weights(self, cost_matrix: np.ndarray, detections: list) -> np.ndarray:
        """Weight the cost matrix by detection confidence scores."""
        if cost_matrix.size == 0:
            return cost_matrix
        
        det_scores = np.array([d.confidence for d in detections])
        # Scale cost based on detection confidence
        fused_cost = cost_matrix * (1.0 - det_scores[None, :])
        return fused_cost
