import torch
import torch.nn as nn
import os
from torch.utils.data import Dataset, DataLoader
import numpy as np
from PIL import Image

class DummyDetectionDataset(Dataset):
    """
    A custom dataset that reads images and generates dummy bounding box annotations
    if real annotations (like COCO JSON) are missing. This allows the pipeline
    to execute immediately.
    """
    def __init__(self, img_dir, num_classes, img_size=128):
        self.img_dir = img_dir
        self.img_size = img_size
        self.num_classes = num_classes
        self.files = []
        if os.path.exists(img_dir):
            self.files = [f for f in os.listdir(img_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        img_path = os.path.join(self.img_dir, self.files[idx])
        img = Image.open(img_path).convert('RGB')
        img = img.resize((self.img_size, self.img_size))
        img = np.array(img).astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1)) # HWC to CHW
        img = torch.tensor(img)

        # Generate dummy target for a 4x4 grid (YOLO style)
        # Target shape: (num_classes + 5, grid_h, grid_w) = (num_classes + 5, 4, 4)
        target = torch.zeros((self.num_classes + 5, 4, 4))
        
        # Put 1 random object in a random grid cell
        grid_x, grid_y = np.random.randint(0, 4), np.random.randint(0, 4)
        class_id = np.random.randint(0, self.num_classes)
        
        target[class_id, grid_y, grid_x] = 1.0 # Class probability
        target[self.num_classes, grid_y, grid_x] = 1.0 # Object confidence
        target[self.num_classes+1:self.num_classes+5, grid_y, grid_x] = torch.rand(4) # x, y, w, h
        
        return img, target

class SimpleDetectorCNN(nn.Module):
    def __init__(self, num_classes):
        super(SimpleDetectorCNN, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2), # 64x64
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2), # 32x32
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2), # 16x16
            nn.Conv2d(64, 128, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2), # 8x8
            nn.Conv2d(128, 256, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2)  # 4x4 grid
        )
        # Output: (B, num_classes + 5 (conf, x, y, w, h), grid_h, grid_w)
        self.detector_head = nn.Conv2d(256, num_classes + 5, 1)

    def forward(self, x):
        x = self.features(x)
        x = self.detector_head(x)
        return x

def run_cnn_training(config):
    print("[Agent 2 - CNN] Starting CNN Object Detector Training")
    num_classes = config['cnn']['num_classes']
    batch_size = config['cnn']['batch_size']
    lr = config['cnn']['learning_rate']
    epochs = config['cnn']['epochs']
    img_size = config['cnn']['image_size']
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Agent 2 - CNN] Using device: {device}")
    
    model = SimpleDetectorCNN(num_classes).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    
    # We train on the watermarked synthetic data to close the loop
    # or fallback to data/raw if watermark was skipped
    train_dir = "output/watermarked_data"
    if not os.path.exists(train_dir) or len(os.listdir(train_dir)) == 0:
        train_dir = "data/raw/class0" # fallback
        
    dataset = DummyDetectionDataset(train_dir, num_classes, img_size=img_size)
    if len(dataset) == 0:
        print("[Agent 2 - CNN] WARNING: Training directory is empty. Cannot train.")
        return
        
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    # Simple composite loss for YOLO-style grids
    mse_loss = nn.MSELoss()
    bce_loss = nn.BCEWithLogitsLoss()
    
    print(f"[Agent 2 - CNN] Training on {len(dataset)} images for {epochs} epochs.")
    
    model.train()
    for epoch in range(epochs):
        epoch_loss = 0.0
        for imgs, targets in dataloader:
            imgs, targets = imgs.to(device), targets.to(device)
            
            optimizer.zero_grad()
            preds = model(imgs) # Shape: (B, num_classes + 5, 4, 4)
            
            # preds[:, :num_classes] -> classes
            # preds[:, num_classes] -> conf
            # preds[:, num_classes+1:] -> bbox
            
            loss_cls = bce_loss(preds[:, :num_classes], targets[:, :num_classes])
            loss_conf = bce_loss(preds[:, num_classes], targets[:, num_classes])
            loss_bbox = mse_loss(torch.sigmoid(preds[:, num_classes+1:]), targets[:, num_classes+1:])
            
            loss = loss_cls + loss_conf + loss_bbox * 5.0 # weight bbox
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            
        if (epoch + 1) % 5 == 0 or epoch == epochs - 1:
            print(f"[Agent 2 - CNN] Epoch {epoch+1}/{epochs} | Loss: {epoch_loss/len(dataloader):.4f}")
    
    os.makedirs("output/checkpoints", exist_ok=True)
    torch.save(model.state_dict(), "output/checkpoints/cnn_detector.pth")
    print("[Agent 2 - CNN] Checkpoint saved.")
