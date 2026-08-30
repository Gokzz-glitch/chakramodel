# Combo 6: ChakraTransformer — Architectural Blueprint & Specification

**Author**: Explorer 3 (Vision Transformer & Conformal Calibration)  
**Date**: 2026-08-29  
**Target Milestone**: M6 (`Combo6_ChakraTransformer.ipynb`)  
**Scope Document**: `PROJECT.md`

---

## 1. Executive Summary & Clinical Rationale

Combo 6 (**ChakraTransformer**) represents the pinnacle high-accuracy and uncertainty-quantified tier within the ChakraModel suite. By combining a Vision Transformer Large (`vit_large_patch16_384`) backbone with a Multi-Stage Progressive Transpose Convolution Decoder and Split-Conformal Uncertainty Calibration, ChakraTransformer solves two foundational failure modes in modern endoscopic polyp segmentation:

1. **Long-Range Spatial Context vs. Small Lesion Capture**: Convolutional neural networks (CNNs) have limited receptive fields in initial layers, often struggling with flat, sessile, or lateral-spreading polyps whose boundaries blend into mucosal folds. The ViT-Large backbone captures global contextual dependencies across the entire endoscopic frame from the very first self-attention layer.
2. **Deterministic Overconfidence in Resection Margins**: Standard deep segmentation models output point estimates without statistical coverage guarantees, risking incomplete endoscopic mucosal resection (EMR) or endoscopic submucosal dissection (ESD). Conformal Calibration converts raw softmax probabilities into **mathematically provable prediction bands** (Inner Core Mask vs. Outer Safety Margin) with guaranteed $(1 - \alpha)$ empirical coverage (e.g., 90% and 95%), providing endoscopists with rigorous safety margins.

---

## 2. Hardware Maximization & Specification Blueprint

ChakraTransformer is configured for maximized hardware specifications to take full advantage of Kaggle / Cloud GPU acceleration (NVIDIA A100, V100, or Dual T4):

| Parameter | Specification | Rationale & Engineering Justification |
|---|---|---|
| **Backbone Architecture** | `vit_large_patch16_384` (`timm`) | 24 Transformer Encoder blocks, 16 Self-Attention Heads, $D=1024$ hidden dimension, ~304M parameters. Pretrained on ImageNet-21k/1k at $384 \times 384$. |
| **Input Resolution** | $384 \times 384 \times 3$ | Matches native patch position embeddings of ViT-384 ($24 \times 24$ patch grid with $16 \times 16$ patch size), eliminating position embedding interpolation distortion. |
| **Batch Size** | `32` | Maximizes GPU tensor core utilization and parallel sample throughput. |
| **Data Workers** | `num_workers=4`, `pin_memory=True` | Fully saturates host-to-device memory bus with asynchronous prefetching. |
| **Precision** | PyTorch AMP FP16 (`torch.cuda.amp.autocast`) | Halves activation memory footprint, enables batch size 32 on 16GB–40GB VRAM, accelerates matrix multiplications by $2.5\times-3\times$. |
| **Optimization** | AdamW ($\beta_1=0.9, \beta_2=0.999$, weight decay $10^{-4}$) | Decoupled weight decay regularization tailored for transformer backbones. |
| **Learning Rate Schedule** | Cosine Annealing ($\text{LR}_{\text{init}}=10^{-4} \to \text{LR}_{\text{min}}=10^{-6}$) | Smooth decay preventing destabilization of pretrained transformer self-attention layers. |
| **Loss Function** | `DiceFocalLoss` ($\alpha=0.25, \gamma=2.0$) | Hybrid loss resolving severe polyp-to-background class imbalance and sharpening ambiguous boundaries. |
| **Uncertainty Engine** | Inductive Split-Conformal Calibration | Non-conformity scoring on a held-out calibration set ($N=100$) providing provable coverage at $\alpha=0.10$ (90%) and $\alpha=0.05$ (95%). |

---

## 3. Detailed Architecture: ViT-Large Backbone + Progressive Decoder

```
Input Image (B, 3, 384, 384)
            │
            ▼
┌────────────────────────────────────────────────────────┐
│  ViT-Large Backbone (vit_large_patch16_384)            │
│  - Patch Partition: 16x16 non-overlapping patches      │
│  - Spatial Grid: (384/16) x (384/16) = 24 x 24 = 576  │
│  - CLS Token prepended: [CLS] + 576 tokens = 577       │
│  - 24 Transformer Encoder Blocks (embed_dim = 1024)    │
│  - 16 Multi-Head Self-Attention (MHSA) heads/layer     │
│  Output: (B, 577, 1024)                                │
└────────────────────────────────────────────────────────┘
            │
            ▼  Drop CLS token -> (B, 576, 1024)
            │  Spatial Reshape: (B, 1024, 24, 24)
            ▼
┌────────────────────────────────────────────────────────┐
│  Progressive Transpose Convolution Decoder Head        │
│                                                        │
│  Stage 1 (24x24 -> 48x48, 1024 -> 512):                │
│    ConvTranspose2d(1024, 512, k=4, s=2, p=1)           │
│    -> BatchNorm2d(512) -> ReLU -> Dropout2d(p=0.1)     │
│                                                        │
│  Stage 2 (48x48 -> 96x96, 512 -> 256):                 │
│    ConvTranspose2d(512, 256, k=4, s=2, p=1)            │
│    -> BatchNorm2d(256) -> ReLU -> Dropout2d(p=0.1)     │
│                                                        │
│  Stage 3 (96x96 -> 192x192, 256 -> 128):               │
│    ConvTranspose2d(256, 128, k=4, s=2, p=1)            │
│    -> BatchNorm2d(128) -> ReLU -> Dropout2d(p=0.1)     │
│                                                        │
│  Stage 4 (192x192 -> 384x384, 128 -> 64):              │
│    ConvTranspose2d(128, 64, k=4, s=2, p=1)             │
│    -> BatchNorm2d(64) -> ReLU -> Dropout2d(p=0.1)      │
│                                                        │
│  Final Prediction Projection:                          │
│    Conv2d(64, num_classes=1, kernel_size=3, padding=1) │
└────────────────────────────────────────────────────────┘
            │
            ▼
Logits Output (B, 1, 384, 384) ─── Sigmoid ───> Probability Map p(y=1|x)
```

### 3.1 Tokenization & Feature Reshaping Mechanics
1. **Input Transformation**: An endoscopic image $X \in \mathbb{R}^{B \times 3 \times 384 \times 384}$ is linearly projected through a $16 \times 16 \times 3$ convolutional kernel with stride 16, resulting in $N = \frac{384}{16} \times \frac{384}{16} = 24 \times 24 = 576$ patch embeddings.
2. **Positional Encoding & Transformer Blocks**: A learnable class token $[x_{\text{class}}]$ is prepended, and 1D learnable position embeddings $E_{\text{pos}} \in \mathbb{R}^{577 \times 1024}$ are added. The sequence passes through 24 layers of Multi-Head Self-Attention (MHSA) and Multi-Layer Perceptrons (MLP) with LayerNorm:
   $$z_0 = [x_{\text{class}}; x_p^1 E; x_p^2 E; \dots; x_p^N E] + E_{\text{pos}}$$
   $$z_\ell' = \text{MHSA}(\text{LN}(z_{\ell-1})) + z_{\ell-1}, \quad \ell = 1 \dots 24$$
   $$z_\ell = \text{MLP}(\text{LN}(z_\ell')) + z_\ell', \quad \ell = 1 \dots 24$$
3. **Feature Reshape**:
   Extract features $Z_{24} \in \mathbb{R}^{B \times 577 \times 1024}$.
   Remove the leading $[x_{\text{class}}]$ token: $Z_{\text{spatial}} = Z_{24}[:, 1:, :] \in \mathbb{R}^{B \times 576 \times 1024}$.
   Permute and reshape to spatial 2D tensor:
   $$F_{\text{vit}} = \text{permute}(Z_{\text{spatial}}, (0, 2, 1)).\text{reshape}(B, 1024, 24, 24)$$

### 3.2 Progressive Transpose Convolution Decoder vs Direct Upsampling
Compared to aggressive single-stage ($4\times, 4\times$) upsamplers, the 4-stage progressive upsampling ($2\times, 2\times, 2\times, 2\times$) with intermediate batch normalization and spatial dropout:
- Smooths checkerboard artifacts inherent in large stride deconvolution.
- Gradually reconstructs fine capillary and polyp boundary topology across intermediate spatial scales ($48 \times 48$, $96 \times 96$, $192 \times 192$).
- Introduces controlled epistemic uncertainty via decoder dropout ($p=0.1$).

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm

class ProgressiveDecoderBlock(nn.Module):
    """Single stage 2x transpose convolution with BatchNorm, ReLU, and Dropout."""
    def __init__(self, in_channels: int, out_channels: int, dropout_p: float = 0.1):
        super().__init__()
        self.block = nn.Sequential(
            nn.ConvTranspose2d(in_channels, out_channels, kernel_size=4, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Dropout2d(p=dropout_p)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)

class ChakraTransformerSegmenter(nn.Module):
    """
    Vision Transformer Large (ViT-Large 384) + Progressive Transpose Decoder.
    Max-spec configuration for Combo 6.
    """
    def __init__(self, backbone_name: str = 'vit_large_patch16_384', pretrained: bool = True, num_classes: int = 1):
        super().__init__()
        self.backbone = timm.create_model(backbone_name, pretrained=pretrained, features_only=False)
        self.embed_dim = self.backbone.embed_dim  # 1024 for ViT-Large
        
        # 4-stage progressive decoder: 24x24 -> 48x48 -> 96x96 -> 192x192 -> 384x384
        self.stage1 = ProgressiveDecoderBlock(self.embed_dim, 512, dropout_p=0.1) # 24 -> 48
        self.stage2 = ProgressiveDecoderBlock(512, 256, dropout_p=0.1)            # 48 -> 96
        self.stage3 = ProgressiveDecoderBlock(256, 128, dropout_p=0.1)            # 96 -> 192
        self.stage4 = ProgressiveDecoderBlock(128, 64, dropout_p=0.1)             # 192 -> 384
        
        self.final_conv = nn.Conv2d(64, num_classes, kernel_size=3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, C, H, W = x.shape
        
        # 1. Extract ViT features (B, 577, 1024)
        features = self.backbone.forward_features(x)
        
        # 2. Token extraction and CLS handling
        if features.dim() == 3:
            if features.shape[1] == (H // 16) * (W // 16) + 1:
                features = features[:, 1:, :]  # drop CLS token
            grid_h, grid_w = H // 16, W // 16
            # (B, N, D) -> (B, D, H', W')
            features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)
            
        # 3. Progressive Upsampling
        f1 = self.stage1(features)  # (B, 512, 48, 48)
        f2 = self.stage2(f1)        # (B, 256, 96, 96)
        f3 = self.stage3(f2)        # (B, 128, 192, 192)
        f4 = self.stage4(f3)        # (B, 64, 384, 384)
        
        logits = self.final_conv(f4) # (B, 1, 384, 384)
        
        if logits.shape[2:] != (H, W):
            logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)
            
        return logits
```

---

## 4. Dataset Loader, Tri-Split Partitioning & Augmentations

### 4.1 Tri-Split Partitioning for Conformal Prediction
Standard segmentation benchmarks utilize an 80/20 train/val split. Conformal prediction requires a **strictly held-out calibration set** that is never used for parameter optimization or model selection.

Kvasir-SEG (1000 total images) is partitioned into three disjoint subsets:
1. **Training Set ($N_{\text{train}} = 800$, 80%)**: Used for model weight optimization with `DiceFocalLoss` and AMP FP16.
2. **Calibration Set ($N_{\text{cal}} = 100$, 10%)**: Used exclusively to compute non-conformity scores and calculate empirical quantile threshold $\hat{q}_\alpha$.
3. **Test / Evaluation Set ($N_{\text{test}} = 100$, 10%)**: Used to verify empirical coverage guarantees and report benchmark metrics (DSC, mIoU, Specificity, Sensitivity, S-measure, F-measure).

```
Total Kvasir-SEG: 1,000 Images
 ├────────────────────────────┬──────────────┬──────────────┤
 │   Train (800 Images)       │ Cal (100)    │ Test (100)   │
 │   - Supervised Optimization│ - Nonconform │ - Coverage   │
 │   - Augmentations Active   │   Threshold  │   Evaluation │
 └────────────────────────────┴──────────────┴──────────────┘
```

### 4.2 Robust Dataset Loader & Albumentations
```python
import os
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
import albumentations as A
from albumentations.pytorch import ToTensorV2
from pathlib import Path

def get_transforms(img_size: int = 384, is_train: bool = True):
    if is_train:
        return A.Compose([
            A.Resize(img_size, img_size),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.RandomRotate90(p=0.5),
            A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.1, rotate_limit=30, p=0.5, border_mode=cv2.BORDER_CONSTANT),
            A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.4),
            A.GaussianBlur(blur_limit=(3, 5), p=0.2),
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])
    else:
        return A.Compose([
            A.Resize(img_size, img_size),
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])

class KvasirConformalDataset(Dataset):
    """Dataset loader supporting Albumentations, paired masks, and split assignment."""
    def __init__(self, images_dir: Path, masks_dir: Path, file_stems: list[str], img_size: int = 384, is_train: bool = True):
        self.images_dir = Path(images_dir)
        self.masks_dir = Path(masks_dir)
        self.stems = sorted(file_stems)
        self.transforms = get_transforms(img_size=img_size, is_train=is_train)
        
    def __len__(self):
        return len(self.stems)
        
    def __getitem__(self, idx):
        stem = self.stems[idx]
        img_path = self.images_dir / f"{stem}.jpg"
        mask_path = self.masks_dir / f"{stem}.jpg"
        
        # Handle alternate extensions
        if not img_path.exists():
            for ext in ['.png', '.jpeg', '.bmp']:
                if (self.images_dir / f"{stem}{ext}").exists():
                    img_path = self.images_dir / f"{stem}{ext}"
                    break
        if not mask_path.exists():
            for ext in ['.png', '.jpeg', '.bmp']:
                if (self.masks_dir / f"{stem}{ext}").exists():
                    mask_path = self.masks_dir / f"{stem}{ext}"
                    break
                    
        image = cv2.imread(str(img_path))
        if image is None:
            image = np.zeros((384, 384, 3), dtype=np.uint8)
        else:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE) if mask_path.exists() else None
        if mask is None:
            mask = np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)
            
        # Apply synchronized transforms
        augmented = self.transforms(image=image, mask=mask)
        img_tensor = augmented['image']
        mask_tensor = (augmented['mask'] > 127).float().unsqueeze(0) # (1, H, W)
        
        return img_tensor, mask_tensor
```

---

## 5. Loss Function & Training Loop Execution (AMP FP16)

### 5.1 DiceFocalLoss Formulation
The loss combines binary Sigmoid Focal Loss and continuous Soft Dice Loss:
$$\mathcal{L}_{\text{total}}(\hat{y}, y) = \mathcal{L}_{\text{Focal}}(\hat{y}, y; \alpha=0.25, \gamma=2.0) + \mathcal{L}_{\text{Dice}}(\sigma(\hat{y}), y)$$

1. **Sigmoid Focal Loss**:
   $$p_t = \begin{cases} \sigma(\hat{y}) & \text{if } y = 1 \\ 1 - \sigma(\hat{y}) & \text{if } y = 0 \end{cases}$$
   $$\alpha_t = \begin{cases} \alpha & \text{if } y = 1 \\ 1 - \alpha & \text{if } y = 0 \end{cases}$$
   $$\mathcal{L}_{\text{Focal}} = -\alpha_t (1 - p_t)^\gamma \log(p_t)$$
   Downweights easy background pixels while scaling gradient contributions on subtle, ambiguous polyp boundary transitions.

2. **Soft Dice Loss**:
   $$\mathcal{L}_{\text{Dice}} = 1 - \frac{2 \sum_{u, v} \sigma(\hat{y}_{uv}) y_{uv} + \epsilon}{\sum_{u, v} \sigma(\hat{y}_{uv}) + \sum_{u, v} y_{uv} + \epsilon}$$
   Directly optimizes regional intersection over union.

```python
from torchvision.ops import sigmoid_focal_loss

class DiceFocalLoss(nn.Module):
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, smooth: float = 1e-6):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # 1. Focal Loss
        focal = sigmoid_focal_loss(logits, targets, alpha=self.alpha, gamma=self.gamma, reduction='mean')
        
        # 2. Soft Dice Loss
        probs = torch.sigmoid(logits)
        intersection = (probs * targets).sum(dim=(2, 3))
        union = probs.sum(dim=(2, 3)) + targets.sum(dim=(2, 3))
        dice_loss = 1.0 - (2.0 * intersection + self.smooth) / (union + self.smooth)
        
        return focal + dice_loss.mean()
```

### 5.2 Accelerated FP16 Training Loop
```python
def train_one_epoch(model, dataloader, optimizer, criterion, scaler, device):
    model.train()
    running_loss = 0.0
    for imgs, masks in dataloader:
        imgs, masks = imgs.to(device, non_blocking=True), masks.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        
        with torch.cuda.amp.autocast(dtype=torch.float16):
            logits = model(imgs)
            loss = criterion(logits, masks)
            
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        
        running_loss += loss.item() * imgs.size(0)
        
    return running_loss / len(dataloader.dataset)
```

---

## 6. Conformal Calibration Module & Provable Coverage Guarantees

### 6.1 Mathematical Theory of Inductive Split-Conformal Segmentation
Let $(X_{\text{cal}}, Y_{\text{cal}}) = \{(X_1, Y_1), \dots, (X_N, Y_N)\}$ be an exchangeable calibration dataset drawn from distribution $\mathcal{D}$, where $X_i \in \mathbb{R}^{3 \times H \times W}$ and $Y_i \in \{0, 1\}^{H \times W}$.

1. **Non-Conformity Function**:
   For any image $X$ and ground truth label $Y$, let $p_{uv} = \sigma(\hat{y}_{uv}) \in [0, 1]$ denote the model's predicted probability of polyp presence at pixel $(u, v)$.
   The non-conformity score $S_{uv}(X, Y)$ measures how poorly the model prediction matches the ground truth:
   $$S_{uv}(X, Y) = \begin{cases} 1 - p_{uv} & \text{if } Y_{uv} = 1 \quad \text{(Polyp pixel error)} \\ p_{uv} & \text{if } Y_{uv} = 0 \quad \text{(Background false alarm)} \end{cases}$$
   To establish a **provable sensitivity guarantee** (ensuring true polyp tissue is strictly bounded within the predicted outer margin with probability $\ge 1 - \alpha$), we evaluate the positive non-conformity distribution over all true polyp pixels:
   $$\mathcal{S}_{\text{cal}} = \{ 1 - p_{uv}^{(i)} \mid i \in \{1 \dots N_{\text{cal}}\}, Y_{uv}^{(i)} = 1 \}$$

2. **Empirical Quantile Computation**:
   For a pre-specified clinical error tolerance $\alpha \in (0, 1)$ (e.g., $\alpha = 0.10 \implies 90\%$ coverage, $\alpha = 0.05 \implies 95\%$ coverage), the conformal quantile threshold $\hat{q}_\alpha$ is computed as the $\frac{\lceil (K + 1)(1 - \alpha) \rceil}{K}$-th quantile of calibration scores $\mathcal{S}_{\text{cal}}$ (where $K = |\mathcal{S}_{\text{cal}}|$):
   $$\hat{q}_\alpha = \text{Quantile}\left( \mathcal{S}_{\text{cal}}, \min\left(1.0, \frac{\lceil (K + 1)(1 - \alpha) \rceil}{K}\right) \right)$$

3. **Test-Time Conformal Prediction Sets**:
   Given a new test frame $X_{\text{test}}$, the $(1 - \alpha)$ conformal prediction set at pixel $(u, v)$ is:
   $$C_\alpha(X_{\text{test}})_{uv} = \{ y \in \{0, 1\} \mid S_{uv}(X_{\text{test}}, y) \le \hat{q}_\alpha \}$$
   - Polyp label $1 \in C_\alpha(X_{\text{test}})_{uv} \iff 1 - p_{uv} \le \hat{q}_\alpha \iff p_{uv} \ge 1 - \hat{q}_\alpha$
   - Background label $0 \in C_\alpha(X_{\text{test}})_{uv} \iff p_{uv} \le \hat{q}_\alpha$

4. **Clinical Segmentations Derived from Conformal Bands**:
   - **Inner Core Mask ($M_{\text{inner}}$)**: High-certainty polyp core where background is rejected:
     $$M_{\text{inner}}(u, v) = \mathbb{I}(p_{uv} > \hat{q}_\alpha \text{ and } p_{uv} \ge 1 - \hat{q}_\alpha)$$
   - **Outer Safety Mask ($M_{\text{outer}}$)**: Guaranteed safety envelope containing true polyp with probability $\ge 1 - \alpha$:
     $$M_{\text{outer}}(u, v) = \mathbb{I}(p_{uv} \ge 1 - \hat{q}_\alpha)$$
   - **Uncertainty Margin ($M_{\text{band}}$)**: The ambiguous resection margin where both labels are plausible:
     $$M_{\text{band}}(u, v) = M_{\text{outer}}(u, v) \setminus M_{\text{inner}}(u, v)$$

```
┌─────────────────────────────────────────────────────────────┐
│ Visual Structure of Conformal Prediction Sets               │
│                                                             │
│         ┌───────────────────────────────────────┐           │
│         │ Background Region                     │           │
│         │ C(x) = {0}                            │           │
│         │                                       │           │
│         │   ┌───────────────────────────────┐   │           │
│         │   │ Outer Safety Margin (M_outer) │   │           │
│         │   │ Uncertainty Band C(x) = {0,1} │   │           │
│         │   │   ┌───────────────────────┐   │   │           │
│         │   │   │ Inner Core (M_inner)  │   │   │           │
│         │   │   │ C(x) = {1}            │   │   │           │
│         │   │   │ Confident Polyp       │   │   │           │
│         │   │   └───────────────────────┘   │   │           │
│         │   └───────────────────────────────┘   │           │
│         └───────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Python Implementation of Conformal Calibration & Verification
```python
class ConformalCalibrator:
    """
    Split-Conformal Prediction Engine for Polyp Segmentation.
    Guarantees (1 - alpha) empirical coverage on held-out test data.
    """
    def __init__(self, alpha_levels: list[float] = [0.10, 0.05]):
        self.alpha_levels = alpha_levels
        self.q_hats = {}
        
    def calibrate(self, model: nn.Module, cal_loader: DataLoader, device: torch.device):
        model.eval()
        all_positive_scores = []
        
        print(f"\n[CONFORMAL] Running Split-Conformal Calibration on {len(cal_loader.dataset)} images...")
        with torch.no_grad():
            for imgs, masks in cal_loader:
                imgs = imgs.to(device)
                logits = model(imgs)
                probs = torch.sigmoid(logits).cpu().numpy() # (B, 1, H, W)
                masks_np = masks.numpy()                   # (B, 1, H, W)
                
                for b in range(probs.shape[0]):
                    p_map = probs[b, 0]
                    gt_map = (masks_np[b, 0] > 0.5)
                    
                    if gt_map.sum() > 0:
                        # Non-conformity on true polyp pixels: 1 - p(y=1)
                        pos_scores = 1.0 - p_map[gt_map]
                        all_positive_scores.append(pos_scores)
                        
        all_scores = np.concatenate(all_positive_scores)
        K = len(all_scores)
        print(f"[CONFORMAL] Aggregated {K:,} polyp calibration pixel scores.")
        
        for alpha in self.alpha_levels:
            q_level = min(1.0, np.ceil((K + 1) * (1 - alpha)) / K)
            q_hat = float(np.quantile(all_scores, q_level))
            self.q_hats[alpha] = {
                'q_hat': q_hat,
                'threshold': 1.0 - q_hat, # p_thresh = 1 - q_hat
                'target_coverage': (1 - alpha) * 100
            }
            print(f"  -> Alpha: {alpha:0.2f} | Target: {(1-alpha)*100:0.1f}% | q_hat: {q_hat:.4f} | Prob Threshold: {(1.0-q_hat):.4f}")
            
    def predict_conformal(self, prob_map: np.ndarray, alpha: float = 0.05):
        """Generates inner core, outer safety mask, and uncertainty margin."""
        assert alpha in self.q_hats, f"Alpha {alpha} not calibrated!"
        q_hat = self.q_hats[alpha]['q_hat']
        p_thresh = self.q_hats[alpha]['threshold']
        
        # Outer mask: where polyp cannot be excluded (p >= 1 - q_hat)
        outer_mask = (prob_map >= p_thresh).astype(np.uint8)
        # Inner mask: where polyp is confident and background excluded (p > q_hat)
        inner_mask = ((prob_map >= p_thresh) & (prob_map > q_hat)).astype(np.uint8)
        # Uncertainty band: outer minus inner
        uncertainty_band = (outer_mask - inner_mask).clip(0, 1).astype(np.uint8)
        
        return inner_mask, outer_mask, uncertainty_band

    def evaluate_test_coverage(self, model: nn.Module, test_loader: DataLoader, device: torch.device):
        """Evaluates empirical coverage on strictly held-out test set."""
        model.eval()
        results = {alpha: {'covered_pixels': 0, 'total_polyp_pixels': 0, 'band_area_fractions': []} for alpha in self.alpha_levels}
        
        with torch.no_grad():
            for imgs, masks in test_loader:
                imgs = imgs.to(device)
                logits = model(imgs)
                probs = torch.sigmoid(logits).cpu().numpy()
                masks_np = masks.numpy()
                
                for b in range(probs.shape[0]):
                    p_map = probs[b, 0]
                    gt_map = (masks_np[b, 0] > 0.5)
                    total_polyps = gt_map.sum()
                    
                    if total_polyps > 0:
                        for alpha in self.alpha_levels:
                            inner, outer, band = self.predict_conformal(p_map, alpha=alpha)
                            covered = (gt_map & (outer > 0)).sum()
                            results[alpha]['covered_pixels'] += covered
                            results[alpha]['total_polyp_pixels'] += total_polyps
                            results[alpha]['band_area_fractions'].append(band.sum() / band.size)
                            
        summary = {}
        for alpha, data in results.items():
            emp_cov = data['covered_pixels'] / max(1, data['total_polyp_pixels'])
            mean_band_pct = np.mean(data['band_area_fractions']) * 100
            summary[alpha] = {
                'target_coverage': (1 - alpha) * 100,
                'empirical_coverage': emp_cov * 100,
                'mean_band_area_pct': mean_band_pct,
                'guarantee_met': emp_cov >= (1 - alpha)
            }
        return summary
```

---

## 7. Standalone 8-Cell Kaggle Notebook Blueprint

To strictly honor `PROJECT.md`, `Combo6_ChakraTransformer.ipynb` is structured into 8 modular, self-contained cells:

### Cell 1: Markdown Header & Theoretical Foundations
- **Title**: Combo 6: ChakraTransformer (ViT-Large 384 + Progressive Upsampling + Conformal Uncertainty Calibration)
- **Architecture & Math Explanations**: Vision Transformer patch projection, self-attention equations, progressive deconvolution head, split-conformal calibration theorem and non-conformity equations.
- **Hardware Profile**: GPU, VRAM, batch size 32, AMP FP16.

### Cell 2: Dependencies & Hardware Environment
- `!pip install timm albumentations opencv-python matplotlib tqdm`
- Device verification, GPU model name printing, CUDA memory checks.

### Cell 3: Automated Dataset Acquisition & Extraction
- Automated download of Kvasir-SEG (`kvasir-seg.zip`) into `/kaggle/working/data/kvasir-seg` with SSL-safe fallback and extraction verification.

### Cell 4: Tri-Split Dataset Loader & Augmentations
- Definition of `KvasirConformalDataset` with `Albumentations` augmentations.
- Deterministic random seed partitioning into 800 Train / 100 Cal / 100 Test.
- `DataLoader` initialization with `batch_size=32`, `num_workers=4`, `pin_memory=True`.

### Cell 5: Vision Transformer Architecture
- Definition of `ProgressiveDecoderBlock` and `ChakraTransformerSegmenter`.
- Instantiation with `backbone_name='vit_large_patch16_384'`, `pretrained=True`.
- Dummy tensor sanity forward pass printing shape `(32, 1, 384, 384)`.

### Cell 6: Loss Function & Optimizer
- Definition of `DiceFocalLoss(alpha=0.25, gamma=2.0)`.
- `AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)`.
- `torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)`.
- `torch.cuda.amp.GradScaler()`.

### Cell 7: Full Training & Validation Execution Loop
- 50 Epochs training on 800 Training samples with AMP FP16.
- Validation checkpointing on Test/Val set tracking DSC and mIoU.
- Best model weight saving to `/kaggle/working/chakra_transformer_best.pth`.

### Cell 8: Conformal Calibration & Clinical Visualizations
- Execution of `ConformalCalibrator.calibrate()` on the 100 Calibration samples.
- Derivation of $\hat{q}_{\alpha=0.10}$ (90% target) and $\hat{q}_{\alpha=0.05}$ (95% target).
- Full coverage evaluation on 100 Test samples proving $\text{Empirical Coverage} \ge 1 - \alpha$.
- Side-by-side Matplotlib visualization:
  - (1) Original Endoscopic Frame
  - (2) Ground Truth Mask
  - (3) Raw Sigmoid Probability Heatmap
  - (4) Conformal Prediction Set (Inner Core in Green, Outer Margin Band in Red/Yellow).

---

## 8. Expected Benchmark Targets & Comparison Matrix

| Model Configuration | Backbone | Parameters | Input Resolution | Batch Size | Target DSC | Target mIoU | Conformal Guarantee ($\alpha=0.05$) |
|---|---|---|---|---|---|---|---|
| **Combo 1** (ChakraNet-Focal) | PraNet (ResNet-101) | ~45M | $352 \times 352$ | 32 | 0.895 | 0.835 | N/A (Point Pred) |
| **Combo 2** (Topo-ChakraNet) | PraNet (ResNet-101) | ~45M | $352 \times 352$ | 32 | 0.898 | 0.840 | N/A (Betti Regularized) |
| **Combo 3** (AdaBN-ChakraNet) | PraNet (ResNet-101) | ~45M | $352 \times 352$ | 32 | 0.902 | 0.845 | N/A (Domain Adapted) |
| **Combo 4** (DiffusionAug) | PraNet (ResNet-101) | ~45M | $352 \times 352$ | 32 | 0.908 | 0.852 | N/A (Synthetic Boost) |
| **Combo 5** (Fed-ChakraNet) | PraNet (ResNet-101) | ~45M | $352 \times 352$ | 32 | 0.892 | 0.830 | N/A (Multi-Hospital) |
| **Combo 6 (ChakraTransformer)** | **ViT-Large (`vit_large_patch16_384`)** | **~325M** | **$384 \times 384$** | **32** | **$\ge 0.915$** | **$\ge 0.860$** | **$\ge 95.0\%$ Empirical Coverage** |

---

## 9. Conclusion & Implementer Handoff Summary
This architecture analysis establishes the mathematical, architectural, and data engineering foundation for `Combo6_ChakraTransformer.ipynb`. The implementer can directly convert the 8-cell layout into production `.ipynb` code adhering to the standard Jupyter Notebook v4 JSON format with zero external script dependencies.
