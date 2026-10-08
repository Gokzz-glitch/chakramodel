import hashlib
import json
import sys
from pathlib import Path
import cv2
import numpy as np
import torch

# Force CPU by mocking CUDA availability before importing other modules

from ultralytics import YOLO

# Ensure we can import chakranet and metrics_engine
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from chakranet_segmenter import ChakraNet
from metrics_engine_v2 import MetricsEngineV2

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def verify_dataset(dataset_name, images_dir, masks_dir, yolo_model, segmenter, metrics_engine):
    print(f"\n============================================================")
    print(f"VERIFYING DATASET: {dataset_name}")
    print(f"============================================================")
    
    if not images_dir.exists():
        print(f"[ERROR] Images directory not found: {images_dir}")
        return
        
    image_paths = sorted(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.tif")))
    
    # NO SLICING/SUBSETTING - Enforce evaluation on the entire dataset
    print(f"Total images found: {len(image_paths)}")
    
    results = []
    
    for i, img_path in enumerate(image_paths):
        # Handle multiple possible mask extensions
        mask_path = None
        for ext in [".png", ".jpg", ".tif", ".bmp"]:
            potential_path = masks_dir / (img_path.stem + ext)
            if potential_path.exists():
                mask_path = potential_path
                break
                
        if not mask_path:
            print(f"[WARN] Mask not found for {img_path.name}")
            continue
            
        img_bgr = cv2.imread(str(img_path))
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        # YOLO requires 448x448 input based on our checkpoint
        img_resized = cv2.resize(img_bgr, (448, 448))
        yolo_results = yolo_model(img_resized, verbose=False)[0]
        c_mask = np.zeros((448, 448), dtype=np.uint8)
        
        if len(yolo_results.boxes) > 0:
            boxes = sorted(yolo_results.boxes, key=lambda b: b.conf[0].item(), reverse=True)
            box = boxes[0].xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(int, box)
            
            w_box, h_box = x2 - x1, y2 - y1
            px, py = int(0.25 * w_box), int(0.25 * h_box)
            px1, py1 = max(0, x1 - px), max(0, y1 - py)
            px2, py2 = max(0, min(448, x2 + px)), max(0, min(448, y2 + py))
            
            if px2 > px1 and py2 > py1:
                roi_crop = img_resized[py1:py2, px1:px2]
                seg_roi_mask, _, _, _ = segmenter.segment_roi(roi_crop, threshold=0.45)
                if seg_roi_mask is not None:
                    seg_roi_mask = cv2.resize(seg_roi_mask, (px2-px1, py2-py1), interpolation=cv2.INTER_NEAREST)
                    c_mask[py1:py2, px1:px2] = seg_roi_mask
                    
        gt_resized = cv2.resize(gt_mask, (448, 448), interpolation=cv2.INTER_NEAREST)
        
        # EXPLICIT BINARIZATION to [0, 1] before metrics computation
        c_bin = (c_mask > 127).astype(np.uint8)
        gt_bin = (gt_resized > 127).astype(np.uint8)
        
        metrics = metrics_engine.compute_all(c_bin, gt_bin)
        results.append(metrics["Dice"])
        
        if (i + 1) % 50 == 0 or (i + 1) == len(image_paths):
            print(f"[{i + 1}/{len(image_paths)}] Processed. Current Avg Dice: {np.mean(results):.4f}")
            
    avg_dice = float(np.mean(results))
    print(f"\n[DONE] {dataset_name}")
    print(f"Total Evaluated Images: {len(results)}")
    print(f"Final True Average Dice: {avg_dice:.4f}")
    print(f"============================================================")

def verify_strict():
    root = Path(__file__).parent.parent
    weight_path = root / "weights" / "chakra_transformer_best.pth"
    yolo_path = root / "weights" / "best.pt"
    
    print("=" * 60)
    print("STRICT CHECKPOINT AND ARCHITECTURE VERIFICATION")
    print("=" * 60)
    print(f"Segmenter Checkpoint: {weight_path}")
    print(f"Segmenter MD5: {md5(weight_path)}")
    print(f"YOLO Checkpoint: {yolo_path}")
    print(f"YOLO MD5: {md5(yolo_path)}")
    print("=" * 60)
    
    # Enable CUDA if available, fallback to CPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing on device: {device}")
    
    yolo_model = YOLO(yolo_path)
    yolo_model.to(device)
    
    segmenter = ChakraNet(img_size=(384, 384), device=device)
    segmenter.model.to(device)
    
    # Load weights correctly by explicitly stripping 'module.'
    sd = torch.load(weight_path, map_location=device)
    sd_fixed = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in sd.items()}
    res = segmenter.model.load_state_dict(sd_fixed, strict=False)
    print(f"ChakraNet Weights Loaded. Missing keys: {len(res.missing_keys)}, Unexpected keys: {len(res.unexpected_keys)}")
    
    metrics_engine = MetricsEngineV2()
    
    # CVC-ColonDB (N=380)
    colondb_images = root / "data/cvc-colondb/images"
    colondb_masks = root / "data/cvc-colondb/masks"
    verify_dataset("CVC-ColonDB", colondb_images, colondb_masks, yolo_model, segmenter, metrics_engine)
    
    # CVC-300 (N=60)
    cvc300_images = root / "data/cvc-300/images"
    cvc300_masks = root / "data/cvc-300/masks"
    verify_dataset("CVC-300", cvc300_images, cvc300_masks, yolo_model, segmenter, metrics_engine)

if __name__ == "__main__":
    verify_strict()
