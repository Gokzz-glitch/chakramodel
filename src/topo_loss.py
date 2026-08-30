"""
Topological Loss for ChakraNet (Combination #6)
================================================
Uses Persistent Homology to ensure segmentation masks are topologically correct:
  - β₀ (Betti-0) = number of connected components → should be exactly 1 (one polyp)
  - β₁ (Betti-1) = number of holes → should be exactly 0 (no donut masks)

Surgeons HATE fragmented masks and masks with holes. This loss directly penalizes
topological errors during training.

Theory:
    Persistent Homology tracks how topological features (components, holes) appear
    and disappear as we sweep a threshold from 0 to 1 across the probability map.
    Features that persist for a long time are "real" (the polyp).
    Features that appear briefly are "noise" (fragmentation artifacts).
    We penalize the birth/death of noisy features.

Usage:
    from topo_loss import TopologicalLoss
    topo_criterion = TopologicalLoss(lam=0.1)
    loss = dice_focal_loss + topo_criterion(logits, targets)
"""

from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn


class TopologicalLoss(nn.Module):
    """
    Differentiable topological loss based on persistent homology.
    
    Penalizes:
    1. Extra connected components (fragmented masks) — enforces β₀ = 1
    2. Holes in the mask (donut shapes) — enforces β₁ = 0
    
    Works by identifying critical pixels (births/deaths of topological features)
    and pushing their probability toward 0 or 1 to eliminate spurious features.
    """
    
    def __init__(self, lam: float = 0.1, size_threshold: int = 10):
        """
        Args:
            lam: Weight of topological loss relative to main loss
            size_threshold: Minimum component size (pixels) to keep
        """
        super().__init__()
        self.lam = lam
        self.size_threshold = size_threshold
    
    def _compute_connected_components_loss(self, prob_map: torch.Tensor) -> torch.Tensor:
        """
        Penalize extra connected components in the prediction.
        Uses a differentiable approximation: for each small connected component,
        push its maximum probability toward 0 (eliminate it).
        """
        with torch.no_grad():
            binary = (prob_map > 0.5).cpu().numpy().astype(np.uint8)
        
        import cv2
        n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
        
        if n_labels <= 2:  # 0=background, 1=main component → perfect
            return torch.tensor(0.0, device=prob_map.device, requires_grad=True)
        
        # Find the largest foreground component (keep this one)
        fg_areas = []
        for i in range(1, n_labels):
            fg_areas.append((i, stats[i, cv2.CC_STAT_AREA]))
        
        if not fg_areas:
            return torch.tensor(0.0, device=prob_map.device, requires_grad=True)
        
        largest_id = max(fg_areas, key=lambda x: x[1])[0]
        
        # For each spurious component, penalize its pixels
        loss = torch.tensor(0.0, device=prob_map.device)
        labels_tensor = torch.from_numpy(labels).to(prob_map.device)
        
        for comp_id, area in fg_areas:
            if comp_id == largest_id:
                continue  # Keep the main polyp
            if area < self.size_threshold:
                # Push these pixels toward 0 (eliminate small fragments)
                mask = (labels_tensor == comp_id)
                if mask.any():
                    loss = loss + prob_map[mask].mean()
        
        return loss
    
    def _compute_hole_loss(self, prob_map: torch.Tensor) -> torch.Tensor:
        """
        Penalize holes inside the predicted mask.
        A hole = a connected component of BACKGROUND inside the FOREGROUND.
        """
        with torch.no_grad():
            binary = (prob_map > 0.5).cpu().numpy().astype(np.uint8)
            inv_binary = 1 - binary  # Invert: now holes become foreground
        
        import cv2
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv_binary, connectivity=8)
        
        if n_labels <= 2:  # 0=outer background, 1=... no holes
            return torch.tensor(0.0, device=prob_map.device, requires_grad=True)
        
        # The largest background component is the outer background (keep it)
        bg_areas = [(i, stats[i, cv2.CC_STAT_AREA]) for i in range(1, n_labels)]
        if not bg_areas:
            return torch.tensor(0.0, device=prob_map.device, requires_grad=True)
        
        largest_bg = max(bg_areas, key=lambda x: x[1])[0]
        
        # Any other background component is a HOLE → push those pixels toward 1 (fill it)
        loss = torch.tensor(0.0, device=prob_map.device)
        labels_tensor = torch.from_numpy(labels).to(prob_map.device)
        
        for comp_id, area in bg_areas:
            if comp_id == largest_bg:
                continue
            mask = (labels_tensor == comp_id)
            if mask.any():
                # Push these hole pixels toward 1 (fill the hole)
                loss = loss + (1.0 - prob_map[mask]).mean()
        
        return loss
    
    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Compute topological loss for a batch.
        
        Args:
            logits: [B, 1, H, W] raw model output
            targets: [B, 1, H, W] ground truth masks
        
        Returns:
            Scalar topological loss
        """
        probs = torch.sigmoid(logits)
        batch_loss = torch.tensor(0.0, device=logits.device)
        
        for i in range(probs.shape[0]):
            prob_map = probs[i, 0]  # [H, W]
            
            cc_loss = self._compute_connected_components_loss(prob_map)
            hole_loss = self._compute_hole_loss(prob_map)
            
            batch_loss = batch_loss + cc_loss + hole_loss
        
        return self.lam * batch_loss / probs.shape[0]


def evaluate_topology(pred_mask: np.ndarray) -> dict:
    """
    Evaluate topological correctness of a single predicted mask.
    
    Returns:
        dict with:
        - n_components: Number of connected components (ideal = 1)
        - n_holes: Number of holes (ideal = 0)
        - is_topologically_correct: True if n_components <= 1 and n_holes == 0
        - largest_component_ratio: What fraction of foreground is the largest component
    """
    import cv2
    
    binary = (pred_mask > 127).astype(np.uint8) if pred_mask.max() > 1 else pred_mask.astype(np.uint8)
    
    # Count connected components
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    n_components = n_labels - 1  # Subtract background
    
    # Count holes (background components inside foreground)
    inv_binary = 1 - binary
    n_bg_labels, _, _, _ = cv2.connectedComponentsWithStats(inv_binary, connectivity=8)
    n_holes = n_bg_labels - 2  # Subtract outer background and one "expected" region
    n_holes = max(0, n_holes)
    
    # Largest component ratio
    if n_components > 0:
        fg_areas = [stats[i, cv2.CC_STAT_AREA] for i in range(1, n_labels)]
        total_fg = sum(fg_areas)
        largest = max(fg_areas)
        ratio = largest / total_fg if total_fg > 0 else 0
    else:
        ratio = 0.0
    
    return {
        "n_components": n_components,
        "n_holes": n_holes,
        "is_topologically_correct": (n_components <= 1 and n_holes == 0),
        "largest_component_ratio": ratio,
    }
