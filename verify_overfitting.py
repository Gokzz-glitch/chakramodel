import os
import cv2
import json
import torch
import numpy as np
from pathlib import Path
from tabulate import tabulate
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "chakra_transformer"))

from src.run_all_combos import ChakraNet
from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter
from metrics.seg_metrics import dice as binary_dice_coefficient

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
            return False
        try:
            if self.model_type == "chakranet":
                self.model = ChakraNet(channels=48).to(DEVICE)
                sd = torch.load(self.weight_path, map_location=DEVICE)
                sd = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
                self.model.load_state_dict(sd, strict=False)
                self.model.eval()
            elif self.model_type == "transformer":
                self.model = ChakraTransformerSegmenter(pretrained=False).to(DEVICE)
                self.model.load_state_dict(torch.load(self.weight_path, map_location=DEVICE))
                self.model.eval()
                self.img_size = 384
            return True
        except Exception as e:
            print(f"Error loading {self.name}: {e}")
            return False

    def predict(self, img_path):
        img_np = cv2.imread(str(img_path))
        if img_np is None: return None
        orig_shape = img_np.shape[:2]
        
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

def evaluate_on_dataset(model_wrapper, dataset_path, num_samples=30):
    images_dir = dataset_path / "images"
    masks_dir = dataset_path / "masks"
    
    img_paths = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg"))
    if num_samples and len(img_paths) > num_samples:
        np.random.seed(42)
        img_paths = np.random.choice(img_paths, num_samples, replace=False)
        
    dices = []
    
    for img_path in img_paths:
        mask_path = masks_dir / f"{img_path.stem}.png"
        if not mask_path.exists(): mask_path = masks_dir / f"{img_path.stem}.jpg"
        if not mask_path.exists(): continue
            
        gt_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if gt_mask is None: continue
        gt_mask = (gt_mask > 127).astype(np.uint8)
        
        pred_mask = model_wrapper.predict(img_path)
        if pred_mask is None: continue
            
        dice = binary_dice_coefficient(pred_mask, gt_mask)
        dices.append(dice)
        
    return np.mean(dices) if dices else 0

def main():
    root = Path(__file__).resolve().parent
    models = [
        ModelWrapper("ChakraTransformer", "transformer", root/"chakra_transformer_vit_large_best (1).pth"),
        ModelWrapper("ChakraNet-Combo1", "chakranet", root/"weights"/"combo1_best.pth"),
        ModelWrapper("ChakraNet-Combo2", "chakranet", root/"weights"/"combo2_best.pth"),
        ModelWrapper("ChakraNet-Combo3", "chakranet", root/"weights"/"combo3_best.pth")
    ]
    
    # We test on Kvasir-SEG (in-distribution) vs Unseen datasets (out-of-distribution)
    datasets = {
        "In-Distribution": [root/"data"/"kvasir-seg"],
        "Out-of-Distribution": [
            root/"data"/"cvc-clinicdb",
            root/"data"/"etis-larib",
            root/"data"/"cvc-colondb",
            root/"data"/"cvc-300"
        ]
    }
    
    models = [m for m in models if m.load()]
    
    table_data = []
    
    for model in models:
        print(f"Testing {model.name}...")
        
        # Test In-Distribution (Training dataset)
        in_dist_dice = 0
        if datasets["In-Distribution"][0].exists():
            in_dist_dice = evaluate_on_dataset(model, datasets["In-Distribution"][0], num_samples=100)
            
        # Test Out-of-Distribution
        out_dist_dices = []
        for ds in datasets["Out-of-Distribution"]:
            if ds.exists():
                out_dist_dices.append(evaluate_on_dataset(model, ds, num_samples=30))
                
        out_dist_avg = np.mean(out_dist_dices) if out_dist_dices else 0
        
        # Generalization Gap (Lower is better, meaning it didn't overfit to Kvasir-SEG)
        gap = in_dist_dice - out_dist_avg
        
        status = "Healthy" if gap < 0.15 else "Slight Overfitting" if gap < 0.25 else "Severe Overfitting"
        
        table_data.append([
            model.name,
            f"{in_dist_dice:.4f}",
            f"{out_dist_avg:.4f}",
            f"{gap:.4f}",
            status
        ])
        
    print("\n# Overfitting Analysis Report\n")
    headers = ["Model", "Train/In-Dist Dice", "Test/Out-Dist Dice", "Generalization Gap", "Overfitting Status"]
    report = tabulate(table_data, headers=headers, tablefmt="github")
    print(report)
    
    with open("overfitting_report.md", "w") as f:
        f.write("# Overfitting Analysis Report\n\n")
        f.write(report)
        f.write("\n\n*Note: Generalization Gap = In-Dist Dice - Out-Dist Dice. A smaller gap indicates the model generalizes well and is not overfitted to the training set.*")

if __name__ == "__main__":
    main()
