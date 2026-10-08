import torch
import torch.nn as nn
import torch.nn.functional as F

from .backbones import build_backbone

class ConvBlock(nn.Module):
    """
    Standard convolution block for U-Net.
    Consists of 2x (Conv3x3 -> BatchNorm2d -> ReLU).
    """
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class DecoderBlock(nn.Module):
    """
    U-Net decoder block.
    Bilinear upsampling -> concat with skip -> ConvBlock.
    """
    def __init__(self, in_channels: int, skip_channels: int, out_channels: int):
        super().__init__()
        self.conv = ConvBlock(in_channels + skip_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor = None) -> torch.Tensor:
        x = F.interpolate(x, scale_factor=2.0, mode='bilinear', align_corners=False)
        if skip is not None:
            # Ensure dimensions match in case of rounding differences
            if x.shape[2:] != skip.shape[2:]:
                x = F.interpolate(x, size=skip.shape[2:], mode='bilinear', align_corners=False)
            x = torch.cat([x, skip], dim=1)
        return self.conv(x)


class UNet(nn.Module):
    """
    U-Net architecture with a pluggable backbone encoder.
    
    Supports any backbone registered in backbones.py:
      - Standard timm CNNs (resnet50, efficientnet_b3, etc.)
      - DINOv2 ViT (vit_base_patch14_dinov2.lvd142m)
      - EndoViT (MAE pre-trained on Endo700k)
      - PVT-v2 hierarchical transformers (pvt_v2_b2)
    
    The backbone is selected entirely via the model config dict.
    
    References:
    - Ronneberger et al., "U-Net: Convolutional Networks for Biomedical Image Segmentation", 2015.
    """
    def __init__(self, config: dict = None, backbone: str = 'resnet50', pretrained: bool = True):
        super().__init__()
        
        # 1. Encoder — use the unified backbone factory
        if config is not None:
            self.encoder = build_backbone(config)
        else:
            # Legacy fallback for backward compatibility
            self.encoder = build_backbone({
                'backbone': backbone,
                'pretrained': pretrained,
                'pretrained_source': 'imagenet',
            })
        
        # Get encoder feature channels from the backbone
        enc_ch = self.encoder.feature_channels
        
        # 2. Decoder
        # Decoder channels: [256, 128, 64, 32, 16]
        # Level 1: 1/32 -> 1/16
        self.dec1 = DecoderBlock(enc_ch[4], enc_ch[3], 256)
        # Level 2: 1/16 -> 1/8
        self.dec2 = DecoderBlock(256, enc_ch[2], 128)
        # Level 3: 1/8 -> 1/4
        self.dec3 = DecoderBlock(128, enc_ch[1], 64)
        # Level 4: 1/4 -> 1/2
        self.dec4 = DecoderBlock(64, enc_ch[0], 32)
        # Level 5: 1/2 -> 1/1 (no skip connection from stem)
        self.dec5 = DecoderBlock(32, 0, 16)
        
        # 3. Final layer
        self.final_conv = nn.Conv2d(16, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> dict:
        """
        Args:
            x: Input image tensor of shape (B, 3, H, W) where H, W are divisible by 32.
        Returns:
            dict: Contains 'pred' with the output logit map of shape (B, 1, H, W).
        """
        # Encode
        features = self.encoder(x)
        f0, f1, f2, f3, f4 = features
        
        # Decode
        d1 = self.dec1(f4, f3)
        d2 = self.dec2(d1, f2)
        d3 = self.dec3(d2, f1)
        d4 = self.dec4(d3, f0)
        d5 = self.dec5(d4)  # No skip for the final upsample to original resolution
        
        # Final output
        logits = self.final_conv(d5)
        
        return {'pred': logits}


if __name__ == '__main__':
    # Test block — verify UNet works with different backbone configs
    
    configs = [
        {
            'name': 'ResNet-50 (ImageNet)',
            'architecture': 'unet',
            'backbone': 'resnet50',
            'pretrained': False,
            'pretrained_source': 'imagenet',
        },
    ]
    
    for cfg in configs:
        print(f"\n{'='*60}")
        print(f"Testing: {cfg['name']}")
        print(f"{'='*60}")
        
        model = UNet(config=cfg)
        dummy_x = torch.randn(2, 3, 352, 352)
        
        outputs = model(dummy_x)
        pred = outputs['pred']
        
        print(f"Input shape:  {dummy_x.shape}")
        print(f"Output shape: {pred.shape}")
        
        num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"Trainable parameters: {num_params / 1e6:.2f} M")
        print(f"Encoder channels: {model.encoder.feature_channels}")

