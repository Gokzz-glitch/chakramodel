"""
ResNet-18 Visual Perception Backbone with Spatial Feature Projection Head
"""

import torch
import torch.nn as nn
from typing import Optional


class BasicBlock(nn.Module):
    """Standard ResNet Residual Block."""
    expansion = 1

    def __init__(self, in_planes: int, planes: int, stride: int = 1):
        super(BasicBlock, self).__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion * planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion * planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion * planes)
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        out = self.relu(out)
        return out


class NativeResNet18(nn.Module):
    """Pure PyTorch ResNet-18 Architecture (Zero External Dependency)."""

    def __init__(self):
        super().__init__()
        self.in_planes = 64
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        self.layer1 = self._make_layer(64, 2, stride=1)
        self.layer2 = self._make_layer(128, 2, stride=2)
        self.layer3 = self._make_layer(256, 2, stride=2)
        self.layer4 = self._make_layer(512, 2, stride=2)
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))

    def _make_layer(self, planes: int, num_blocks: int, stride: int) -> nn.Sequential:
        strides = [stride] + [1] * (num_blocks - 1)
        layers = []
        for s in strides:
            layers.append(BasicBlock(self.in_planes, planes, s))
            self.in_planes = planes * BasicBlock.expansion
        return nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.maxpool(out)
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        out = self.avgpool(out)
        return torch.flatten(out, 1)


class VisionBackbone(nn.Module):
    """
    Perception module extracting latent visual embeddings from raw RGB images.
    """

    def __init__(
        self,
        latent_dim: int = 128,
        pretrained: bool = True,
        freeze_backbone: bool = True,
    ):
        super().__init__()
        self.latent_dim = latent_dim

        # Use torchvision if available, otherwise pure PyTorch NativeResNet18
        try:
            from torchvision.models import resnet18, ResNet18_Weights
            weights = ResNet18_Weights.DEFAULT if pretrained else None
            resnet = resnet18(weights=weights)
            resnet.fc = nn.Identity()
            self.backbone = resnet
        except Exception:
            self.backbone = NativeResNet18()

        # Freeze visual representation parameters if requested
        if freeze_backbone:
            for param in self.backbone.parameters():
                param.requires_grad = False
            self.backbone.eval()

        # Learnable spatial projection head mapping 512-dim visual features to latent_dim
        self.projection_head = nn.Sequential(
            nn.Linear(512, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Dropout(p=0.05),
            nn.Linear(256, latent_dim),
            nn.LayerNorm(latent_dim),
            nn.ReLU(),
        )

        # ImageNet normalization buffers
        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass for RGB visual stream.
        
        Args:
            x (torch.Tensor): Shape (B, H, W, 3) or (B, 3, H, W) in [0, 255] or [0, 1]
            
        Returns:
            latent_embeddings (torch.Tensor): Shape (B, latent_dim)
        """
        # Convert (B, H, W, C) -> (B, C, H, W)
        if x.dim() == 4 and x.shape[-1] == 3:
            x = x.permute(0, 3, 1, 2)

        # Scale uint8 [0, 255] to float32 [0.0, 1.0]
        if x.max() > 1.0:
            x = x / 255.0

        # Normalize with ImageNet channel statistics
        x_norm = (x - self.mean) / self.std

        # Extract 512-dim visual representation
        with torch.set_grad_enabled(not self.backbone.training):
            feat = self.backbone(x_norm)

        # Project to policy latent space
        return self.projection_head(feat)
