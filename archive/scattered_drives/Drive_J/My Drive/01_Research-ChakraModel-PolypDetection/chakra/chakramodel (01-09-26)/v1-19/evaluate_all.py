import os
import cv2
import json
import torch
import numpy as np
from pathlib import Path
from tqdm import tqdm
from tabulate import tabulate
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.run_all_combos import ChakraNet
from src.pranet_segmenter import PraNetSegmenter
from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter
from ultralytics import YOLO
from metrics.seg_metrics import dice as binary_dice_coefficient, iou as binary_iou

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class ModelWrapper:
    def __init__(self, name, model_type, weight_path, img_size=448):
        self.name = name
        self.model_type = model_type
        self.weight_path = Path(weight_path)
        self.img_size = img_size
        self.model = None

    def load(self):
        if not self.weight_path.exists():
            print(f"[WARN] Weights not found for {self.name}: {self.weight_path}")
            return False
            
        print(f"Loading {self.name}...")
        try:
            if self.model_type == "chakranet":
                self.model = ChakraNet(channels=48).to(DEVICE)
                sd = torch.load(self.weight_path, map_location=DEVICE)
                sd = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
                self.model.load_state_dict(sd, strict=False)
                self.model.eval()
            elif self.model_type == "pranet":
                self.model = PraNetSegmenter(device=str(DEVICE))
                self.model.model.load_state_dict(torch.load(self.weight_path, map_location=DEVICE))
                self.model.model.eval()
            elif self.model_type == "transformer":
                self.model = ChakraTransformerSegmenter(pretrained=False).to(DEVICE)
                self.model.load_state_dict(torch.load(self.weight_path, map_location=DEVICE))
                self.model.eval()
                self.img_size = 384
            elif self.model_type == "yolo":
                self.model = YOLO(str(self.weight_path))
                self.img_size = 640
            return True
        except Exception as e:
            print(f"[ERROR] Failed to load {self.name}: {e}")
            return False

    def predict(self, img_path):
        img_np = cv2.imread(str(img_path))
        if img_np is None: return None
        orig_shape = img_np.shape[:2]
        
        if self.model_type == "yolo":
            results = self.model(str(img_path), verbose=False)
            res = results[0]
            mask = np.zeros(orig_shape, dtype=np.uint8)
            if res.masks is not None:
                for m in res.masks.data:
                    m = m.cpu().numpy()
                    m = cv2.resize(m, (orig_shape[1], orig_shape[0]), interpolation=cv2.INTER_NEAREST)
                    mask = np.logical_or(mask, m > 0.5).astype(np.uint8)
            return mask
        elif self.model_type == "pranet":
            pred, _, _, _ = self.model.segment_roi(img_np, threshold=0.45)
            if pred is not None:
                return cv2.resize(pred, (orig_shape[1], orig_shape[0]), interpolation=cv2.INTER_NEAREST) > 127
            return np.zeros(orig_shape, dtype=bool)
        else:
            img_resized = cv2.resize(img_np, (self.img_size, self.img_size))
            img_t = torch.from_numpy(img_resized).permute(2, 0, 1).float() / 255.0
            mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
            std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            img_t = (img_t - mean) / std
            img_t = img_t.unsqueeze(0).to(DEVICE)
            
            with torch.no_grad():
                out = self.model(img_t)
                if isinstance(out, tuple): out = out[0]
                prob = torch.sigmoid(out).cpu().numpy()[0, 0]
                
            pred = (prob > 0.5).astype(np.uint8)
            pred = cv2.resize(pred, (orig_shape[1], orig_shape[0]), interpolation=cv2.INTER_NEAREST)
            return pred

def evaluate_on_dataset(model_wrapper, dataset_path, num_samples=100):
    images_dir = dataset_path / "images"
    masks_dir = dataset_path / "masks"
    
    img_paths = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg"))
    if num_samples and len(img_paths) > num_samples:
        np.random.seed(42)
        img_paths = np.random.choice(img_paths, num_samples, replace=False)
        
    dices = []
    ious = []
    
    for img_path in tqdm(img_paths, desc=f"Eval {model_wrapper.name} on {dataset_path.name}"):
        mask_path = masks_dir / f"{img_path.stem}.png"
        if not mask_path.exists():
            mask_path = masks_dir / f"{img_path.stem}.jpg"
        
        if not mask_path.exists(): continue
            
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if gt_mask is None: continue
        gt_mask = (gt_mask > 127).astype(np.uint8)
        
        pred_mask = model_wrapper.predict(img_path)
        if pred_mask is None: continue
            
        dice = binary_dice_coefficient(pred_mask, gt_mask)
        iou = binary_iou(pred_mask, gt_mask)
        dices.append(dice)
        ious.append(iou)
        
    return np.mean(dices) if dices else 0, np.mean(ious) if ious else 0

def main():
    root = Path(__file__).resolve().parent
    models = [
        ModelWrapper("ChakraNet-Combo1", "chakranet", root/"weights"/"combo1_best.pth"),
        ModelWrapper("ChakraNet-Combo2", "chakranet", root/"weights"/"combo2_best.pth"),
        ModelWrapper("ChakraNet-Combo3", "chakranet", root/"weights"/"combo3_best.pth"),
        ModelWrapper("PraNet", "pranet", root/"weights"/"pranet_kvasir_best.pth"),
        ModelWrapper("ChakraTransformer", "transformer", root/"weights"/"chakra_transformer_vit_large_best (1).pth"),
        ModelWrapper("YOLOv8-Polyp", "yolo", root/"outputs"/"polyp_yolov8n"/"weights"/"best.pt"),
        ModelWrapper("YOLOv8-Base", "yolo", root/"best.pt"),
    ]
    
    datasets = [
        root/"data"/"cvc-clinicdb",
        root/"data"/"etis-larib"
    ]
    
    models = [m for m in models if m.weight_path.exists()]
    datasets = [d for d in datasets if d.exists()]
    
    results = {}
    
    for model in models:
        if not model.load(): continue
        
        model_res = {}
        for ds in datasets:
            dice, iou = evaluate_on_dataset(model, ds, num_samples=50) # Use 50 samples for speed
            model_res[ds.name] = {"dice": dice, "iou": iou}
            
        results[model.name] = model_res
        
    sota = {
        "PraNet-2020": {"dice": 0.898, "iou": 0.840},
        "Polyp-PVT-2023": {"dice": 0.917, "iou": 0.864},
        "SAM-2-Adapter-2024": {"dice": 0.931, "iou": 0.880}
    }
    
    report_path = root / "model_comparison_report.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Comprehensive Model Comparison Report\n\n")
        f.write("Evaluation of all ChakraModel variants against State-of-the-Art (SOTA) literature.\n\n")
        
        for ds in datasets:
            f.write(f"## Dataset: {ds.name} (Cross-Dataset / Zero-Shot)\n\n")
            table_data = []
            
            for m in models:
                if m.name in results and ds.name in results[m.name]:
                    r = results[m.name][ds.name]
                    table_data.append([m.name, f"{r['dice']:.4f}", f"{r['iou']:.4f}", "Local Model"])
                    
            for sname, sres in sota.items():
                table_data.append([sname, f"{sres['dice']:.4f}", f"{sres['iou']:.4f}", "Literature (SOTA)"])
                
            table_data.sort(key=lambda x: float(x[1]), reverse=True)
            
            headers = ["Model", "Mean Dice", "Mean IoU", "Source"]
            f.write(tabulate(table_data, headers=headers, tablefmt="github"))
            f.write("\n\n")
            
    print(f"\nEvaluation complete. Report generated at {report_path}")
    
if __name__ == "__main__":
    main()
