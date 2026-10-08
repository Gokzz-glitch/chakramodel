"""
Topological Loss for ChakraNet (Combination #6)
================================================
Uses Persistent Homology to ensure segmentation masks are topologically correct.
"""

from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn
import gudhi
import cv2

class TopologicalLoss(nn.Module):
    """
    Differentiable topological loss based on persistent homology using Gudhi.
    Penalizes topological features (connected components and holes) that do not match the ground truth.
    """
    def __init__(self, lam: float = 0.1):
        super().__init__()
        self.lam = lam

    def _get_gt_betti_numbers(self, target: torch.Tensor):
        binary = (target > 0.5).cpu().numpy().astype(np.uint8)
        n_labels, _, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        betti_0 = n_labels - 1 
        
        padded_binary = np.pad(binary, pad_width=1, mode='constant', constant_values=0)
        inv_binary = 1 - padded_binary
        n_bg_labels, _, _, _ = cv2.connectedComponentsWithStats(inv_binary, connectivity=8)
        betti_1 = max(0, n_bg_labels - 2) 
        
        return betti_0, betti_1

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        batch_loss = torch.tensor(0.0, device=logits.device)
        
        for i in range(probs.shape[0]):
            prob_map = probs[i, 0]
            target_map = targets[i, 0]
            
            gt_b0, gt_b1 = self._get_gt_betti_numbers(target_map)
            
            prob_np = prob_map.detach().cpu().numpy()
            filtration = (1.0 - prob_np).flatten()
            
            cc = gudhi.CubicalComplex(dimensions=prob_np.shape, top_dimensional_cells=filtration)
            cc.compute_persistence()
            cofaces = cc.cofaces_of_persistence_pairs()
            
            # Gudhi returns [regular_pairs, essential_pairs]
            # Each is a list of arrays for dimension 0, 1, ...
            regular = cofaces[0]
            essential = cofaces[1]
            
            pairs_0 = regular[0] if len(regular) > 0 else []
            pairs_1 = regular[1] if len(regular) > 1 else []
            
            loss = torch.tensor(0.0, device=logits.device)
            
            if len(pairs_0) > 0:
                persistences_0 = [(idx, filtration[d] - filtration[b]) for idx, (b, d) in enumerate(pairs_0)]
                persistences_0.sort(key=lambda x: x[1], reverse=True)
                
                # We expect gt_b0 components. 1 is essential, so we keep (gt_b0 - 1) pairs
                keep_0 = max(0, gt_b0 - 1)
                noise_0 = persistences_0[keep_0:]
                for idx, _ in noise_0:
                    b, d = pairs_0[idx]
                    loss = loss + (prob_map.view(-1)[b] - prob_map.view(-1)[d]) ** 2
            
            # If gt_b0 == 0, we must penalize the essential component as well!
            if gt_b0 == 0 and len(essential) > 0 and len(essential[0]) > 0:
                for b_arr in essential[0]:
                    b = b_arr[0] if isinstance(b_arr, (list, np.ndarray)) else b_arr
                    # Penalize the birth pixel to 0 (force the false positive to disappear)
                    loss = loss + (prob_map.view(-1)[b]) ** 2
                    
            if len(pairs_1) > 0:
                persistences_1 = [(idx, filtration[d] - filtration[b]) for idx, (b, d) in enumerate(pairs_1)]
                persistences_1.sort(key=lambda x: x[1], reverse=True)
                
                keep_1 = gt_b1
                noise_1 = persistences_1[keep_1:]
                for idx, _ in noise_1:
                    b, d = pairs_1[idx]
                    loss = loss + (prob_map.view(-1)[b] - prob_map.view(-1)[d]) ** 2
            
            batch_loss = batch_loss + loss

        return self.lam * batch_loss / probs.shape[0]

def evaluate_topology(pred_mask: np.ndarray) -> dict:
    binary = (pred_mask > 127).astype(np.uint8) if pred_mask.max() > 1 else pred_mask.astype(np.uint8)
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    n_components = max(0, n_labels - 1)
    
    padded_binary = np.pad(binary, pad_width=1, mode='constant', constant_values=0)
    inv_binary = 1 - padded_binary
    n_bg_labels, _, _, _ = cv2.connectedComponentsWithStats(inv_binary, connectivity=8)
    n_holes = max(0, n_bg_labels - 2)
    
    ratio = 0.0
    if n_components > 0:
        fg_areas = [stats[i, cv2.CC_STAT_AREA] for i in range(1, n_labels)]
        total_fg = sum(fg_areas)
        ratio = max(fg_areas) / total_fg if total_fg > 0 else 0.0
        
    return {
        "n_components": n_components,
        "n_holes": n_holes,
        "is_topologically_correct": (n_components <= 1 and n_holes == 0),
        "largest_component_ratio": ratio,
    }
