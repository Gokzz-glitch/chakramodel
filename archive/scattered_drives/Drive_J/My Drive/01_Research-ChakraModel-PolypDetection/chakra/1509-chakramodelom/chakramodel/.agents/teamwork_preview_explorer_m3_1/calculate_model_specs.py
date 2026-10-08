import os
import sys
import time
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm
from ultralytics import YOLO
import thop

root = Path(r"m:\chakramodel")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Executing on device: {device}")

# 1. Define ChakraTransformerSegmenter exactly matching checkpoint weights/chakra_transformer_best.pth
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
        B, C, H, W = x.shape
        features = self.backbone.forward_features(x)
        if features.dim() == 3:
            expected = (H // 16) * (W // 16)
            if features.shape[1] == expected + 1:
                features = features[:, 1:]
            grid_h = H // 16
            grid_w = W // 16
            features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)
        x_dec = features
        for i, layer in enumerate(self.decode_head):
            x_dec = layer(x_dec)
            if i == 2:
                x_dec = self.dropout1(x_dec)
            elif i == 5:
                x_dec = self.dropout2(x_dec)
        if x_dec.shape[2:] != (H, W):
            x_dec = F.interpolate(x_dec, size=(H, W), mode='bilinear', align_corners=False)
        return x_dec

# 2. Benchmark YOLO Models
print("\n" + "="*80)
print("BENCHMARKING YOLO MODELS")
print("="*80)

for name, p in [("YOLOv8n Polyp (best.pt)", root / "weights" / "best.pt"), 
                ("YOLOv8x COCO (yolov8x.pt)", root / "yolov8x.pt")]:
    if not p.exists():
        continue
    yolo = YOLO(str(p))
    model = yolo.model.to(device)
    model.eval()
    inp = torch.randn(1, 3, 640, 640).to(device)
    total_params = sum(param.numel() for param in model.parameters())
    trainable_params = sum(param.numel() for param in model.parameters() if param.requires_grad)
    
    flops, params = thop.profile(model, inputs=(inp,), verbose=False)
    
    # Warmup & latency
    with torch.no_grad():
        for _ in range(5):
            _ = model(inp)
        t0 = time.time()
        n_iters = 10
        for _ in range(n_iters):
            _ = model(inp)
        dt = (time.time() - t0) / n_iters
    fps = 1.0 / dt
    
    print(f"Model: {name}")
    print(f"  Total Parameters: {total_params:,} ({total_params/1e6:.2f} M)")
    print(f"  Trainable Params: {trainable_params:,}")
    print(f"  GFLOPs @ 640x640: {flops / 1e9:.2f} GFLOPs (FLOPs: {flops:,})")
    print(f"  Inference Latency: {dt*1000:.2f} ms ({fps:.1f} FPS)")
    print()

# 3. Benchmark ChakraTransformerSegmenter
print("="*80)
print("BENCHMARKING CHAKRATRANSFORMER")
print("="*80)
vit_model = ChakraTransformerSegmenter()
vit_ckpt_path = root / "weights" / "chakra_transformer_best.pth"
if vit_ckpt_path.exists():
    sd = torch.load(str(vit_ckpt_path), map_location='cpu')
    if any(k.startswith('module.') for k in sd.keys()):
        sd = {k.replace('module.', ''): v for k, v in sd.items()}
    vit_model.load_state_dict(sd, strict=True)
    print("Successfully loaded weights/chakra_transformer_best.pth with strict=True!")

vit_model.to(device)
vit_model.eval()

vit_params = sum(p.numel() for p in vit_model.parameters())
backbone_params = sum(p.numel() for p in vit_model.backbone.parameters())
head_params = sum(p.numel() for p in vit_model.decode_head.parameters())

print(f"ChakraTransformer Total Parameters: {vit_params:,} ({vit_params/1e6:.2f} M)")
print(f"  - ViT Backbone Parameters:        {backbone_params:,} ({backbone_params/1e6:.2f} M)")
print(f"  - Decode Head Parameters:         {head_params:,} ({head_params/1e6:.2f} M)")
print(f"  - Model File Size (MB):           {vit_ckpt_path.stat().st_size / (1024*1024):.2f} MB")
print(f"  - Memory footprint (FP32):        {vit_params * 4 / (1024*1024):.2f} MB")
print(f"  - Memory footprint (FP16):        {vit_params * 2 / (1024*1024):.2f} MB")

# Test 384x384
inp384 = torch.randn(1, 3, 384, 384).to(device)
flops384, _ = thop.profile(vit_model, inputs=(inp384,), verbose=False)
with torch.no_grad():
    for _ in range(3): _ = vit_model(inp384)
    t0 = time.time()
    n_iters = 5
    for _ in range(n_iters): _ = vit_model(inp384)
    dt384 = (time.time() - t0) / n_iters
print(f"\nResolution 384x384:")
print(f"  GFLOPs: {flops384 / 1e9:.2f} GFLOPs (FLOPs: {flops384:,})")
print(f"  Inference Latency: {dt384*1000:.2f} ms ({1.0/dt384:.1f} FPS)")

# ViT-Large strictly requires 384x384 because patch_embed checks H == img_size[0]
print("Note: vit_large_patch16_384 strictly requires (384, 384) input resolution.")

# 4. Benchmark ChakraNet / PraNetResNet101
print("\n" + "="*80)
print("BENCHMARKING CHAKRANET / PRANET (combo1_best.pth)")
print("="*80)
sys.path.insert(0, str(root / "src"))
from pranet_resnet101 import PraNetResNet101
try:
    pranet = PraNetResNet101(channels=48, mc_dropout_p=0.0)
    combo1_p = root / "weights" / "combo1_best.pth"
    sd1 = torch.load(str(combo1_p), map_location='cpu')
    pranet.load_state_dict(sd1, strict=False)
    pranet.to(device)
    pranet.eval()
    p_params = sum(p.numel() for p in pranet.parameters())
    print(f"PraNet / ChakraNet (Combo 1) Parameters: {p_params:,} ({p_params/1e6:.2f} M)")
    inp352 = torch.randn(1, 3, 352, 352).to(device)
    flops_p, _ = thop.profile(pranet, inputs=(inp352,), verbose=False)
    with torch.no_grad():
        for _ in range(3): _ = pranet(inp352)
        t0 = time.time()
        n_iters = 10
        for _ in range(n_iters): _ = pranet(inp352)
        dt_p = (time.time() - t0) / n_iters
    print(f"Resolution 352x352:")
    print(f"  GFLOPs: {flops_p / 1e9:.2f} GFLOPs (FLOPs: {flops_p:,})")
    print(f"  Inference Latency: {dt_p*1000:.2f} ms ({1.0/dt_p:.1f} FPS)")
    
    # Also 448x448 for PraNet
    inp448 = torch.randn(1, 3, 448, 448).to(device)
    flops_p448, _ = thop.profile(pranet, inputs=(inp448,), verbose=False)
    with torch.no_grad():
        for _ in range(3): _ = pranet(inp448)
        t0 = time.time()
        for _ in range(n_iters): _ = pranet(inp448)
        dt_p448 = (time.time() - t0) / n_iters
    print(f"Resolution 448x448:")
    print(f"  GFLOPs: {flops_p448 / 1e9:.2f} GFLOPs (FLOPs: {flops_p448:,})")
    print(f"  Inference Latency: {dt_p448*1000:.2f} ms ({1.0/dt_p448:.1f} FPS)")
except Exception as e:
    print(f"Error benchmarking PraNet: {e}")

print("="*80)
