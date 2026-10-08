"""ChakraNet (AdaBN-ChakraNet): PraNet with a ResNet-101 backbone, 4-stage RFB, PPD decoder and
CBAM reverse attention. Extracted unchanged from the project's adabn-chakranet notebook (cell 5);
the only edit is the `pretrained_backbone` switch so inference does not download ImageNet weights.
Eval-mode forward returns one logit map [B,1,H,W]; train-mode returns 5 deep-supervision maps.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models

class BasicConv2d(nn.Module):
    # Standard Convolution-BatchNorm-ReLU Block
    def __init__(self, in_planes, out_planes, kernel_size, stride=1, padding=0, dilation=1, relu=True):
        super(BasicConv2d, self).__init__()
        self.conv = nn.Conv2d(
            in_planes, out_planes,
            kernel_size=kernel_size, stride=stride,
            padding=padding, dilation=dilation, bias=False
        )
        self.bn = nn.BatchNorm2d(out_planes)
        self.relu = nn.ReLU(inplace=True) if relu else nn.Identity()

    def forward(self, x):
        return self.relu(self.bn(self.conv(x)))


class RFBBlock(nn.Module):
    # Receptive Field Block with multi-dilation atrous convolutions
    def __init__(self, in_channel, out_channel):
        super(RFBBlock, self).__init__()
        self.relu = nn.ReLU(True)
        self.branch0 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
        )
        self.branch1 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 3), padding=(0, 1)),
            BasicConv2d(out_channel, out_channel, kernel_size=(3, 1), padding=(1, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=3, dilation=3)
        )
        self.branch2 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 5), padding=(0, 2)),
            BasicConv2d(out_channel, out_channel, kernel_size=(5, 1), padding=(2, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=5, dilation=5)
        )
        self.branch3 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 7), padding=(0, 3)),
            BasicConv2d(out_channel, out_channel, kernel_size=(7, 1), padding=(3, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=7, dilation=7)
        )
        self.conv_cat = BasicConv2d(4 * out_channel, out_channel, 3, padding=1)
        self.conv_res = BasicConv2d(in_channel, out_channel, 1)

    def forward(self, x):
        x0 = self.branch0(x)
        x1 = self.branch1(x)
        x2 = self.branch2(x)
        x3 = self.branch3(x)
        x_cat = self.conv_cat(torch.cat((x0, x1, x2, x3), 1))
        return self.relu(x_cat + self.conv_res(x))


class CBAM(nn.Module):
    # Convolutional Block Attention Module: Channel Attention + Spatial Attention
    def __init__(self, channels, r=8):
        super(CBAM, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(channels, channels // r, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channels // r, channels, bias=False)
        )
        self.spatial_conv = nn.Conv2d(2, 1, kernel_size=7, padding=3, bias=False)

    def forward(self, x):
        avg_out = self.fc(self.avg_pool(x))
        max_out = self.fc(self.max_pool(x))
        ca = torch.sigmoid(avg_out + max_out).view(x.size(0), -1, 1, 1)
        x = x * ca
        avg_s = torch.mean(x, dim=1, keepdim=True)
        max_s, _ = torch.max(x, dim=1, keepdim=True)
        sa = torch.sigmoid(self.spatial_conv(torch.cat([avg_s, max_s], dim=1)))
        return x * sa


class ReverseAttention(nn.Module):
    # Reverse Attention Module with Saliency Inversion and CBAM
    def __init__(self, in_channel, out_channel):
        super(ReverseAttention, self).__init__()
        self.conv1 = BasicConv2d(in_channel, out_channel, 3, padding=1)
        self.conv2 = BasicConv2d(out_channel, out_channel, 3, padding=1)
        self.cbam  = CBAM(out_channel)
        self.conv_out = nn.Conv2d(out_channel, 1, kernel_size=1)

    def forward(self, feat, saliency_map):
        rev_weight = 1.0 - torch.sigmoid(saliency_map)
        x = feat * rev_weight.expand_as(feat)
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.cbam(x)
        return self.conv_out(x)


class PraNetResNet101(nn.Module):
    # Max-Spec PraNet with ResNet-101 Backbone
    def __init__(self, channels=64, mc_dropout_p=0.15, pretrained_backbone=True):
        super(PraNetResNet101, self).__init__()
        self.channels = channels
        self.mc_dropout_enabled = False
        self.mc_p = mc_dropout_p

        # Backbone: Pretrained ResNet-101 (ImageNet V2 weights)
        if pretrained_backbone:
            weights = models.ResNet101_Weights.IMAGENET1K_V2 if hasattr(models, 'ResNet101_Weights') else True
        else:
            weights = None   # inference: the checkpoint supplies every weight, no download needed
        resnet = models.resnet101(weights=weights)
        
        self.stem = nn.Sequential(resnet.conv1, resnet.bn1, resnet.relu, resnet.maxpool)
        self.layer1 = resnet.layer1  # [B, 256, H/4, W/4]
        self.layer2 = resnet.layer2  # [B, 512, H/8, W/8]
        self.layer3 = resnet.layer3  # [B, 1024, H/16, W/16]
        self.layer4 = resnet.layer4  # [B, 2048, H/32, W/32]

        # Multi-scale Receptive Field Blocks
        self.rfb1 = RFBBlock(256, channels)
        self.rfb2 = RFBBlock(512, channels)
        self.rfb3 = RFBBlock(1024, channels)
        self.rfb4 = RFBBlock(2048, channels)

        # Parallel Partial Decoder (PPD)
        self.ppd_conv = BasicConv2d(channels * 3, channels, 3, padding=1)
        self.ppd_out  = nn.Conv2d(channels, 1, kernel_size=1)

        # Reverse Attention Modules (Cascaded Top-Down Refinement)
        self.ra4 = ReverseAttention(channels, channels)
        self.ra3 = ReverseAttention(channels, channels)
        self.ra2 = ReverseAttention(channels, channels)
        self.ra1 = ReverseAttention(channels, channels)

        # Spatial Dropout for MC Uncertainty
        self.drop = nn.Dropout2d(p=mc_dropout_p)

    def enable_mc_dropout(self):
        self.mc_dropout_enabled = True

    def disable_mc_dropout(self):
        self.mc_dropout_enabled = False

    def forward(self, x):
        h, w = x.shape[2], x.shape[3]
        dropout_active = self.training or self.mc_dropout_enabled

        # Backbone Stage Extraction
        x0 = self.stem(x)
        e1 = self.layer1(x0)
        e2 = self.layer2(e1)
        e3 = self.layer3(e2)
        e4 = self.layer4(e3)

        # Receptive Field Blocks
        r1 = self.rfb1(e1)
        r2 = self.rfb2(e2)
        r3 = self.rfb3(e3)
        r4 = self.rfb4(e4)

        if dropout_active:
            r1 = self.drop(r1)
            r2 = self.drop(r2)
            r3 = self.drop(r3)
            r4 = self.drop(r4)

        # Parallel Partial Decoder (PPD at H/8)
        sz2 = r2.shape[2:]
        r3_up = F.interpolate(r3, size=sz2, mode='bilinear', align_corners=False)
        r4_up = F.interpolate(r4, size=sz2, mode='bilinear', align_corners=False)
        ppd_feat = self.ppd_conv(torch.cat([r2, r3_up, r4_up], dim=1))
        s_g = self.ppd_out(ppd_feat)

        # Reverse Attention Cascade
        s_g_r4 = F.interpolate(s_g, size=r4.shape[2:], mode='bilinear', align_corners=False)
        s_4 = self.ra4(r4, s_g_r4)

        s_4_r3 = F.interpolate(s_4, size=r3.shape[2:], mode='bilinear', align_corners=False)
        s_3 = self.ra3(r3, s_4_r3)

        s_3_r2 = F.interpolate(s_3, size=r2.shape[2:], mode='bilinear', align_corners=False)
        s_2 = self.ra2(r2, s_3_r2)

        s_2_r1 = F.interpolate(s_2, size=r1.shape[2:], mode='bilinear', align_corners=False)
        s_1 = self.ra1(r1, s_2_r1)

        # Output Logits [B, 1, H, W]
        out = F.interpolate(s_1, size=(h, w), mode='bilinear', align_corners=False)

        if self.training:
            s_g_up = F.interpolate(s_g, size=(h, w), mode='bilinear', align_corners=False)
            s_4_up = F.interpolate(s_4, size=(h, w), mode='bilinear', align_corners=False)
            s_3_up = F.interpolate(s_3, size=(h, w), mode='bilinear', align_corners=False)
            s_2_up = F.interpolate(s_2, size=(h, w), mode='bilinear', align_corners=False)
            return out, s_2_up, s_3_up, s_4_up, s_g_up

        return out
