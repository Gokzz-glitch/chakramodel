import os
import cv2
import torch
import numpy as np
from tqdm import tqdm
import torch.nn as nn
import torch.nn.functional as F
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

# ==========================================================
# CHAKRAMODEL: GENERALIZED MULTI-DATASET AUTO-DISCOVERY EVAL
# ==========================================================
# Fixes vs. the previous auto-discover attempt:
#  1. Mask detection checks the FULL PATH (folder name included),
#     not just the filename -- catches "Ground Truth/1.png",
#     "masks/173.png", etc. where the file itself is plain numeric.
#  2. Each discovered dataset root is walked RECURSIVELY and
#     images/masks are paired by matching basename across the
#     whole subtree -- handles nested layouts like
#     PNG/Original/ + PNG/Ground Truth/.
#  3. LEAKAGE GUARD: if a "train manifest" (list of filenames used
#     during YOLO training) is provided, any matched pair whose
#     image was in that training set is excluded from the eval,
#     so Dice numbers reflect genuine held-out performance.
# ==========================================================

IMG_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
MASK_TOKENS = ("mask", "ground", "gt", "label", "seg", "segmentation", "manual")
CONFIDENCE_THRESHOLDS = [0.25, 0.40, 0.50, 0.65, 0.80]

# Optional: point this at the training images folder used to build your
# YOLO combo dataset, to auto-exclude any overlapping filenames from eval.
# Leave as None to evaluate without a leakage guard.
TRAIN_IMAGES_DIR = "/kaggle/working/chakramodel_yolo_combo_dataset/images/train"


def load_train_manifest(train_images_dir):
    """Return a set of basenames (no source prefix, no ext) used in training,
    so we can exclude them from eval. Handles the "<source>_<origbase>.png"
    naming used by build_yolo_combo_dataset.py."""
    if not train_images_dir or not os.path.isdir(train_images_dir):
        return set()
    used = set()
    for f in os.listdir(train_images_dir):
        stem = os.path.splitext(f)[0]
        # strip the "<source>_" prefix build_yolo_combo_dataset.py adds
        if "_" in stem:
            used.add(stem.split("_", 1)[1])
        used.add(stem)
    return used


def is_image(fname):
    return fname.lower().endswith(IMG_EXTS)


def looks_like_mask_path(path):
    low = path.lower()
    return any(tok in low for tok in MASK_TOKENS)


def discover_dataset_roots(kaggle_input="/kaggle/input"):
    """
    Auto-discover dataset roots: group files by their top-level dataset
    (handles both /input/<slug>/ and /input/datasets/<user>/<slug>/),
    then keep only groups that contain BOTH image-like and mask-like
    files somewhere in their subtree.
    """
    groups = {}
    for dirpath, _, filenames in os.walk(kaggle_input):
        for f in filenames:
            if not is_image(f):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, kaggle_input)
            parts = rel.split(os.sep)
            if parts[0] == "datasets" and len(parts) > 2:
                key = os.sep.join(parts[:3])
            else:
                key = parts[0]
            groups.setdefault(key, []).append(full)

    valid = {}
    for key, files in groups.items():
        images = [f for f in files if not looks_like_mask_path(f)]
        masks = [f for f in files if looks_like_mask_path(f)]
        if images and masks:
            valid[key] = {"images": images, "masks": masks}
        else:
            reason = "no mask-like files found" if not masks else "no plain image files found"
            print(f"[SKIP] {key}: {reason} ({len(images)} image-like, {len(masks)} mask-like)")
    return valid


def pair_images_masks(images, masks):
    """Match by exact basename (no extension) between the image list and mask list."""
    mask_lookup = {}
    for m in masks:
        base = os.path.splitext(os.path.basename(m))[0]
        mask_lookup.setdefault(base, m)  # first match wins; ambiguity -> skip via absence
    pairs = []
    for img in images:
        base = os.path.splitext(os.path.basename(img))[0]
        if base in mask_lookup:
            pairs.append((img, mask_lookup[base]))
    return pairs


def calculate_dice(pred, target):
    smooth = 1e-5
    pred_f = pred.flatten()
    target_f = target.flatten()
    intersection = np.sum(pred_f * target_f)
    return (2. * intersection + smooth) / (np.sum(pred_f) + np.sum(target_f) + smooth)


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


# ---------------- Weight discovery (recursive, name-based -- no hardcoded slugs) ----------------
print("Locating weights...")
yolo_weight = None
vit_weight = None
for root, _, files in os.walk("/kaggle/input"):
    for f in files:
        if f == "best.pt":
            yolo_weight = os.path.join(root, f)
        if f == "chakra_transformer_best.pth":
            vit_weight = os.path.join(root, f)
# also allow a freshly-trained model to take priority if present
fresh_best = "/kaggle/working/polyp_yolov8x_etis_fix/weights/best.pt"
if os.path.exists(fresh_best):
    yolo_weight = fresh_best
    print(f"  Using freshly-trained YOLO weights: {fresh_best}")

if not yolo_weight or not vit_weight:
    raise FileNotFoundError("Weights not found anywhere under /kaggle/input or /kaggle/working.")
print(f"YOLO weight: {yolo_weight}")
print(f"ViT weight:  {vit_weight}")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

yolo_model = YOLO(yolo_weight)

segmenter = ChakraTransformerSegmenter('vit_large_patch16_384', pretrained=False, num_classes=1)
state_dict = torch.load(vit_weight, map_location='cpu', weights_only=True)
if "model" in state_dict: state_dict = state_dict["model"]
new_state_dict = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in state_dict.items()}
segmenter.load_state_dict(new_state_dict, strict=False)
segmenter.to(DEVICE)
segmenter.eval()

norm_mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(DEVICE)
norm_std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(DEVICE)

# ---------------- Auto-discovery ----------------
print("\nScanning /kaggle/input for valid image+mask datasets...")
valid_datasets = discover_dataset_roots("/kaggle/input")
print(f"\nFound {len(valid_datasets)} valid dataset(s): {list(valid_datasets.keys())}")

train_manifest = load_train_manifest(TRAIN_IMAGES_DIR)
if train_manifest:
    print(f"Loaded training manifest ({len(train_manifest)} filenames) -- leakage guard active.")
else:
    print("No training manifest found -- leakage guard inactive (results may include seen images).")

# ---------------- Evaluation ----------------
all_results = {}

for ds_name, content in valid_datasets.items():
    print(f"\n{'=' * 60}\nEVALUATING: {ds_name}\n{'=' * 60}")
    pairs = pair_images_masks(content["images"], content["masks"])
    print(f"  Matched {len(pairs)} image-mask pairs.")

    if train_manifest:
        before = len(pairs)
        pairs = [
            (img, mask) for img, mask in pairs
            if os.path.splitext(os.path.basename(img))[0] not in train_manifest
        ]
        excluded = before - len(pairs)
        if excluded:
            print(f"  Excluded {excluded} pairs seen during training -- {len(pairs)} held-out pairs remain.")

    if not pairs:
        print("  Skipping -- no held-out pairs available.")
        continue

    results_by_threshold = {t: {"dices": [], "zero_skips": 0} for t in CONFIDENCE_THRESHOLDS}
    MIN_THRESH = min(CONFIDENCE_THRESHOLDS)

    with torch.no_grad():
        for img_path, mask_path in tqdm(pairs, desc=ds_name):
            img_bgr = cv2.imread(img_path)
            gt_mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if img_bgr is None or gt_mask is None:
                continue

            orig_h, orig_w = gt_mask.shape[:2]
            if np.max(gt_mask) == 1:
                gt_mask = gt_mask * 255
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
                gx, gy, gx2, gy2 = int(x1 * scale_x), int(y1 * scale_y), int(x2 * scale_x), int(y2 * scale_y)
                gw, gh = gx2 - gx, gy2 - gy
                px, py = int(0.25 * gw), int(0.25 * gh)
                px1, py1 = max(0, gx - px), max(0, gy - py)
                px2, py2 = min(orig_w, gx + gw + px), min(orig_h, gy + gh + py)
                roi_crop = img_bgr[py1:py2, px1:px2]
                if roi_crop.size == 0:
                    continue
                roi_crop_resized, (dw, dh, r) = letterbox(roi_crop, new_shape=(384, 384))
                roi_crop_rgb = cv2.cvtColor(roi_crop_resized, cv2.COLOR_BGR2RGB)
                t_roi = torch.from_numpy(roi_crop_rgb).permute(2, 0, 1).unsqueeze(0).float().to(DEVICE) / 255.0
                t_roi = (t_roi - norm_mean) / norm_std
                out = segmenter(t_roi)
                if isinstance(out, tuple):
                    out = out[0]
                prob = torch.sigmoid(out).float().squeeze().cpu().numpy()
                seg_roi_mask = (prob > 0.5).astype(np.uint8)
                top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
                left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
                unpad_h = 384 - top - bottom
                unpad_w = 384 - left - right
                seg_roi_mask_unpad = seg_roi_mask[top:top + unpad_h, left:left + unpad_w]
                seg_roi_mask_resized = cv2.resize(seg_roi_mask_unpad, (px2 - px1, py2 - py1), interpolation=cv2.INTER_NEAREST)
                cached_masks.append({"conf": conf, "mask": seg_roi_mask_resized, "coords": (py1, py2, px1, px2)})

            for thresh in CONFIDENCE_THRESHOLDS:
                full_pred = np.zeros((orig_h, orig_w), dtype=np.uint8)
                passed = 0
                for c_mask in cached_masks:
                    if c_mask["conf"] >= thresh:
                        py1, py2, px1, px2 = c_mask["coords"]
                        full_pred[py1:py2, px1:px2] = np.maximum(full_pred[py1:py2, px1:px2], c_mask["mask"])
                        passed += 1
                if passed == 0:
                    results_by_threshold[thresh]["zero_skips"] += 1
                dice = calculate_dice(full_pred, gt_bin)
                results_by_threshold[thresh]["dices"].append(dice)

    all_results[ds_name] = results_by_threshold
    print(f"\n  --- {ds_name} results ---")
    for thresh in CONFIDENCE_THRESHOLDS:
        dices = results_by_threshold[thresh]["dices"]
        avg_dice = np.mean(dices) if dices else 0.0
        print(f"  Threshold: {thresh:.2f} | Dice: {avg_dice:.4f} | Zero Detections: {results_by_threshold[thresh]['zero_skips']}")

# ---------------- Final cross-dataset summary ----------------
print("\n" + "=" * 70)
print("FINAL SUMMARY -- ALL DATASETS x ALL THRESHOLDS")
print("=" * 70)
header = f"{'Dataset':30s}" + "".join(f"{t:>10.2f}" for t in CONFIDENCE_THRESHOLDS)
print(header)
for ds_name, results_by_threshold in all_results.items():
    row = f"{ds_name:30s}"
    for t in CONFIDENCE_THRESHOLDS:
        dices = results_by_threshold[t]["dices"]
        avg = np.mean(dices) if dices else float("nan")
        row += f"{avg:>10.4f}"
    print(row)
