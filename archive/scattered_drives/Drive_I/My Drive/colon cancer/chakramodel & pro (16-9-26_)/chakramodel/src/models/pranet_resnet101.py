import torch
import torch.nn as nn
import torchvision.models as models
import torch.nn.functional as F

class BasicConv2d(nn.Module):
    def __init__(self, ic, oc, k, s=1, p=0, d=1, relu=True):
        super().__init__()
        layers = [nn.Conv2d(ic, oc, k, s, p, d, bias=False), nn.BatchNorm2d(oc)]
        if relu: layers.append(nn.ReLU(inplace=True))
        self.net = nn.Sequential(*layers)
    def forward(self, x): return self.net(x)


class RFBBlock(nn.Module):
    """Receptive Field Block — captures multi-scale polyp context"""
    def __init__(self, ic, oc):
        super().__init__()
        self.b0 = BasicConv2d(ic, oc, 1)
        self.b1 = nn.Sequential(
            BasicConv2d(ic, oc, 1),
            BasicConv2d(oc, oc, (1,3), p=(0,1)),
            BasicConv2d(oc, oc, (3,1), p=(1,0)),
            BasicConv2d(oc, oc, 3, p=3, d=3))
        self.b2 = nn.Sequential(
            BasicConv2d(ic, oc, 1),
            BasicConv2d(oc, oc, (1,5), p=(0,2)),
            BasicConv2d(oc, oc, (5,1), p=(2,0)),
            BasicConv2d(oc, oc, 3, p=5, d=5))
        self.b3 = nn.Sequential(
            BasicConv2d(ic, oc, 1),
            BasicConv2d(oc, oc, (1,7), p=(0,3)),
            BasicConv2d(oc, oc, (7,1), p=(3,0)),
            BasicConv2d(oc, oc, 3, p=7, d=7))
        self.cat = BasicConv2d(4*oc, oc, 3, p=1)
        self.res = BasicConv2d(ic, oc, 1)
        self.act = nn.ReLU(True)

    def forward(self, x):
        return self.act(self.cat(torch.cat([self.b0(x), self.b1(x), self.b2(x), self.b3(x)], 1)) + self.res(x))


class CBAM(nn.Module):
    """Convolutional Block Attention Module — channel + spatial attention"""
    def __init__(self, ch, r=8):
        super().__init__()
        self.ch_avg = nn.AdaptiveAvgPool2d(1)
        self.ch_max = nn.AdaptiveMaxPool2d(1)
        self.ch_fc  = nn.Sequential(nn.Flatten(), nn.Linear(ch, ch//r, bias=False),
                                    nn.ReLU(), nn.Linear(ch//r, ch, bias=False))
        self.sp_conv = nn.Conv2d(2, 1, 7, padding=3, bias=False)

    def forward(self, x):
        ca = torch.sigmoid(self.ch_fc(self.ch_avg(x)) + self.ch_fc(self.ch_max(x)))
        x  = x * ca.view(x.shape[0], -1, 1, 1)
        sp = torch.sigmoid(self.sp_conv(torch.cat([x.mean(1,keepdim=True), x.max(1,keepdim=True)[0]], 1)))
        return x * sp


class ReverseAttention(nn.Module):
    """Reverse Attention — focuses on boundary, not interior"""
    def __init__(self, ic, oc):
        super().__init__()
        self.conv1 = BasicConv2d(ic, oc, 3, p=1)
        self.conv2 = BasicConv2d(oc, oc, 3, p=1)
        self.attn  = CBAM(oc)
        self.out   = nn.Conv2d(oc, 1, 1)

    def forward(self, feat, sal):
        rev = feat * (1.0 - torch.sigmoid(sal)).expand_as(feat)
        return self.out(self.attn(self.conv2(self.conv1(rev))))

class PraNetResNet101(nn.Module):
    def __init__(self, channels=48, mc_dropout_p=0.15):
        super(PraNetResNet101, self).__init__()
        self.channels = channels
        self.mc_dropout_enabled = False
        resnet = models.resnet50(weights=None)
        
        self.enc0 = nn.Sequential(resnet.conv1, resnet.bn1, resnet.relu, resnet.maxpool)
        self.enc1 = resnet.layer1
        self.enc2 = resnet.layer2
        self.enc3 = resnet.layer3
        self.enc4 = resnet.layer4
        
        # All channels are 48 in the checkpoint
        self.rfb1 = RFBBlock(256, 48)
        self.rfb2 = RFBBlock(512, 48)
        self.rfb3 = RFBBlock(1024, 48)
        self.rfb4 = RFBBlock(2048, 48)
        
        # ppd_conv takes 192 channels -> 48 * 4. This means it concatenated 4 features!
        self.ppd_conv = BasicConv2d(48 * 4, 48, 3, p=1)
        self.ppd_out  = nn.Conv2d(48, 1, kernel_size=1)
        
        # Reverse attention operates on 48 channels
        self.ra4 = ReverseAttention(48, 48)
        self.ra3 = ReverseAttention(48, 48)
        self.ra2 = ReverseAttention(48, 48)
        self.ra1 = ReverseAttention(48, 48)
        self.drop = nn.Dropout2d(p=mc_dropout_p)
    def enable_mc_dropout(self): self.mc_dropout_enabled = True
    def disable_mc_dropout(self): self.mc_dropout_enabled = False
    def forward(self, x):
        h, w = x.shape[2], x.shape[3]
        dropout_active = self.training or self.mc_dropout_enabled
        x0 = self.enc0(x)
        e1 = self.enc1(x0)
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)
        e4 = self.enc4(e3)
        r1, r2, r3, r4 = self.rfb1(e1), self.rfb2(e2), self.rfb3(e3), self.rfb4(e4)
        if dropout_active:
            r1, r2, r3, r4 = self.drop(r1), self.drop(r2), self.drop(r3), self.drop(r4)
        sz2 = r2.shape[2:]
        r1_down = F.interpolate(r1, size=sz2, mode='bilinear', align_corners=False)
        r3_up = F.interpolate(r3, size=sz2, mode='bilinear', align_corners=False)
        r4_up = F.interpolate(r4, size=sz2, mode='bilinear', align_corners=False)
        ppd_feat = self.ppd_conv(torch.cat([r1_down, r2, r3_up, r4_up], dim=1))
        s_g = self.ppd_out(ppd_feat)
        s_g_r4 = F.interpolate(s_g, size=r4.shape[2:], mode='bilinear', align_corners=False)
        s_4 = self.ra4(r4, s_g_r4)
        s_4_r3 = F.interpolate(s_4, size=r3.shape[2:], mode='bilinear', align_corners=False)
        s_3 = self.ra3(r3, s_4_r3)
        s_3_r2 = F.interpolate(s_3, size=r2.shape[2:], mode='bilinear', align_corners=False)
        s_2 = self.ra2(r2, s_3_r2)
        s_2_r1 = F.interpolate(s_2, size=r1.shape[2:], mode='bilinear', align_corners=False)
        s_1 = self.ra1(r1, s_2_r1)
        out = F.interpolate(s_1, size=(h, w), mode='bilinear', align_corners=False)
        if self.training:
            s_g_up = F.interpolate(s_g, size=(h, w), mode='bilinear', align_corners=False)
            s_4_up = F.interpolate(s_4, size=(h, w), mode='bilinear', align_corners=False)
            s_3_up = F.interpolate(s_3, size=(h, w), mode='bilinear', align_corners=False)
            s_2_up = F.interpolate(s_2, size=(h, w), mode='bilinear', align_corners=False)
            return out, s_2_up, s_3_up, s_4_up, s_g_up
        return out
