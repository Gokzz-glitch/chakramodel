import torch
import torch.nn as nn
import torch.nn.functional as F
import timm

class DecoderStage(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.block = nn.Sequential(
            nn.ConvTranspose2d(in_channels, out_channels, kernel_size=4, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )
    
    def forward(self, x):
        return self.block(x)

class ChakraTransformerSegmenter(nn.Module):
    def __init__(self, backbone_name='vit_large_patch16_384', pretrained=False, num_classes=1):
        super(ChakraTransformerSegmenter, self).__init__()
        
        self.backbone = timm.create_model(
            backbone_name, 
            pretrained=pretrained, 
            features_only=False,
            drop_rate=0.1,
            attn_drop_rate=0.1
        )
        
        self.embed_dim = self.backbone.embed_dim
        
        self.stage1 = DecoderStage(self.embed_dim, 512)
        self.stage2 = DecoderStage(512, 256)
        self.stage3 = DecoderStage(256, 128)
        self.stage4 = DecoderStage(128, 64)
        
        self.final_conv = nn.Conv2d(64, num_classes, kernel_size=3, padding=1)
        
        self.dropout1 = nn.Dropout2d(p=0.5)
        self.dropout2 = nn.Dropout2d(p=0.5)

    def forward(self, x):
        B, C, H, W = x.shape
        
        features = self.backbone.forward_features(x)
        
        if features.dim() == 3:
            if features.shape[1] == (H // 16) * (W // 16) + 1:
                features = features[:, 1:]
            
            grid_h = H // 16
            grid_w = W // 16
            features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)
            
        x_dec = self.stage1(features)
        x_dec = self.dropout1(x_dec)
        x_dec = self.stage2(x_dec)
        x_dec = self.stage3(x_dec)
        x_dec = self.dropout2(x_dec)
        x_dec = self.stage4(x_dec)
        
        logits = self.final_conv(x_dec)
        
        if logits.shape[2:] != (H, W):
            logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)
            
        return logits

model = ChakraTransformerSegmenter()
try:
    ckpt = torch.load('weights/chakra_transformer_best.pth', map_location='cpu')
    model.load_state_dict(ckpt)
    print("SUCCESS: Weights loaded successfully!")
except Exception as e:
    print(f"FAILED: {e}")
