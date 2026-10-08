import sys
from pathlib import Path
import json
import numpy as np
import torch
import torch.nn as nn
import cv2

root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir / "src"))
from run_all_combos import ChakraNet

class ConformalEvaluator:
    """
    Evaluates the calibration and uncertainty of the Conformal Prediction module (C6).
    """
    
    @staticmethod
    def expected_calibration_error(predictions, targets, num_bins=10):
        """
        Calculates Expected Calibration Error (ECE) for binary classification.
        predictions: (N,) flat array of predicted probabilities [0, 1] for class 1.
        targets: (N,) flat array of binary ground truth labels {0, 1}.
        """
        predictions_binary = (predictions > 0.5).astype(float)
        confidences = np.maximum(predictions, 1.0 - predictions)
        accuracies = (predictions_binary == targets).astype(float)
        
        bin_boundaries = np.linspace(0.5, 1.0, num_bins + 1)
        bin_lowers = bin_boundaries[:-1]
        bin_uppers = bin_boundaries[1:]
        
        ece = 0.0
        
        for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
            if bin_lower == 0.5:
                in_bin = (confidences >= bin_lower) & (confidences <= bin_upper)
            else:
                in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
            
            prop_in_bin = np.mean(in_bin)
            
            if prop_in_bin > 0:
                empirical_prob = np.mean(accuracies[in_bin])
                avg_confidence_in_bin = np.mean(confidences[in_bin])
                
                ece += np.abs(avg_confidence_in_bin - empirical_prob) * prop_in_bin
                
        return ece

    @staticmethod
    def brier_score(predictions, targets):
        """
        Calculates the Brier Score (Mean Squared Error between probabilities and labels).
        Lower is better (0.0 is perfect).
        """
        return np.mean((predictions - targets) ** 2)

if __name__ == "__main__":
    print("Testing ConformalEvaluator on real Kvasir-SEG test data...")
    
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    images_dir = root_dir / "data" / "kvasir-seg" / "images"
    masks_dir = root_dir / "data" / "kvasir-seg" / "masks"
    
    if not images_dir.exists():
        print(f"[WARN] Kvasir-SEG not found at {images_dir}")
        sys.exit(0)
        
    image_paths = sorted([p for p in images_dir.glob("*.jpg")])
    n_test = max(1, int(0.2 * len(image_paths)))
    image_paths = image_paths[-n_test:]
    
    model = ChakraNet(channels=48, mc_dropout_p=0.0).to(DEVICE)
    weight_path = root_dir / "weights" / "combo1_best.pth"
    if weight_path.exists():
        sd = torch.load(weight_path, map_location=DEVICE)
        sd = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
        model.load_state_dict(sd, strict=False)
    model.eval()
    
    preds_list = []
    targets_list = []
    
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(DEVICE)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(DEVICE)
    
    with torch.no_grad():
        from torch.cuda.amp import autocast
        for img_path in image_paths:
            mask_path = masks_dir / img_path.name
            if not mask_path.exists():
                continue
                
            img = cv2.imread(str(img_path))
            msk = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            
            if img is None or msk is None:
                continue
                
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (448, 448), interpolation=cv2.INTER_LINEAR)
            msk = cv2.resize(msk, (448, 448), interpolation=cv2.INTER_NEAREST)
            
            t = torch.from_numpy(img).permute(2,0,1).unsqueeze(0).float().to(DEVICE) / 255.0
            t = (t - mean) / std
            
            with autocast():
                out = model(t)
                if isinstance(out, tuple): out = out[0]
                prob = torch.sigmoid(out).float().squeeze().cpu().numpy()
            
            gt = (msk > 127).astype(np.float32)
            
            preds_list.append(prob.flatten())
            targets_list.append(gt.flatten())
            
    preds = np.concatenate(preds_list)
    targets = np.concatenate(targets_list)
    
    ece = ConformalEvaluator.expected_calibration_error(preds, targets)
    bs = ConformalEvaluator.brier_score(preds, targets)
    
    print(f"ChakraNet - ECE: {ece:.4f}")
    print(f"ChakraNet - Brier Score: {bs:.4f}")
