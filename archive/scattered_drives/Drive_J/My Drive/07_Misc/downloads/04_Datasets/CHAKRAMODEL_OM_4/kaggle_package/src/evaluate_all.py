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
from utils.transforms import letterbox_pad, unletterbox

USE_GT_BBOX = False

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DATASETS = {
    "kvasir-seg":  ("data/kvasir-seg/images",  "data/kvasir-seg/masks"),
    "cvc-clinicdb": ("data/cvc-clinicdb/images", "data/cvc-clinicdb/masks"),
    "cvc-colondb": ("data/cvc-colondb/images", "data/cvc-colondb/masks"),
    "cvc-300": ("data/cvc-300/images", "data/cvc-300/masks"),
    "etis-larib": ("data/etis-larib/images", "data/etis-larib/masks")
}

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
            
        orig_h, orig_w = gt_mask.shape[:2]
        eval_size = (384, 384)
        img_resized = cv2.resize(img_bgr, eval_size)
        gt_bin = (gt_mask > 127).astype(np.uint8)
        if gt_bin.ndim == 3:
            gt_bin = gt_bin.squeeze(-1)
        
        if USE_GT_BBOX:
            y_indices, x_indices = np.where(gt_bin > 0)
            if len(y_indices) > 0:
                # Get GT box in original coordinates
                orig_x1, orig_x2 = np.min(x_indices), np.max(x_indices)
                orig_y1, orig_y2 = np.min(y_indices), np.max(y_indices)
                
                orig_w_box, orig_h_box = orig_x2 - orig_x1, orig_y2 - orig_y1
                orig_px, orig_py = int(0.25 * orig_w_box), int(0.25 * orig_h_box)
                
                orig_px1 = max(0, orig_x1 - orig_px)
                orig_py1 = max(0, orig_y1 - orig_py)
                orig_px2 = min(orig_w, orig_x2 + orig_px)
                orig_py2 = min(orig_h, orig_y2 + orig_py)
                
                boxes = [[orig_px1, orig_py1, orig_px2, orig_py2]]
            else:
                boxes = []
        else:
            yolo_results = yolo_model(img_resized, verbose=False)[0]
            boxes = []
            if len(yolo_results.boxes) > 0:
                for box_data in yolo_results.boxes:
                    box = box_data.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = map(int, box)
                    
                    w, h = x2 - x1, y2 - y1
                    px, py = int(0.25 * w), int(0.25 * h)
                    px1, py1 = max(0, x1 - px), max(0, y1 - py)
                    px2, py2 = min(eval_size[0], x2 + px), min(eval_size[1], y2 + py)
                    
                    scale_x = orig_w / eval_size[0]
                    scale_y = orig_h / eval_size[1]

                    orig_px1 = max(0, int(px1 * scale_x))
                    orig_py1 = max(0, int(py1 * scale_y))
                    orig_px2 = min(orig_w, int(px2 * scale_x))
                    orig_py2 = min(orig_h, int(py2 * scale_y))
                    
                    boxes.append([orig_px1, orig_py1, orig_px2, orig_py2])
        
        c_mask = np.zeros((orig_h, orig_w), dtype=np.uint8)
        
        if len(boxes) > 0:
            for b in boxes:
                orig_px1, orig_py1, orig_px2, orig_py2 = b
                
                if orig_px2 > orig_px1 and orig_py2 > orig_py1:
                    roi_crop = img_bgr[orig_py1:orig_py2, orig_px1:orig_px2]
                    
                    # Use letterbox padding as in training
                    roi_crop_resized, meta = letterbox_pad(roi_crop, target_size=(384, 384))
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
                    
                    # Reverse letterbox padding
                    seg_roi_mask_resized = unletterbox(seg_roi_mask, meta)
                    c_mask[orig_py1:orig_py2, orig_px1:orig_px2] = np.maximum(c_mask[orig_py1:orig_py2, orig_px1:orig_px2], seg_roi_mask_resized)
        
        c_bin = (c_mask > 127).astype(np.uint8)
        
        # Compute metrics using proper engine
        if c_bin.shape != gt_bin.shape:
            print(f"Shape mismatch! c_bin: {c_bin.shape}, gt_bin: {gt_bin.shape}, orig_h: {orig_h}, orig_w: {orig_w}")
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
    
    segmenter = ChakraTransformerSegmenter(pretrained=False).to(DEVICE)
    weight_path = root_dir / "weights" / "chakra_transformer_best.pth"
    
    if not weight_path.exists():
        print(f"Weight not found: {weight_path}")
        return
        
    sd = torch.load(weight_path, map_location=DEVICE)
    sd = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in sd.items()}
    
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

