"""
combo1_model.py — Exact model class for combo1_best.pth (102.7 MB, 25.60M params).

Architecture identified from weight inspection:
  - Backbone: ResNet-50 (enc0→enc4), exact ResNet-50 channel structure
  - RFB: Asymmetric multi-scale receptive field blocks (branches: 1×1, 1×k+k×1, concat)
    * b0: 1x1 conv only
    * b1: 1x1 → 1×3 → 3×1 → 3×3
    * b2: 1x1 → 1×5 → 5×1 → 3×3
    * b3: 1x1 → 1×7 → 7×1 → 3×3
    * concat(b0+b1+b2+b3) → ConvBN → + residual(1×1)
  - PPD: Single ConvBN(192→48, 3×3) on concatenated [rfb4,rfb3,rfb2] → pred head
  - RA: Reverse Attention with CBAM (channel FC 48→6→48, spatial 7×7)
         Structure: multiply feature by (1-sigmoid(prev_pred)), conv1, conv2, CBAM, out → residual add

Family: CNN + Reverse Attention (NOT a Transformer)
This is a ResNet-50 backbone with custom RFB blocks and CBAM-augmented reverse attention.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


# ─── Building blocks ─────────────────────────────────────────────────────────

class ConvBN(nn.Sequential):
    """Conv2d + BatchNorm2d, no ReLU (ReLU applied outside when needed)."""
    def __init__(self, in_ch, out_ch, kernel, stride=1, padding=0, groups=1):
        super().__init__(
            nn.Conv2d(in_ch, out_ch, kernel, stride=stride, padding=padding,
                      groups=groups, bias=False),
            nn.BatchNorm2d(out_ch),
        )
    # wraps in nn.Sequential named 'net' to match weight keys like 'rfb1.b0.net.0.weight'


class _Net(nn.Module):
    """Container that stores its layers under self.net so keys match *.net.0.*, *.net.1.*"""
    def __init__(self, *layers):
        super().__init__()
        self.net = nn.Sequential(*layers)
    def forward(self, x):
        return self.net(x)


# ─── ResNet-50 components ─────────────────────────────────────────────────────

class Bottleneck(nn.Module):
    expansion = 4
    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super().__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, 1, bias=False)
        self.bn1   = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, 3, stride=stride, padding=1, bias=False)
        self.bn2   = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, planes * 4, 1, bias=False)
        self.bn3   = nn.BatchNorm2d(planes * 4)
        self.relu  = nn.ReLU(inplace=True)
        self.downsample = downsample

    def forward(self, x):
        identity = x
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        if self.downsample is not None:
            identity = self.downsample(x)
        return self.relu(out + identity)


def _res_layer(in_ch, planes, n_blocks, stride=1):
    """Build a ResNet stage as an nn.Sequential."""
    layers, ds = [], None
    out_ch = planes * 4
    if stride != 1 or in_ch != out_ch:
        ds = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 1, stride=stride, bias=False),
            nn.BatchNorm2d(out_ch),
        )
    layers.append(Bottleneck(in_ch, planes, stride, ds))
    for _ in range(1, n_blocks):
        layers.append(Bottleneck(out_ch, planes))
    return nn.Sequential(*layers)


# ─── RFB ─────────────────────────────────────────────────────────────────────

class RFB(nn.Module):
    """
    Asymmetric Receptive Field Block.
    4 branches: b0 (1×1), b1 (1×1+1×3+3×1+3×3), b2 (1×1+1×5+5×1+3×3), b3 (1×1+1×7+7×1+3×3)
    cat: conv(4*ch→ch), res: shortcut(in→ch), output = ReLU(cat+res)
    All convs wrapped in _Net so weight keys are *.net.0.weight, *.net.1.*
    """
    def __init__(self, in_ch, out_ch):
        super().__init__()
        # Branch 0: single 1x1
        self.b0 = _Net(
            nn.Conv2d(in_ch, out_ch, 1, bias=False),
            nn.BatchNorm2d(out_ch),
        )
        # Branch 1: 1x1 → 1x3 → 3x1 → 3x3
        self.b1 = nn.Sequential(
            _Net(nn.Conv2d(in_ch, out_ch, 1, bias=False), nn.BatchNorm2d(out_ch)),
            _Net(nn.Conv2d(out_ch, out_ch, (1,3), padding=(0,1), bias=False), nn.BatchNorm2d(out_ch)),
            _Net(nn.Conv2d(out_ch, out_ch, (3,1), padding=(1,0), bias=False), nn.BatchNorm2d(out_ch)),
            _Net(nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False), nn.BatchNorm2d(out_ch)),
        )
        # Branch 2: 1x1 → 1x5 → 5x1 → 3x3
        self.b2 = nn.Sequential(
            _Net(nn.Conv2d(in_ch, out_ch, 1, bias=False), nn.BatchNorm2d(out_ch)),
            _Net(nn.Conv2d(out_ch, out_ch, (1,5), padding=(0,2), bias=False), nn.BatchNorm2d(out_ch)),
            _Net(nn.Conv2d(out_ch, out_ch, (5,1), padding=(2,0), bias=False), nn.BatchNorm2d(out_ch)),
            _Net(nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False), nn.BatchNorm2d(out_ch)),
        )
        # Branch 3: 1x1 → 1x7 → 7x1 → 3x3
        self.b3 = nn.Sequential(
            _Net(nn.Conv2d(in_ch, out_ch, 1, bias=False), nn.BatchNorm2d(out_ch)),
            _Net(nn.Conv2d(out_ch, out_ch, (1,7), padding=(0,3), bias=False), nn.BatchNorm2d(out_ch)),
            _Net(nn.Conv2d(out_ch, out_ch, (7,1), padding=(3,0), bias=False), nn.BatchNorm2d(out_ch)),
            _Net(nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False), nn.BatchNorm2d(out_ch)),
        )
        # Concat fusion
        self.cat = _Net(nn.Conv2d(out_ch * 4, out_ch, 3, padding=1, bias=False), nn.BatchNorm2d(out_ch))
        # Residual shortcut
        self.res = _Net(nn.Conv2d(in_ch, out_ch, 1, bias=False), nn.BatchNorm2d(out_ch))

    def forward(self, x):
        b0 = F.relu(self.b0(x), inplace=True)
        b1 = x
        for m in self.b1:
            b1 = F.relu(m(b1), inplace=True)
        b2 = x
        for m in self.b2:
            b2 = F.relu(m(b2), inplace=True)
        b3 = x
        for m in self.b3:
            b3 = F.relu(m(b3), inplace=True)
        cat = F.relu(self.cat(torch.cat([b0, b1, b2, b3], dim=1)), inplace=True)
        return F.relu(cat + self.res(x), inplace=True)


# ─── CBAM attention ───────────────────────────────────────────────────────────

class CBAMAttn(nn.Module):
    """Channel + Spatial attention (CBAM-lite)."""
    def __init__(self, ch, reduction=8):
        super().__init__()
        mid = max(ch // reduction, 1)
        # ch_fc: Linear(ch→mid→ch), stored as ch_fc.1.weight, ch_fc.3.weight
        self.ch_fc = nn.Sequential(
            nn.Flatten(1),
            nn.Linear(ch, mid, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(mid, ch, bias=False),
        )
        # sp_conv: Conv2d(2, 1, 7x7)
        self.sp_conv = nn.Conv2d(2, 1, 7, padding=3, bias=False)

    def forward(self, x):
        # Channel attention
        avg = x.mean(dim=[2, 3])
        ch_w = torch.sigmoid(self.ch_fc(avg)).unsqueeze(-1).unsqueeze(-1)
        x = x * ch_w
        # Spatial attention
        avg_sp = x.mean(dim=1, keepdim=True)
        max_sp = x.max(dim=1, keepdim=True).values
        sp_w = torch.sigmoid(self.sp_conv(torch.cat([avg_sp, max_sp], dim=1)))
        return x * sp_w


# ─── Reverse Attention ────────────────────────────────────────────────────────

class RA(nn.Module):
    """
    Reverse Attention with CBAM.
    ra*.conv1 / ra*.conv2: ConvBN(48→48, 3×3) each under .net
    ra*.attn: CBAMAttn(48, reduction=8) → ch_fc.1/3, sp_conv
    ra*.out: Conv2d(48→1, 1×1) with bias
    """
    def __init__(self, ch):
        super().__init__()
        self.conv1 = _Net(nn.Conv2d(ch, ch, 3, padding=1, bias=False), nn.BatchNorm2d(ch))
        self.conv2 = _Net(nn.Conv2d(ch, ch, 3, padding=1, bias=False), nn.BatchNorm2d(ch))
        self.attn  = CBAMAttn(ch, reduction=ch // 6)  # mid=6 for ch=48
        self.out   = nn.Conv2d(ch, 1, 1)

    def forward(self, x, prev_pred):
        # Reverse attention: mask out already-detected regions
        ra = 1.0 - torch.sigmoid(
            F.interpolate(prev_pred, x.shape[2:], mode='bilinear', align_corners=False)
        )
        x = x * ra
        x = F.relu(self.conv1(x), inplace=True)
        x = F.relu(self.conv2(x), inplace=True)
        x = self.attn(x)
        # Residual: add back the upsampled previous prediction
        return self.out(x) + F.interpolate(prev_pred, x.shape[2:], mode='bilinear', align_corners=False)


# ─── PPD ─────────────────────────────────────────────────────────────────────

class PPD(nn.Module):
    """Parallel Partial Decoder: concat [rfb4,rfb3,rfb2] at rfb4's scale → ConvBN → pred."""
    def __init__(self, ch):
        super().__init__()
        self.ppd_conv = _Net(nn.Conv2d(ch * 3, ch, 3, padding=1, bias=False), nn.BatchNorm2d(ch))
        self.ppd_pred = nn.Conv2d(ch, 1, 1)

    def forward(self, f4, f3, f2):
        h, w = f4.shape[2:]
        f3u = F.interpolate(f3, (h, w), mode='bilinear', align_corners=False)
        f2u = F.interpolate(f2, (h, w), mode='bilinear', align_corners=False)
        merged = F.relu(self.ppd_conv(torch.cat([f4, f3u, f2u], dim=1)), inplace=True)
        return self.ppd_pred(merged)


# ─── Full model ───────────────────────────────────────────────────────────────

class Combo1Model(nn.Module):
    """
    combo1_best.pth model: ResNet-50 + Asymmetric RFB + PPD + CBAM-RA.
    25.60M parameters, 102.7 MB.
    
    This is a PraNet-family model with custom modifications:
    - Asymmetric convolutions in RFB (no dilation, uses 1xK+Kx1 pairs)
    - CBAM attention inside each Reverse Attention module
    
    USAGE in benchmark_eval.py:
        from combo1_model import Combo1Model
        MODEL_REGISTRY = {"combo1": Combo1Model}
    
    CMD:
        python scripts/benchmark_eval.py \\
            --checkpoint _weights_check/weights/checkpoints/combo1_best.pth \\
            --model_class combo1 \\
            --data_root data/raw
    """
    def __init__(self):
        super().__init__()
        ch = 48  # RFB output channels

        # Stem
        self.enc0 = nn.Sequential(
            nn.Conv2d(3, 64, 7, stride=2, padding=3, bias=False),
            nn.BatchNorm2d(64),
        )
        # ResNet-50 stages
        self.enc1 = _res_layer(64,    64,  3)          # → 256-ch, /4
        self.enc2 = _res_layer(256,  128,  4, stride=2) # → 512-ch, /8
        self.enc3 = _res_layer(512,  256,  6, stride=2) # → 1024-ch, /16
        self.enc4 = _res_layer(1024, 512,  3, stride=2) # → 2048-ch, /32

        # RFBs
        self.rfb1 = RFB(256,  ch)
        self.rfb2 = RFB(512,  ch)
        self.rfb3 = RFB(1024, ch)
        self.rfb4 = RFB(2048, ch)

        # PPD — stored as top-level ppd_conv / ppd_pred to match checkpoint keys
        # Input = concat [rfb4, rfb3, rfb2, rfb1] all upsampled to rfb4 scale = 4*ch = 192
        self.ppd_conv = _Net(nn.Conv2d(ch * 4, ch, 3, padding=1, bias=False), nn.BatchNorm2d(ch))
        self.ppd_pred = nn.Conv2d(ch, 1, 1)

        # Reverse Attention (coarse→ra4→ra3→ra2→ra1)
        self.ra4 = RA(ch)
        self.ra3 = RA(ch)
        self.ra2 = RA(ch)
        self.ra1 = RA(ch)

    def forward(self, x):
        H, W = x.shape[2:]

        # Encoder
        e0 = F.relu(self.enc0(x), inplace=True)
        e0 = F.max_pool2d(e0, 3, stride=2, padding=1)  # /4
        e1 = self.enc1(e0)   # 256-ch, /4
        e2 = self.enc2(e1)   # 512-ch, /8
        e3 = self.enc3(e2)   # 1024-ch, /16
        e4 = self.enc4(e3)   # 2048-ch, /32

        # RFB
        f1 = self.rfb1(e1)
        f2 = self.rfb2(e2)
        f3 = self.rfb3(e3)
        f4 = self.rfb4(e4)

        # PPD coarse prediction — concat all 4 RFB features at f4's scale
        h4, w4 = f4.shape[2:]
        f3u = F.interpolate(f3, (h4, w4), mode='bilinear', align_corners=False)
        f2u = F.interpolate(f2, (h4, w4), mode='bilinear', align_corners=False)
        f1u = F.interpolate(f1, (h4, w4), mode='bilinear', align_corners=False)
        ppd_feat = F.relu(self.ppd_conv(torch.cat([f4, f3u, f2u, f1u], dim=1)), inplace=True)
        coarse = self.ppd_pred(ppd_feat)  # /32

        # Reverse Attention chain
        ra4 = self.ra4(f4, coarse)     # /32
        ra3 = self.ra3(f3, ra4)        # /16
        ra2 = self.ra2(f2, ra3)        # /8
        ra1 = self.ra1(f1, ra2)        # /4

        # Upsample to input resolution
        return F.interpolate(ra1, (H, W), mode='bilinear', align_corners=False)


if __name__ == "__main__":
    import sys, torch
    model = Combo1Model()
    ckpt_path = sys.argv[1] if len(sys.argv) > 1 else "_weights_check/weights/checkpoints/combo1_best.pth"
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    missing, unexpected = model.load_state_dict(ckpt, strict=False)
    print(f"Missing  ({len(missing)}): {missing[:5]}")
    print(f"Unexpected ({len(unexpected)}): {unexpected[:5]}")
    n = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {n/1e6:.2f}M")
    dummy = torch.randn(1, 3, 352, 352)
    with torch.no_grad():
        out = model(dummy)
    print(f"Output shape: {out.shape}  (expect [1,1,352,352])")
