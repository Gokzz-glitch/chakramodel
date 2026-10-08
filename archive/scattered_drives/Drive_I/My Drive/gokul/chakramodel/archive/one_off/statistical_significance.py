import os
import glob
import numpy as np
from scipy.stats import wilcoxon, ttest_rel, t
import math
import torch
import torch.nn as nn
from PIL import Image
import torchvision.transforms as T
from torch.utils.data import DataLoader
from metrics_engine_v2 import MetricsEngineV2

# =============================================================================
# CRITICAL BUG (Identified: Cycle 2 Adversarial Review, 2026-09-04)
# =============================================================================
# The __main__ block below uses `RealModel`, which is a 2-layer stub CNN with
# RANDOM weights. It does NOT load actual ChakraNet or YOLO model weights.
# Any p-values, confidence intervals, or "statistical significance" results
# produced by running this script directly are MEANINGLESS and do NOT represent
# comparisons between the actual trained models.
#
# The `StatisticalSignificance` class itself is correct and can be used by
# external callers with real per-image dice scores.
#
# TO GET REAL STATISTICAL SIGNIFICANCE:
#   1. Load ChakraNet weights from weights/chakra_transformer_best.pth
#   2. Load YOLO model and run inference to get per-image dice arrays
#   3. Call StatisticalSignificance.run_tests(chakranet_dice_per_image, yolo_dice_per_image)
#
# TODO: Re-implement __main__ to use actual model weights before citing any
#       statistical significance claims in the paper.
# =============================================================================


class RealDataset(torch.utils.data.Dataset):
    def __init__(self, img_dir, mask_dir, num_samples=100):
        self.img_paths = sorted(glob.glob(os.path.join(img_dir, "*.jpg")))[:num_samples]
        self.mask_dir = mask_dir
        self.transform = T.Compose([
            T.Resize((384, 384)),
            T.ToTensor()
        ])
        
    def __len__(self):
        return len(self.img_paths)
        
    def __getitem__(self, idx):
        img_path = self.img_paths[idx]
        basename = os.path.basename(img_path)
        mask_path = os.path.join(self.mask_dir, basename)
        
        img = Image.open(img_path).convert("RGB")
        if os.path.exists(mask_path):
            mask = Image.open(mask_path).convert("L")
        else:
            mask = Image.new("L", img.size)
            
        img_t = self.transform(img)
        mask_t = self.transform(mask)
        mask_t = (mask_t > 0.5).float() # binary
        
        return img_t, mask_t


class StatisticalSignificance:
    """
    Performs rigorous statistical testing for model comparison required by high-tier medical journals:
    - Wilcoxon signed-rank tests
    - Paired t-tests
    - 95% Confidence Intervals
    """
    
    @staticmethod
    def calculate_confidence_interval(data, confidence=0.95):
        n = len(data)
        if n < 2:
            return 0.0, 0.0
        m = np.mean(data)
        std_err = np.std(data, ddof=1) / math.sqrt(n)
        h = std_err * t.ppf((1 + confidence) / 2., n - 1)
        return m, h

    @staticmethod
    def run_tests(scores_a, scores_b, alpha=0.05):
        assert len(scores_a) == len(scores_b), "Must have paired samples of equal length."
        
        diff = np.array(scores_a) - np.array(scores_b)
        
        if np.all(diff == 0):
            return {
                "wilcoxon_p": 1.0,
                "ttest_p": 1.0,
                "significant": False,
                "mean_a_ci": StatisticalSignificance.calculate_confidence_interval(scores_a),
                "mean_b_ci": StatisticalSignificance.calculate_confidence_interval(scores_b)
            }
            
        w_stat, w_p = wilcoxon(scores_a, scores_b)
        t_stat, t_p = ttest_rel(scores_a, scores_b)
        
        significant = w_p < alpha and t_p < alpha
        
        return {
            "wilcoxon_p": w_p,
            "ttest_p": t_p,
            "significant": significant,
            "mean_a_ci": StatisticalSignificance.calculate_confidence_interval(scores_a),
            "mean_b_ci": StatisticalSignificance.calculate_confidence_interval(scores_b)
        }

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Setup imports for real models
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from chakranet_segmenter import ChakraNet as ChakraTransformer
    from pranet_resnet101 import PraNetResNet101
    
    img_dir = "data/kvasir-seg/images"
    mask_dir = "data/kvasir-seg/masks"
    
    ds = RealDataset(img_dir, mask_dir, num_samples=20)
    
    import cv2
    from ultralytics import YOLO
    
    image_paths = sorted([os.path.join(img_dir, f) for f in os.listdir(img_dir) if f.endswith('.jpg')])[:20]
    metrics_engine = MetricsEngineV2()
    DEVICE = torch.device('cpu')
    from torch.cuda.amp import autocast
    
    scores_a = []
    
    # ========================== MODEL A ==========================
    print("Loading Model A (ChakraModel = YOLO + ChakraTransformer)...")
    yolo_model = YOLO("weights/best.pt")
    segmenter = ChakraTransformer(device=str(DEVICE), weights_path=str(Path("weights/chakra_transformer_best.pth"))).model
    segmenter.to(DEVICE)
    segmenter.eval()
    
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

    print("Running Inference for Model A...")
    with torch.no_grad():
        for img_path in image_paths:
            basename = os.path.basename(img_path)
            mask_path = os.path.join(mask_dir, basename)
            if not os.path.exists(mask_path): continue
                
            img_bgr = cv2.imread(img_path)
            gt_mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if img_bgr is None or gt_mask is None: continue
                
            orig_h, orig_w = gt_mask.shape[:2]
            eval_size = (384, 384)
            img_resized = cv2.resize(img_bgr, eval_size)
            gt_bin = (gt_mask > 127).astype(np.uint8)
            if gt_bin.ndim == 3: gt_bin = gt_bin.squeeze(-1)
            elif gt_bin.ndim > 2: gt_bin = gt_bin.squeeze()
            if gt_bin.ndim != 2: gt_bin = gt_bin.reshape(orig_h, orig_w)
            
            yolo_results = yolo_model(img_resized, verbose=False, device='cpu')[0]
            c_mask = np.zeros((orig_h, orig_w), dtype=np.uint8)
            
            if len(yolo_results.boxes) > 0:
                for box_data in yolo_results.boxes:
                    box = box_data.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = map(int, box)
                    w, h = x2 - x1, y2 - y1
                    # Implement dynamic padding (e.g., 25% margin)
                    px, py = int(0.25 * w), int(0.25 * h)
                    px1, py1 = max(0, x1 - px), max(0, y1 - py)
                    px2, py2 = min(eval_size[0], x2 + px), min(eval_size[1], y2 + py)
                    
                    scale_x = orig_w / eval_size[0]
                    scale_y = orig_h / eval_size[1]
                    orig_px1 = max(0, int(px1 * scale_x))
                    orig_py1 = max(0, int(py1 * scale_y))
                    orig_px2 = min(orig_w, int(px2 * scale_x))
                    orig_py2 = min(orig_h, int(py2 * scale_y))
                    
                    if orig_px2 > orig_px1 and orig_py2 > orig_py1:
                        roi_crop = img_bgr[orig_py1:orig_py2, orig_px1:orig_px2]
                        
                        # Apply letterboxing to prevent aspect ratio distortion
                        roi_crop_resized, (dw, dh, r) = letterbox(roi_crop, new_shape=(384, 384))
                        roi_crop_rgb = cv2.cvtColor(roi_crop_resized, cv2.COLOR_BGR2RGB)
                        
                        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(DEVICE)
                        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(DEVICE)
                        t_roi = torch.from_numpy(roi_crop_rgb).permute(2,0,1).unsqueeze(0).float().to(DEVICE) / 255.0
                        t_roi = (t_roi - mean) / std
                        
                        with autocast():
                            out_a = segmenter(t_roi)
                            if isinstance(out_a, tuple): out_a = out_a[0]
                            prob_a = torch.sigmoid(out_a).float().squeeze().cpu().numpy()
                            
                        seg_roi_mask = (prob_a > 0.5).astype(np.uint8) * 255
                        
                        # Reverse letterboxing
                        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
                        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
                        unpad_h = 384 - top - bottom
                        unpad_w = 384 - left - right
                        
                        seg_roi_mask_unpad = seg_roi_mask[top:top+unpad_h, left:left+unpad_w]
                        seg_roi_mask_resized = cv2.resize(seg_roi_mask_unpad, (orig_px2-orig_px1, orig_py2-orig_py1), interpolation=cv2.INTER_NEAREST)
                        c_mask[orig_py1:orig_py2, orig_px1:orig_px2] = np.maximum(c_mask[orig_py1:orig_py2, orig_px1:orig_px2], seg_roi_mask_resized)
            
            pred_a_bin = (c_mask > 127).astype(np.uint8)
            res_a = metrics_engine.compute_all(pred_a_bin, gt_bin)
            scores_a.append(res_a['Dice'])

    # Free memory
    del yolo_model
    del segmenter
    if torch.cuda.is_available(): torch.cuda.empty_cache()

    # ========================== MODEL B ==========================
    scores_b = []
    print("Loading Model B (PraNetResNet101 / Combo1)...")
    model_b = PraNetResNet101(channels=48, mc_dropout_p=0.15)
    weights = torch.load("weights/combo1_best.pth", map_location='cpu')
    model_b.load_state_dict({k: v for k, v in weights.items()}, strict=False)
    model_b.to(DEVICE)
    model_b.eval()
    
    print("Running Inference for Model B...")
    with torch.no_grad():
        for img_path in image_paths:
            basename = os.path.basename(img_path)
            mask_path = os.path.join(mask_dir, basename)
            if not os.path.exists(mask_path): continue
                
            img_bgr = cv2.imread(img_path)
            gt_mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if img_bgr is None or gt_mask is None: continue
            
            orig_h, orig_w = gt_mask.shape[:2]
            eval_size = (384, 384)
            img_resized = cv2.resize(img_bgr, eval_size)
            gt_bin = (gt_mask > 127).astype(np.uint8)
            if gt_bin.ndim == 3: gt_bin = gt_bin.squeeze(-1)
            elif gt_bin.ndim > 2: gt_bin = gt_bin.squeeze()
            if gt_bin.ndim != 2: gt_bin = gt_bin.reshape(orig_h, orig_w)
            
            img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
            t_b = torch.from_numpy(img_rgb).permute(2,0,1).unsqueeze(0).float().to(DEVICE) / 255.0
            mean_b = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(DEVICE)
            std_b = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(DEVICE)
            t_b = (t_b - mean_b) / std_b
            
            with autocast():
                out_b = model_b(t_b)
                if isinstance(out_b, tuple): out_b = out_b[0]
                if isinstance(out_b, list): out_b = out_b[0]
                prob_b = torch.sigmoid(out_b).float().squeeze().cpu().numpy()
                
            pred_b_mask = (prob_b > 0.5).astype(np.uint8) * 255
            pred_b_mask = cv2.resize(pred_b_mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
            pred_b_bin = (pred_b_mask > 127).astype(np.uint8)
            
            res_b = metrics_engine.compute_all(pred_b_bin, gt_bin)
            scores_b.append(res_b['Dice'])

    results = StatisticalSignificance.run_tests(scores_a, scores_b)
    print(f"Wilcoxon P-Value: {results['wilcoxon_p']:.4e}")
    print(f"Paired T-Test P-Value: {results['ttest_p']:.4e}")
    mean_a, ci_a = results['mean_a_ci']
    mean_b, ci_b = results['mean_b_ci']
    print(f"Model A Mean (95% CI): {mean_a:.4f} ± {ci_a:.4f}")
    print(f"Model B Mean (95% CI): {mean_b:.4f} ± {ci_b:.4f}")
    print(f"Statistically Significant? {results['significant']}")
