import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.utils.data import DataLoader

# Add src to Python path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from src.data_loaders.dataset import PolypDataset

def denormalize(tensor, mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)):
    """Denormalizes image tensor to [0, 1] for visualization."""
    mean = torch.tensor(mean).view(3, 1, 1)
    std = torch.tensor(std).view(3, 1, 1)
    tensor = tensor * std + mean
    return torch.clamp(tensor, 0, 1)

def visualize_batch(dataloader, output_path: str, num_samples: int = 4):
    """Fetches a batch and saves a visualization grid."""
    images, masks = next(iter(dataloader))
    
    batch_size = images.size(0)
    num_samples = min(num_samples, batch_size)
    
    fig, axes = plt.subplots(num_samples, 3, figsize=(12, 4 * num_samples))
    if num_samples == 1:
        axes = np.expand_dims(axes, axis=0)
        
    for i in range(num_samples):
        # Denormalize image and convert to numpy HWC
        img = denormalize(images[i]).permute(1, 2, 0).numpy()
        
        # Get mask (H, W)
        mask = masks[i].squeeze(0).numpy()
        
        # Overlay mask on image (make mask red)
        overlay = img.copy()
        overlay[mask > 0.5] = overlay[mask > 0.5] * 0.5 + np.array([1.0, 0.0, 0.0]) * 0.5
        
        axes[i, 0].imshow(img)
        axes[i, 0].set_title("Image (Augmented)")
        axes[i, 0].axis('off')
        
        axes[i, 1].imshow(mask, cmap='gray')
        axes[i, 1].set_title("Ground Truth Mask")
        axes[i, 1].axis('off')
        
        axes[i, 2].imshow(overlay)
        axes[i, 2].set_title("Overlay")
        axes[i, 2].axis('off')
        
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=150)
    print(f"Visualization saved to {output_path}")

if __name__ == "__main__":
    data_root = project_root / "data" / "raw"
    split_file = project_root / "data" / "processed" / "train.txt"
    out_dir = project_root / "results" / "sample_predictions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dataset_sanity_check.png"
    
    if not split_file.exists():
        print(f"Error: {split_file} not found. Run generate_splits.py first.")
        sys.exit(1)
        
    print("Initializing dataset...")
    dataset = PolypDataset(data_root=str(data_root), split_file=str(split_file), img_size=352, is_train=True)
    dataloader = DataLoader(dataset, batch_size=4, shuffle=True, num_workers=0)
    
    print("Generating visualization...")
    visualize_batch(dataloader, str(out_path), num_samples=4)
