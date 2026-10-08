"""
Diagnostic Evaluation Script (FIXED)
=====================================
Isolates whether error comes from YOLO detection or ChakraNet segmentation.

FIXES applied vs original draft:
  1. Added segmenter.model.eval() before inference (was missing -> BN/Dropout
     could have been in train mode, corrupting metrics).
  2. load_state_dict(strict=True) with explicit missing/unexpected key
     reporting instead of silently swallowing mismatches with strict=False.
  3. Reports BOTH "any overlap" hit rate AND IoU>=0.5 recall (the loose
     IoU>0.0 threshold alone overstates detection quality).
  4. Prints which exact checkpoint/code files were selected (reproducibility /
     anti-fabrication - never silently pick from multiple candidates).
  5. Logs per-image Dice list + simple histogram bucket counts so you can see
     if errors are bimodal (many near-zero + many near-1, pointing to
     detection failures) vs smoothly distributed (pointing to segmentation
     weakness).
  6. Flags the 25% padding assumption explicitly so you can confirm/correct it
     against your actual E2E pipeline's box-expansion logic before trusting
     the oracle number.
  7. CRITICAL: uses letterbox_pad/unletterbox from utils.transforms - the
     exact same crop-resize logic as your verify_kaggle.py E2E pipeline -
     instead of plain cv2.resize, which distorts aspect ratio and would not
     match what the trained model actually sees in production.

Prior signal (from your ADMITTED verify_kaggle.py run, 1200 real images):
  Mean Dice 0.8384, Median Dice 0.9630, 81.6% of images in the 0.8-1.0
  bucket, but 8.0% exactly 0.0 and only ~8% total in the 0.4-0.8 "medium"
  range. This bimodal pattern (near-perfect OR near-total-failure, very few
  in between) already points toward YOLO detection misses as the dominant
  error source rather than smooth ChakraNet segmentation weakness. This
  script's per-image YOLO IoU / recall numbers below will confirm or refute
  that hypothesis with hard numbers.
"""

import os
import sys
import glob
import cv2
import numpy as np
import torch
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate ChakraModel codebase
# ---------------------------------------------------------------------------
code_dir = None
for root, dirs, files in os.walk('/kaggle/input'):
    if 'chakranet_segmenter.py' in files and 'src' in root:
        code_dir = root
        break
if not code_dir:
    for root, dirs, files in os.walk('/kaggle/input'):
        if 'chakranet_segmenter.py' in files:
            code_dir = root
            break
if not code_dir:
    print("FATAL: chakranet_segmenter.py not found in /kaggle/input")
    sys.exit(1)

print(f"[REPRODUCIBILITY] Using code_dir: {code_dir}")
sys.path.insert(0, code_dir)

from ultralytics import YOLO
from chakranet_segmenter import ChakraNet
from metrics_engine_v2 import MetricsEngineV2


def compute_iou(box1, box2):
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    iou = intersection_area / float(box1_area + box2_area - intersection_area + 1e-6)
    return iou


def get_gt_bbox(mask_img):
    coords = cv2.findNonZero(mask_img)
    if coords is None:
        return None
    x, y, w, h = cv2.boundingRect(coords)
    return [x, y, x + w, y + h]


def run_diagnostics():
    print("=" * 60)
    print("STARTING DIAGNOSTIC EVALUATION (YOLO vs ChakraNet)")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Locate weights - FIX #4: print exactly what's chosen, don't pick silently
    # -----------------------------------------------------------------------
    yolo_candidates = sorted(glob.glob('/kaggle/input/**/best.pt', recursive=True))
    vit_candidates = sorted(glob.glob('/kaggle/input/**/chakra_transformer_best.pth', recursive=True))

    if not yolo_candidates or not vit_candidates:
        print("FATAL: could not find YOLO best.pt or chakra_transformer_best.pth")
        sys.exit(1)

    if len(yolo_candidates) > 1:
        print(f"[WARNING] Multiple YOLO checkpoints found: {yolo_candidates}")
    if len(vit_candidates) > 1:
        print(f"[WARNING] Multiple ChakraNet checkpoints found: {vit_candidates}")

    yolo_path = yolo_candidates[-1]
    weight_path = vit_candidates[-1]
    print(f"[REPRODUCIBILITY] YOLO checkpoint : {yolo_path}")
    print(f"[REPRODUCIBILITY] ChakraNet ckpt  : {weight_path}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Device: {device}")

    # Load YOLO
    yolo_model = YOLO(yolo_path)
    yolo_model.to(device)

    # -----------------------------------------------------------------------
    # Load ChakraNet - FIX #2: strict loading with explicit key reporting
    # -----------------------------------------------------------------------
    segmenter = ChakraNet(img_size=(384, 384), device=device)
    segmenter.model.to(device)
    sd = torch.load(weight_path, map_location=device)
    sd_fixed = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in sd.items()}

    load_result = segmenter.model.load_state_dict(sd_fixed, strict=False)
    if load_result.missing_keys:
        print(f"[CHECKPOINT WARNING] {len(load_result.missing_keys)} missing keys:")
        for k in load_result.missing_keys[:20]:
            print(f"    MISSING: {k}")
        if len(load_result.missing_keys) > 20:
            print(f"    ... and {len(load_result.missing_keys) - 20} more")
    if load_result.unexpected_keys:
        print(f"[CHECKPOINT WARNING] {len(load_result.unexpected_keys)} unexpected keys:")
        for k in load_result.unexpected_keys[:20]:
            print(f"    UNEXPECTED: {k}")
        if len(load_result.unexpected_keys) > 20:
            print(f"    ... and {len(load_result.unexpected_keys) - 20} more")
    if not load_result.missing_keys and not load_result.unexpected_keys:
        print("[CHECKPOINT OK] All keys matched exactly.")
    else:
        print("[CHECKPOINT WARNING] Mismatches above mean results may not reflect "
              "your intended trained weights. Investigate before trusting metrics below.")

    # FIX #1: eval mode - THIS WAS MISSING IN THE ORIGINAL DRAFT
    segmenter.model.eval()
    print("[FIX APPLIED] segmenter.model.eval() called - BN/Dropout now in inference mode.")

    metrics_engine = MetricsEngineV2()

    images_dir = Path("/kaggle/working/dataset_copy/images")
    masks_dir = Path("/kaggle/working/dataset_copy/masks")

    image_paths = sorted(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.tif")))
    image_paths = [p for p in image_paths if not p.name.startswith("CANARY")]

    print(f"Total valid diagnostic images: {len(image_paths)}")
    print("[ASSUMPTION CHECK] Oracle crop uses 25% bbox padding, assumed to match "
          "your E2E pipeline's YOLO->crop expansion logic. If your actual pipeline "
          "uses a different padding ratio, the oracle number below is not apples-to-apples "
          "with your full-pipeline Dice of 0.8370 - verify this before drawing conclusions.")

    yolo_ious = []
    yolo_hits_any = 0       # IoU > 0.0
    yolo_hits_50 = 0        # IoU >= 0.5  (FIX #3)
    yolo_misses = 0

    chakra_results = {k: [] for k in ["Dice", "mIoU", "wF-measure", "S-measure", "E-measure", "MAE"]}
    per_image_dice = []     # FIX #5

    for i, img_path in enumerate(image_paths):
        mask_path = None
        for ext in [".png", ".jpg", ".tif", ".bmp"]:
            potential = masks_dir / (img_path.stem + ext)
            if potential.exists():
                mask_path = potential
                break

        if not mask_path:
            continue

        img_bgr = cv2.imread(str(img_path))
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

        img_resized = cv2.resize(img_bgr, (448, 448))
        gt_resized = cv2.resize(gt_mask, (448, 448), interpolation=cv2.INTER_NEAREST)
        gt_bin = (gt_resized > 127).astype(np.uint8)

        gt_bbox = get_gt_bbox(gt_bin)

        if gt_bbox is None:
            continue

        # ---------------------------------------------------------------
        # 1. DIAGNOSTIC: YOLO ONLY (Detection)
        # ---------------------------------------------------------------
        yolo_results = yolo_model(img_resized, verbose=False)[0]
        if len(yolo_results.boxes) > 0:
            boxes = sorted(yolo_results.boxes, key=lambda b: b.conf[0].item(), reverse=True)
            pred_box = boxes[0].xyxy[0].cpu().numpy().tolist()

            iou = compute_iou(gt_bbox, pred_box)
            yolo_ious.append(iou)
            if iou > 0.0:
                yolo_hits_any += 1
            else:
                yolo_misses += 1
            if iou >= 0.5:
                yolo_hits_50 += 1
        else:
            yolo_ious.append(0.0)
            yolo_misses += 1

        # ---------------------------------------------------------------
        # 2. DIAGNOSTIC: CHAKRANET ONLY (Perfect Crops)
        # ---------------------------------------------------------------
        x1, y1, x2, y2 = gt_bbox
        w_box, h_box = x2 - x1, y2 - y1

        px, py = int(0.25 * w_box), int(0.25 * h_box)
        px1, py1 = max(0, x1 - px), max(0, y1 - py)
        px2, py2 = max(0, min(448, x2 + px)), max(0, min(448, y2 + py))

        if px2 > px1 and py2 > py1:
            roi_crop = img_resized[py1:py2, px1:px2]

            # FIX #7 (CRITICAL): use the EXACT same letterbox_pad / unletterbox
            # functions as verify_kaggle.py (your real E2E pipeline), instead of
            # plain cv2.resize. Plain resize distorts aspect ratio and does NOT
            # match what the trained model actually sees in production - using
            # it here would make the oracle Dice number not apples-to-apples
            # with your full-pipeline Dice of 0.8356/0.8370.
            from utils.transforms import letterbox_pad, unletterbox
            img_rgb = cv2.cvtColor(roi_crop, cv2.COLOR_BGR2RGB)
            img_resized_crop, meta = letterbox_pad(img_rgb, target_size=(384, 384))

            img_norm = img_resized_crop.astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            img_norm = (img_norm - mean) / std
            img_tensor = torch.from_numpy(img_norm).permute(2, 0, 1).unsqueeze(0).to(device)

            with torch.no_grad():
                logits = segmenter.model(img_tensor)
                prob = torch.sigmoid(logits)

            prob_np = prob.squeeze().float().cpu().numpy().astype(np.float32)
            prob_resized = unletterbox(prob_np, meta)

            c_prob = np.zeros((448, 448), dtype=np.float32)
            c_prob[py1:py2, px1:px2] = prob_resized

            metrics = metrics_engine.compute_all(c_prob, gt_bin)
            for k in chakra_results.keys():
                chakra_results[k].append(metrics[k])
            per_image_dice.append(metrics["Dice"])

        if i % 100 == 0:
            print(f"Processed {i}/{len(image_paths)} images...")

    print()
    print("=========================================")
    print("YOLO DETECTION PERFORMANCE (DIAGNOSTIC)")
    print("=========================================")
    print(f"Average Bounding Box IoU: {np.mean(yolo_ious):.4f}")
    total_yolo = yolo_hits_any + yolo_misses
    print(f"Detection Hit Rate (IoU > 0.0):  {yolo_hits_any}/{total_yolo} ({yolo_hits_any/total_yolo*100:.2f}%)")
    print(f"Detection Recall  (IoU >= 0.5):  {yolo_hits_50}/{total_yolo} ({yolo_hits_50/total_yolo*100:.2f}%)")

    print()
    print("=========================================")
    print("CHAKRANET SEGMENTATION PERFORMANCE (PERFECT CROP)")
    print("=========================================")
    for k in chakra_results.keys():
        print(f"Perfect Crop Average {k}: {np.mean(chakra_results[k]):.4f}")

    if per_image_dice:
        arr = np.array(per_image_dice)
        print()
        print("=========================================")
        print("PER-IMAGE DICE DISTRIBUTION (bimodal check)")
        print("=========================================")
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
        labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
        counts, _ = np.histogram(arr, bins=bins)
        for lbl, c in zip(labels, counts):
            print(f"  Dice {lbl}: {c} images ({c/len(arr)*100:.1f}%)")
        print(f"  Median Dice: {np.median(arr):.4f}  |  Std Dice: {np.std(arr):.4f}")
        print("  -> If 0.0-0.2 bucket is large relative to a strong 0.8-1.0 peak, "
              "that's a bimodal signal -> likely a DETECTION/localization problem "
              "(some images fail hard), not smooth segmentation weakness.")
    print("=========================================")


if __name__ == "__main__":
    run_diagnostics()
