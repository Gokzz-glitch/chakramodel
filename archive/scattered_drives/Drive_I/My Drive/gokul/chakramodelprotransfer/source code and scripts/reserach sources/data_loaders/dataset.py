import cv2
import pandas as pd
from pathlib import Path
import torch
from torch.utils.data import Dataset
from .augmentations import (
    CopyPasteAugmentation, 
    ColorExchangeAugmentation, 
    CutMixAugmentation,
    build_train_transforms,
    build_val_transforms
)

class PolypDataset(Dataset):
    """
    Standard Dataset class for Polyp Segmentation.
    Expects a TSV manifest containing relative paths to images and masks.
    """
    def __init__(self, data_root: str, manifest_path: str, img_size: int = 352, is_train: bool = True, aug_config: dict = None):
        self.data_root = Path(data_root)
        self.manifest_path = Path(manifest_path)
        self.img_size = img_size
        self.is_train = is_train
        self.aug_config = aug_config or {}
        
        # Read the TSV manifest
        self.data = pd.read_csv(self.manifest_path, sep='\t')
        
        self.advanced_augs = []
        if self.is_train and self.aug_config:
            if self.aug_config.get('copy_paste', {}).get('enabled', False):
                self.advanced_augs.append(CopyPasteAugmentation(self.data_root, self.data, p=self.aug_config['copy_paste'].get('p', 0.3)))
            if self.aug_config.get('color_exchange', {}).get('enabled', False):
                self.advanced_augs.append(ColorExchangeAugmentation(self.data_root, self.data, p=self.aug_config['color_exchange'].get('p', 0.3)))
            if self.aug_config.get('cutmix', {}).get('enabled', False):
                self.advanced_augs.append(CutMixAugmentation(self.data_root, self.data, p=self.aug_config['cutmix'].get('p', 0.2), alpha=self.aug_config['cutmix'].get('alpha', 1.0)))

        config = {'img_size': self.img_size}
        if self.is_train:
            self.transform = build_train_transforms(config)
        else:
            self.transform = build_val_transforms(config)

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
        
        # Apply dataset-level advanced augmentations (they take numpy arrays)
        for aug in self.advanced_augs:
            image, mask = aug(image, mask)
        
        # Albumentations apply to both image and mask
        augmented = self.transform(image=image, mask=mask)
        image = augmented['image']
        mask = augmented['mask']
        
        # Scale mask to [0, 1] and add channel dimension
        mask = mask.float() / 255.0
        mask = mask.unsqueeze(0)
        
        return image, mask
