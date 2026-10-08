import torch
import torch.nn as nn
import timm
from ultralytics import YOLO

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

    def forward(self, x):
        pass

def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

print("Calculating parameters...")
try:
    vit_model = ChakraTransformerSegmenter()
    vit_params = count_parameters(vit_model)
    print(f"ChakraTransformer (ViT-Large) Parameters: {vit_params:,}")
except Exception as e:
    print("Error loading ViT:", e)

try:
    yolo_model = YOLO("M:/chakramodel/kaggle_bundle/weights/best.pt")
    # yolo model params
    yolo_params = sum(p.numel() for p in yolo_model.model.parameters() if p.requires_grad)
    print(f"YOLO Model Parameters: {yolo_params:,}")
except Exception as e:
    print("Error loading YOLO:", e)
