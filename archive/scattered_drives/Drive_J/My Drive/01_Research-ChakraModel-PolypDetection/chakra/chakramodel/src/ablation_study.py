import os
import cv2
import numpy as np
import torch
import time
from pathlib import Path
from tabulate import tabulate
from tqdm import tqdm
from ultralytics import YOLO

import sys
sys.path.insert(0, str(Path(__file__).parent))
from chakranet_segmenter import ChakraNet
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from metrics_engine_v2 import MetricsEngineV2

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

def find_mask(masks_dir: Path, stem: str) -> Path | None:
    for ext in IMAGE_EXTS:
        p = masks_dir / (stem + ext)
        if p.exists():
            return p
    return None

def main():
    root = Path(__file__).parent.parent
    data_dir = root / "data" / "kvasir-seg"
    images_dir = data_dir / "images"
    masks_dir = data_dir / "masks"

    if not images_dir.exists():
        print(f"[ERROR] Dataset not found at {images_dir}")
        sys.exit(1)

    image_paths = sorted([p for p in images_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS])
    # Fix Data Leakage: Use the last 20% of the sorted dataset as the test set
    n_test = max(1, int(0.2 * len(image_paths)))
    image_paths = image_paths[-n_test:]

    model_path = root / "weights" / "best.pt"
    if not model_path.exists():
        raise FileNotFoundError(f"Missing fine-tuned YOLO model at {model_path}. COCO models like yolov8n.pt are medically invalid.")
    yolo_model = YOLO(model_path)
    segmenter = ChakraNet(img_size=(448, 448))

    metrics_engine = MetricsEngineV2()
    
    results = {
        "Baseline 1 (YOLO Only)": {"dice": [], "iou": [], "wF": [], "S": [], "E": [], "time": []},
        "Baseline 2 (ChakraNet Only)": {"dice": [], "iou": [], "wF": [], "S": [], "E": [], "time": []},
        "Proposed (ChakraModel - Padded Crop)": {"dice": [], "iou": [], "wF": [], "S": [], "E": [], "time": []}
    }

    for img_path in tqdm(image_paths, desc="Running Ablation Study"):
        mask_path = find_mask(masks_dir, img_path.stem)
        if not mask_path: continue

        img_bgr = cv2.imread(str(img_path))
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if img_bgr is None or gt_mask is None: continue

        eval_size = (448, 448)
        img_resized = cv2.resize(img_bgr, eval_size)
        gt_resized = cv2.resize(gt_mask, eval_size, interpolation=cv2.INTER_NEAREST)
        gt_bin = (gt_resized > 127).astype(np.uint8)

        # Baseline 1: YOLO
        t0 = time.perf_counter()
        yolo_results = yolo_model(img_resized, verbose=False)[0]
        yolo_mask = np.zeros(eval_size, dtype=np.uint8)
        if len(yolo_results.boxes) > 0:
            for box in yolo_results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(eval_size[0], x2), min(eval_size[1], y2)
                yolo_mask[y1:y2, x1:x2] = 1
        t1 = time.perf_counter()
        results["Baseline 1 (YOLO Only)"]["time"].append(t1 - t0)
        
        m_yolo = metrics_engine.compute_all(yolo_mask, gt_bin)
        results["Baseline 1 (YOLO Only)"]["dice"].append(m_yolo["Dice"])
        results["Baseline 1 (YOLO Only)"]["iou"].append(m_yolo["mIoU"])
        results["Baseline 1 (YOLO Only)"]["wF"].append(m_yolo["wF-measure"])
        results["Baseline 1 (YOLO Only)"]["S"].append(m_yolo["S-measure"])
        results["Baseline 1 (YOLO Only)"]["E"].append(m_yolo["E-measure"])

        # Baseline 2: ChakraNet Only
        t0 = time.perf_counter()
        p_mask, _, _, _ = segmenter.segment_roi(img_resized)
        if p_mask is None: p_mask = np.zeros(eval_size, dtype=np.uint8)
        p_mask = cv2.resize(p_mask, eval_size, interpolation=cv2.INTER_NEAREST)
        p_bin = (p_mask > 127).astype(np.uint8)
        t1 = time.perf_counter()
        results["Baseline 2 (ChakraNet Only)"]["time"].append(t1 - t0)
        
        m_pranet = metrics_engine.compute_all(p_bin, gt_bin)
        results["Baseline 2 (ChakraNet Only)"]["dice"].append(m_pranet["Dice"])
        results["Baseline 2 (ChakraNet Only)"]["iou"].append(m_pranet["mIoU"])
        results["Baseline 2 (ChakraNet Only)"]["wF"].append(m_pranet["wF-measure"])
        results["Baseline 2 (ChakraNet Only)"]["S"].append(m_pranet["S-measure"])
        results["Baseline 2 (ChakraNet Only)"]["E"].append(m_pranet["E-measure"])

        # Proposed: ChakraModel (YOLO Context-Padded Crop -> ChakraNet)
        t0 = time.perf_counter()
        c_mask = np.zeros(eval_size, dtype=np.uint8)
        if len(yolo_results.boxes) > 0:
            for box_data in yolo_results.boxes:
                box = box_data.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, box)
                
                # Add 25% padding for context
                w, h = x2 - x1, y2 - y1
                px, py = int(0.25 * w), int(0.25 * h)
                px1, py1 = max(0, x1 - px), max(0, y1 - py)
                px2, py2 = min(eval_size[0], x2 + px), min(eval_size[1], y2 + py)
                
                if px2 > px1 and py2 > py1:
                    roi_crop = img_resized[py1:py2, px1:px2]
                    seg_roi_mask, _, _, _ = segmenter.segment_roi(roi_crop)
                    if seg_roi_mask is not None:
                        seg_roi_mask = cv2.resize(seg_roi_mask, (px2-px1, py2-py1), interpolation=cv2.INTER_NEAREST)
                        c_mask[py1:py2, px1:px2] = np.maximum(c_mask[py1:py2, px1:px2], seg_roi_mask)
                    
        c_bin = (c_mask > 127).astype(np.uint8)
        t1 = time.perf_counter()
        results["Proposed (ChakraModel - Padded Crop)"]["time"].append(results["Baseline 1 (YOLO Only)"]["time"][-1] + (t1 - t0))
        
        m_prop = metrics_engine.compute_all(c_bin, gt_bin)
        results["Proposed (ChakraModel - Padded Crop)"]["dice"].append(m_prop["Dice"])
        results["Proposed (ChakraModel - Padded Crop)"]["iou"].append(m_prop["mIoU"])
        results["Proposed (ChakraModel - Padded Crop)"]["wF"].append(m_prop["wF-measure"])
        results["Proposed (ChakraModel - Padded Crop)"]["S"].append(m_prop["S-measure"])
        results["Proposed (ChakraModel - Padded Crop)"]["E"].append(m_prop["E-measure"])

    print("\n# Ablation Study Results")
    table_data = []
    for model_name, metrics in results.items():
        m_dice = np.mean(metrics["dice"])
        m_iou = np.mean(metrics["iou"])
        m_wf = np.mean(metrics["wF"])
        m_s = np.mean(metrics["S"])
        m_e = np.mean(metrics["E"])
        m_time = np.mean(metrics["time"])
        fps = 1.0 / m_time if m_time > 0 else 0
        table_data.append([model_name, f"{m_dice:.4f}", f"{m_iou:.4f}", f"{m_wf:.4f}", f"{m_s:.4f}", f"{m_e:.4f}", f"{fps:.1f} FPS"])
        
    print(tabulate(table_data, headers=["Architecture", "Dice (DSC)", "mIoU", "wF", "S", "E", "Speed"], tablefmt="github"))
    
    out_path = root / "ablation_results.md"
    with open(out_path, "w") as f:
        f.write("# Ablation Study Results\n\n")
        f.write("Comparison of YOLO alone, ChakraNet alone, and the combined ChakraModel pipeline (Context-Padded Crop).\n\n")
        f.write(tabulate(table_data, headers=["Architecture", "Dice (DSC)", "mIoU", "wF", "S", "E", "Speed"], tablefmt="github"))
        f.write("\n")

if __name__ == "__main__":
    main()
