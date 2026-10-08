import torch
import torch.nn as nn
from timm.models.vision_transformer import VisionTransformer


class ImageEncoder(nn.Module):
    """Vision Transformer image encoder for fetal ultrasound classification."""
    
    def __init__(self, num_classes=2, embed_dim=384, depth=12, num_heads=6, pretrained=False):
        super().__init__()
        self.vit = VisionTransformer(
            img_size=224,
            patch_size=16,
            in_chans=3,
            num_classes=num_classes,
            embed_dim=embed_dim,
            depth=depth,
            num_heads=num_heads,
            mlp_ratio=4.0,
            drop_rate=0.0,
            attn_drop_rate=0.0,
            drop_path_rate=0.0,
        )
    
    def forward(self, x):
        return self.vit(x)


class TabularEncoder(nn.Module):
    """Transformer-based tabular feature encoder for clinical features."""
    
    def __init__(self, input_dim=1, embed_dim=128, num_heads=4, num_layers=2, num_classes=1, flatten=False):
        super().__init__()
        self.flatten = flatten
        # Simple embedding from input to embed_dim
        self.embedding = nn.Linear(input_dim, embed_dim)
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=2048,
            batch_first=True,
            activation='relu'
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Output layers (matching checkpoint exactly)
        if flatten:
            # Checkpoint flattens transformer output before linear
            # For sequence length 97 (or similar), this creates large dimension
            self.linear = nn.Sequential(
                nn.Linear(12416, 128),  # Flattened transformer output from checkpoint
            )
        else:
            self.linear = nn.Sequential(
                nn.Linear(embed_dim, 128),  # Project from embed_dim to 128
            )
        
        self.mlp = nn.Sequential(
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, num_classes),
        )
    
    def forward(self, x):
        # x shape: (batch, input_dim) - assume input_dim=1 for single features
        if len(x.shape) == 1:
            x = x.unsqueeze(-1)
        x = self.embedding(x)  # (batch, 1, embed_dim)
        x = self.transformer(x)  # (batch, 1, embed_dim)
        
        if self.flatten:
            x = x.reshape(x.size(0), -1)  # Flatten: (batch, 1*embed_dim)
        else:
            # Handle both 2D and 3D outputs
            if len(x.shape) == 3:
                x = x.mean(dim=1)  # Average pooling: (batch, embed_dim)
        
        x = self.linear(x)  # (batch, 128)
        x = self.mlp(x)  # (batch, num_classes)
        return x


class MultimodalClassifier(nn.Module):
    """Combined image + tabular feature classifier for CHD prediction."""
    
    def __init__(self, num_classes=2, fusion_dim=128):
        super().__init__()
        self.image_encoder = ImageEncoder(num_classes=fusion_dim, embed_dim=384, depth=12, num_heads=6)
        self.tabular_encoder = TabularEncoder(input_dim=1, embed_dim=128, num_heads=4, num_layers=2, num_classes=fusion_dim)
        self.classifier = nn.Linear(fusion_dim * 2, num_classes)
    
    def forward(self, image, tabular):
        img_feat = self.image_encoder(image)
        tab_feat = self.tabular_encoder(tabular)
        combined = torch.cat([img_feat, tab_feat], dim=1)
        return self.classifier(combined)
