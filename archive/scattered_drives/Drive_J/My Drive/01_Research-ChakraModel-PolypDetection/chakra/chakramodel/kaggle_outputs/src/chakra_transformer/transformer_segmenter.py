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
        self.backbone = timm.create_model(
            backbone_name, 
            pretrained=pretrained, 
            features_only=False,
            drop_rate=0.1,
            attn_drop_rate=0.1
        )
        
        # In a standard ViT Large, the feature dimension is usually 1024
        self.embed_dim = self.backbone.embed_dim
        
        # Simple segmentation head (Progressive upsampling)
        # 384/16 = 24x24 grid. 
        self.decode_head = nn.Sequential(
            nn.ConvTranspose2d(self.embed_dim, 256, kernel_size=4, stride=4),  # 0
            nn.BatchNorm2d(256), # 1
            nn.ReLU(inplace=True), # 2
            nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4),   # 3
            nn.BatchNorm2d(64), # 4
            nn.ReLU(inplace=True), # 5
            nn.Conv2d(64, num_classes, kernel_size=3, padding=1) # 6
        )
        self.dropout1 = nn.Dropout2d(p=0.5)
        self.dropout2 = nn.Dropout2d(p=0.5)

    def enable_mc_dropout(self):
        """Enable Dropout layers during evaluation for Monte Carlo sampling."""
        for m in self.modules():
            name = m.__class__.__name__
            if name.startswith('Dropout') or 'DropPath' in name:
                m.train()

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
            
        # Decode into segmentation mask applying MC dropout manually to preserve state_dict
        x_dec = features
        for i, layer in enumerate(self.decode_head):
            x_dec = layer(x_dec)
            if i == 2:
                x_dec = self.dropout1(x_dec)
            elif i == 5:
                x_dec = self.dropout2(x_dec)
        logits = x_dec
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
