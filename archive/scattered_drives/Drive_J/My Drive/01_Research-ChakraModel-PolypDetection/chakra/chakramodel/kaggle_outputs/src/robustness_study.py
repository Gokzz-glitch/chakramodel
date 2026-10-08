import os
import cv2
import numpy as np
import torch
from pathlib import Path
from tabulate import tabulate
from tqdm import tqdm
from ultralytics import YOLO

import sys
sys.path.insert(0, str(Path(__file__).parent))
from chakranet_segmenter import ChakraNet
from metrics.seg_metrics import dice as binary_dice_coefficient, iou as binary_iou

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

def find_mask(masks_dir: Path, stem: str) -> Path | None:
    for ext in IMAGE_EXTS:
        p = masks_dir / (stem + ext)
        if p.exists():
            return p
    return None

def apply_glare(img):
    out = img.copy()
    h, w = out.shape[:2]
    # Add 3-5 random bright white circles to simulate specular reflection
    for _ in range(np.random.randint(3, 6)):
        center = (np.random.randint(0, w), np.random.randint(0, h))
        radius = np.random.randint(10, 30)
        cv2.circle(out, center, radius, (255, 255, 255), -1)
        # Add some blur to the glare to make it look realistic
        out = cv2.GaussianBlur(out, (11, 11), 0)
    return out

def apply_blur(img):
    return cv2.GaussianBlur(img, (25, 25), 0)

def apply_dim(img):
    return np.clip(img.astype(np.float32) * 0.3, 0, 255).astype(np.uint8)

def eval_pipeline(yolo_model, segmenter, img_bgr, gt_bin, eval_size):
    img_resized = cv2.resize(img_bgr, eval_size)
    yolo_results = yolo_model(img_resized, verbose=False)[0]
    
    c_mask = np.zeros(eval_size, dtype=np.uint8)
    if len(yolo_results.boxes) > 0:
        boxes = sorted(yolo_results.boxes, key=lambda b: b.conf[0].item(), reverse=True)
        box = boxes[0].xyxy[0].cpu().numpy()
        x1, y1, x2, y2 = map(int, box)
        
        w, h = x2 - x1, y2 - y1
        px, py = int(0.25 * w), int(0.25 * h)
        px1, py1 = max(0, x1 - px), max(0, y1 - py)
        px2, py2 = min(eval_size[0], x2 + px), min(eval_size[1], y2 + py)
        
        if px2 > px1 and py2 > py1:
            roi_crop = img_resized[py1:py2, px1:px2]
            seg_roi_mask, _, _, _ = segmenter.segment_roi(roi_crop)
            if seg_roi_mask is not None:
                seg_roi_mask = cv2.resize(seg_roi_mask, (px2-px1, py2-py1), interpolation=cv2.INTER_NEAREST)
                c_mask[py1:py2, px1:px2] = seg_roi_mask
                
    c_bin = (c_mask > 127).astype(np.uint8)
    dice = binary_dice_coefficient(c_bin, gt_bin)
    iou = binary_iou(c_bin, gt_bin)
    return dice, iou

def main():
    root = Path(__file__).parent.parent
    data_dir = root / "data" / "kvasir-seg"
    images_dir = data_dir / "images"
    masks_dir = data_dir / "masks"

    if not images_dir.exists():
        print(f"[ERROR] Dataset not found at {images_dir}")
        sys.exit(1)

    image_paths = sorted([p for p in images_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS])
    
    # Take a representative subset (first 200 images) to speed up evaluation if needed
    # Or just run full if we have time. Let's run full.
    print(f"Loaded {len(image_paths)} Kvasir-SEG test images for robustness evaluation.")

    model_path = root / "weights" / "best.pt"
    if not model_path.exists(): model_path = "yolov8n.pt"
    yolo_model = YOLO(model_path)
    segmenter = ChakraNet(img_size=(352, 352))

    conditions = ["Clean", "Motion Blur", "Low Light", "Specular Glare"]
    results = {c: {"dice": [], "iou": []} for c in conditions}

    for img_path in tqdm(image_paths, desc="Running Robustness Study"):
        mask_path = find_mask(masks_dir, img_path.stem)
        if not mask_path: continue

        img_bgr = cv2.imread(str(img_path))
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if img_bgr is None or gt_mask is None: continue

        eval_size = (448, 448)
        gt_resized = cv2.resize(gt_mask, eval_size, interpolation=cv2.INTER_NEAREST)
        gt_bin = (gt_resized > 127).astype(np.uint8)

        # 1. Clean
        d, i = eval_pipeline(yolo_model, segmenter, img_bgr, gt_bin, eval_size)
        results["Clean"]["dice"].append(d)
        results["Clean"]["iou"].append(i)

        # 2. Motion Blur
        img_blur = apply_blur(img_bgr)
        d, i = eval_pipeline(yolo_model, segmenter, img_blur, gt_bin, eval_size)
        results["Motion Blur"]["dice"].append(d)
        results["Motion Blur"]["iou"].append(i)

        # 3. Low Light
        img_dim = apply_dim(img_bgr)
        d, i = eval_pipeline(yolo_model, segmenter, img_dim, gt_bin, eval_size)
        results["Low Light"]["dice"].append(d)
        results["Low Light"]["iou"].append(i)

        # 4. Specular Glare
        img_glare = apply_glare(img_bgr)
        d, i = eval_pipeline(yolo_model, segmenter, img_glare, gt_bin, eval_size)
        results["Specular Glare"]["dice"].append(d)
        results["Specular Glare"]["iou"].append(i)

    print("\n\n# Clinical Robustness Study Results")
    table_data = []
    clean_dice = np.mean(results["Clean"]["dice"])
    
    for condition in conditions:
        m_dice = np.mean(results[condition]["dice"])
        m_iou = np.mean(results[condition]["iou"])
        
        drop_pct = 0.0
        if condition != "Clean":
            drop_pct = ((clean_dice - m_dice) / clean_dice) * 100
            
        drop_str = f"-{drop_pct:.1f}%" if condition != "Clean" else "-"
        table_data.append([condition, f"{m_dice:.4f}", f"{m_iou:.4f}", drop_str])
        
    print(tabulate(table_data, headers=["Condition", "Dice (DSC)", "mIoU", "Degradation"], tablefmt="github"))
    
    out_path = root / "robustness_results.md"
    with open(out_path, "w") as f:
        f.write("# Clinical Robustness Study Results\n\n")
        f.write("Evaluating ChakraModel against synthetic real-world corruptions (blur, poor lighting, specular glare).\n\n")
        f.write(tabulate(table_data, headers=["Condition", "Dice (DSC)", "mIoU", "Degradation"], tablefmt="github"))
        f.write("\n")
        
if __name__ == "__main__":
    main()
