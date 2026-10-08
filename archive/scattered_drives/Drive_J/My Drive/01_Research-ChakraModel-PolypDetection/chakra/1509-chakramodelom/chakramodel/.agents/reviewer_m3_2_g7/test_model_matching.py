import torch
from pathlib import Path
import timm
import torch.nn as nn
import torch.nn.functional as F

class ChakraTransformerSegmenter(nn.Module):
    def __init__(self, backbone_name='vit_large_patch16_384', pretrained=False, num_classes=1):
        super().__init__()
        self.backbone = timm.create_model(backbone_name, pretrained=pretrained, features_only=False)
        self.embed_dim = self.backbone.embed_dim
        self.decode_head = nn.Sequential(
            nn.ConvTranspose2d(self.embed_dim, 256, kernel_size=4, stride=4),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, num_classes, kernel_size=3, padding=1)
        )
        self.dropout1 = nn.Dropout2d(p=0.5)
        self.dropout2 = nn.Dropout2d(p=0.5)

model = ChakraTransformerSegmenter(pretrained=False)
weights_path = Path("weights/chakra_transformer_best.pth")
sd = torch.load(weights_path, map_location="cpu", weights_only=True)
clean_sd = {k.replace("module.", "").replace("_orig_mod.", ""): v for k, v in sd.items()}

res = model.load_state_dict(clean_sd, strict=False)
print(f"ChakraTransformerSegmenter - Missing keys: {len(res.missing_keys)}, Unexpected keys: {len(res.unexpected_keys)}")
if res.missing_keys:
    print(f"Sample missing keys: {res.missing_keys[:5]}")
if res.unexpected_keys:
    print(f"Sample unexpected keys: {res.unexpected_keys[:5]}")
