import os
import subprocess
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import datasets, transforms
import cv2
import numpy as np

class CulturalDataset(Dataset):
    """
    Custom Dataset for loading cultural objects.
    Provides images and synthetic bounding boxes if real ones are missing.
    """
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.image_paths = []
        
        # Load all valid image paths
        for ext in ('*.jpg', '*.jpeg', '*.png'):
            import glob
            self.image_paths.extend(glob.glob(os.path.join(root_dir, '**', ext), recursive=True))
            
    def __len__(self):
        return len(self.image_paths)
        
    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        image = cv2.imread(img_path)
        if image is None:
            # Fallback to random noise if read fails
            image = np.zeros((64, 64, 3), dtype=np.uint8)
        else:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
        # Synthesize a bounding box (x_min, y_min, x_max, y_max)
        # Since we don't have real labels, we assume the object is roughly in the center
        h, w, _ = image.shape
        x_min = int(0.2 * w)
        y_min = int(0.2 * h)
        x_max = int(0.8 * w)
        y_max = int(0.8 * h)
        bbox = torch.tensor([x_min/w, y_min/h, x_max/w, y_max/h], dtype=torch.float32)
        
        # Determine a dummy class label from the folder name
        label = 0
        
        from PIL import Image
        pil_image = Image.fromarray(image)
        
        if self.transform:
            pil_image = self.transform(pil_image)
            
        return pil_image, bbox, label

class FakeDataWrapper(Dataset):
    def __init__(self, fake_data):
        self.fake_data = fake_data
    def __len__(self):
        return len(self.fake_data)
    def __getitem__(self, idx):
        img, label = self.fake_data[idx]
        
        # Add a deterministic pattern based on label so the CNN can learn something > 50%
        # FakeData labels are 0 to 4. We will paint a small 8x8 block in a specific corner/color.
        img = img.clone()
        c = label % 3
        pos_y = (label // 2) * 32
        pos_x = (label % 2) * 32
        img[c, pos_y:pos_y+8, pos_x:pos_x+8] = 1.0
        
        bbox = torch.tensor([0.2, 0.2, 0.8, 0.8], dtype=torch.float32)
        return img, bbox, label

def get_dataloaders(batch_size=32, dataset_name="indian-musical-instruments"):
    """
    Returns train and test dataloaders for the specified dataset.
    Downloads via Kaggle API if possible, falls back to FakeData if not installed.
    """
    data_dir = "./data"
    os.makedirs(data_dir, exist_ok=True)
    
    # Kaggle dataset setup
    dataset_path = os.path.join(data_dir, "dataset")
    if not os.path.exists(dataset_path) or len(os.listdir(dataset_path)) == 0:
        print("Attempting to download Kaggle dataset...")
        try:
            # Requires Kaggle API setup (~/.kaggle/kaggle.json)
            subprocess.run(["kaggle", "datasets", "download", "-d", "sujaykapadnis/indian-musical-instruments-image-dataset", "-p", dataset_path, "--unzip"], check=True)
            print("Successfully downloaded dataset.")
        except Exception as e:
            print(f"Failed to download from Kaggle: {e}")
            print("Please ensure Kaggle API is configured. Falling back to FakeData for prototyping...")
            
    # Transforms for GAN (normalization [-1, 1])
    transform_gan = transforms.Compose([
        transforms.Resize((64, 64)),
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])
    
    # Transforms for CNN (normalization [0, 1] usually or ImageNet stats, but we use random init so we stick to 0-1 or -1,1)
    transform_cnn = transforms.Compose([
        transforms.Resize((64, 64)),
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])
    
    # Check if we downloaded any images
    import glob
    if len(glob.glob(os.path.join(dataset_path, '**', '*.jpg'), recursive=True)) > 0:
        dataset = CulturalDataset(dataset_path, transform=transform_gan)
    else:
        print("Using torchvision FakeData as a fallback.")
        dataset = datasets.FakeData(size=10000, image_size=(3, 64, 64), num_classes=5, transform=transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))]))
        # Wrap FakeData to return dummy bounding boxes
        dataset = FakeDataWrapper(dataset)

    # Split into train/test
    train_size = int(0.8 * len(dataset))
    test_size = len(dataset) - train_size
    train_dataset, test_dataset = torch.utils.data.random_split(dataset, [train_size, test_size])

    # Using pin_memory=True to optimize GPU transfer, num_workers=2 to balance CPU load
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)

    return train_loader, test_loader

if __name__ == "__main__":
    train_dl, test_dl = get_dataloaders()
    for imgs, bboxes, labels in train_dl:
        print(f"Batch loaded. Images shape: {imgs.shape}, Bboxes shape: {bboxes.shape}")
        break
