import cv2
import pandas as pd
from pathlib import Path
import torch
from torch.utils.data import Dataset
import albumentations as A
from albumentations.pytorch import ToTensorV2

class PolypDataset(Dataset):
    """
    Standard Dataset class for Polyp Segmentation.
    Expects a TSV manifest containing relative paths to images and masks.
    """
    def __init__(self, data_root: str, manifest_path: str, img_size: int = 352, is_train: bool = True):
        self.data_root = Path(data_root)
        self.manifest_path = Path(manifest_path)
        self.img_size = img_size
        self.is_train = is_train
        
        # Read the TSV manifest
        self.data = pd.read_csv(self.manifest_path, sep='\t')
        
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
        return len(self.data)
        
    def __getitem__(self, idx):
        row = self.data.iloc[idx]
        
        img_path = self.data_root / row['image']
        mask_path = self.data_root / row['mask']
        
        if not img_path.exists():
            raise FileNotFoundError(f"Image not found: {img_path}")
        if not mask_path.exists():
            raise FileNotFoundError(f"Mask not found: {mask_path}")
            
        # Read image
        image = cv2.imread(str(img_path))
        if image is None:
             raise ValueError(f"Failed to read image: {img_path}")
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Read mask
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
             raise ValueError(f"Failed to read mask: {mask_path}")
        
        # Augmentations apply to both image and mask
        augmented = self.transform(image=image, mask=mask)
        image = augmented['image']
        mask = augmented['mask']
        
        # Scale mask to [0, 1] and add channel dimension
        mask = mask.float() / 255.0
        mask = mask.unsqueeze(0)
        
        return image, mask
