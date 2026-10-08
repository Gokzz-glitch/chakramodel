import hashlib
import json
import sys
import os
from pathlib import Path
import cv2
import numpy as np
import torch

# Force CPU by mocking CUDA availability before importing other modules
torch.cuda.is_available = lambda: False

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

def verify_colondb():
    root = Path(__file__).parent.parent
    weight_path = root / "weights" / "chakra_transformer_best.pth"
    yolo_path = root / "weights" / "best.pt"
    
    print("=" * 60, flush=True)
    print("CHECKPOINT VERIFICATION", flush=True)
    print("=" * 60, flush=True)
    nonce = os.environ.get("VERIFY_NONCE", "NO_NONCE")
    print(f"VERIFY_NONCE: {nonce}", flush=True)
    print(f"Segmenter Checkpoint: {weight_path}", flush=True)
    print(f"Segmenter MD5: {md5(weight_path)}")
    print(f"YOLO Checkpoint: {yolo_path}")
    print(f"YOLO MD5: {md5(yolo_path)}")
    print("=" * 60)
    
    # Force CPU to avoid CUDA OOM during verification
    device = "cpu"
    
    yolo_model = YOLO(yolo_path)
    yolo_model.to(device)
    
    # Initialize ChakraNet and force CPU
    segmenter = ChakraNet(img_size=(384, 384), device=device)
    segmenter.model.to(device)
    
    # FIX 1: Manually load weights and correctly strip 'module.'
    sd = torch.load(weight_path, map_location=device)
    sd_fixed = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in sd.items()}
    res = segmenter.model.load_state_dict(sd_fixed, strict=False)
    print(f"ChakraNet Weights Loaded. Missing keys: {len(res.missing_keys)}, Unexpected keys: {len(res.unexpected_keys)}")
    
    metrics_engine = MetricsEngineV2()
    
    images_dir = root / "data/cvc-colondb/images"
    masks_dir = root / "data/cvc-colondb/masks"
    
    image_paths = sorted(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")))
    
    print(f"Total images found: {len(image_paths)}", flush=True)
    print(f"\nEvaluating on {len(image_paths)} CVC-ColonDB images...", flush=True)
    
    results = []
    
    for i, img_path in enumerate(image_paths):
        mask_path = masks_dir / img_path.name
        if not mask_path.exists():
            continue
            
        img_bgr = cv2.imread(str(img_path))
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
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
        
        # FIX 2: Binarize masks to [0, 1] before metrics computation!
        c_bin = (c_mask > 127).astype(np.uint8)
        gt_bin = (gt_resized > 127).astype(np.uint8)
        
        metrics = metrics_engine.compute_all(c_bin, gt_bin)
        results.append(metrics["Dice"])
        print(f"{img_path.name}: {metrics['Dice']:.4f}", flush=True)
        
    avg_dice = float(np.mean(results))
    print(f"\nFinished evaluation!")
    print(f"True Average Dice for CVC-ColonDB: {avg_dice:.4f}")
    
    print("\nCONCLUSION:")
    if avg_dice > 0.8:
        print("The 0.84 Dice from evaluate_all.py is the TRUE score.")
    else:
        print("The 0.006 Dice from benchmark_kvasir.py is the TRUE score.")

if __name__ == "__main__":
    verify_colondb()
