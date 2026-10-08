import torch
import torch.nn as nn
import torch.nn.functional as F
import timm

class ChakraTransformerSegmenter(nn.Module):
    """
    High-Accuracy Vision Transformer (ViT) based segmentation model for Polyp Detection.
    Upgraded to ViT-Large with 384x384 resolution since hardware is not a limitation.
    """
    def __init__(self, backbone_name='vit_large_patch16_384', pretrained=True, num_classes=1):
        super(ChakraTransformerSegmenter, self).__init__()
        
        # We use timm to fetch a powerful pretrained Vision Transformer backbone
        self.backbone = timm.create_model(backbone_name, pretrained=pretrained, features_only=False)
        
        # In a standard ViT Large, the feature dimension is usually 1024
        self.embed_dim = self.backbone.embed_dim
        
        # Decode the patch grid progressively. Keeping the feature map at each
        # stage gives the mask head more capacity to recover object boundaries
        # than a single large upsampling operation.
        self.decode_head = nn.Sequential(
            nn.ConvTranspose2d(self.embed_dim, 512, kernel_size=2, stride=2),  # 24x24 -> 48x48
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(512, 256, kernel_size=2, stride=2),  # 48x48 -> 96x96
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(256, 128, kernel_size=2, stride=2),  # 96x96 -> 192x192
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2),   # 192x192 -> 384x384
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, num_classes, kernel_size=1)
        )

    def forward(self, x):
        B, C, H, W = x.shape
        
        # Extract features from ViT backbone
        features = self.backbone.forward_features(x)
        
        # Ensure it's the patch tokens (B, N, C) -> (B, C, H', W')
        if features.dim() == 3:
            # Drop CLS token if present
            if features.shape[1] == (H // 16) * (W // 16) + 1:
                features = features[:, 1:]
            
            grid_h = H // 16
            grid_w = W // 16
            features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)
            
        # Decode into segmentation mask
        logits = self.decode_head(features)
        
        # Upsample if output doesn't match input exactly
        if logits.shape[2:] != (H, W):
            logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)
            
        return logits

if __name__ == "__main__":
    # Test the model with dummy data
    model = ChakraTransformerSegmenter()
    dummy_input = torch.randn(2, 3, 384, 384)
    output = model(dummy_input)
    print(f"Model output shape: {output.shape} (Expected: [2, 1, 384, 384])")
