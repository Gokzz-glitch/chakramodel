import os, cv2, torch, time
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from tqdm import tqdm
import timm
from ultralytics import YOLO

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
    top = (side - h) // 2
    bottom = side - h - top
    left = (side - w) // 2
    right = side - w - left
    canvas = cv2.copyMakeBorder(crop, top, bottom, left, right, cv2.BORDER_REFLECT_101)
    resized = cv2.resize(canvas, (target, target), interpolation=cv2.INTER_LINEAR)
    y_off, x_off = top, left
    return resized, (x_off, y_off, side)

def unpad_and_resize_mask(pred_mask, x_off, y_off, side, orig_h, orig_w):
    mask_side = cv2.resize(pred_mask.astype(np.float32), (side, side), interpolation=cv2.INTER_LINEAR)
    mask_crop = mask_side[y_off:y_off+orig_h, x_off:x_off+orig_w]
    return mask_crop

def calc_dice(pred, gt):
    tp = (pred * gt).sum()
    fp = (pred * (1 - gt)).sum()
    fn = ((1 - pred) * gt).sum()
    return (2.0 * tp + 1e-6) / (2.0 * tp + fp + fn + 1e-6)


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Loading models on {device}...")

yolo_model = YOLO('M:/chakramodel/weights/best.pt')
vit_model = ChakraTransformerSegmenter(pretrained=False).to(device)
weights = torch.load('M:/chakramodel/weights/chakra_transformer_best.pth', map_location=device, weights_only=True)
vit_model.load_state_dict(weights)
vit_model.eval()

img_files = sorted([f for f in Path('M:/chakramodel/datasets/colon_cancer_dataset/segmented-images/images').iterdir() if f.suffix.lower() in {'.jpg','.png'}])
mask_dict = {f.stem: f for f in Path('M:/chakramodel/datasets/colon_cancer_dataset/segmented-images/masks').iterdir()}

np.random.seed(42)
perm = np.random.permutation(len(img_files))
test_files = [img_files[i] for i in perm[850:1000]]  # 150 test images

mean_rgb = np.array([0.485, 0.456, 0.406])
std_rgb = np.array([0.229, 0.224, 0.225])

tight_dices = []
padded_dices = []

print(f"\\n--- PHASE 1: Real YOLO Accuracy on {len(test_files)} images ---")
for img_path in tqdm(test_files):
    img = cv2.imread(str(img_path))
    gt_mask = cv2.imread(str(mask_dict[img_path.stem]), cv2.IMREAD_GRAYSCALE)
    gt_mask_bin = (gt_mask > 127).astype(np.uint8)
    
    # Run Real YOLO
    results = yolo_model(img, verbose=False)
    boxes = results[0].boxes
    
    # If YOLO completely misses the polyp
    if len(boxes) == 0:
        tight_dices.append(0.0)
        padded_dices.append(0.0)
        continue
    
    # Take the highest confidence box
    box = boxes[0].xyxy[0].cpu().numpy()
    x1, y1, x2, y2 = map(int, box)
    
    if (x2 - x1) < 10 or (y2 - y1) < 10:
        tight_dices.append(0.0)
        padded_dices.append(0.0)
        continue

    # Pipeline A: Tight Crop
    crop_tight = img[max(0,y1):min(img.shape[0],y2), max(0,x1):min(img.shape[1],x2)]
    if crop_tight.size == 0: 
        tight_dices.append(0.0)
    else:
        crop_tight_resized = cv2.resize(crop_tight, (384, 384))
        crop_tight_rgb = cv2.cvtColor(crop_tight_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        crop_tight_rgb = (crop_tight_rgb - mean_rgb) / std_rgb
        t_tight = torch.from_numpy(crop_tight_rgb.transpose(2, 0, 1)).unsqueeze(0).float().to(device)
        
        with torch.no_grad():
            with torch.amp.autocast('cuda' if torch.cuda.is_available() else 'cpu'):
                logits_tight = vit_model(t_tight)
                pred_tight = torch.sigmoid(logits_tight)[0, 0].cpu().numpy()
            pred_mask_tight = (pred_tight > 0.5).astype(np.uint8)
        
        mapped_tight = cv2.resize(pred_mask_tight, (crop_tight.shape[1], crop_tight.shape[0]), interpolation=cv2.INTER_NEAREST)
        full_pred_tight = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
        full_pred_tight[max(0,y1):max(0,y1)+crop_tight.shape[0], max(0,x1):max(0,x1)+crop_tight.shape[1]] = mapped_tight
        tight_dices.append(calc_dice(full_pred_tight, gt_mask_bin.squeeze()))

    # Pipeline B: Padded Crop
    px1, py1, px2, py2 = context_pad_bbox(x1, y1, x2, y2, img.shape[1], img.shape[0], pad_ratio=0.5)
    crop_pad = img[py1:py2, px1:px2]
    if crop_pad.size == 0:
        padded_dices.append(0.0)
    else:
        crop_pad_resized, (x_off, y_off, side) = pad_to_square_then_resize(crop_pad, target=384)
        crop_pad_rgb = cv2.cvtColor(crop_pad_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        crop_pad_rgb = (crop_pad_rgb - mean_rgb) / std_rgb
        t_pad = torch.from_numpy(crop_pad_rgb.transpose(2, 0, 1)).unsqueeze(0).float().to(device)
        
        with torch.no_grad():
            with torch.amp.autocast('cuda' if torch.cuda.is_available() else 'cpu'):
                logits_pad = vit_model(t_pad)
                pred_pad = torch.sigmoid(logits_pad)[0, 0].cpu().numpy()
            pred_mask_pad = (pred_pad > 0.5).astype(np.uint8)
            
        mapped_pad = unpad_and_resize_mask(pred_mask_pad, x_off, y_off, side, crop_pad.shape[0], crop_pad.shape[1])
        full_pred_pad = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
        full_pred_pad[py1:py2, px1:px2] = (mapped_pad > 0.5).astype(np.uint8)
        padded_dices.append(calc_dice(full_pred_pad, gt_mask_bin.squeeze()))

tight_mean, tight_std = np.mean(tight_dices), np.std(tight_dices)
pad_mean, pad_std = np.mean(padded_dices), np.std(padded_dices)

print(f"\\nREAL YOLO RESULTS (N=150):")
print(f"Baseline (Tight): {tight_mean:.4f} ± {tight_std:.4f}")
print(f"Proposed (Padded): {pad_mean:.4f} ± {pad_std:.4f}")
print(f"Improvement: +{pad_mean - tight_mean:.4f} Dice")


print(f"\\n--- PHASE 2: End-to-End FPS Profiling ---")
test_img = cv2.imread(str(test_files[0]))
# Warmup
for _ in range(10):
    res = yolo_model(test_img, verbose=False)
    t = torch.randn(1, 3, 384, 384).to(device)
    vit_model(t)
torch.cuda.synchronize()

num_frames = 100
start_time = time.time()
for _ in range(num_frames):
    res = yolo_model(test_img, verbose=False)
    boxes = res[0].boxes
    if len(boxes) > 0:
        box = boxes[0].xyxy[0].cpu().numpy()
        x1, y1, x2, y2 = map(int, box)
        px1, py1, px2, py2 = context_pad_bbox(x1, y1, x2, y2, test_img.shape[1], test_img.shape[0], pad_ratio=0.5)
        crop_pad = test_img[py1:py2, px1:px2]
        crop_pad_resized, (x_off, y_off, side) = pad_to_square_then_resize(crop_pad, target=384)
        
        crop_pad_rgb = cv2.cvtColor(crop_pad_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        crop_pad_rgb = (crop_pad_rgb - mean_rgb) / std_rgb
        t_pad = torch.from_numpy(crop_pad_rgb.transpose(2, 0, 1)).unsqueeze(0).float().to(device)
        
        with torch.no_grad():
            with torch.amp.autocast('cuda' if torch.cuda.is_available() else 'cpu'):
                logits_pad = vit_model(t_pad)
                pred_probs = torch.sigmoid(logits_pad)[0, 0]
            pred_mask_pad = (pred_probs > 0.5).cpu().numpy().astype(np.uint8)
        
        mapped_pad = unpad_and_resize_mask(pred_mask_pad, x_off, y_off, side, crop_pad.shape[0], crop_pad.shape[1])
        full_pred_pad = np.zeros_like(test_img[:, :, 0])
        full_pred_pad[py1:py2, px1:px2] = (mapped_pad > 0.5).astype(np.uint8)

torch.cuda.synchronize()
end_time = time.time()
total_time = end_time - start_time
fps = num_frames / total_time
print(f"Total time for {num_frames} frames: {total_time:.2f}s")
print(f"End-to-End Pipeline FPS: {fps:.2f} FPS")
