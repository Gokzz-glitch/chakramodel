import argparse
import logging
import os
import sys
import yaml
from pathlib import Path

# Ensure project root is on sys.path for imports
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
from tqdm import tqdm

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter

from src.data_loaders.dataset import PolypDataset
from src.models import build_model
from src.utils.metrics import SegmentationMetrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Polyp Segmentation Training")
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()

def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config

def build_loss(config: dict):
    # BCE + Dice
    class BCEDiceLoss(nn.Module):
        def __init__(self, bce_weight=1.0, dice_weight=1.0, dice_smooth=1.0):
            super().__init__()
            self.bce = nn.BCEWithLogitsLoss()
            self.bce_weight = bce_weight
            self.dice_weight = dice_weight
            self.dice_smooth = dice_smooth
            
        def forward(self, pred, target):
            bce_loss = self.bce(pred, target)
            pred_sigmoid = torch.sigmoid(pred)
            intersection = (pred_sigmoid * target).sum(dim=(2, 3))
            union = pred_sigmoid.sum(dim=(2, 3)) + target.sum(dim=(2, 3))
            dice_loss = 1 - (2.0 * intersection + self.dice_smooth) / (union + self.dice_smooth)
            return self.bce_weight * bce_loss + self.dice_weight * dice_loss.mean()
            
    if config.get("type") == "bce_dice":
        return BCEDiceLoss(
            bce_weight=config.get("bce_weight", 1.0),
            dice_weight=config.get("dice_weight", 1.0),
            dice_smooth=config.get("dice_smooth", 1.0)
        )
    raise ValueError(f"Unknown loss: {config.get('type')}")

def main():
    args = parse_args()
    config = load_config(args.config)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    data_root = config["data"]["data_root"]
    train_manifest = config["data"]["train_manifest"]
    val_manifest = config["data"]["val_manifest"]
    
    train_dataset = PolypDataset(data_root=data_root, manifest_path=train_manifest, is_train=True)
    val_dataset = PolypDataset(data_root=data_root, manifest_path=val_manifest, is_train=False)
    
    train_loader = DataLoader(
        train_dataset, 
        batch_size=config["training"]["batch_size"],
        shuffle=True, 
        num_workers=config["training"].get("num_workers", 4),
        pin_memory=config["training"].get("pin_memory", True)
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config["training"]["batch_size"],
        shuffle=False,
        num_workers=config["training"].get("num_workers", 4),
        pin_memory=config["training"].get("pin_memory", True)
    )
    
    model = build_model(config["model"]).to(device)
    criterion = build_loss(config["loss"]).to(device)
    
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=config["training"]["optimizer"]["lr"],
        weight_decay=config["training"]["optimizer"].get("weight_decay", 0)
    )
    
    max_epochs = 3 if args.debug else config["training"]["epochs"]
    base_lr = config["training"]["optimizer"]["lr"]
    power = config["training"]["scheduler"].get("power", 0.9)
    
    scaler = torch.cuda.amp.GradScaler(enabled=torch.cuda.is_available())
    metrics_calc = SegmentationMetrics()
    
    writer = None
    if not args.debug and config["logging"]["tensorboard"]["enabled"]:
        writer = SummaryWriter(config["logging"]["tensorboard"]["log_dir"])
        
    best_val_dice = 0.0
    checkpoint_dir = Path(config["checkpointing"]["dir"])
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    for epoch in range(max_epochs):
        # PolyLR Scheduler
        lr = base_lr * (1 - epoch / max_epochs) ** power
        for param_group in optimizer.param_groups:
            param_group['lr'] = lr
            
        model.train()
        train_loss = 0.0
        
        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{max_epochs}")
        for i, (images, masks) in enumerate(pbar):
            if args.debug and i > 0:
                break
            images, masks = images.to(device), masks.to(device)
            
            optimizer.zero_grad()
            with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
                outputs = model(images)
                logits = outputs['pred']
                loss = criterion(logits, masks)
                
            scaler.scale(loss).backward()
            
            if config["training"].get("gradient_clip", {}).get("enabled", False):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(), 
                    config["training"]["gradient_clip"].get("max_norm", 0.5)
                )
                
            scaler.step(optimizer)
            scaler.update()
            
            train_loss += loss.item()
            pbar.set_postfix({"loss": f"{loss.item():.4f}"})
            
        train_loss /= len(train_loader) if not args.debug else 1
        
        # Validation
        model.eval()
        metrics_calc.reset()
        val_loss = 0.0
        
        with torch.no_grad():
            for i, (images, masks) in enumerate(val_loader):
                if args.debug and i > 0:
                    break
                images, masks = images.to(device), masks.to(device)
                with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
                    outputs = model(images)
                    logits = outputs['pred']
                    loss = criterion(logits, masks)
                val_loss += loss.item()
                
                preds = torch.sigmoid(logits).cpu().numpy()
                masks_np = masks.cpu().numpy()
                for p, m in zip(preds, masks_np):
                    metrics_calc.update(p[0], m[0])
                    
        val_results = metrics_calc.compute()
        val_dice = val_results['mDice']
        val_loss /= len(val_loader) if not args.debug else 1
        
        logger.info(f"Epoch {epoch+1} - Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}, Val Dice: {val_dice:.4f}, Val IoU: {val_results['mIoU']:.4f}")
        
        if writer:
            writer.add_scalar("Loss/train", train_loss, epoch)
            writer.add_scalar("Loss/val", val_loss, epoch)
            writer.add_scalar("Metrics/val_dice", val_dice, epoch)
            writer.add_scalar("Metrics/val_iou", val_results['mIoU'], epoch)
            writer.add_scalar("LR", lr, epoch)
            
        if val_dice > best_val_dice and not args.debug:
            best_val_dice = val_dice
            filename = config["checkpointing"]["filename_template"].format(epoch=epoch+1, val_dice=val_dice)
            save_path = checkpoint_dir / filename
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_dice': val_dice
            }, save_path)
            logger.info(f"Saved best model to {save_path}")

if __name__ == "__main__":
    main()
