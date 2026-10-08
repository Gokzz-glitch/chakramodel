import argparse
import sys
import time
from pathlib import Path
import numpy as np
from tqdm import tqdm

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from train_pranet import KvasirSEGDataset, DiceFocalLoss
from metrics.seg_metrics import dice, iou
from transformer_segmenter import ChakraTransformerSegmenter
from topo_loss import TopologicalLoss

def main():
    parser = argparse.ArgumentParser(description="Train ChakraTransformer (Research Track)")
    parser.add_argument('--batch-size', type=int, default=16, help='Batch size for training')
    parser.add_argument('--epochs', type=int, default=50, help='Number of epochs')
    parser.add_argument('--lr', type=float, default=1e-4, help='Learning rate (AdamW)')
    parser.add_argument('--num-workers', type=int, default=2, help='Number of dataloader workers')
    args = parser.parse_args()

    print("=== ChakraTransformer Training (High-Accuracy Research Track) ===")
    print(f"Batch Size: {args.batch_size}, Epochs: {args.epochs}, LR: {args.lr}")
    print("Initializing Vision Transformer (ViT-Large)...")

    assert torch.cuda.is_available(), "CUDA must be available to train! CPU training is disabled."
    device = torch.device("cuda")
    model = ChakraTransformerSegmenter().to(device)
    
    if torch.cuda.device_count() > 1:
        print(f"Using {torch.cuda.device_count()} GPUs with DataParallel!")
        model = nn.DataParallel(model)
        
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    criterion_dice = DiceFocalLoss()
    criterion_topo = TopologicalLoss(lam=0.1)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.lr * 0.01)

    print(f"Model initialized on {device}. Loading dataset...")
    
    root = Path(__file__).resolve().parent.parent.parent
    images_dir = root / "data" / "kvasir-seg" / "images"
    masks_dir  = root / "data" / "kvasir-seg" / "masks"
    
    if not images_dir.exists():
        print("[ERROR] Kvasir-SEG not found. Run: python src/download_kvasir.py")
        sys.exit(1)
        
    img_size = 384  # Upgraded resolution for ViT-Large
    
    full_dataset = KvasirSEGDataset(images_dir, masks_dir, img_size=img_size, augment=True, use_gt_bbox_crop=True)
    val_dataset  = KvasirSEGDataset(images_dir, masks_dir, img_size=img_size, augment=False, use_gt_bbox_crop=True)

    all_paths = sorted([p for p in images_dir.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif"}])
    n_train   = int(0.7 * len(all_paths))
    n_val     = int(0.1 * len(all_paths))
    n_cal     = int(0.1 * len(all_paths)) # Explicitly separate calibration/test sets

    train_set = torch.utils.data.Subset(full_dataset, range(n_train))
    val_set   = torch.utils.data.Subset(val_dataset,  range(n_train, n_train + n_val))

    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True,  num_workers=args.num_workers, pin_memory=True)
    val_loader   = DataLoader(val_set,   batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers, pin_memory=True)

    weights_dir = root / "weights"
    weights_dir.mkdir(exist_ok=True)
    best_dice = 0.0
    best_path = weights_dir / "chakra_transformer_best.pth"

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        
        print(f"\n--- Epoch {epoch}/{args.epochs} ---")
        pbar = tqdm(train_loader, desc="Training")
        for imgs, masks in pbar:
            imgs, masks = imgs.to(device), masks.to(device)
            optimizer.zero_grad()
            logits = model(imgs)
            loss_dice = criterion_dice(logits, masks)
            
            # Topological Loss is disabled in the main training loop (future work)
            # as it causes extreme slowdowns on 384x384 feature maps.
            loss = loss_dice
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            pbar.set_postfix({'loss': f"{loss.item():.4f}"})
            
        scheduler.step()
        train_loss /= len(train_loader)

        model.eval()
        val_dice_scores = []
        val_iou_scores  = []
        with torch.no_grad():
            for imgs, masks in val_loader:
                imgs  = imgs.to(device)
                logits = model(imgs)
                probs  = torch.sigmoid(logits).cpu().numpy()
                masks_np = masks.numpy()
                for i in range(len(probs)):
                    pred = (probs[i, 0] > 0.5).astype(np.uint8) * 255
                    gt   = (masks_np[i, 0] > 0.5).astype(np.uint8) * 255
                    val_dice_scores.append(dice(pred, gt))
                    val_iou_scores.append(iou(pred, gt))

        mean_dice = float(np.mean(val_dice_scores))
        mean_iou  = float(np.mean(val_iou_scores))
        lr_now    = optimizer.param_groups[0]["lr"]

        print(f"  --> Epoch [{epoch:3d}/{args.epochs}] Summary | Train Loss: {train_loss:.4f} | Val Dice: {mean_dice:.4f} | Val IoU: {mean_iou:.4f} | LR: {lr_now:.6f}", flush=True)

        if mean_dice > best_dice:
            best_dice = mean_dice
            torch.save(model.state_dict(), best_path)
            print(f"  *** New best Dice: {best_dice:.4f} -> saved to {best_path}")

    print(f"\nTraining Complete! Best Val Dice: {best_dice:.4f}. Weights saved: {best_path}")

if __name__ == '__main__':
    main()
