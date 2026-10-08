"""
Model architectures for Colonoscopy Polyp Detection.

Supports transfer learning with pre-trained models from torchvision.
"""

import torch
import torch.nn as nn
import torchvision.models as models
from typing import Optional


class PolypClassifier(nn.Module):
    """Transfer learning-based classifier for polyp detection.
    
    Uses a pre-trained backbone (ResNet-50 or EfficientNet-B4)
    with a custom classification head.
    
    Args:
        model_name: Name of the backbone ('resnet50' or 'efficientnet_b4')
        num_classes: Number of output classes (default: 2)
        pretrained: Whether to use pre-trained weights (default: True)
        freeze_backbone: Whether to freeze backbone layers (default: True)
        dropout_rate: Dropout rate for the classifier head (default: 0.3)
    """
    
    SUPPORTED_MODELS = ['resnet50', 'efficientnet_b4']
    
    def __init__(
        self,
        model_name: str = 'efficientnet_b4',
        num_classes: int = 2,
        pretrained: bool = True,
        freeze_backbone: bool = True,
        dropout_rate: float = 0.3
    ):
        super().__init__()
        
        if model_name not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Model '{model_name}' not supported. "
                f"Choose from: {self.SUPPORTED_MODELS}"
            )
        
        self.model_name = model_name
        self.num_classes = num_classes
        
        # Load backbone
        if model_name == 'resnet50':
            weights = models.ResNet50_Weights.DEFAULT if pretrained else None
            self.backbone = models.resnet50(weights=weights)
            in_features = self.backbone.fc.in_features
            self.backbone.fc = nn.Identity()  # Remove original classifier
            
        elif model_name == 'efficientnet_b4':
            weights = models.EfficientNet_B4_Weights.DEFAULT if pretrained else None
            self.backbone = models.efficientnet_b4(weights=weights)
            in_features = self.backbone.classifier[1].in_features
            self.backbone.classifier = nn.Identity()  # Remove original classifier
        
        # Freeze backbone if requested
        if freeze_backbone:
            self._freeze_backbone()
        
        # Custom classification head
        self.classifier = nn.Sequential(
            nn.Dropout(dropout_rate),
            nn.Linear(in_features, 512),
            nn.ReLU(inplace=True),
            nn.BatchNorm1d(512),
            nn.Dropout(dropout_rate / 2),
            nn.Linear(512, num_classes)
        )
        
        # Initialize classifier weights
        self._init_classifier()
    
    def _freeze_backbone(self):
        """Freeze all backbone parameters."""
        for param in self.backbone.parameters():
            param.requires_grad = False
        print(f"Backbone ({self.model_name}) frozen.")
    
    def unfreeze_backbone(self, num_layers: Optional[int] = None):
        """Unfreeze backbone layers for fine-tuning.
        
        Args:
            num_layers: Number of layers to unfreeze from the end.
                       None = unfreeze all layers.
        """
        if num_layers is None:
            for param in self.backbone.parameters():
                param.requires_grad = True
            print(f"All backbone layers unfrozen.")
        else:
            params = list(self.backbone.parameters())
            for param in params[-num_layers:]:
                param.requires_grad = True
            print(f"Last {num_layers} backbone layers unfrozen.")
    
    def _init_classifier(self):
        """Initialize classifier head with Kaiming initialization."""
        for m in self.classifier.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.
        
        Args:
            x: Input tensor of shape (batch_size, 3, H, W)
            
        Returns:
            Logits of shape (batch_size, num_classes)
        """
        features = self.backbone(x)
        logits = self.classifier(features)
        return logits
    
    def get_trainable_params(self) -> int:
        """Count number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
    
    def get_total_params(self) -> int:
        """Count total number of parameters."""
        return sum(p.numel() for p in self.parameters())


def build_model(config: dict) -> PolypClassifier:
    """Factory function to build model from config dictionary.
    
    Args:
        config: Dictionary with model configuration
        
    Returns:
        Initialized PolypClassifier
    """
    model = PolypClassifier(
        model_name=config.get('name', 'efficientnet_b4'),
        num_classes=config.get('num_classes', 2),
        pretrained=config.get('pretrained', True),
        freeze_backbone=config.get('freeze_backbone', True),
    )
    
    print(f"\nModel: {model.model_name}")
    print(f"Total params: {model.get_total_params():,}")
    print(f"Trainable params: {model.get_trainable_params():,}")
    
    return model


if __name__ == "__main__":
    # Quick test
    model = build_model({'name': 'efficientnet_b4', 'num_classes': 2})
    dummy_input = torch.randn(2, 3, 384, 384)
    output = model(dummy_input)
    print(f"\nInput shape: {dummy_input.shape}")
    print(f"Output shape: {output.shape}")
    print("Model test passed! ✅")
