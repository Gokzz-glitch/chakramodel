import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from scipy.ndimage import distance_transform_edt
from typing import Dict, Union, List

class SoftDiceLoss(nn.Module):
    """
    Soft Dice Loss for binary segmentation.
    Operates on logits and applies sigmoid internally for numerical stability.
    """
    def __init__(self, smooth: float = 1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Args:
            logits: Predictions before sigmoid (B, 1, H, W)
            targets: Ground truth binary masks (B, 1, H, W)
        """
        preds = torch.sigmoid(logits)
        
        # Flatten predictions and targets
        preds_flat = preds.view(-1)
        targets_flat = targets.view(-1)
        
        intersection = (preds_flat * targets_flat).sum()
        union = preds_flat.sum() + targets_flat.sum()
        
        dice = (2. * intersection + self.smooth) / (union + self.smooth)
        return 1.0 - dice


class BCEDiceLoss(nn.Module):
    """
    Combined BCE + Dice Loss.
    Standard loss for polyp segmentation (used by PraNet, SANet, HarDNet-MSEG).
    """
    def __init__(self, bce_weight: float = 1.0, dice_weight: float = 1.0, smooth: float = 1.0):
        super().__init__()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight
        self.bce = nn.BCEWithLogitsLoss()
        self.dice = SoftDiceLoss(smooth=smooth)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce_loss = self.bce(logits, targets)
        dice_loss = self.dice(logits, targets)
        return self.bce_weight * bce_loss + self.dice_weight * dice_loss


class BoundaryLoss(nn.Module):
    """
    Boundary-aware loss penalizing predictions at boundary regions more heavily.
    Reference: Kervadec et al., 'Boundary loss for highly unbalanced segmentation' (2019)
    """
    def __init__(self):
        super().__init__()

    def get_sdm(self, mask: np.ndarray) -> np.ndarray:
        """Computes Signed Distance Map (SDM)"""
        pos_mask = mask > 0.5
        neg_mask = ~pos_mask
        
        res = np.zeros_like(mask, dtype=np.float32)
        if pos_mask.any():
            res[pos_mask] = - distance_transform_edt(pos_mask)[pos_mask] + 1
        if neg_mask.any():
            res[neg_mask] = distance_transform_edt(neg_mask)[neg_mask]
        
        return res

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Args:
            logits: (B, 1, H, W)
            targets: (B, 1, H, W)
        """
        preds = torch.sigmoid(logits)
        
        with torch.no_grad():
            targets_np = targets.cpu().numpy()
            sdm = np.zeros_like(targets_np, dtype=np.float32)
            for b in range(targets_np.shape[0]):
                for c in range(targets_np.shape[1]):
                    sdm[b, c] = self.get_sdm(targets_np[b, c])
            sdm_tensor = torch.from_numpy(sdm).to(logits.device)
            
        # The boundary loss integrates the SDM over the predicted probabilities
        loss = (preds * sdm_tensor).mean()
        return loss


class DeepSupervisionLoss(nn.Module):
    """
    Applies a base loss at multiple scales.
    Used for Phase 6 ablation (e.g., outputs from decoder layers).
    """
    def __init__(self, base_loss: nn.Module, weights: List[float] = [1.0, 0.5, 0.25, 0.125]):
        super().__init__()
        self.base_loss = base_loss
        self.weights = weights

    def forward(self, logits: Union[torch.Tensor, Dict[str, torch.Tensor]], targets: torch.Tensor) -> torch.Tensor:
        if isinstance(logits, torch.Tensor):
            return self.base_loss(logits, targets)
            
        total_loss = 0.0
        for i, (key, logit_scale) in enumerate(logits.items()):
            weight = self.weights[i] if i < len(self.weights) else 0.0
            if weight == 0.0:
                continue
                
            # Resize targets to match logit_scale if needed
            if logit_scale.shape[2:] != targets.shape[2:]:
                target_scale = F.interpolate(targets, size=logit_scale.shape[2:], mode='nearest')
            else:
                target_scale = targets
                
            total_loss += weight * self.base_loss(logit_scale, target_scale)
            
        return total_loss

class BCEDiceBoundaryLoss(nn.Module):
    """
    Combined BCE + Dice + Boundary Loss.
    """
    def __init__(self, bce_weight: float = 1.0, dice_weight: float = 1.0, boundary_weight: float = 1.0):
        super().__init__()
        self.bce_dice = BCEDiceLoss(bce_weight, dice_weight)
        self.boundary = BoundaryLoss()
        self.boundary_weight = boundary_weight
        
    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        loss = self.bce_dice(logits, targets)
        loss += self.boundary_weight * self.boundary(logits, targets)
        return loss


def build_loss(config: dict) -> nn.Module:
    """
    Factory function for building loss functions based on config.
    
    Args:
        config: Dict containing 'type' and loss parameters.
                Supported types: 'bce_dice', 'dice', 'boundary', 'bce_dice_boundary'.
    """
    loss_type = config.get('type', 'bce_dice').lower()
    
    if loss_type == 'bce_dice':
        return BCEDiceLoss(
            bce_weight=config.get('bce_weight', 1.0),
            dice_weight=config.get('dice_weight', 1.0),
            smooth=config.get('smooth', 1.0)
        )
    elif loss_type == 'dice':
        return SoftDiceLoss(smooth=config.get('smooth', 1.0))
    elif loss_type == 'boundary':
        return BoundaryLoss()
    elif loss_type == 'bce_dice_boundary':
        return BCEDiceBoundaryLoss(
            bce_weight=config.get('bce_weight', 1.0),
            dice_weight=config.get('dice_weight', 1.0),
            boundary_weight=config.get('boundary_weight', 1.0)
        )
    else:
        raise ValueError(f"Unsupported loss type: {loss_type}")
