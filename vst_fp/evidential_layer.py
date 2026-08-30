import torch
import torch.nn as nn
import torch.nn.functional as F

class EvidentialDecisionEngine(nn.Module):
    """
    Stage 4: Evidential Decision Engine (Uncertainty Calibration).
    Replaces standard softmax outputs with parameterized Dirichlet distributions
    to distinguish between aleatoric and epistemic uncertainty.
    """
    def __init__(self, in_channels=1, num_classes=2):
        super().__init__()
        # In this mock, we map the verified mask into evidence for background (0) and polyp (1)
        self.evidence_layer = nn.Sequential(
            nn.Conv3d(in_channels, num_classes, kernel_size=1),
            nn.Softplus() # Evidence must be non-negative
        )

    def forward(self, verified_masks):
        """
        Args:
            verified_masks: Tensor of shape (B, 1, T, H, W)
        Returns:
            alpha: Dirichlet parameters (B, num_classes, T, H, W)
            uncertainty: Total uncertainty map (B, 1, T, H, W)
        """
        # Generate evidence for each class
        evidence = self.evidence_layer(verified_masks)
        
        # Alpha = evidence + 1
        alpha = evidence + 1.0
        
        # Total certainty is sum of alpha
        S = torch.sum(alpha, dim=1, keepdim=True)
        
        # Uncertainty = K / S (where K is num_classes)
        num_classes = alpha.shape[1]
        uncertainty = num_classes / S
        
        return alpha, uncertainty
