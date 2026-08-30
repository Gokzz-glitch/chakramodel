"""
ChakraNet Paper Figure Generator
================================
Generates publication-quality figures for the paper:
  Fig 1: Architecture diagram (manual — use draw.io)
  Fig 2: Qualitative results with uncertainty + conformal bands
  Fig 3: Cross-dataset comparison bar chart
  Fig 4: Conformal coverage calibration curve
  Fig 5: Failure cases with high uncertainty
  Fig 6: Topological correctness comparison

Usage:
    python src/generate_paper_figures.py --weights weights/pranet_kvasir_best.pth
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

sys.path.insert(0, str(Path(__file__).parent))
from pranet_segmenter import PraNetMicroRefiner

# Publication style settings
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
})


def load_model(weights_path, device):
    model = PraNetMicroRefiner(channels=24).to(device)
    model.load_state_dict(torch.load(weights_path, map_location=device))
    model.eval()
    return model


def mc_dropout_inference(model, img_tensor, device, n_passes=16):
    """Run MC Dropout for uncertainty estimation."""
    model.enable_mc_dropout()
    probs = []
    with torch.no_grad():
        for _ in range(n_passes):
            logits = model(img_tensor.to(device))
            probs.append(torch.sigmoid(logits).squeeze().cpu().numpy())
    model.mc_dropout = False
    
    probs = np.stack(probs, axis=0)
    mean_prob = np.mean(probs, axis=0)
    variance = np.var(probs, axis=0)
    return mean_prob, variance


def preprocess_image(img_bgr, img_size=352):
    """Preprocess image for model input."""
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (img_size, img_size))
    tensor = torch.from_numpy(resized).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
    tensor = (tensor - mean) / std
    return tensor, rgb, resized


def generate_fig2_qualitative(model, device, data_dir, output_dir, n_samples=4):
    """
    Fig 2: The HERO figure of the paper.
    Shows: Original → Prediction → Uncertainty → Conformal Band → Ground Truth
    """
    images_dir = data_dir / "kvasir-seg" / "images"
    masks_dir = data_dir / "kvasir-seg" / "masks"
    
    img_paths = sorted(images_dir.glob("*.jpg"))[:n_samples * 3]
    
    # Pick diverse samples (easy, medium, hard based on polyp size)
    selected = []
    for p in img_paths:
        mask_path = masks_dir / (p.stem + ".jpg")
        if not mask_path.exists():
            mask_path = masks_dir / (p.stem + ".png")
        if mask_path.exists():
            gt = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if gt is not None:
                polyp_ratio = (gt > 127).sum() / gt.size
                selected.append((p, mask_path, polyp_ratio))
    
    # Sort by polyp size and pick diverse samples
    selected.sort(key=lambda x: x[2])
    if len(selected) >= n_samples:
        step = len(selected) // n_samples
        selected = [selected[i * step] for i in range(n_samples)]
    
    fig, axes = plt.subplots(n_samples, 5, figsize=(18, 4 * n_samples))
    col_titles = ['Input Image', 'Prediction', 'Uncertainty Map', 'Conformal Band', 'Ground Truth']
    
    for col_idx, title in enumerate(col_titles):
        axes[0, col_idx].set_title(title, fontsize=13, fontweight='bold')
    
    for row_idx, (img_path, mask_path, _) in enumerate(selected):
        # Load image and ground truth
        img_bgr = cv2.imread(str(img_path))
        gt = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        tensor, rgb, resized_rgb = preprocess_image(img_bgr)
        gt_resized = cv2.resize(gt, (352, 352), interpolation=cv2.INTER_NEAREST)
        
        # MC Dropout inference
        mean_prob, variance = mc_dropout_inference(model, tensor, device, n_passes=16)
        pred_mask = (mean_prob > 0.5).astype(np.uint8) * 255
        
        # Conformal bands (approximate — using variance thresholds)
        inner_mask = (mean_prob > 0.7).astype(np.float32)
        outer_mask = (mean_prob > 0.3).astype(np.float32)
        band = outer_mask - inner_mask
        
        # Col 1: Input Image
        axes[row_idx, 0].imshow(resized_rgb)
        axes[row_idx, 0].axis('off')
        
        # Col 2: Prediction overlay
        overlay = resized_rgb.copy()
        pred_colored = np.zeros_like(overlay)
        pred_colored[pred_mask > 0] = [0, 255, 128]
        blended = cv2.addWeighted(overlay, 0.6, pred_colored, 0.4, 0)
        # Draw contour
        contours, _ = cv2.findContours(pred_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(blended, contours, -1, (0, 255, 255), 2)
        axes[row_idx, 1].imshow(blended)
        axes[row_idx, 1].axis('off')
        
        # Col 3: Uncertainty heatmap
        axes[row_idx, 2].imshow(resized_rgb, alpha=0.3)
        im = axes[row_idx, 2].imshow(variance, cmap='hot', alpha=0.7, vmin=0, vmax=variance.max() + 1e-6)
        axes[row_idx, 2].axis('off')
        
        # Col 4: Conformal band visualization
        conf_vis = resized_rgb.copy().astype(np.float32)
        # Inner (confident) = green
        conf_vis[inner_mask > 0] = conf_vis[inner_mask > 0] * 0.5 + np.array([0, 200, 0]) * 0.5
        # Band (uncertain) = yellow
        conf_vis[band > 0] = conf_vis[band > 0] * 0.3 + np.array([255, 255, 0]) * 0.7
        axes[row_idx, 3].imshow(conf_vis.astype(np.uint8))
        axes[row_idx, 3].axis('off')
        
        # Col 5: Ground truth
        gt_overlay = resized_rgb.copy()
        gt_colored = np.zeros_like(gt_overlay)
        gt_colored[gt_resized > 127] = [255, 100, 100]
        gt_blended = cv2.addWeighted(gt_overlay, 0.6, gt_colored, 0.4, 0)
        axes[row_idx, 4].imshow(gt_blended)
        axes[row_idx, 4].axis('off')
    
    plt.tight_layout()
    save_path = output_dir / "fig2_qualitative_results.png"
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {save_path}")


def generate_fig3_comparison_bar(output_dir, results=None):
    """
    Fig 3: Cross-dataset comparison bar chart.
    Placeholder — will be filled with actual numbers after benchmarking.
    """
    if results is None:
        # Placeholder data — replace with real numbers
        datasets = ['Kvasir\n(100)', 'CVC-Clinic\n(62)', 'CVC-Colon\n(380)', 'CVC-300\n(60)', 'ETIS\n(196)']
        pranet_orig = [0.898, 0.899, 0.640, 0.871, 0.628]
        polyp_pvt =   [0.917, 0.937, 0.808, 0.900, 0.787]
        chakranet =   [0.0, 0.0, 0.0, 0.0, 0.0]  # TO BE FILLED
    
    x = np.arange(len(datasets))
    width = 0.25
    
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    
    bars1 = ax.bar(x - width, pranet_orig, width, label='PraNet (2020)', color='#4A90D9', alpha=0.85)
    bars2 = ax.bar(x, polyp_pvt, width, label='Polyp-PVT (2023)', color='#7EC8E3', alpha=0.85)
    bars3 = ax.bar(x + width, chakranet, width, label='ChakraNet (Ours)', color='#FF6B6B', alpha=0.90, edgecolor='darkred', linewidth=1.2)
    
    ax.set_ylabel('mean Dice Score', fontsize=12)
    ax.set_title('Cross-Dataset Generalization Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(datasets)
    ax.legend(loc='lower right', fontsize=10)
    ax.set_ylim(0.5, 1.0)
    ax.grid(axis='y', alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(f'{height:.3f}', xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    save_path = output_dir / "fig3_cross_dataset_comparison.png"
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"  Saved: {save_path} (placeholder — update with real ChakraNet numbers)")


def generate_fig4_coverage_curve(output_dir):
    """
    Fig 4: Conformal coverage calibration curve.
    Shows: target coverage vs empirical coverage at different alpha levels.
    Placeholder — will be filled after conformal calibration.
    """
    alphas = [0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30]
    target_coverage = [1 - a for a in alphas]
    
    # Placeholder — replace with actual conformal results
    empirical_kvasir = [0.0] * len(alphas)  # TO BE FILLED
    empirical_cvc = [0.0] * len(alphas)     # TO BE FILLED
    
    fig, ax = plt.subplots(1, 1, figsize=(7, 5))
    
    ax.plot([0.7, 1.0], [0.7, 1.0], 'k--', alpha=0.4, label='Ideal calibration')
    ax.plot(target_coverage, empirical_kvasir, 'o-', color='#2ecc71', markersize=8,
            linewidth=2, label='Kvasir-SEG (In-Distribution)')
    ax.plot(target_coverage, empirical_cvc, 's-', color='#e74c3c', markersize=8,
            linewidth=2, label='CVC-ClinicDB (Out-of-Distribution)')
    
    ax.set_xlabel('Target Coverage (1 - α)', fontsize=12)
    ax.set_ylabel('Empirical Coverage', fontsize=12)
    ax.set_title('Conformal Prediction Calibration Curve', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.set_xlim(0.65, 1.02)
    ax.set_ylim(0.65, 1.02)
    ax.grid(True, alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    save_path = output_dir / "fig4_conformal_coverage.png"
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"  Saved: {save_path} (placeholder — update after conformal calibration)")


def main():
    parser = argparse.ArgumentParser(description="Generate paper figures")
    parser.add_argument("--weights", type=str, default=None)
    parser.add_argument("--n_samples", type=int, default=4, help="Rows in qualitative figure")
    args = parser.parse_args()
    
    root = Path(__file__).parent.parent
    data_dir = root / "data"
    output_dir = root / "paper_figures"
    output_dir.mkdir(exist_ok=True)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    weights = args.weights or str(root / "weights" / "pranet_kvasir_best.pth")
    
    print(f"\n{'='*55}")
    print(f"  ChakraNet Paper Figure Generator")
    print(f"  Device:  {device}")
    print(f"  Weights: {weights}")
    print(f"  Output:  {output_dir}")
    print(f"{'='*55}\n")
    
    if Path(weights).exists():
        model = load_model(weights, device)
        
        print("  Generating Fig 2: Qualitative results...")
        generate_fig2_qualitative(model, device, data_dir, output_dir, n_samples=args.n_samples)
    else:
        print(f"  [SKIP] Model weights not found: {weights}")
        print(f"  Generating placeholder figures only...")
    
    print("  Generating Fig 3: Cross-dataset comparison (placeholder)...")
    generate_fig3_comparison_bar(output_dir)
    
    print("  Generating Fig 4: Conformal coverage curve (placeholder)...")
    generate_fig4_coverage_curve(output_dir)
    
    print(f"\n{'='*55}")
    print(f"  All figures saved to: {output_dir}/")
    print(f"  Figures with real data: Fig 2")
    print(f"  Placeholder figures:   Fig 3, 4 (update after benchmarking)")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
