import os, cv2, torch
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from tqdm import tqdm
import timm

class ChakraTransformerSegmenter(nn.Module):
    def __init__(self, backbone_name: str = 'vit_large_patch16_384', pretrained: bool = False, num_classes: int = 1):
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
            nn.Conv2d(64, num_classes, kernel_size=3, padding=1),
        )
        self.dropout1 = nn.Dropout2d(p=0.5)
        self.dropout2 = nn.Dropout2d(p=0.5)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, h, w = x.shape
        features = self.backbone.forward_features(x)
        if features.dim() == 3:
            grid_h, grid_w = h // 16, w // 16
            expected = grid_h * grid_w
            if features.shape[1] == expected + 1:
                features = features[:, 1:, :]
            elif features.shape[1] > expected:
                features = features[:, :expected, :]
            features = features.transpose(1, 2).contiguous().view(b, self.embed_dim, grid_h, grid_w)
            
        x_dec = features
        for i, layer in enumerate(self.decode_head):
            x_dec = layer(x_dec)
            if i == 2: x_dec = self.dropout1(x_dec)
            elif i == 5: x_dec = self.dropout2(x_dec)
            
        logits = x_dec
        if logits.shape[2:] != (h, w):
            logits = F.interpolate(logits, size=(h, w), mode='bilinear', align_corners=False)
        return logits


def context_pad_bbox(x1, y1, x2, y2, frame_w, frame_h, pad_ratio=0.5):
    w, h = x2 - x1, y2 - y1
    pad_x, pad_y = w * pad_ratio, h * pad_ratio
    return (
        max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y)),
        min(frame_w, int(x2 + pad_x)), min(frame_h, int(y2 + pad_y))
    )

def pad_to_square_then_resize(crop, target=384):
    h, w = crop.shape[:2]
    side = max(h, w)
    canvas = np.zeros((side, side, 3), dtype=crop.dtype)
    y_off, x_off = (side - h) // 2, (side - w) // 2
    canvas[y_off:y_off+h, x_off:x_off+w] = crop
    resized = cv2.resize(canvas, (target, target), interpolation=cv2.INTER_LINEAR)
    return resized, (x_off, y_off, side)

def unpad_and_resize_mask(pred_mask, x_off, y_off, side, orig_h, orig_w):
    # Mask is target x target. Resize back to side x side
    mask_side = cv2.resize(pred_mask.astype(np.float32), (side, side), interpolation=cv2.INTER_LINEAR)
    # Crop out the pad
    mask_crop = mask_side[y_off:y_off+orig_h, x_off:x_off+orig_w]
    return mask_crop

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print("Loading model...")
model = ChakraTransformerSegmenter(pretrained=False).to(device)
weights = torch.load('M:/chakramodel/weights/chakra_transformer_best.pth', map_location=device, weights_only=True)
model.load_state_dict(weights)
model.eval()

img_files = sorted([f for f in Path('M:/chakramodel/datasets/colon_cancer_dataset/segmented-images/images').iterdir() if f.suffix.lower() in {'.jpg','.png'}])
mask_dict = {f.stem: f for f in Path('M:/chakramodel/datasets/colon_cancer_dataset/segmented-images/masks').iterdir()}

np.random.seed(42)
perm = np.random.permutation(len(img_files))
test_files = [img_files[i] for i in perm[850:870]]  # 20 test images

mean = np.array([0.485, 0.456, 0.406])
std = np.array([0.229, 0.224, 0.225])

tight_dices = []
padded_dices = []

print(f"Validating {len(test_files)} images for Hybrid Crop effects...")

for img_path in test_files:
    img = cv2.imread(str(img_path))
    mask_path = mask_dict[img_path.stem]
    gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    gt_mask_bin = (gt_mask > 127).astype(np.uint8)
    
    # 1. Simulate YOLO Bbox from GT Mask (perfect localization)
    contours, _ = cv2.findContours(gt_mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: continue
    
    x, y, w, h = cv2.boundingRect(contours[0])
    # Add a small random perturbation to simulate YOLO +/- 10%
    x_pert = int(x + (np.random.rand() - 0.5) * 0.2 * w)
    y_pert = int(y + (np.random.rand() - 0.5) * 0.2 * h)
    w_pert = int(w * (1.0 + (np.random.rand() - 0.5) * 0.2))
    h_pert = int(h * (1.0 + (np.random.rand() - 0.5) * 0.2))
    
    x1 = max(0, x_pert)
    y1 = max(0, y_pert)
    x2 = min(img.shape[1], x1 + w_pert)
    y2 = min(img.shape[0], y1 + h_pert)
    
    if (x2 - x1) < 10 or (y2 - y1) < 10:
        continue
    
    # Pipeline A: Tight Crop
    crop_tight = img[y1:y2, x1:x2]
    # Squashed resize
    crop_tight_resized = cv2.resize(crop_tight, (384, 384))
    crop_tight_rgb = cv2.cvtColor(crop_tight_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    crop_tight_rgb = (crop_tight_rgb - mean) / std
    t_tight = torch.from_numpy(crop_tight_rgb.transpose(2, 0, 1)).unsqueeze(0).float().to(device)
    
    with torch.no_grad():
        logits_tight = model(t_tight)
        pred_tight = torch.sigmoid(logits_tight)[0, 0].cpu().numpy()
        pred_mask_tight = (pred_tight > 0.5).astype(np.uint8)
    
    # Map back (naive stretch back)
    mapped_tight = cv2.resize(pred_mask_tight, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
    full_pred_tight = np.zeros_like(gt_mask_bin)
    full_pred_tight[y1:y2, x1:x2] = mapped_tight
    
    # Pipeline B: Context Padded + Aspect Preserved
    px1, py1, px2, py2 = context_pad_bbox(x1, y1, x2, y2, img.shape[1], img.shape[0], pad_ratio=0.5)
    crop_pad = img[py1:py2, px1:px2]
    
    crop_pad_resized, (x_off, y_off, side) = pad_to_square_then_resize(crop_pad, target=384)
    crop_pad_rgb = cv2.cvtColor(crop_pad_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    crop_pad_rgb = (crop_pad_rgb - mean) / std
    t_pad = torch.from_numpy(crop_pad_rgb.transpose(2, 0, 1)).unsqueeze(0).float().to(device)
    
    with torch.no_grad():
        logits_pad = model(t_pad)
        pred_pad = torch.sigmoid(logits_pad)[0, 0].cpu().numpy()
        pred_mask_pad = (pred_pad > 0.5).astype(np.uint8)
        
    mapped_pad = unpad_and_resize_mask(pred_mask_pad, x_off, y_off, side, crop_pad.shape[0], crop_pad.shape[1])
    full_pred_pad = np.zeros_like(gt_mask_bin)
    full_pred_pad[py1:py2, px1:px2] = (mapped_pad > 0.5).astype(np.uint8)
    
    # Calc Dice
    def calc_dice(pred, gt):
        tp = (pred * gt).sum()
        fp = (pred * (1 - gt)).sum()
        fn = ((1 - pred) * gt).sum()
        return (2.0 * tp + 1e-6) / (2.0 * tp + fp + fn + 1e-6)
        
    tight_dices.append(calc_dice(full_pred_tight, gt_mask_bin))
    padded_dices.append(calc_dice(full_pred_pad, gt_mask_bin))

print(f"\\n--- Hybrid Validation Results ---")
print(f"Baseline (Tight Crop + Squashed): {np.mean(tight_dices):.4f}")
print(f"Proposed (Context Padded + Aspect Preserved): {np.mean(padded_dices):.4f}")
print(f"Improvement: +{np.mean(padded_dices) - np.mean(tight_dices):.4f} Dice points!")
