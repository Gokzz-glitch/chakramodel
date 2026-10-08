import os
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset
import albumentations as A
from albumentations.pytorch import ToTensorV2
from pathlib import Path

class PolypDataset(Dataset):
    """
    Standard Dataset class for Polyp Segmentation.
    Expects a split file containing relative paths to images, e.g., 'kvasir-seg/images/img1.jpg'.
    Assumes masks are located by replacing 'images' with 'masks' in the path.
    """
    def __init__(self, data_root: str, split_file: str, img_size: int = 352, is_train: bool = True):
        self.data_root = Path(data_root)
        self.img_size = img_size
        self.is_train = is_train
        
        with open(split_file, 'r') as f:
            self.image_paths = [line.strip() for line in f.readlines() if line.strip()]
            
        self.transform = self._get_transforms()
        
    def _get_transforms(self):
        if self.is_train:
            return A.Compose([
                A.Resize(self.img_size, self.img_size),
                A.HorizontalFlip(p=0.5),
                A.VerticalFlip(p=0.5),
                A.RandomRotate90(p=0.5),
                A.ShiftScaleRotate(shift_limit=0.0625, scale_limit=0.2, rotate_limit=15, p=0.5, border_mode=cv2.BORDER_REFLECT_101),
                A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.5),
                A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
                ToTensorV2()
            ])
        else:
            return A.Compose([
                A.Resize(self.img_size, self.img_size),
                A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
                ToTensorV2()
            ])

    def __len__(self):
        return len(self.image_paths)
        
    def __getitem__(self, idx):
        rel_img_path = self.image_paths[idx]
        # Replace 'images' with 'masks'
        rel_mask_path = rel_img_path.replace('images', 'masks')
        
        img_path = self.data_root / rel_img_path
        mask_path = self.data_root / rel_mask_path
        
        if not img_path.exists():
            raise FileNotFoundError(f"Image not found: {img_path}")
        if not mask_path.exists():
            raise FileNotFoundError(f"Mask not found: {mask_path}")
            
        # Read image
        image = cv2.imread(str(img_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Read mask
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        # Augmentations apply to both image and mask
        augmented = self.transform(image=image, mask=mask)
        image = augmented['image']
        mask = augmented['mask']
        
        # Scale mask to [0, 1] and add channel dimension
        mask = mask.float() / 255.0
        mask = mask.unsqueeze(0)
        
        return image, mask

if __name__ == "__main__":
    # Quick sanity check
    project_root = Path(__file__).resolve().parents[2]
    data_root = project_root / "data" / "raw"
    split_file = project_root / "data" / "processed" / "train.txt"
    
    if split_file.exists():
        dataset = PolypDataset(data_root=str(data_root), split_file=str(split_file), img_size=352, is_train=True)
        img, mask = dataset[0]
        print(f"Dataset length: {len(dataset)}")
        print(f"Image shape: {img.shape}, dtype: {img.dtype}, min: {img.min():.3f}, max: {img.max():.3f}")
        print(f"Mask shape: {mask.shape}, dtype: {mask.dtype}, min: {mask.min():.3f}, max: {mask.max():.3f}")
    else:
        print("Split file not found. Run generate_splits.py first.")
