import os
import cv2
import torch
import numpy as np
from tqdm import tqdm
import subprocess
import sys

# 1. Install dependencies if missing BEFORE importing them
try:
    import ultralytics
    import timm
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "ultralytics", "timm"], check=True)
    import ultralytics
    import timm

from ultralytics import YOLO
import torch.nn as nn
import torch.nn.functional as F

# ==========================================
# PATH A: HARDENED INFERENCE CONFIGURATION
# ==========================================

# We will sweep across multiple thresholds to find the optimum!
CONFIDENCE_THRESHOLDS = [0.25, 0.40, 0.50, 0.65, 0.80]

# ==========================================
# DATASET CONFIGURATION
# ==========================================
# To evaluate a new dataset, just add a new line below:
# 'YourDatasetName': '/kaggle/input/path-to-your-dataset-folder'
# If a path doesn't exist or is empty, the script will safely skip it.

EVAL_DATASETS = {
    'CVC-ClinicDB': '/kaggle/input/chakramodel-evaluation-datasets/cvc-clinicdb',
    'CVC-300': '/kaggle/input/chakramodel-evaluation-datasets/cvc-300',
    'ETIS-Larib': '/kaggle/input/chakramodel-evaluation-datasets/etis-laribpolypdb'
    
    # Example of adding a new dataset (remove the # to enable):
    # 'Kvasir': '/kaggle/input/hyperkvasir-dataset-first-half-ld-dataset',
}
# ==========================================
# Check for weights in typical kaggle paths
weight_dir_options = [
    "/kaggle/input/chakramodel-weights",
    "/kaggle/input/datasets/gokulrocky/chakramodel-weights",
    "/kaggle/input/datasets/gokulraj324/chakramodel-weights",
    "/kaggle/working",
    "."
]

yolo_weight = None
vit_weight = None

for d in weight_dir_options:
    if os.path.exists(os.path.join(d, "best.pt")):
        yolo_weight = os.path.join(d, "best.pt")
    if os.path.exists(os.path.join(d, "chakra_transformer_best.pth")):
        vit_weight = os.path.join(d, "chakra_transformer_best.pth")

if not yolo_weight or not vit_weight:
    print("ERROR: Weights not found in Kaggle! Please upload best.pt and chakra_transformer_best.pth")
    sys.exit(1)

print(f"Found YOLO weight at {yolo_weight}")
print(f"Found ViT weight at {vit_weight}")

# 3. Model definitions
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
            nn.Conv2d(64, num_classes, kernel_size=3, padding=1),
        )
        self.dropout1 = nn.Dropout2d(p=0.5)
        self.dropout2 = nn.Dropout2d(p=0.5)

    def forward(self, x):
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

def letterbox(img, new_shape=(384, 384), color=(0, 0, 0)):
    shape = img.shape[:2]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw, dh = dw / 2, dh / 2
    if shape[::-1] != new_unpad:
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return img, (dw, dh, r)

def calculate_dice(pred, target):
    smooth = 1e-5
    pred_f = pred.flatten()
    target_f = target.flatten()
    intersection = np.sum(pred_f * target_f)
    return (2. * intersection + smooth) / (np.sum(pred_f) + np.sum(target_f) + smooth)

print("Loading YOLO stage 1...")
yolo_model = YOLO(yolo_weight)

print("Loading ChakraTransformer stage 2...")
segmenter = ChakraTransformerSegmenter('vit_large_patch16_384', pretrained=False, num_classes=1)
state_dict = torch.load(vit_weight, map_location='cpu', weights_only=True)
if "model" in state_dict: state_dict = state_dict["model"]
new_state_dict = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in state_dict.items()}

load_result = segmenter.load_state_dict(new_state_dict, strict=False)
print("ViT Weights Load Result:")
if load_result.missing_keys:
    print(f"  Missing Keys: {len(load_result.missing_keys)}")
if load_result.unexpected_keys:
    print(f"  Unexpected Keys: {len(load_result.unexpected_keys)}")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
segmenter.to(DEVICE)
segmenter.eval()

# 5. Fix: Precompute normalization tensors
norm_mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(DEVICE)
norm_std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(DEVICE)


# Loop over all defined datasets
for ds_name, dataset_path in EVAL_DATASETS.items():
    print(f"\n{'='*50}")
    print(f"EVALUATING DATASET: {ds_name}")
    print(f"{'-'*50}")
    
    if not os.path.exists(dataset_path):
        print(f"SKIPPING {ds_name} - Path not found: {dataset_path}")
        continue
    all_files = []
    for root, _, files in os.walk(dataset_path):
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.bmp')):
                all_files.append(os.path.join(root, f))
    
    mask_files = []
    img_files = []
    for f in all_files:
        low = f.lower()
        if 'mask' in low or 'ground' in low or 'gt' in low or 'label' in low:
            mask_files.append(f)
        else:
            img_files.append(f)
    
    # 4. Fix: Strict matching to avoid numeric substring collisions
    matched_pairs = []
    for img_path in img_files:
        base = os.path.splitext(os.path.basename(img_path))[0]
        matched_mask = None
        
        # Exact base match
        for m in mask_files:
            if os.path.splitext(os.path.basename(m))[0] == base:
                matched_mask = m
                break
                
        # Try explicit common suffixes if exact match fails
        if not matched_mask:
            for suffix in ['_mask', '_gt']:
                for m in mask_files:
                    if os.path.splitext(os.path.basename(m))[0] == f"{base}{suffix}":
                        matched_mask = m
                        break
                if matched_mask: break
                
        if matched_mask:
            matched_pairs.append((img_path, matched_mask))
        else:
            print(f"WARNING: No strict mask match found for {img_path}")
    
    print(f"Successfully matched {len(matched_pairs)} image-mask pairs.")
    
    # 3. Fix: Cache Inference for Threshold Sweeping
    results_by_threshold = {t: {"dices": [], "zero_skips": 0} for t in CONFIDENCE_THRESHOLDS}
    MIN_THRESH = min(CONFIDENCE_THRESHOLDS)
    
    print(f"\n--- Running Cached Pipeline inference (YOLO base conf={MIN_THRESH}) ---")
    
    with torch.no_grad():
        for img_path, mask_path in tqdm(matched_pairs):
            img_bgr = cv2.imread(img_path)
            gt_mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if img_bgr is None or gt_mask is None: continue
            
            orig_h, orig_w = gt_mask.shape[:2]
            
            if np.max(gt_mask) == 1:
                gt_mask = gt_mask * 255
            gt_bin = (gt_mask > 127).astype(np.uint8)
            
            # 2. Fix: Include negative frames in eval
            # (calculate_dice inherently handles 0/0 smoothly)
            
            # YOLO Inference at 384x384
            img_resized = cv2.resize(img_bgr, (384, 384))
            yolo_results = yolo_model(img_resized, conf=MIN_THRESH, imgsz=384, verbose=False, device=DEVICE)[0]
            
            # Pre-segment all boxes passing the minimum threshold
            cached_masks = []
            for box_data in yolo_results.boxes:
                conf = float(box_data.conf[0].cpu())
                box = box_data.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, box)
                
                scale_x = orig_w / 384.0
                scale_y = orig_h / 384.0
                
                gx, gy, gx2, gy2 = int(x1*scale_x), int(y1*scale_y), int(x2*scale_x), int(y2*scale_y)
                gw, gh = gx2 - gx, gy2 - gy
                
                px, py = int(0.25 * gw), int(0.25 * gh)
                px1, py1 = max(0, gx - px), max(0, gy - py)
                px2, py2 = min(orig_w, gx + gw + px), min(orig_h, gy + gh + py)
                
                roi_crop = img_bgr[py1:py2, px1:px2]
                if roi_crop.size == 0: continue
                    
                roi_crop_resized, (dw, dh, r) = letterbox(roi_crop, new_shape=(384, 384))
                roi_crop_rgb = cv2.cvtColor(roi_crop_resized, cv2.COLOR_BGR2RGB)
                
                t_roi = torch.from_numpy(roi_crop_rgb).permute(2,0,1).unsqueeze(0).float().to(DEVICE) / 255.0
                t_roi = (t_roi - norm_mean) / norm_std
                
                out = segmenter(t_roi)
                if isinstance(out, tuple): out = out[0]
                prob = torch.sigmoid(out).float().squeeze().cpu().numpy()
                seg_roi_mask = (prob > 0.5).astype(np.uint8)
                
                top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
                left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
                unpad_h = 384 - top - bottom
                unpad_w = 384 - left - right
                
                seg_roi_mask_unpad = seg_roi_mask[top:top+unpad_h, left:left+unpad_w]
                seg_roi_mask_resized = cv2.resize(seg_roi_mask_unpad, (px2-px1, py2-py1), interpolation=cv2.INTER_NEAREST)
                
                cached_masks.append({
                    "conf": conf,
                    "mask": seg_roi_mask_resized,
                    "coords": (py1, py2, px1, px2)
                })
    
            # Assemble full masks for each threshold sweep
            for thresh in CONFIDENCE_THRESHOLDS:
                full_pred = np.zeros((orig_h, orig_w), dtype=np.uint8)
                passed = 0
                
                for c_mask in cached_masks:
                    if c_mask["conf"] >= thresh:
                        py1, py2, px1, px2 = c_mask["coords"]
                        full_pred[py1:py2, px1:px2] = np.maximum(
                            full_pred[py1:py2, px1:px2], 
                            c_mask["mask"]
                        )
                        passed += 1
                
                if passed == 0:
                    results_by_threshold[thresh]["zero_skips"] += 1
                    
                dice = calculate_dice(full_pred, gt_bin)
                results_by_threshold[thresh]["dices"].append(dice)
    
    print("\n==============================================")
    print("--- Confidence Threshold Sweep Results ---")
    print("==============================================")
    for thresh in CONFIDENCE_THRESHOLDS:
        avg_dice = np.mean(results_by_threshold[thresh]["dices"])
        zero_skips = results_by_threshold[thresh]["zero_skips"]
        print(f"Threshold: {thresh:.2f} | Dice: {avg_dice:.4f} | Zero Detections: {zero_skips}")
    print("==============================================")
