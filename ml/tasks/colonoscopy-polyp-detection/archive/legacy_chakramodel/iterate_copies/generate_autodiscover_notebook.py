import nbformat as nbf

nb = nbf.v4.new_notebook()

# Cell 1: Intro Markdown
cell_intro = nbf.v4.new_markdown_cell("""
# ChakraModel: Ultimate Auto-Discovery Evaluation Pipeline
This notebook automatically scans all attached Kaggle datasets, runs diagnostics to find which ones contain valid Image+Mask pairs, loads the YOLO & ViT models, and runs the 5-point Confidence Threshold Sweep across all valid datasets.
""")

# Cell 2: Install Dependencies
cell_install = nbf.v4.new_code_cell("""
!pip install -q ultralytics timm
""")

# Cell 3: Imports
cell_imports = nbf.v4.new_code_cell("""
import os
import cv2
import torch
import numpy as np
from tqdm import tqdm
from ultralytics import YOLO
import timm
import torch.nn as nn
import torch.nn.functional as F
import warnings
warnings.filterwarnings('ignore')
""")

# Cell 4: Auto-Discovery & Diagnostics
cell_discovery = nbf.v4.new_code_cell("""
# ==========================================
# 1. AUTO-DISCOVER DATASETS
# ==========================================
print("Scanning Kaggle Inputs for valid Evaluation Datasets...")
kaggle_input = "/kaggle/input"
valid_datasets = {}

for root, dirs, files in os.walk(kaggle_input):
    # Only look at bottom-level directories that have images
    img_count = sum(1 for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.bmp')))
    mask_count = sum(1 for f in files if 'mask' in f.lower() or 'ground' in f.lower() or 'gt' in f.lower() or 'label' in f.lower())
    
    if img_count > 0:
        dataset_name = os.path.basename(root)
        if mask_count > 0 and (img_count - mask_count) > 0:
            print(f"[OK] Found valid dataset: {dataset_name} (Images: {img_count - mask_count}, Masks: {mask_count})")
            valid_datasets[dataset_name] = root
        elif mask_count == 0:
            print(f"[SKIP] {dataset_name} has {img_count} images but ZERO masks.")
        else:
            # Maybe the images and masks are in the same folder and not explicitly named "mask"
            pass

print("\\nWill evaluate the following datasets:")
for name, path in valid_datasets.items():
    print(f" -> {name}: {path}")
""")

# Cell 5: Model Definitions & Loading
cell_models = nbf.v4.new_code_cell("""
# ==========================================
# 2. LOAD MODELS
# ==========================================
print("Locating Weights...")
weight_dir_options = [
    "/kaggle/input/chakramodel-weightsupdated4",
    "/kaggle/input/chakramodel-weights",
    "/kaggle/input/datasets/gokulrocky/chakramodel-weights",
    "/kaggle/input/datasets/gokulraj324/chakramodel-weights",
    "/kaggle/working",
    "."
]

yolo_weight = None
vit_weight = None

for root, _, files in os.walk("/kaggle/input"):
    for f in files:
        if f == "best.pt":
            yolo_weight = os.path.join(root, f)
        if f == "chakra_transformer_best.pth":
            vit_weight = os.path.join(root, f)

if not yolo_weight or not vit_weight:
    raise FileNotFoundError("ERROR: Weights not found in Kaggle! Please upload best.pt and chakra_transformer_best.pth")

print(f"Loaded YOLO weight: {yolo_weight}")
print(f"Loaded ViT weight: {vit_weight}")

# ChakraTransformer Definition
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

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print("Loading YOLO stage 1...")
yolo_model = YOLO(yolo_weight)

print("Loading ChakraTransformer stage 2...")
segmenter = ChakraTransformerSegmenter('vit_large_patch16_384', pretrained=False, num_classes=1)
state_dict = torch.load(vit_weight, map_location='cpu', weights_only=True)
if "model" in state_dict: state_dict = state_dict["model"]
new_state_dict = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in state_dict.items()}
segmenter.load_state_dict(new_state_dict, strict=False)
segmenter.to(DEVICE)
segmenter.eval()

norm_mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(DEVICE)
norm_std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(DEVICE)
""")

# Cell 6: Evaluation Loop
cell_eval = nbf.v4.new_code_cell("""
# ==========================================
# 3. RUN EVALUATION SWEEP
# ==========================================
CONFIDENCE_THRESHOLDS = [0.25, 0.40, 0.50, 0.65, 0.80]
MIN_THRESH = min(CONFIDENCE_THRESHOLDS)

for ds_name, dataset_path in valid_datasets.items():
    print(f"\\n{'='*60}")
    print(f"EVALUATING DATASET: {ds_name}")
    print(f"Path: {dataset_path}")
    print(f"{'='*60}")
    
    all_files = [os.path.join(dataset_path, f) for f in os.listdir(dataset_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.bmp'))]
    
    mask_files = [f for f in all_files if 'mask' in f.lower() or 'ground' in f.lower() or 'gt' in f.lower() or 'label' in f.lower()]
    img_files = [f for f in all_files if f not in mask_files]
    
    matched_pairs = []
    for img_path in img_files:
        base = os.path.splitext(os.path.basename(img_path))[0]
        matched_mask = None
        
        for m in mask_files:
            if os.path.splitext(os.path.basename(m))[0] == base:
                matched_mask = m
                break
        if not matched_mask:
            for suffix in ['_mask', '_gt']:
                for m in mask_files:
                    if os.path.splitext(os.path.basename(m))[0] == f"{base}{suffix}":
                        matched_mask = m
                        break
                if matched_mask: break
                
        if matched_mask:
            matched_pairs.append((img_path, matched_mask))

    print(f"Successfully matched {len(matched_pairs)} image-mask pairs.")
    if len(matched_pairs) == 0:
        print("Skipping dataset because no pairs could be matched.")
        continue
        
    results_by_threshold = {t: {"dices": [], "zero_skips": 0} for t in CONFIDENCE_THRESHOLDS}
    
    with torch.no_grad():
        for img_path, mask_path in tqdm(matched_pairs, desc=f"Evaluating {ds_name}"):
            img_bgr = cv2.imread(img_path)
            gt_mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if img_bgr is None or gt_mask is None: continue
            
            orig_h, orig_w = gt_mask.shape[:2]
            if np.max(gt_mask) == 1: gt_mask = gt_mask * 255
            gt_bin = (gt_mask > 127).astype(np.uint8)
            
            img_resized = cv2.resize(img_bgr, (384, 384))
            yolo_results = yolo_model(img_resized, conf=MIN_THRESH, imgsz=384, verbose=False, device=DEVICE)[0]
            
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

    print(f"\\n--- {ds_name} Results ---")
    for thresh in CONFIDENCE_THRESHOLDS:
        avg_dice = np.mean(results_by_threshold[thresh]["dices"])
        zero_skips = results_by_threshold[thresh]["zero_skips"]
        print(f"Threshold: {thresh:.2f} | Dice: {avg_dice:.4f} | Zero Detections: {zero_skips}")
""")

nb['cells'] = [cell_intro, cell_install, cell_imports, cell_discovery, cell_models, cell_eval]
nbf.write(nb, 'm:/chakramodel/AutoDiscover_Evaluation.ipynb')
