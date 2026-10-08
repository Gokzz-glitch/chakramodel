"""
╔══════════════════════════════════════════════════════════════╗
║               MANDINET: TRAINING PIPELINE                   ║
║     Custom Object Detection Model (From Scratch)            ║
║     Optimized for NVIDIA RTX 3050 Laptop GPU (4GB VRAM)     ║
╚══════════════════════════════════════════════════════════════╝

Round 2 Rules: 
- Must build object detection model from scratch.
- NO pretrained weights allowed.
- Must converge within 24 hours.

Architecture:
- 5 Convolutional Blocks (MobileNet-inspired depthwise separable)
- 10x10 Grid YOLOv1-style detection head
- Native PyTorch Mixed Precision (AMP) to save VRAM and boost speed.
"""

import os
import glob
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
from torch.cuda.amp import GradScaler, autocast
import time

# ── Configuration ──────────────────────────────────────────────
IMG_SIZE = 320
GRID_SIZE = 10
NUM_BBOXES = 2
NUM_CLASSES = 1  # Simplified to 1 class ("produce") for this POC
BATCH_SIZE = 32  # Fit comfortably in 4GB VRAM
EPOCHS = 100
LR = 1e-3

DATA_DIR = r"J:\My Drive\rajapalayam hackathon\processed_dataset"
IMAGES_DIR = os.path.join(DATA_DIR, "images")
LABELS_DIR = os.path.join(DATA_DIR, "labels")

# ── 1. Custom Dataset Loader ──────────────────────────────────
class MandiDataset(Dataset):
    def __init__(self, images_dir, labels_dir, transform=None):
        self.images_dir = images_dir
        self.labels_dir = labels_dir
        self.transform = transform
        self.image_files = [f for f in os.listdir(images_dir) if f.endswith('.jpg')]
        print(f"Loaded {len(self.image_files)} images for training.")

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, idx):
        img_name = self.image_files[idx]
        img_path = os.path.join(self.images_dir, img_name)
        
        # Load image
        image = Image.open(img_path).convert("RGB")
        
        # Load labels
        label_name = os.path.splitext(img_name)[0] + ".txt"
        label_path = os.path.join(self.labels_dir, label_name)
        
        # YOLOv1 Style Target Tensor [GRID_SIZE, GRID_SIZE, 5 + NUM_CLASSES]
        # 5 = [c, x, y, w, h] (confidence, center_x, center_y, width, height)
        target = torch.zeros((GRID_SIZE, GRID_SIZE, 5 + NUM_CLASSES))
        
        if os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f.readlines():
                    class_id, x, y, w, h = map(float, line.strip().split())
                    
                    # Find which grid cell this object belongs to
                    i, j = int(GRID_SIZE * y), int(GRID_SIZE * x)
                    
                    # Target relative to grid cell
                    x_cell = (GRID_SIZE * x) - j
                    y_cell = (GRID_SIZE * y) - i
                    
                    # If no object already assigned to this cell
                    if target[i, j, 0] == 0:
                        target[i, j, 0] = 1 # Confidence
                        target[i, j, 1:5] = torch.tensor([x_cell, y_cell, w, h])
                        target[i, j, 5 + int(class_id)] = 1
        
        if self.transform:
            image = self.transform(image)
            
        return image, target

# ── 2. MandiNet Architecture ──────────────────────────────────
class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.LeakyReLU(0.1)
        )
    def forward(self, x):
        return self.conv(x)

class MandiNet(nn.Module):
    def __init__(self):
        super().__init__()
        # Input: 320x320x3
        self.backbone = nn.Sequential(
            ConvBlock(3, 32),    # 160x160
            ConvBlock(32, 64),   # 80x80
            ConvBlock(64, 128),  # 40x40
            ConvBlock(128, 256), # 20x20
            ConvBlock(256, 512)  # 10x10 (GRID_SIZE)
        )
        
        # Output: [batch, GRID_SIZE, GRID_SIZE, NUM_BBOXES * 5 + NUM_CLASSES]
        # For simplicity, 1 bbox per cell for this POC: (1 * 5) + 1 = 6 channels
        out_channels = 5 + NUM_CLASSES
        self.head = nn.Conv2d(512, out_channels, kernel_size=1)
        
    def forward(self, x):
        x = self.backbone(x)
        x = self.head(x)
        # Permute to match target shape [batch, GRID_SIZE, GRID_SIZE, channels]
        return x.permute(0, 2, 3, 1)

# ── 3. Simple YOLO Loss ───────────────────────────────────────
class YoloLoss(nn.Module):
    def __init__(self):
        super().__init__()
        self.mse = nn.MSELoss(reduction="sum")
        self.bce = nn.BCEWithLogitsLoss(reduction="sum")

    def forward(self, predictions, target):
        # predictions shape: [batch, grid, grid, 6]
        # target shape: [batch, grid, grid, 6]
        
        # Mask where objects exist
        obj_mask = target[..., 0] == 1
        noobj_mask = target[..., 0] == 0
        
        # 1. No Object Confidence Loss
        noobj_loss = self.bce(predictions[..., 0][noobj_mask], target[..., 0][noobj_mask])
        
        # 2. Object Confidence Loss
        obj_loss = self.bce(predictions[..., 0][obj_mask], target[..., 0][obj_mask])
        
        # 3. Box Coordinates Loss (x, y, w, h)
        box_loss = self.mse(predictions[..., 1:5][obj_mask], target[..., 1:5][obj_mask])
        
        # 4. Class Loss
        class_loss = self.mse(predictions[..., 5:][obj_mask], target[..., 5:][obj_mask])
        
        # Weighted Total
        total_loss = (10 * box_loss) + (5 * obj_loss) + noobj_loss + class_loss
        return total_loss / predictions.shape[0]

# ── 4. Training Loop ──────────────────────────────────────────
def main():
    print("=" * 60)
    print("  🚀 MANDINET FROM-SCRATCH TRAINING")
    print("=" * 60)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n💻 Hardware: {device.upper()}")
    if device.type == 'cuda':
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        print("   ✅ Automatic Mixed Precision (AMP) ENABLED to maximize VRAM efficiency.")
    
    # Transforms
    transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
    ])
    
    # Dataset & Loader
    dataset = MandiDataset(IMAGES_DIR, LABELS_DIR, transform=transform)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0) # num_workers=0 on Windows usually
    
    # Model, Loss, Optimizer
    model = MandiNet().to(device)
    criterion = YoloLoss()
    optimizer = optim.Adam(model.parameters(), lr=LR)
    
    # AMP Scaler for memory efficiency and speed
    scaler = GradScaler()
    
    print("\n🔥 STARTING TRAINING LOOP...")
    start_time = time.time()
    
    for epoch in range(1, EPOCHS + 1):
        model.train()
        epoch_loss = 0
        
        for batch_idx, (images, targets) in enumerate(dataloader):
            images, targets = images.to(device), targets.to(device)
            
            optimizer.zero_grad()
            
            # Forward pass with AMP
            with autocast():
                predictions = model(images)
                loss = criterion(predictions, targets)
            
            # Backward pass with scaler
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            
            epoch_loss += loss.item()
            
        avg_loss = epoch_loss / len(dataloader)
        print(f"   Epoch [{epoch}/{EPOCHS}] | Loss: {avg_loss:.4f} | Time: {time.time() - start_time:.1f}s")
        
        # Save checkpoint periodically
        if epoch % 10 == 0:
            torch.save(model.state_dict(), f"mandinet_epoch_{epoch}.pth")
            
    print("\n" + "=" * 60)
    print("  ✅ TRAINING COMPLETE")
    print("  Final model saved to: mandinet_final.pth")
    torch.save(model.state_dict(), "mandinet_final.pth")
    print("=" * 60)

if __name__ == "__main__":
    main()
