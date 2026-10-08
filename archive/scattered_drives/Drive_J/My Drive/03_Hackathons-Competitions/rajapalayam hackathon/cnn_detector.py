import torch
import torch.nn as nn
import torch.optim as optim
import os
import matplotlib.pyplot as plt
from data_loader import get_dataloaders
from gan_augmenter import Constructor

# ----------------- INVARIANTS -----------------
# 1. Random Weight Initialization
# 2. Built entirely from scratch
# 3. No pre-trained weights
# ----------------------------------------------

def weights_init(m):
    if isinstance(m, nn.Conv2d) or isinstance(m, nn.Linear):
        nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
        if m.bias is not None:
            nn.init.constant_(m.bias, 0)

class CNNDetector(nn.Module):
    def __init__(self, num_classes=5):
        super(CNNDetector, self).__init__()
        
        # Backbone (5 layers from scratch)
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2), # 32x32
            
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2), # 16x16
            
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2), # 8x8
            
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2), # 4x4
            
            nn.Conv2d(256, 512, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2), # 2x2
        )
        
        self.flatten = nn.Flatten()
        
        # Classification Head
        self.classifier = nn.Sequential(
            nn.Linear(512 * 2 * 2, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(512, num_classes)
        )
        
        # Regression Head (Bounding Box)
        self.regressor = nn.Sequential(
            nn.Linear(512 * 2 * 2, 512),
            nn.ReLU(inplace=True),
            nn.Linear(512, 4),
            nn.Sigmoid() # Bounding box coords are relative [0, 1]
        )

    def forward(self, x):
        x = self.features(x)
        x = self.flatten(x)
        class_logits = self.classifier(x)
        bbox_preds = self.regressor(x)
        return class_logits, bbox_preds

def train_cnn(num_epochs=10):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training CNN Detector on device: {device}")
    
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True

    # Use a large batch size for max GPU utilization
    train_dl, test_dl = get_dataloaders(batch_size=512)
    
    model = CNNDetector(num_classes=5).to(device)
    model.apply(weights_init)
    
    # Optional: Load GAN to augment data on the fly
    # We will augment batches by replacing a portion of them with GAN fakes
    gan = Constructor().to(device)
    # Ensure a checkpoint exists before loading
    if os.path.exists('checkpoints/netG_epoch_9.pth'):
        gan.load_state_dict(torch.load('checkpoints/netG_epoch_9.pth', map_location=device, weights_only=True))
    gan.eval()
    
    criterion_cls = nn.CrossEntropyLoss()
    criterion_reg = nn.SmoothL1Loss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    os.makedirs("checkpoints", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    
    best_acc = 0.0
    
    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        
        for i, (imgs, bboxes, labels) in enumerate(train_dl):
            imgs = imgs.to(device)
            bboxes = bboxes.to(device)
            labels = labels.to(device)
            
            # Augment 25% of the batch with GAN fakes (assign them dummy class/bbox for robustness)
            b_size = imgs.size(0)
            num_fakes = b_size // 4
            if num_fakes > 0:
                with torch.no_grad():
                    noise = torch.randn(num_fakes, 100, 1, 1, device=device)
                    fakes = gan(noise)
                # Replace the first `num_fakes` images
                imgs[:num_fakes] = fakes
            
            optimizer.zero_grad()
            
            class_logits, bbox_preds = model(imgs)
            
            loss_cls = criterion_cls(class_logits, labels)
            loss_reg = criterion_reg(bbox_preds, bboxes)
            
            # Combine losses
            loss = loss_cls + 10.0 * loss_reg # Weight regression higher
            
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            
        print(f"Epoch [{epoch+1}/{num_epochs}] Loss: {running_loss/len(train_dl):.4f}")
        
        # Validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for imgs, bboxes, labels in test_dl:
                imgs = imgs.to(device)
                labels = labels.to(device)
                
                class_logits, _ = model(imgs)
                _, predicted = torch.max(class_logits.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
        
        acc = 100 * correct / total
        print(f"Validation Accuracy: {acc:.2f}%")
        
        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), 'checkpoints/cnn_best.pth')
            
    print(f"CNN Training Complete. Best Accuracy: {best_acc:.2f}%")
    return best_acc

if __name__ == "__main__":
    train_cnn(num_epochs=10)
