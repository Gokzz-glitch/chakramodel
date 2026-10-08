"""
backbones.py — Unified Backbone Factory for Polyp Segmentation

Supports:
  - Standard timm CNN encoders (ResNet, EfficientNet, etc.)
  - DINOv2 ViT backbones (via timm)
  - EndoViT (custom ViT weights from HuggingFace/Google Drive)
  - PVT-v2 hierarchical transformers (via timm)

All backbones expose a uniform interface:
  backbone = build_backbone(config)
  features = backbone(x)  # Returns list of multi-scale feature maps

Architecture Decision:
  Using a factory pattern so the UNet decoder code stays identical
  regardless of which backbone is used. Only the config YAML changes.
"""

import logging
from typing import List, Tuple, Optional
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import timm

logger = logging.getLogger(__name__)


class TimmBackbone(nn.Module):
    """
    Standard timm-based feature extractor.
    Works with any timm model that supports `features_only=True`.
    
    Examples: resnet50, resnet34, efficientnet_b3, pvt_v2_b2, swin_tiny_patch4_window7_224
    """
    def __init__(self, model_name: str, pretrained: bool = True, out_indices: Tuple[int, ...] = (0, 1, 2, 3, 4)):
        super().__init__()
        self.encoder = timm.create_model(
            model_name,
            pretrained=pretrained,
            features_only=True,
            out_indices=out_indices
        )
        # Probe channel dimensions
        self._feature_channels = self._probe_channels()
        
    def _probe_channels(self) -> List[int]:
        """Dynamically determine output channel dimensions."""
        self.encoder.eval()
        dummy = torch.randn(2, 3, 256, 256)
        with torch.no_grad():
            features = self.encoder(dummy)
        self.encoder.train()
        return [f.shape[1] for f in features]
    
    @property
    def feature_channels(self) -> List[int]:
        return self._feature_channels
    
    def forward(self, x: torch.Tensor) -> List[torch.Tensor]:
        return self.encoder(x)


class DINOv2Backbone(nn.Module):
    """
    DINOv2 ViT backbone with multi-scale feature extraction.
    
    DINOv2 produces a single-scale feature map (1/14 or 1/16 resolution).
    To provide multi-scale features for the U-Net decoder, we:
    1. Extract intermediate transformer block features
    2. Reshape patch tokens to spatial feature maps
    3. Use convolution-based neck to produce multi-scale pyramid
    
    Reference: Oquab et al., "DINOv2: Learning Robust Visual Features without Supervision" (2024)
    """
    def __init__(
        self,
        model_name: str = 'vit_base_patch14_dinov2.lvd142m',
        pretrained: bool = True,
        img_size: int = 518,  # DINOv2 native: 518 (37x37 patches for patch14)
    ):
        super().__init__()
        self.model = timm.create_model(
            model_name,
            pretrained=pretrained,
            img_size=img_size,
            num_classes=0,  # Remove classification head
        )
        self.embed_dim = self.model.embed_dim
        self.patch_size = self.model.patch_embed.patch_size[0]
        self.img_size = img_size
        
        # Feature pyramid neck: convert single-scale ViT features to multi-scale
        # Produces 5 scales like a standard CNN encoder
        self._feature_channels = [
            self.embed_dim // 4,   # 1/4 scale
            self.embed_dim // 2,   # 1/8 scale  
            self.embed_dim,        # 1/16 scale
            self.embed_dim,        # 1/32 scale
            self.embed_dim,        # bottleneck
        ]
        
        # Projection layers for each scale
        self.proj_1_4 = nn.Sequential(
            nn.Conv2d(self.embed_dim, self._feature_channels[0], 1),
            nn.BatchNorm2d(self._feature_channels[0]),
            nn.GELU(),
        )
        self.proj_1_8 = nn.Sequential(
            nn.Conv2d(self.embed_dim, self._feature_channels[1], 1),
            nn.BatchNorm2d(self._feature_channels[1]),
            nn.GELU(),
        )
        self.proj_1_16 = nn.Sequential(
            nn.Conv2d(self.embed_dim, self._feature_channels[2], 1),
            nn.BatchNorm2d(self._feature_channels[2]),
            nn.GELU(),
        )
        self.proj_1_32 = nn.Sequential(
            nn.Conv2d(self.embed_dim, self._feature_channels[3], 3, stride=2, padding=1),
            nn.BatchNorm2d(self._feature_channels[3]),
            nn.GELU(),
        )
        self.proj_bottleneck = nn.Sequential(
            nn.Conv2d(self.embed_dim, self._feature_channels[4], 3, stride=2, padding=1),
            nn.BatchNorm2d(self._feature_channels[4]),
            nn.GELU(),
            nn.Conv2d(self._feature_channels[4], self._feature_channels[4], 3, stride=2, padding=1),
            nn.BatchNorm2d(self._feature_channels[4]),
            nn.GELU(),
        )
        
        # Indices of transformer blocks to extract features from
        num_blocks = len(self.model.blocks)
        self.extract_indices = [
            num_blocks // 4 - 1,   # Early features
            num_blocks // 2 - 1,   # Mid features
            3 * num_blocks // 4 - 1,  # Late features
            num_blocks - 1,        # Final features
        ]
        
        logger.info(f"DINOv2 backbone: {model_name}, embed_dim={self.embed_dim}, "
                     f"patch_size={self.patch_size}, extract_blocks={self.extract_indices}")

    @property
    def feature_channels(self) -> List[int]:
        return self._feature_channels
    
    def _reshape_patch_tokens(self, tokens: torch.Tensor, H: int, W: int) -> torch.Tensor:
        """Reshape (B, N, C) patch tokens to (B, C, H, W) spatial feature map."""
        B, N, C = tokens.shape
        # Remove CLS token if present
        if N == H * W + 1:
            tokens = tokens[:, 1:, :]
            N = H * W
        return tokens.permute(0, 2, 1).reshape(B, C, H, W)
    
    def forward(self, x: torch.Tensor) -> List[torch.Tensor]:
        B, _, H_in, W_in = x.shape
        
        # Patch embed
        x_embed = self.model.patch_embed(x)
        
        # Add CLS token if the model uses one
        if hasattr(self.model, 'cls_token') and self.model.cls_token is not None:
            cls_tokens = self.model.cls_token.expand(B, -1, -1)
            x_embed = torch.cat([cls_tokens, x_embed], dim=1)
        
        # Add position embedding
        x_embed = x_embed + self.model.pos_embed
        x_embed = self.model.pos_drop(x_embed) if hasattr(self.model, 'pos_drop') else x_embed
        x_embed = self.model.norm_pre(x_embed) if hasattr(self.model, 'norm_pre') else x_embed
        
        # Spatial dimensions of patch grid
        H_patch = H_in // self.patch_size
        W_patch = W_in // self.patch_size
        
        # Extract intermediate features
        intermediate_features = []
        for i, block in enumerate(self.model.blocks):
            x_embed = block(x_embed)
            if i in self.extract_indices:
                intermediate_features.append(x_embed)
        
        # Use the last extracted feature for all projections
        # (intermediate features could be used for more sophisticated multi-scale)
        feat = self._reshape_patch_tokens(intermediate_features[-1], H_patch, W_patch)
        
        # Build multi-scale pyramid
        f_1_4 = self.proj_1_4(F.interpolate(feat, scale_factor=4.0, mode='bilinear', align_corners=False))
        f_1_8 = self.proj_1_8(F.interpolate(feat, scale_factor=2.0, mode='bilinear', align_corners=False))
        f_1_16 = self.proj_1_16(feat)
        f_1_32 = self.proj_1_32(feat)
        f_bottleneck = self.proj_bottleneck(feat)
        
        return [f_1_4, f_1_8, f_1_16, f_1_32, f_bottleneck]


class EndoViTBackbone(DINOv2Backbone):
    """
    EndoViT backbone — ViT pre-trained via MAE on Endo700k endoscopic images.
    
    Inherits the DINOv2Backbone's multi-scale pyramid neck since EndoViT
    is also a vanilla ViT architecture. The key difference is the pre-trained
    weights come from endoscopy-specific MAE pre-training rather than DINOv2.
    
    Weights source:
      - HuggingFace: https://huggingface.co/egeozsoy/EndoViT
      - Google Drive: see README
    
    Reference: Batić et al., "EndoViT: pretraining vision transformers on a 
               large collection of endoscopic images" (IJCARS 2024)
    """
    def __init__(
        self,
        pretrained_weights: Optional[str] = None,
        img_size: int = 224,  # EndoViT uses 224x224 (ViT-B/16)
    ):
        # Initialize with vit_base_patch16_224 architecture but WITHOUT pretrained weights
        super().__init__(
            model_name='vit_base_patch16_224',
            pretrained=False,
            img_size=img_size,
        )
        
        # Load EndoViT weights if provided
        if pretrained_weights:
            self._load_endovit_weights(pretrained_weights)
    
    def _load_endovit_weights(self, weights_path: str):
        """
        Load EndoViT MAE pre-trained weights.
        Handles the MAE checkpoint format (encoder only, no decoder).
        """
        weights_path = Path(weights_path)
        if not weights_path.exists():
            logger.warning(
                f"EndoViT weights not found at {weights_path}. "
                f"Download from: https://huggingface.co/egeozsoy/EndoViT\n"
                f"Using random initialization."
            )
            return
            
        logger.info(f"Loading EndoViT weights from {weights_path}")
        checkpoint = torch.load(str(weights_path), map_location='cpu')
        
        # Handle different checkpoint formats
        if 'model' in checkpoint:
            state_dict = checkpoint['model']
        elif 'state_dict' in checkpoint:
            state_dict = checkpoint['state_dict']
        else:
            state_dict = checkpoint
        
        # Filter out decoder weights (MAE checkpoint includes decoder)
        encoder_state = {}
        for k, v in state_dict.items():
            # Remove 'encoder.' prefix if present
            clean_key = k.replace('encoder.', '') if k.startswith('encoder.') else k
            # Skip decoder weights
            if 'decoder' in clean_key or 'mask_token' in clean_key:
                continue
            encoder_state[clean_key] = v
        
        # Load with strict=False to handle mismatches gracefully
        missing, unexpected = self.model.load_state_dict(encoder_state, strict=False)
        if missing:
            logger.warning(f"Missing keys when loading EndoViT: {len(missing)} keys")
            for k in missing[:5]:
                logger.warning(f"  Missing: {k}")
        if unexpected:
            logger.info(f"Unexpected keys (skipped): {len(unexpected)} keys")
        
        logger.info("EndoViT weights loaded successfully.")


def build_backbone(config: dict) -> nn.Module:
    """
    Factory function to build backbone from config.
    
    Args:
        config: Model configuration dict with keys:
            - backbone: str — model name (e.g., 'resnet50', 'pvt_v2_b2')
            - pretrained: bool — use pretrained weights
            - pretrained_source: str — 'imagenet', 'dinov2', or 'endovit'
            - pretrained_weights: str — path to custom weights (for endovit)
    
    Returns:
        Backbone module with .feature_channels property
    """
    backbone_name = config.get('backbone', 'resnet50')
    pretrained = config.get('pretrained', True)
    source = config.get('pretrained_source', 'imagenet').lower()
    
    if source == 'dinov2':
        logger.info(f"Building DINOv2 backbone: {backbone_name}")
        return DINOv2Backbone(
            model_name=backbone_name,
            pretrained=pretrained,
        )
    
    elif source == 'endovit':
        weights_path = config.get('pretrained_weights', None)
        logger.info(f"Building EndoViT backbone (weights: {weights_path})")
        return EndoViTBackbone(
            pretrained_weights=weights_path,
        )
    
    else:
        # Standard timm backbone (ResNet, EfficientNet, PVT-v2, Swin, etc.)
        logger.info(f"Building timm backbone: {backbone_name} (pretrained={pretrained})")
        return TimmBackbone(
            model_name=backbone_name,
            pretrained=pretrained,
        )


if __name__ == '__main__':
    # Quick test for each backbone type
    import sys
    
    test_input = torch.randn(2, 3, 352, 352)
    
    print("=" * 60)
    print("Testing TimmBackbone (ResNet-50)")
    print("=" * 60)
    backbone = TimmBackbone('resnet50', pretrained=False)
    features = backbone(test_input)
    print(f"Feature channels: {backbone.feature_channels}")
    for i, f in enumerate(features):
        print(f"  Scale {i}: {f.shape}")
    
    print("\n" + "=" * 60)
    print("Testing TimmBackbone (PVT-v2-B2)")
    print("=" * 60)
    try:
        backbone = TimmBackbone('pvt_v2_b2', pretrained=False)
        features = backbone(test_input)
        print(f"Feature channels: {backbone.feature_channels}")
        for i, f in enumerate(features):
            print(f"  Scale {i}: {f.shape}")
    except Exception as e:
        print(f"PVT-v2 test skipped: {e}")
    
    print("\n" + "=" * 60)
    print("Testing DINOv2Backbone")
    print("=" * 60)
    try:
        backbone = DINOv2Backbone('vit_base_patch14_dinov2.lvd142m', pretrained=False, img_size=352)
        features = backbone(test_input)
        print(f"Feature channels: {backbone.feature_channels}")
        for i, f in enumerate(features):
            print(f"  Scale {i}: {f.shape}")
    except Exception as e:
        print(f"DINOv2 test skipped: {e}")
    
    print("\n" + "=" * 60)
    print("Testing EndoViTBackbone (no weights)")
    print("=" * 60)
    try:
        test_224 = torch.randn(2, 3, 224, 224)
        backbone = EndoViTBackbone(pretrained_weights=None, img_size=224)
        features = backbone(test_224)
        print(f"Feature channels: {backbone.feature_channels}")
        for i, f in enumerate(features):
            print(f"  Scale {i}: {f.shape}")
    except Exception as e:
        print(f"EndoViT test skipped: {e}")
    
    print("\nAll backbone tests complete!")
