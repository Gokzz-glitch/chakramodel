import os
import sys
import glob
import cv2
import numpy as np
import torch
from pathlib import Path
import hashlib

# Disable CUDA if running entirely on CPU
# torch.cuda.is_available = lambda: False

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def verify_strict():
    print("=" * 60)
    print("STRICT CHECKPOINT AND ARCHITECTURE VERIFICATION")
    print("=" * 60)
    
    # Identify codebase path
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
    assert code_dir, "FATAL: ChakraModel codebase not found in /kaggle/input"
    sys.path.insert(0, code_dir)
    print(f"[VERIFY] Codebase found at: {code_dir}")
    
    from ultralytics import YOLO
    from chakranet_segmenter import ChakraNet
    from metrics_engine_v2 import MetricsEngineV2

    # BUG 3 FIX: Strict Weight Selection
    yolo_candidates = glob.glob('/kaggle/input/**/best.pt', recursive=True)
    vit_candidates = glob.glob('/kaggle/input/**/chakra_transformer_best.pth', recursive=True)
    
    print(f"YOLO candidates found: {yolo_candidates}")
    print(f"ViT candidates found: {vit_candidates}")
    
    assert len(yolo_candidates) > 0, "FATAL: best.pt not found!"
    assert len(vit_candidates) > 0, "FATAL: chakra_transformer_best.pth not found!"
    
    yolo_path = yolo_candidates[-1]
    weight_path = vit_candidates[-1]

    print(f"Segmenter Checkpoint: {weight_path}")
    print(f"Segmenter MD5: {md5(weight_path)}")
    print(f"YOLO Checkpoint: {yolo_path}")
    print(f"YOLO MD5: {md5(yolo_path)}")
    print("=" * 60)
    
    nonce = os.environ.get("VERIFY_NONCE", "NO_NONCE")
    print(f"VERIFY_NONCE: {nonce}")
    
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
    
    total_keys = len(segmenter.model.state_dict())
    if len(res.missing_keys) > (0.1 * total_keys):
        print(f"[FATAL] Major weight mismatch! Missing keys > 10% ({len(res.missing_keys)} missing out of {total_keys}).")
        sys.exit(1)
    
    metrics_engine = MetricsEngineV2()
    
    dataset_name = os.environ.get("VERIFY_DATASET_NAME")
    dataset_root = os.environ.get("VERIFY_DATASET_ROOT")
    
    if not dataset_name or not dataset_root:
        print("[FATAL] VERIFY_DATASET_NAME or VERIFY_DATASET_ROOT environment variable not set.")
        sys.exit(1)
        
    print(f"\n============================================================")
    print(f"VERIFYING DATASET: {dataset_name}")
    print(f"============================================================")
    
    d_root = Path(dataset_root)
    images_dir = d_root / "images"
    masks_dir = d_root / "masks"
    
    if not images_dir.exists():
        print(f"[FATAL] Images directory not found: {images_dir}")
        sys.exit(1)
        
    image_paths = sorted(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.tif")))
    print(f"Total images found: {len(image_paths)}")
    
    results = {k: [] for k in ["Dice", "mIoU", "wF-measure", "S-measure", "E-measure", "MAE"]}
    
    for i, img_path in enumerate(image_paths):
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
        gt_resized = cv2.resize(gt_mask, (448, 448), interpolation=cv2.INTER_NEAREST)
        
        img_resized = cv2.resize(img_bgr, (448, 448))
        yolo_results = yolo_model(img_resized, verbose=False)[0]
        
        # Soft prob map initialized to 0
        c_prob = np.zeros((448, 448), dtype=np.float32)
        
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
                
                # BUG 2 FIX: Direct manual inference to get probability map instead of hard mask
                img_rgb = cv2.cvtColor(roi_crop, cv2.COLOR_BGR2RGB)
                img_resized_crop = cv2.resize(img_rgb, (384, 384))
                img_norm = img_resized_crop.astype(np.float32) / 255.0
                mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
                std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
                img_norm = (img_norm - mean) / std
                img_tensor = torch.from_numpy(img_norm).permute(2, 0, 1).unsqueeze(0).to(device)
                
                try:
                    with torch.no_grad():
                        logits = segmenter.model(img_tensor)
                        prob = torch.sigmoid(logits)
                except RuntimeError as e:
                    if "out of memory" in str(e).lower():
                        print("[WARN] Switched to CPU due to CUDA OutOfMemory!")
                        img_tensor_cpu = img_tensor.cpu()
                        segmenter.model.to('cpu')
                        with torch.no_grad():
                            logits = segmenter.model(img_tensor_cpu)
                            prob = torch.sigmoid(logits)
                        segmenter.model.to(device)
                    else:
                        raise
                        
                prob_np = prob.squeeze().cpu().numpy()
                prob_resized = cv2.resize(prob_np, (px2-px1, py2-py1), interpolation=cv2.INTER_LINEAR)
                
                c_prob[py1:py2, px1:px2] = prob_resized
        
        # Explicit binarization ONLY for the ground truth here (network outputs soft prob)
        gt_bin = (gt_resized > 127).astype(np.uint8)
        
        # Pass continuous probability map (c_prob) directly to compute_all 
        # (compute_all handles thresholding for Dice/IoU internally)
        metrics = metrics_engine.compute_all(c_prob, gt_bin)
        
        for k in results.keys():
            results[k].append(metrics[k])
            
        # IMPORTANT: Print per-image dice WITH FILENAME for canary detection
        dice_score = metrics['Dice']
        print(f"File: {img_path.name} | Dice: {dice_score:.4f}")
        
    print(f"\n[DONE] {dataset_name}")
    print(f"Total Evaluated Images: {len(results['Dice'])}")
    for k in results.keys():
        print(f"Final True Average {k}: {float(np.mean(results[k])):.4f}")
    print(f"============================================================")

if __name__ == "__main__":
    verify_strict()
