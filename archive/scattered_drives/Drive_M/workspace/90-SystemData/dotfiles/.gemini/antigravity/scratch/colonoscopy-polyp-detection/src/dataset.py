"""
Custom PyTorch Dataset for Colonoscopy Polyp Detection.

Handles loading, preprocessing, and augmenting colonoscopy images
for training deep learning models.
"""

import os
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset
from PIL import Image

import albumentations as A
from albumentations.pytorch import ToTensorV2


def get_train_transforms(image_size: int = 384) -> A.Compose:
    """Training augmentations for medical images.
    
    Includes geometric and color augmentations that are
    appropriate for colonoscopy images.
    """
    return A.Compose([
        A.Resize(image_size, image_size),
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.ShiftScaleRotate(
            shift_limit=0.1,
            scale_limit=0.15,
            rotate_limit=30,
            p=0.5
        ),
        A.RandomBrightnessContrast(
            brightness_limit=0.2,
            contrast_limit=0.2,
            p=0.5
        ),
        A.GaussNoise(p=0.2),
        A.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
        ToTensorV2()
    ])


def get_val_transforms(image_size: int = 384) -> A.Compose:
    """Validation/test transforms — only resize and normalize."""
    return A.Compose([
        A.Resize(image_size, image_size),
        A.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
        ToTensorV2()
    ])


class ColonoscopyDataset(Dataset):
    """PyTorch Dataset for colonoscopy polyp images.
    
    Expects a directory structure like:
        data_dir/
        ├── polyp/
        │   ├── img001.jpg
        │   └── ...
        └── normal/
            ├── img001.jpg
            └── ...
    
    Args:
        data_dir: Path to the dataset directory
        transform: Albumentations transform pipeline
        image_size: Target image size (default: 384)
    """
    
    # Class labels
    CLASSES = ['normal', 'polyp']
    
    def __init__(
        self,
        data_dir: str,
        transform: Optional[A.Compose] = None,
        image_size: int = 384
    ):
        self.data_dir = Path(data_dir)
        self.image_size = image_size
        self.transform = transform or get_val_transforms(image_size)
        
        # Collect all image paths and labels
        self.samples = []
        self._load_samples()
    
    def _load_samples(self):
        """Scan directory and collect (image_path, label) pairs."""
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        
        for class_idx, class_name in enumerate(self.CLASSES):
            class_dir = self.data_dir / class_name
            if not class_dir.exists():
                print(f"Warning: Directory {class_dir} not found. Skipping.")
                continue
            
            for img_path in sorted(class_dir.iterdir()):
                if img_path.suffix.lower() in valid_extensions:
                    self.samples.append((str(img_path), class_idx))
        
        print(f"Loaded {len(self.samples)} images from {self.data_dir}")
        for class_idx, class_name in enumerate(self.CLASSES):
            count = sum(1 for _, label in self.samples if label == class_idx)
            print(f"  {class_name}: {count} images")
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]
        
        # Load image using OpenCV (BGR) and convert to RGB
        image = cv2.imread(img_path)
        if image is None:
            raise ValueError(f"Failed to load image: {img_path}")
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Apply augmentations
        transformed = self.transform(image=image)
        image = transformed['image']
        
        return image, label
    
    def get_class_weights(self) -> torch.Tensor:
        """Compute class weights for handling imbalanced datasets.
        
        Useful for colonoscopy datasets where polyp images
        may be significantly fewer than normal images.
        """
        labels = [label for _, label in self.samples]
        class_counts = np.bincount(labels, minlength=len(self.CLASSES))
        total = len(labels)
        weights = total / (len(self.CLASSES) * class_counts)
        return torch.FloatTensor(weights)


if __name__ == "__main__":
    # Quick test
    print("Testing ColonoscopyDataset...")
    print("Create your data directory structure first:")
    print("  data/processed/train/polyp/")
    print("  data/processed/train/normal/")
    print("\nThen run this script to verify loading works.")
