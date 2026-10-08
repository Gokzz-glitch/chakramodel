"""Training script for fine-tuning pre-trained CHD models."""
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm
from typing import Tuple


def train_epoch(
    model: nn.Module,
    train_loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: str = 'cpu',
    scaler = None
) -> float:
    """Train for one epoch.
    
    Args:
        model: Model to train
        train_loader: Training data loader
        optimizer: Optimizer
        criterion: Loss function
        device: 'cpu' or 'cuda'
        scaler: Optional GradScaler for mixed precision
    
    Returns:
        Average training loss
    """
    model.train()
    total_loss = 0.0
    
    pbar = tqdm(train_loader, desc='Training')
    for images, labels, _ in pbar:
        images = images.to(device)
        labels = labels.to(device)
        
        optimizer.zero_grad()
        
        with torch.autocast(device_type=device, enabled=(scaler is not None)):
            logits = model(images)
            loss = criterion(logits, labels)
        
        if scaler is not None:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            optimizer.step()
        
        total_loss += loss.item()
        pbar.set_postfix({'loss': loss.item():.4f})
    
    return total_loss / len(train_loader)


def validate(
    model: nn.Module,
    val_loader: DataLoader,
    criterion: nn.Module,
    device: str = 'cpu'
) -> Tuple[float, float, float]:
    """Validate model.
    
    Args:
        model: Model to validate
        val_loader: Validation data loader
        criterion: Loss function
        device: 'cpu' or 'cuda'
    
    Returns:
        (val_loss, accuracy, auc_score)
    """
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    all_probs = []
    all_labels = []
    
    with torch.no_grad():
        for images, labels, _ in tqdm(val_loader, desc='Validating'):
            images = images.to(device)
            labels = labels.to(device)
            
            logits = model(images)
            loss = criterion(logits, labels)
            
            total_loss += loss.item()
            
            probs = torch.softmax(logits, dim=1)
            preds = probs.argmax(dim=1)
            
            correct += (preds == labels).sum().item()
            total += labels.size(0)
            
            all_probs.extend(probs[:, 1].cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
    
    val_loss = total_loss / len(val_loader)
    accuracy = correct / total
    
    try:
        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score(all_labels, all_probs)
    except:
        auc = 0.0
    
    return val_loss, accuracy, auc


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    num_epochs: int = 10,
    learning_rate: float = 1e-4,
    device: str = 'cpu',
    checkpoint_dir: str = './checkpoints'
):
    """Full training loop with checkpointing.
    
    Args:
        model: Model to train
        train_loader: Training data loader
        val_loader: Validation data loader
        num_epochs: Number of epochs
        learning_rate: Learning rate
        device: Device to train on
        checkpoint_dir: Directory to save checkpoints
    """
    import os
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)
    
    best_val_loss = float('inf')
    
    for epoch in range(num_epochs):
        print(f"\nEpoch {epoch + 1}/{num_epochs}")
        
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, accuracy, auc = validate(model, val_loader, criterion, device)
        
        print(f"  Train Loss: {train_loss:.4f}")
        print(f"  Val Loss:   {val_loss:.4f}")
        print(f"  Accuracy:   {accuracy:.4f}")
        print(f"  AUC:        {auc:.4f}")
        
        scheduler.step()
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            checkpoint_path = os.path.join(checkpoint_dir, f'best_model_epoch{epoch+1}.pth')
            torch.save(model.state_dict(), checkpoint_path)
            print(f"  Saved checkpoint: {checkpoint_path}")
    
    return model


if __name__ == '__main__':
    from data import CARDIUMDataModule
    from models import ImageEncoder
    
    # Setup
    data = CARDIUMDataModule(
        data_root=r'I:\My Drive\heartbeat',
        fold=1,
        batch_size=16,
        augment_train=True
    )
    
    print("Dataset loaded:")
    print(f"  Counts: {data.get_class_counts()}")
    
    model = ImageEncoder(num_classes=2)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    
    train_model(
        model,
        data.train_loader(),
        data.val_loader(),
        num_epochs=10,
        learning_rate=1e-4,
        device=device,
        checkpoint_dir='./checkpoints'
    )
