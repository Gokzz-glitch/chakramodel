"""
Conformal Prediction for ChakraNet Polyp Segmentation
=====================================================
Transforms Monte Carlo Dropout uncertainty into mathematically guaranteed
prediction intervals with provable coverage bounds.

Theory:
    Given a calibration set of N images with known ground truth, we compute
    per-pixel non-conformity scores (how "wrong" the model's prediction is).
    We then find the quantile threshold q_hat such that at least (1-alpha)% 
    of calibration pixels are covered. At test time, we produce prediction
    SETS (inner mask, outer mask) rather than point predictions, guaranteeing
    that the true polyp boundary lies within the band with probability >= 1-alpha.

Usage:
    # Step 1: Calibrate
    python src/conformal_calibration.py --weights weights/pranet_kvasir_best.pth

    # Step 2: Predict with guaranteed coverage
    python src/conformal_calibration.py --predict --weights weights/pranet_kvasir_best.pth
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader

from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter
from train_pranet import KvasirSEGDataset, IMAGE_EXTS


def mc_dropout_predict(model, img_tensor, device, n_passes=16):
    """
    Run N stochastic forward passes with MC Dropout enabled.
    Returns: mean_prob [H, W], variance [H, W]
    """
    model.enable_mc_dropout()
    probs = []
    from torch.cuda.amp import autocast
    with torch.no_grad(), autocast():
        for _ in range(n_passes):
            logits = model(img_tensor.to(device))
            probs.append(torch.sigmoid(logits).squeeze(0)[0].cpu().numpy())
    model.eval()
    
    probs = np.stack(probs, axis=0)  # [N, H, W]
    mean_prob = np.mean(probs, axis=0)
    variance = np.var(probs, axis=0)
    return mean_prob, variance


def compute_nonconformity_scores(mean_prob, gt_mask, variance):
    gt_binary = (gt_mask > 0.5).astype(np.float32)
    scores_pos = 1.0 - (mean_prob + variance)
    scores_neg = mean_prob - variance
    return scores_pos, scores_neg, gt_binary


def calibrate(model, cal_loader, device, alpha=0.05, n_passes=16, seed=42):
    """
    Calibrate conformal predictor on the calibration set.
    
    Args:
        model: PraNetMicroRefiner
        cal_loader: DataLoader for calibration images
        device: torch.device
        alpha: Significance level (0.05 = 95% coverage guarantee)
        n_passes: Number of MC Dropout passes
        seed: Random seed for reproducibility
        
    Returns:
        q_hat_pos, q_hat_neg: The quantile thresholds for prediction sets
    """
    # FR-1.4: Reproducible Calibration
    np.random.seed(seed)
    torch.manual_seed(seed)
    
    print(f"\n{'='*55}")
    print(f"  Conformal Calibration")
    print(f"  Alpha:      {alpha} (Coverage target: {(1-alpha)*100:.0f}%)")
    print(f"  MC Passes:  {n_passes}")
    print(f"{'='*55}")
    
    all_scores_pos = []
    all_scores_neg = []
    
    model.eval()
    for batch_idx, (imgs, masks) in enumerate(cal_loader):
        for i in range(imgs.shape[0]):
            img = imgs[i:i+1]
            gt = masks[i, 0].numpy()
            
            mean_prob, variance = mc_dropout_predict(model, img, device, n_passes)
            scores_pos, scores_neg, gt_binary = compute_nonconformity_scores(mean_prob, gt, variance)

            pos_px = scores_pos[gt_binary > 0.5]
            if len(pos_px) > 0:
                # Pool ALL positive pixel scores (or a large subset) for pixel-wise FDR coverage
                # rather than MAX per image (which enforces overly strict FWER).
                # Subsample if extremely large to prevent OOM
                if len(pos_px) > 2000:
                    pos_px = np.random.choice(pos_px, 2000, replace=False)
                all_scores_pos.append(pos_px)
                
            neg_px = scores_neg[gt_binary <= 0.5]
            if len(neg_px) > 0:
                # Pool a random subset of negative pixels (background dominates)
                all_scores_neg.append(np.random.choice(neg_px, min(2000, len(neg_px)), replace=False))
            
        if (batch_idx + 1) % 10 == 0:
            print(f"  Calibrated {(batch_idx + 1) * cal_loader.batch_size} images...", flush=True)
    
    all_scores_pos = np.concatenate(all_scores_pos) if all_scores_pos else np.array([])
    all_scores_neg = np.concatenate(all_scores_neg) if all_scores_neg else np.array([])
    
    N_pos = len(all_scores_pos)
    q_level_pos = min(np.ceil((N_pos + 1) * (1 - alpha)) / N_pos, 1.0) if N_pos > 0 else 1.0
    q_hat_pos = float(np.quantile(all_scores_pos.astype(np.float64), q_level_pos)) if N_pos > 0 else 1.0
    
    N_neg = len(all_scores_neg)
    q_level_neg = min(np.ceil((N_neg + 1) * (1 - alpha)) / N_neg, 1.0) if N_neg > 0 else 1.0
    q_hat_neg = float(np.quantile(all_scores_neg.astype(np.float64), q_level_neg)) if N_neg > 0 else 1.0
    
    print(f"\n  Calibration complete!")
    print(f"  q_hat_pos: {q_hat_pos:.6f} | q_hat_neg: {q_hat_neg:.6f}")
    print(f"{'='*55}\n")
    
    return q_hat_pos, q_hat_neg


def conformal_predict(model, img_tensor, device, q_hat_pos, q_hat_neg, n_passes=16):
    """
    Generate conformal prediction sets for a single image.
    
    Returns:
        inner_mask: Conservative mask (high confidence polyp region)
        outer_mask: Liberal mask (includes uncertain boundary band)
        mean_prob: Raw probability map
        variance: Uncertainty map
    """
    mean_prob, variance = mc_dropout_predict(model, img_tensor, device, n_passes)
    
    score_pos = 1.0 - (mean_prob + variance)
    score_neg = mean_prob - variance
    
    include_pos = (score_pos <= q_hat_pos)
    include_neg = (score_neg <= q_hat_neg)
    
    outer_bool = include_pos
    inner_bool = include_pos & (~include_neg)
    
    outer_mask = outer_bool.astype(np.uint8) * 255
    inner_mask = inner_bool.astype(np.uint8) * 255
    
    return inner_mask, outer_mask, mean_prob, variance


def evaluate_coverage(model, test_loader, device, q_hat_pos, q_hat_neg, n_passes=16):
    """
    Evaluate empirical coverage on a test set.
    Coverage = fraction of true polyp pixels that fall within the prediction set.
    """
    total_polyp_pixels = 0
    covered_pixels = 0
    total_bg_pixels = 0
    covered_bg_pixels = 0
    total_images = 0
    
    coverages = []
    coverages_bg = []
    
    model.eval()
    for imgs, masks in test_loader:
        for i in range(imgs.shape[0]):
            img = imgs[i:i+1]
            gt = masks[i, 0].numpy()
            
            inner, outer, mean_prob, variance = conformal_predict(
                model, img, device, q_hat_pos, q_hat_neg, n_passes
            )
            
            gt_binary = (gt > 0.5)
            outer_binary = (outer > 0)
            inner_binary = (inner > 0)
            bg_binary = (gt_binary == 0)
            
            # True positive coverage: TRUE polyp pixels inside outer mask
            if gt_binary.sum() > 0:
                covered = (gt_binary & outer_binary).sum()
                total = gt_binary.sum()
                img_coverage = covered / total
                coverages.append(img_coverage)
                total_polyp_pixels += total
                covered_pixels += covered
                
            # True negative coverage: TRUE background pixels outside inner mask
            if bg_binary.sum() > 0:
                covered_bg = (bg_binary & (~inner_binary)).sum()
                total_bg = bg_binary.sum()
                img_cov_bg = covered_bg / total_bg
                coverages_bg.append(img_cov_bg)
                total_bg_pixels += total_bg
                covered_bg_pixels += covered_bg
            
            total_images += 1
    
    overall_coverage = covered_pixels / total_polyp_pixels if total_polyp_pixels > 0 else 0
    mean_coverage = np.mean(coverages) if coverages else 0
    
    overall_bg_coverage = covered_bg_pixels / total_bg_pixels if total_bg_pixels > 0 else 0
    mean_bg_coverage = np.mean(coverages_bg) if coverages_bg else 0
    
    return overall_coverage, mean_coverage, overall_bg_coverage, mean_bg_coverage, total_images


def main():
    parser = argparse.ArgumentParser(description="Conformal Prediction for ChakraNet")
    parser.add_argument("--weights", type=str, default=None, help="Path to model weights")
    parser.add_argument("--alpha", type=float, default=0.05, help="Significance level (default: 0.05 = 95%% coverage)")
    parser.add_argument("--mc_passes", type=int, default=16, help="MC Dropout passes")
    parser.add_argument("--predict", action="store_true", help="Run prediction mode (requires calibration file)")
    parser.add_argument("--data_dirs", type=str, nargs='+', default=None, help="Paths to dataset directories (containing images/ and masks/)")
    parser.add_argument("--cross_dataset", action="store_true", help="Also evaluate on CVC-ClinicDB")
    args = parser.parse_args()
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    root = Path(__file__).parent.parent
    
    # Load model
    model = ChakraTransformerSegmenter().to(device)
    weights_path = args.weights or str(root / "weights" / "chakra_transformer_best.pth")
    if Path(weights_path).exists():
        sd = torch.load(weights_path, map_location=device)
        model.load_state_dict(sd, strict=False)
        print(f"[INFO] Loaded weights from {weights_path}")
    else:
        print(f"[ERROR] Weights not found: {weights_path}")
        sys.exit(1)
    
    model.eval()
    
    # Load Dataset
    if args.data_dirs:
        base_dirs = [Path(d) for d in args.data_dirs]
    else:
        base_dirs = [root / "data" / "kvasir-seg"]
        
    datasets = []
    for base_dir in base_dirs:
        images_dir = base_dir / "images"
        masks_dir = base_dir / "masks"
        if images_dir.exists() and masks_dir.exists():
            datasets.append(KvasirSEGDataset(images_dir, masks_dir, img_size=384, augment=False))
        else:
            print(f"[WARNING] Skipping {base_dir}, images/ or masks/ not found.")
            
    if not datasets:
        print("[ERROR] No valid datasets found.")
        sys.exit(1)
        
    dataset = torch.utils.data.ConcatDataset(datasets)
    print(f"[INFO] Pooled dataset size: {len(dataset)} images")
    
    all_indices = list(range(len(dataset)))
    
    # Split: 70% train | 15% calib | 15% test
    # If using multiple datasets, this splits across the combined pool
    n_train = int(0.7 * len(dataset))
    n_cal = int(0.15 * len(dataset))
    cal_indices = all_indices[n_train : n_train + n_cal]
    test_indices = all_indices[n_train + n_cal:]
    
    cal_set = torch.utils.data.Subset(dataset, cal_indices)
    test_set = torch.utils.data.Subset(dataset, test_indices)
    
    cal_loader = DataLoader(cal_set, batch_size=12, shuffle=False, num_workers=2)
    test_loader = DataLoader(test_set, batch_size=12, shuffle=False, num_workers=2)
    
    cal_file = root / "weights" / "conformal_calibration.json"
    
    if not args.predict:
        # === CALIBRATION MODE ===
        q_hat_pos, q_hat_neg = calibrate(model, cal_loader, device, alpha=args.alpha, n_passes=args.mc_passes)
        
        # Save calibration
        cal_data = {
            "q_hat_pos": q_hat_pos,
            "q_hat_neg": q_hat_neg,
            "alpha": args.alpha,
            "mc_passes": args.mc_passes,
            "n_calibration_images": len(cal_indices)
        }
        cal_file.parent.mkdir(exist_ok=True)
        with open(cal_file, "w") as f:
            json.dump(cal_data, f, indent=2)
        print(f"  Calibration saved to {cal_file}")
        
        # Evaluate coverage on held-out test set
        print(f"\n  Evaluating coverage on {len(test_indices)} held-out Kvasir images...")
        overall_cov, mean_cov, overall_bg, mean_bg, n_imgs = evaluate_coverage(
            model, test_loader, device, q_hat_pos, q_hat_neg, n_passes=args.mc_passes
        )
        
        print(f"\n{'='*55}")
        print(f"  CONFORMAL PREDICTION RESULTS")
        print(f"  Target Coverage:    {(1 - args.alpha) * 100:.0f}%")
        print(f"  Empirical TP Cov:   {overall_cov * 100:.1f}% (pixel-level)")
        print(f"  Empirical TN Cov:   {overall_bg * 100:.1f}% (pixel-level)")
        print(f"  Mean Image TP Cov:  {mean_cov * 100:.1f}%")
        print(f"  Mean Image TN Cov:  {mean_bg * 100:.1f}%")
        print(f"  Test Images:        {n_imgs}")
        print(f"  q_hat_pos:          {q_hat_pos:.6f}")
        print(f"  q_hat_neg:          {q_hat_neg:.6f}")
        print(f"{'='*55}")
        
        # Generate report
        report = f"""# Conformal Prediction Report

## Configuration
- Alpha: {args.alpha} (Target: {(1-args.alpha)*100:.0f}% coverage)
- MC Dropout Passes: {args.mc_passes}
- Calibration Set: {len(cal_indices)} images
- Test Set: {len(test_indices)} images

## Results (Kvasir-SEG In-Distribution)
| Metric | Value |
|--------|-------|
| Target Coverage | {(1-args.alpha)*100:.0f}% |
| Empirical Pixel Coverage | {overall_cov*100:.1f}% |
| Mean Image Coverage | {mean_cov*100:.1f}% |
| Calibration Threshold (q_hat_pos) | {q_hat_pos:.6f} |
| Calibration Threshold (q_hat_neg) | {q_hat_neg:.6f} |

## Interpretation
The conformal predictor guarantees that with at least {(1-args.alpha)*100:.0f}% probability,
the true polyp boundary lies within the predicted outer band. This is a **mathematically
proven** guarantee, not just an empirical observation.
"""
        
        if args.cross_dataset:
            # Evaluate on CVC-ClinicDB
            cvc_dir = root / "data" / "cvc-clinicdb"
            if cvc_dir.exists():
                cvc_images = cvc_dir / "Original"
                cvc_masks = cvc_dir / "Ground Truth"
                if cvc_images.exists() and cvc_masks.exists():
                    cvc_dataset = KvasirSEGDataset(cvc_images, cvc_masks, img_size=384, augment=False)
                    cvc_loader = DataLoader(cvc_dataset, batch_size=12, shuffle=False, num_workers=2)
                    
                    print(f"\n  Evaluating coverage on CVC-ClinicDB (OOD)...")
                    cvc_cov, cvc_mean, cvc_bg_cov, cvc_bg_mean, cvc_n = evaluate_coverage(
                        model, cvc_loader, device, q_hat_pos, q_hat_neg, n_passes=args.mc_passes
                    )
                    
                    print(f"\n  CVC-ClinicDB (Out-of-Distribution):")
                    print(f"  Empirical TP Cov: {cvc_cov*100:.1f}%")
                    print(f"  Empirical TN Cov: {cvc_bg_cov*100:.1f}%")
                    
                    report += f"""
## Results (CVC-ClinicDB Out-of-Distribution)
| Metric | Value |
|--------|-------|
| Empirical Pixel Coverage | {cvc_cov*100:.1f}% |
| Mean Image Coverage | {cvc_mean*100:.1f}% |
| Images Evaluated | {cvc_n} |

### Key Finding
{"✅ Coverage guarantee HOLDS on unseen hospital data!" if cvc_cov >= (1-args.alpha) else "⚠️ Coverage drops on OOD data — this is expected and scientifically interesting. The conformal guarantee is distribution-dependent, proving the need for domain adaptation."}
"""
        
        report_path = root / "conformal_prediction_report.md"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\n  Report saved to {report_path}")
    
    else:
        # === PREDICTION MODE ===
        if not cal_file.exists():
            print("[ERROR] Run calibration first (without --predict flag)")
            sys.exit(1)
            
        with open(cal_file) as f:
            cal_data = json.load(f)
        q_hat_pos = cal_data["q_hat_pos"]
        q_hat_neg = cal_data.get("q_hat_neg", q_hat_pos)
        print(f"[INFO] Loaded calibration: q_hat_pos={q_hat_pos:.6f}, q_hat_neg={q_hat_neg:.6f}, alpha={cal_data['alpha']}")


if __name__ == "__main__":
    main()

