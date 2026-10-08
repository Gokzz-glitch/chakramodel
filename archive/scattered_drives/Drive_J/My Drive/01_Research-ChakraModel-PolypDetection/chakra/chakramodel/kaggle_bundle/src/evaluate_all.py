import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from metrics_engine_v2 import MetricsEngineV2
import json

try:
    from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "chakra_transformer"))
    from transformer_segmenter import ChakraTransformerSegmenter
import torch
import cv2
import numpy as np
from tqdm import tqdm
from ultralytics import YOLO

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir / "src"))

from run_all_combos import ChakraNet

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DATASETS = {
    "kvasir-seg":  ("data/kvasir-seg/images",  "data/kvasir-seg/masks"),
    "cvc-clinicdb": ("data/cvc-clinicdb/images", "data/cvc-clinicdb/masks"),
}

def evaluate_dataset(segmenter, yolo_model, metrics_engine, dataset_name, images_rel, masks_rel):
    images_dir = root_dir / images_rel
    masks_dir = root_dir / masks_rel
    
    if not images_dir.exists():
        print(f"[WARN] {dataset_name} not found at {images_dir}")
        return None
        
    image_paths = sorted([p for p in images_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS])
    
    # Fix Data Leakage: Use the last 10% of the sorted dataset as the test set ONLY for Kvasir-SEG
    if dataset_name == "kvasir-seg":
        n_test = max(1, int(0.1 * len(image_paths)))
        image_paths = image_paths[-n_test:]
    
    print(f"\n[EVAL] {dataset_name} ({len(image_paths)} images)")
    
    all_dices, all_ious, all_wFs, all_Ss, all_Es = [], [], [], [], []
    
    for img_path in tqdm(image_paths, desc=f"Evaluating {dataset_name}"):
        mask_path = None
        for ext in IMAGE_EXTS:
            if (masks_dir / (img_path.stem + ext)).exists():
                mask_path = masks_dir / (img_path.stem + ext)
                break
                
        if not mask_path:
            continue
            
        img_bgr = cv2.imread(str(img_path))
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        if img_bgr is None or gt_mask is None:
            continue
            
        orig_h, orig_w = gt_mask.shape
        eval_size = (384, 384)
        img_resized = cv2.resize(img_bgr, eval_size)
        gt_bin = (gt_mask > 127).astype(np.uint8)
        
        # YOLO Detection
        yolo_results = yolo_model(img_resized, verbose=False)[0]
        c_mask = np.zeros(eval_size, dtype=np.uint8)
        
        if len(yolo_results.boxes) > 0:
            # Loop over all detected boxes
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
                    # ChakraNet Segmentation (uses RGB)
                    roi_crop_resized = cv2.resize(roi_crop, (384, 384))
                    roi_crop_rgb = cv2.cvtColor(roi_crop_resized, cv2.COLOR_BGR2RGB)
                    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(DEVICE)
                    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(DEVICE)
                    t = torch.from_numpy(roi_crop_rgb).permute(2,0,1).unsqueeze(0).float().to(DEVICE) / 255.0
                    t = (t - mean) / std
                    
                    with torch.no_grad():
                        from torch.cuda.amp import autocast
                        with autocast():
                            out = segmenter(t)
                            if isinstance(out, tuple): out = out[0]
                            prob = torch.sigmoid(out).float().squeeze().cpu().numpy()
                            
                    seg_roi_mask = (prob > 0.5).astype(np.uint8) * 255
                    if seg_roi_mask is not None:
                        seg_roi_mask = cv2.resize(seg_roi_mask, (px2-px1, py2-py1), interpolation=cv2.INTER_NEAREST)
                        # We paste the mask into the padded bounding box region
                        # Take the maximum so we preserve multiple polyps
                        c_mask[py1:py2, px1:px2] = np.maximum(c_mask[py1:py2, px1:px2], seg_roi_mask)
        
        # Upsample prediction back to original ground truth resolution
        c_mask_orig = cv2.resize(c_mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
        c_bin = (c_mask_orig > 127).astype(np.uint8)
        
        # Compute metrics using proper engine
        m_prop = metrics_engine.compute_all(c_bin, gt_bin)
        all_dices.append(m_prop["Dice"])
        all_ious.append(m_prop["mIoU"])
        all_wFs.append(m_prop["wF-measure"])
        all_Ss.append(m_prop["S-measure"])
        all_Es.append(m_prop["E-measure"])
        
    if not all_dices:
        return None
        
    res = {
        "dataset": dataset_name,
        "images": len(all_dices),
        "dice": float(np.mean(all_dices)),
        "iou": float(np.mean(all_ious)),
        "wF": float(np.mean(all_wFs)),
        "S": float(np.mean(all_Ss)),
        "E": float(np.mean(all_Es))
    }
    
    print(f"  Dice: {res['dice']:.4f} | IoU: {res['iou']:.4f} | wF: {res['wF']:.4f} | S: {res['S']:.4f} | E: {res['E']:.4f}")
    return res

def main():
    model_path = root_dir / "weights" / "best.pt"
    if not model_path.exists():
        print(f"Missing fine-tuned YOLO model at {model_path}.")
        return
    yolo_model = YOLO(model_path)
    
    segmenter = ChakraTransformerSegmenter().to(DEVICE)
    weight_path = root_dir / "weights" / "chakra_transformer_best.pth"
    
    if not weight_path.exists():
        print(f"Weight not found: {weight_path}")
        return
        
    sd = torch.load(weight_path, map_location=DEVICE)
    sd = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
    segmenter.load_state_dict(sd, strict=True)
    segmenter.eval()
    
    metrics_engine = MetricsEngineV2()
    
    all_res = {}
    for name, (img_rel, msk_rel) in DATASETS.items():
        res = evaluate_dataset(segmenter, yolo_model, metrics_engine, name, img_rel, msk_rel)
        if res:
            all_res[name] = res
            
    out_file = root_dir / "results" / "final_5_datasets_eval.json"
    out_file.parent.mkdir(exist_ok=True)
    out_file.write_text(json.dumps(all_res, indent=2))
    print(f"\nSaved results to {out_file}")

if __name__ == "__main__":
    main()

