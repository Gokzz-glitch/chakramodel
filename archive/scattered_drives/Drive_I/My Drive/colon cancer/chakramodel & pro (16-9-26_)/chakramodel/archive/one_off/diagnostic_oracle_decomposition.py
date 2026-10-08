import os
import cv2
import torch
import numpy as np
import argparse
import sys
from pathlib import Path
from tqdm import tqdm
from ultralytics import YOLO
import torch.nn as nn
import torch.nn.functional as F
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

# Anti-fabrication harness
sys.path.append("M:\\chakramodel")
try:
    from anti_fabrication.anti_fabrication_toolkit.core.harness_core import plant_multi_canary
except ImportError as e:
    print(f"Warning: Could not import anti_fabrication harness or ViT class: {e}")
    sys.exit(1)

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

def calculate_iou(boxA, boxB):
    # box format: x1, y1, x2, y2
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    unionArea = boxAArea + boxBArea - interArea
    if unionArea == 0: return 0.0
    return interArea / unionArea

def calculate_dice(pred, target):
    smooth = 1e-5
    pred_f = pred.flatten()
    target_f = target.flatten()
    intersection = np.sum(pred_f * target_f)
    return (2. * intersection + smooth) / (np.sum(pred_f) + np.sum(target_f) + smooth)

def main():
    parser = argparse.ArgumentParser(description="Cross-Dataset Diagnostic Oracle Decomposition")
    parser.add_argument("--img_dir", type=str, required=True, help="Path to images")
    parser.add_argument("--mask_dir", type=str, required=True, help="Path to ground truth masks")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    DEVICE = args.device
    print(f"Running Diagnostic Oracle Decomposition on {DEVICE}...")
    
    # Anti-fabrication check
    try:
        secret = plant_multi_canary(args.img_dir)
        print("Anti-fabrication harness active.")
    except Exception as e:
        print(f"Failed to plant canary: {e}")

    # 1. Load Models
    print("Loading YOLO stage 1...")
    yolo_model = YOLO(r"M:\chakramodel\weights\best.pt")
    
    print("Loading ChakraTransformer stage 2...")
    segmenter = ChakraTransformerSegmenter('vit_large_patch16_384', pretrained=False, num_classes=1)
    state_dict = torch.load(r"M:\chakramodel\weights\chakra_transformer_best.pth", map_location='cpu', weights_only=True)
    if "model" in state_dict: state_dict = state_dict["model"]
    # Remove prefixes from DataParallel / torch.compile models
    new_state_dict = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in state_dict.items()}
    segmenter.load_state_dict(new_state_dict, strict=False)
    segmenter.to(DEVICE)
    segmenter.eval()

    # Metrics Tracking
    total_images = 0
    yolo_hits = 0  # IoU >= 0.5
    yolo_misses_complete = 0 # zero detections
    oracle_dices = []
    
    image_files = [f for f in os.listdir(args.img_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif'))]
    if not image_files:
        print("No images found.")
        return

    print(f"Found {len(image_files)} images. Running decomposition...")
    
    with torch.no_grad():
        for img_name in tqdm(image_files):
            img_path = os.path.join(args.img_dir, img_name)
            mask_path = os.path.join(args.mask_dir, img_name)
            
            # fallback for mismatch extensions
            if not os.path.exists(mask_path):
                base = os.path.splitext(img_name)[0]
                for ext in ['.png', '.jpg', '.tif']:
                    if os.path.exists(os.path.join(args.mask_dir, base + ext)):
                        mask_path = os.path.join(args.mask_dir, base + ext)
                        break
            if not os.path.exists(mask_path):
                continue
                
            img_bgr = cv2.imread(img_path)
            gt_mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if img_bgr is None or gt_mask is None: continue
            
            orig_h, orig_w = gt_mask.shape[:2]
            total_images += 1
            
            # Find Ground Truth Box
            gt_bin = (gt_mask > 127).astype(np.uint8)
            contours, _ = cv2.findContours(gt_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue # No polyp in GT
                
            # Get largest contour for GT box
            c = max(contours, key=cv2.contourArea)
            gx, gy, gw, gh = cv2.boundingRect(c)
            gt_box = [gx, gy, gx+gw, gy+gh]
            
            # TEST 1: YOLO RECALL
            img_resized = cv2.resize(img_bgr, (384, 384))
            yolo_results = yolo_model(img_resized, verbose=False, device=DEVICE)[0]
            
            if len(yolo_results.boxes) == 0:
                yolo_misses_complete += 1
            else:
                best_iou = 0.0
                for box_data in yolo_results.boxes:
                    box = box_data.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = map(int, box)
                    
                    # Scale YOLO box back to original resolution
                    scale_x = orig_w / 384.0
                    scale_y = orig_h / 384.0
                    box_orig = [x1*scale_x, y1*scale_y, x2*scale_x, y2*scale_y]
                    
                    iou = calculate_iou(gt_box, box_orig)
                    best_iou = max(best_iou, iou)
                
                if best_iou >= 0.5:
                    yolo_hits += 1
                elif best_iou == 0.0:
                    yolo_misses_complete += 1
                    
            # TEST 2: CHAKRANET ORACLE
            # Pad the GT box identically to production (25%)
            px, py = int(0.25 * gw), int(0.25 * gh)
            px1, py1 = max(0, gx - px), max(0, gy - py)
            px2, py2 = min(orig_w, gx + gw + px), min(orig_h, gy + gh + py)
            
            roi_crop = img_bgr[py1:py2, px1:px2]
            if roi_crop.size == 0: continue
                
            roi_crop_resized, (dw, dh, r) = letterbox(roi_crop, new_shape=(384, 384))
            roi_crop_rgb = cv2.cvtColor(roi_crop_resized, cv2.COLOR_BGR2RGB)
            
            mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(DEVICE)
            std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(DEVICE)
            t_roi = torch.from_numpy(roi_crop_rgb).permute(2,0,1).unsqueeze(0).float().to(DEVICE) / 255.0
            t_roi = (t_roi - mean) / std
            
            out = segmenter(t_roi)
            if isinstance(out, tuple): out = out[0]
            prob = torch.sigmoid(out).float().squeeze().cpu().numpy()
            seg_roi_mask = (prob > 0.5).astype(np.uint8)
            
            # Reverse letterboxing
            top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
            left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
            unpad_h = 384 - top - bottom
            unpad_w = 384 - left - right
            
            seg_roi_mask_unpad = seg_roi_mask[top:top+unpad_h, left:left+unpad_w]
            seg_roi_mask_resized = cv2.resize(seg_roi_mask_unpad, (px2-px1, py2-py1), interpolation=cv2.INTER_NEAREST)
            
            # Map back to full image for Dice
            full_pred = np.zeros((orig_h, orig_w), dtype=np.uint8)
            full_pred[py1:py2, px1:px2] = seg_roi_mask_resized
            
            dice = calculate_dice(full_pred, gt_bin)
            oracle_dices.append(dice)

    # Summary
    if total_images == 0:
        print("No valid image/mask pairs processed.")
        return

    recall = yolo_hits / total_images
    complete_miss_rate = yolo_misses_complete / total_images
    avg_oracle_dice = np.mean(oracle_dices) if oracle_dices else 0.0

    print("\n--- Diagnostic Decomposition Results ---")
    print(f"Dataset size tested: {total_images} images")
    print("\n1. YOLOv8 Stage 1 (Detection)")
    print(f"   Recall (IoU >= 0.5) : {recall*100:.2f}% ({yolo_hits}/{total_images})")
    print(f"   Complete Misses     : {complete_miss_rate*100:.2f}% ({yolo_misses_complete}/{total_images})")
    
    print("\n2. ChakraNet ViT Oracle Stage 2 (Segmentation)")
    print(f"   Oracle Dice (DSC)   : {avg_oracle_dice:.4f}")
    
    if recall < 0.5:
        print("\n=> CONCLUSION: YOLO Detection is severely failing (Path B priority). Domain shift is breaking bbox localization.")
    if avg_oracle_dice < 0.6:
        print("\n=> CONCLUSION: ChakraNet Oracle Dice is severely failing (Path A priority). The ViT segmentation cannot handle this domain's textures/colors even given a perfect crop.")

if __name__ == "__main__":
    main()
