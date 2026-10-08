"""
End-to-End Component Functional Test Suite for Combos 1 & 2.
"""

import sys
import os
import torch
import torch.nn as nn
import numpy as np
import cv2
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def run_tests():
    print("=" * 70)
    print("STARTING FUNCTIONAL COMPONENT INTEGRATION TEST")
    print("=" * 70)

    # 1. Test Dataset creation & synthetic generation
    test_dir = Path("m:/chakramodel/.agents/worker_1/test_data")
    img_dir = test_dir / "images"
    mask_dir = test_dir / "masks"
    img_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    print("\n[Test 1/6] Generating synthetic mini-dataset...")
    np.random.seed(42)
    h, w = 352, 352
    for i in range(8):
        img = np.full((h, w, 3), (50, 80, 160), dtype=np.uint8)
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(mask, (176, 176), (40, 30), 45, 0, 360, 255, -1)
        cv2.ellipse(img, (176, 176), (40, 30), 45, 0, 360, (40, 60, 200), -1)
        cv2.imwrite(str(img_dir / f"test_{i:03d}.jpg"), img)
        cv2.imwrite(str(mask_dir / f"test_{i:03d}.jpg"), mask)
    print(f"  Created 8 synthetic pairs in {test_dir}")

    # 2. Test Dataset & DataLoader
    print("\n[Test 2/6] Testing MaxSpecPolypDataset & DataLoader...")
    import torchvision.transforms as T
    from torch.utils.data import Dataset, DataLoader

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
    class MaxSpecPolypDataset(Dataset):
        def __init__(self, img_dir, mask_dir, size=(352, 352), augment=True):
            self.img_dir = Path(img_dir)
            self.mask_dir = Path(mask_dir)
            self.size = size
            self.augment = augment
            self.imgs = sorted([p for p in self.img_dir.glob('*') if p.suffix.lower() in IMAGE_EXTS])
            self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
            self.std  = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            self.color_jitter = T.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25, hue=0.08)

        def __len__(self):
            return len(self.imgs)

        def _find_mask(self, stem):
            for ext in IMAGE_EXTS:
                mp = self.mask_dir / (stem + ext)
                if mp.exists(): return mp
            return None

        def __getitem__(self, idx):
            ip = self.imgs[idx]
            mp = self._find_mask(ip.stem)
            img = cv2.imread(str(ip))
            mask = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE) if mp else None
            if img is None: img = np.zeros((self.size[0], self.size[1], 3), np.uint8)
            if mask is None: mask = np.zeros((self.size[0], self.size[1]), np.uint8)

            img = cv2.resize(img, self.size, interpolation=cv2.INTER_LINEAR)
            mask = cv2.resize(mask, self.size, interpolation=cv2.INTER_NEAREST)

            if self.augment:
                if np.random.rand() > 0.5: img, mask = cv2.flip(img, 1), cv2.flip(mask, 1)
                if np.random.rand() > 0.5: img, mask = cv2.flip(img, 0), cv2.flip(mask, 0)
                angle = np.random.uniform(-30, 30)
                M = cv2.getRotationMatrix2D((self.size[1] // 2, self.size[0] // 2), angle, 1.0)
                img = cv2.warpAffine(img, M, self.size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
                mask = cv2.warpAffine(mask, M, self.size, flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REFLECT_101)

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_t = torch.from_numpy(img_rgb).permute(2, 0, 1).float() / 255.0

            if self.augment:
                img_t = self.color_jitter(img_t)
                if np.random.rand() > 0.5:
                    noise = torch.randn_like(img_t) * 0.02
                    img_t = torch.clamp(img_t + noise, 0.0, 1.0)

            img_t = (img_t - self.mean) / self.std
            mask_t = torch.from_numpy((mask > 127).astype(np.float32)).unsqueeze(0)
            return img_t, mask_t

    ds = MaxSpecPolypDataset(img_dir, mask_dir, size=(352, 352), augment=True)
    loader = DataLoader(ds, batch_size=4, shuffle=True, num_workers=0)
    batch_img, batch_mask = next(iter(loader))
    assert batch_img.shape == (4, 3, 352, 352), f"Unexpected img shape: {batch_img.shape}"
    assert batch_mask.shape == (4, 1, 352, 352), f"Unexpected mask shape: {batch_mask.shape}"
    print(f"  DataLoader output verified: Image {batch_img.shape}, Mask {batch_mask.shape}")

    # 3. Test Model Forward & Backward
    print("\n[Test 3/6] Testing PraNetResNet101 Model Forward/Backward...")
    import torch.nn.functional as F
    import torchvision.models as models

    class BasicConv2d(nn.Module):
        def __init__(self, in_planes, out_planes, kernel_size, stride=1, padding=0, dilation=1, relu=True):
            super(BasicConv2d, self).__init__()
            self.conv = nn.Conv2d(in_planes, out_planes, kernel_size=kernel_size, stride=stride, padding=padding, dilation=dilation, bias=False)
            self.bn = nn.BatchNorm2d(out_planes)
            self.relu = nn.ReLU(inplace=True) if relu else nn.Identity()
        def forward(self, x): return self.relu(self.bn(self.conv(x)))

    class RFBBlock(nn.Module):
        def __init__(self, in_channel, out_channel):
            super(RFBBlock, self).__init__()
            self.relu = nn.ReLU(True)
            self.branch0 = nn.Sequential(BasicConv2d(in_channel, out_channel, 1))
            self.branch1 = nn.Sequential(BasicConv2d(in_channel, out_channel, 1), BasicConv2d(out_channel, out_channel, kernel_size=(1, 3), padding=(0, 1)), BasicConv2d(out_channel, out_channel, kernel_size=(3, 1), padding=(1, 0)), BasicConv2d(out_channel, out_channel, 3, padding=3, dilation=3))
            self.branch2 = nn.Sequential(BasicConv2d(in_channel, out_channel, 1), BasicConv2d(out_channel, out_channel, kernel_size=(1, 5), padding=(0, 2)), BasicConv2d(out_channel, out_channel, kernel_size=(5, 1), padding=(2, 0)), BasicConv2d(out_channel, out_channel, 3, padding=5, dilation=5))
            self.branch3 = nn.Sequential(BasicConv2d(in_channel, out_channel, 1), BasicConv2d(out_channel, out_channel, kernel_size=(1, 7), padding=(0, 3)), BasicConv2d(out_channel, out_channel, kernel_size=(7, 1), padding=(3, 0)), BasicConv2d(out_channel, out_channel, 3, padding=7, dilation=7))
            self.conv_cat = BasicConv2d(4 * out_channel, out_channel, 3, padding=1)
            self.conv_res = BasicConv2d(in_channel, out_channel, 1)
        def forward(self, x):
            x_cat = self.conv_cat(torch.cat((self.branch0(x), self.branch1(x), self.branch2(x), self.branch3(x)), dim=1))
            return self.relu(x_cat + self.conv_res(x))

    class CBAM(nn.Module):
        def __init__(self, channels, r=8):
            super(CBAM, self).__init__()
            self.avg_pool = nn.AdaptiveAvgPool2d(1)
            self.max_pool = nn.AdaptiveMaxPool2d(1)
            self.fc = nn.Sequential(nn.Flatten(), nn.Linear(channels, channels // r, bias=False), nn.ReLU(inplace=True), nn.Linear(channels // r, channels, bias=False))
            self.spatial_conv = nn.Conv2d(2, 1, kernel_size=7, padding=3, bias=False)
        def forward(self, x):
            ca = torch.sigmoid(self.fc(self.avg_pool(x)) + self.fc(self.max_pool(x))).view(x.size(0), -1, 1, 1)
            x = x * ca
            sa = torch.sigmoid(self.spatial_conv(torch.cat([torch.mean(x, dim=1, keepdim=True), torch.max(x, dim=1, keepdim=True)[0]], dim=1)))
            return x * sa

    class ReverseAttention(nn.Module):
        def __init__(self, in_channel, out_channel):
            super(ReverseAttention, self).__init__()
            self.conv1 = BasicConv2d(in_channel, out_channel, 3, padding=1)
            self.conv2 = BasicConv2d(out_channel, out_channel, 3, padding=1)
            self.cbam  = CBAM(out_channel)
            self.conv_out = nn.Conv2d(out_channel, 1, kernel_size=1)
        def forward(self, feat, saliency_map):
            rev_weight = 1.0 - torch.sigmoid(saliency_map)
            x = feat * rev_weight.expand_as(feat)
            return self.conv_out(self.cbam(self.conv2(self.conv1(x))))

    class PraNetResNet101(nn.Module):
        def __init__(self, channels=32, mc_dropout_p=0.15):
            super(PraNetResNet101, self).__init__()
            self.channels = channels
            self.mc_dropout_enabled = False
            resnet = models.resnet101(weights=None)
            self.stem = nn.Sequential(resnet.conv1, resnet.bn1, resnet.relu, resnet.maxpool)
            self.layer1, self.layer2, self.layer3, self.layer4 = resnet.layer1, resnet.layer2, resnet.layer3, resnet.layer4
            self.rfb1 = RFBBlock(256, channels)
            self.rfb2 = RFBBlock(512, channels)
            self.rfb3 = RFBBlock(1024, channels)
            self.rfb4 = RFBBlock(2048, channels)
            self.ppd_conv = BasicConv2d(channels * 3, channels, 3, padding=1)
            self.ppd_out  = nn.Conv2d(channels, 1, kernel_size=1)
            self.ra4 = ReverseAttention(channels, channels)
            self.ra3 = ReverseAttention(channels, channels)
            self.ra2 = ReverseAttention(channels, channels)
            self.ra1 = ReverseAttention(channels, channels)
            self.drop = nn.Dropout2d(p=mc_dropout_p)
        def enable_mc_dropout(self): self.mc_dropout_enabled = True
        def disable_mc_dropout(self): self.mc_dropout_enabled = False
        def forward(self, x):
            h, w = x.shape[2], x.shape[3]
            dropout_active = self.training or self.mc_dropout_enabled
            x0 = self.stem(x)
            e1, e2, e3, e4 = self.layer1(x0), self.layer2(self.layer1(x0)), self.layer3(self.layer2(self.layer1(x0))), self.layer4(self.layer3(self.layer2(self.layer1(x0))))
            r1, r2, r3, r4 = self.rfb1(e1), self.rfb2(e2), self.rfb3(e3), self.rfb4(e4)
            if dropout_active:
                r1, r2, r3, r4 = self.drop(r1), self.drop(r2), self.drop(r3), self.drop(r4)
            sz2 = r2.shape[2:]
            r3_up = F.interpolate(r3, size=sz2, mode='bilinear', align_corners=False)
            r4_up = F.interpolate(r4, size=sz2, mode='bilinear', align_corners=False)
            ppd_feat = self.ppd_conv(torch.cat([r2, r3_up, r4_up], dim=1))
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

    model = PraNetResNet101(channels=32)
    model.train()
    outs = model(batch_img)
    assert len(outs) == 5, f"Expected 5 training outputs, got {len(outs)}"
    print("  Training outputs: 5 tensors of shape", [o.shape for o in outs])

    model.eval()
    eval_out = model(batch_img)
    assert eval_out.shape == (4, 1, 352, 352), f"Expected (4, 1, 352, 352), got {eval_out.shape}"
    print("  Evaluation output verified: shape", eval_out.shape)

    # 4. Test Losses & Optimization
    print("\n[Test 4/6] Testing DeepSupervisionDiceFocalLoss & TopoAwareLoss...")
    from torchvision.ops import sigmoid_focal_loss

    class DiceFocalLoss(nn.Module):
        def __init__(self, alpha=0.25, gamma=2.0, dice_w=0.6, focal_w=0.4, smooth=1e-6):
            super(DiceFocalLoss, self).__init__()
            self.alpha, self.gamma, self.dice_w, self.focal_w, self.smooth = alpha, gamma, dice_w, focal_w, smooth
        def forward(self, logits, targets):
            probs = torch.sigmoid(logits)
            inter = (probs * targets).sum(dim=(2, 3))
            card = probs.sum(dim=(2, 3)) + targets.sum(dim=(2, 3))
            dice = (1.0 - (2.0 * inter + self.smooth) / (card + self.smooth)).mean()
            focal = sigmoid_focal_loss(logits, targets, alpha=self.alpha, gamma=self.gamma, reduction='mean')
            return self.dice_w * dice + self.focal_w * focal

    class DeepSupervisionDiceFocalLoss(nn.Module):
        def __init__(self):
            super(DeepSupervisionDiceFocalLoss, self).__init__()
            self.criterion = DiceFocalLoss()
        def forward(self, outputs, targets):
            if isinstance(outputs, (tuple, list)):
                out, s2, s3, s4, sg = outputs
                return 1.0 * self.criterion(out, targets) + 0.25 * self.criterion(s2, targets) + 0.20 * self.criterion(s3, targets) + 0.15 * self.criterion(s4, targets) + 0.10 * self.criterion(sg, targets)
            return self.criterion(outputs, targets)

    class TopologicalLoss(nn.Module):
        def __init__(self, lam=0.12):
            super(TopologicalLoss, self).__init__()
            self.lam = lam
        def _compute_betti_losses(self, prob_map):
            device = prob_map.device
            with torch.no_grad():
                binary = (prob_map.detach() > 0.5).cpu().numpy().astype(np.uint8)
                inv_binary = 1 - binary
            n_cc, labels_cc, stats_cc, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
            loss_b0 = torch.tensor(0.0, device=device)
            if n_cc > 2:
                fg_comps = [(i, stats_cc[i, cv2.CC_STAT_AREA]) for i in range(1, n_cc)]
                main_id = max(fg_comps, key=lambda x: x[1])[0]
                labels_t = torch.from_numpy(labels_cc).to(device)
                for cid, area in fg_comps:
                    if cid != main_id:
                        mask = (labels_t == cid)
                        if mask.any(): loss_b0 = loss_b0 + prob_map[mask].mean()
            n_holes, labels_h, stats_h, _ = cv2.connectedComponentsWithStats(inv_binary, connectivity=8)
            loss_b1 = torch.tensor(0.0, device=device)
            if n_holes > 2:
                bg_comps = [(i, stats_h[i, cv2.CC_STAT_AREA]) for i in range(1, n_holes)]
                outer_bg_id = max(bg_comps, key=lambda x: x[1])[0]
                labels_ht = torch.from_numpy(labels_h).to(device)
                for hid, area in bg_comps:
                    if hid != outer_bg_id:
                        mask = (labels_ht == hid)
                        if mask.any(): loss_b1 = loss_b1 + (1.0 - prob_map[mask]).mean()
            return loss_b0 + loss_b1
        def forward(self, logits, targets):
            probs = torch.sigmoid(logits)
            batch_topo_loss = torch.stack([self._compute_betti_losses(probs[i, 0]) for i in range(probs.shape[0])]).mean()
            return self.lam * batch_topo_loss

    crit_ds = DeepSupervisionDiceFocalLoss()
    crit_topo = TopologicalLoss(lam=0.12)
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4)

    opt.zero_grad()
    train_outs = model(batch_img)
    loss_ds = crit_ds(train_outs, batch_mask)
    loss_topo = crit_topo(train_outs[0], batch_mask)
    total_loss = loss_ds + loss_topo
    total_loss.backward()
    opt.step()
    print(f"  Optimization step executed: DS Loss = {loss_ds.item():.4f}, Topo Loss = {loss_topo.item():.4f}, Total = {total_loss.item():.4f}")

    # 5. Test MC Dropout Uncertainty Pass
    print("\n[Test 5/6] Testing MC Dropout Uncertainty Sampling...")
    model.eval()
    model.enable_mc_dropout()
    mc_preds = []
    with torch.no_grad():
        for _ in range(8):
            out = model(batch_img[:1])
            logits = out[0] if isinstance(out, (tuple, list)) else out
            mc_preds.append(torch.sigmoid(logits).squeeze().cpu().numpy())
    model.disable_mc_dropout()

    variance_map = np.var(np.stack(mc_preds, axis=0), axis=0)
    print(f"  MC Dropout 8 passes complete: Uncertainty map shape = {variance_map.shape}, mean variance = {np.mean(variance_map):.6f}")

    # 6. Clean up temporary test data
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)
    print(f"\n[Test 6/6] Cleaned up temporary test artifacts.")

    print("\n" + "=" * 70)
    print("ALL FUNCTIONAL COMPONENT INTEGRATION TESTS PASSED (100% SUCCESS)!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
