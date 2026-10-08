"""Data loading utilities for CARDIUM dataset."""
import os
from pathlib import Path
from typing import List, Tuple, Optional
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
import numpy as np


class CARDIUMDataset(Dataset):
    """PyTorch dataset for CARDIUM fetal ultrasound images."""
    
    def __init__(
        self,
        data_root: str,
        split: str = 'train',
        fold: int = 1,
        transform: Optional[transforms.Compose] = None,
        include_all: bool = False
    ):
        """
        Args:
            data_root: Path to CARDIUM dataset root
            split: 'train' or 'test'
            fold: Cross-validation fold (1, 2, or 3)
            transform: Image transformations
            include_all: If True, ignore fold and load entire dataset
        """
        self.data_root = Path(data_root)
        self.split = split
        self.fold = fold
        self.include_all = include_all
        
        if transform is None:
            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])
        else:
            self.transform = transform
        
        self.images = []
        self.labels = []
        self._load_dataset()
    
    def _load_dataset(self):
        """Load image paths and labels from dataset structure."""
        if self.include_all:
            # Load entire CARDIUM_dataset (organized as CHD / Non_CHD)
            cardium_root = self.data_root / 'CARDIUM_dataset'
            for label, class_name in enumerate(['Non_CHD', 'CHD']):
                class_dir = cardium_root / class_name
                if class_dir.exists():
                    for subdir in sorted(class_dir.iterdir()):
                        if subdir.is_dir():
                            for img_file in sorted(subdir.glob('*.png')):
                                self.images.append(str(img_file))
                                self.labels.append(label)
        else:
            # Load from fold structure (cardium_images)
            fold_root = self.data_root / 'cardium_images' / 'cardium_images' / f'fold_{self.fold}' / self.split
            
            for label, class_name in enumerate(['Non_CHD', 'CHD']):
                class_dir = fold_root / class_name
                if class_dir.exists():
                    for img_file in sorted(class_dir.glob('*.png')):
                        self.images.append(str(img_file))
                        self.labels.append(label)
    
    def __len__(self) -> int:
        return len(self.images)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int, str]:
        """Return (image_tensor, label, image_path)."""
        img_path = self.images[idx]
        label = self.labels[idx]
        
        try:
            image = Image.open(img_path).convert('RGB')
            image = self.transform(image)
        except Exception as e:
            print(f"Error loading {img_path}: {e}")
            # Return black image on error
            image = torch.zeros(3, 224, 224)
        
        return image, label, img_path


class CARDIUMDataModule:
    """Convenient data loading for training/evaluation."""
    
    def __init__(
        self,
        data_root: str,
        fold: int = 1,
        batch_size: int = 32,
        num_workers: int = 0,
        augment_train: bool = True
    ):
        """Initialize data module.
        
        Args:
            data_root: Root path to dataset
            fold: CV fold (1, 2, 3)
            batch_size: Batch size for loader
            num_workers: DataLoader workers
            augment_train: Apply augmentation to training set
        """
        self.data_root = data_root
        self.fold = fold
        self.batch_size = batch_size
        self.num_workers = num_workers
        
        train_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(0.5) if augment_train else transforms.Lambda(lambda x: x),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ]) if augment_train else None
        
        self.train_dataset = CARDIUMDataset(
            data_root,
            split='train',
            fold=fold,
            transform=train_transform
        )
        
        self.val_dataset = CARDIUMDataset(
            data_root,
            split='test',
            fold=fold,
        )
    
    def train_loader(self) -> DataLoader:
        """Return training DataLoader."""
        return DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=self.num_workers,
            pin_memory=True
        )
    
    def val_loader(self) -> DataLoader:
        """Return validation DataLoader."""
        return DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=self.num_workers,
            pin_memory=True
        )
    
    def get_class_counts(self) -> dict:
        """Return class distribution."""
        train_labels = np.array(self.train_dataset.labels) if len(self.train_dataset.labels) > 0 else np.array([])
        val_labels = np.array(self.val_dataset.labels) if len(self.val_dataset.labels) > 0 else np.array([])
        
        if len(train_labels) > 0:
            train_counts = np.bincount(train_labels)
        else:
            train_counts = np.array([0, 0])
        
        if len(val_labels) > 0:
            val_counts = np.bincount(val_labels)
        else:
            val_counts = np.array([0, 0])
        
        return {
            'train': {'Non_CHD': int(train_counts[0]) if len(train_counts) > 0 else 0, 
                      'CHD': int(train_counts[1]) if len(train_counts) > 1 else 0},
            'val': {'Non_CHD': int(val_counts[0]) if len(val_counts) > 0 else 0, 
                    'CHD': int(val_counts[1]) if len(val_counts) > 1 else 0}
        }
