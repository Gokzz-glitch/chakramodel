"""
PraNet Training on Kvasir-SEG
Trains the PraNetMicroRefiner from scratch on Kvasir-SEG to achieve
competitive Dice/IoU scores for paper publication.

Usage:
    python src/train_pranet.py --epochs 50 --batch 8
    python src/train_pranet.py --epochs 100 --batch 4  # slower, better result

Expected results after 50 epochs:
    Dice > 0.80, mIoU > 0.75 (competitive with original PraNet 0.898)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, str(Path(__file__).parent))
from pranet_segmenter import PraNetMicroRefiner
from metrics.seg_metrics import dice, iou

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif"}


# ─── Dataset ─────────────────────────────────────────────────────────────────
class KvasirSEGDataset(Dataset):
    def __init__(self, images_dir: Path, masks_dir: Path, img_size: int = 352, augment: bool = True):
        self.img_paths = sorted([p for p in images_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS])
        self.masks_dir = masks_dir
        self.img_size  = img_size
        self.augment   = augment
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        self.std  = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)

    def __len__(self):
        return len(self.img_paths)

    def _find_mask(self, stem: str) -> Path | None:
        for ext in IMAGE_EXTS:
            p = self.masks_dir / (stem + ext)
            if p.exists():
                return p
        return None

    def __getitem__(self, idx):
        img_path  = self.img_paths[idx]
        mask_path = self._find_mask(img_path.stem)

        img  = cv2.imread(str(img_path))
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE) if mask_path else None

        if img is None:
            img  = np.zeros((self.img_size, self.img_size, 3), dtype=np.uint8)
            mask = np.zeros((self.img_size, self.img_size),    dtype=np.uint8)

        img  = cv2.resize(img,  (self.img_size, self.img_size), interpolation=cv2.INTER_LINEAR)
        mask = cv2.resize(mask, (self.img_size, self.img_size), interpolation=cv2.INTER_NEAREST) if mask is not None else np.zeros((self.img_size, self.img_size), dtype=np.uint8)

        # Augmentation
        if self.augment:
            if np.random.rand() > 0.5:
                img  = cv2.flip(img,  1)
                mask = cv2.flip(mask, 1)
            if np.random.rand() > 0.5:
                img  = cv2.flip(img,  0)
                mask = cv2.flip(mask, 0)
            # Random rotation
            angle = np.random.uniform(-30, 30)
            M = cv2.getRotationMatrix2D((self.img_size // 2, self.img_size // 2), angle, 1.0)
            img  = cv2.warpAffine(img,  M, (self.img_size, self.img_size))
            mask = cv2.warpAffine(mask, M, (self.img_size, self.img_size))

        # To tensor
        img_t  = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float() / 255.0
        img_t  = (img_t - self.mean) / self.std
        mask_t = torch.from_numpy((mask > 127).astype(np.float32)).unsqueeze(0)

        return img_t, mask_t


# ─── Loss ─────────────────────────────────────────────────────────────────────
class DiceBCELoss(nn.Module):
    def __init__(self):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce_loss = self.bce(logits, targets)
        probs    = torch.sigmoid(logits)
        smooth   = 1e-6
        inter    = (probs * targets).sum(dim=(2, 3))
        dice_loss = 1.0 - (2.0 * inter + smooth) / (probs.sum(dim=(2, 3)) + targets.sum(dim=(2, 3)) + smooth)
        return bce_loss + dice_loss.mean()


# ─── Training Loop ────────────────────────────────────────────────────────────
def train(epochs: int = 50, batch_size: int = 8, lr: float = 1e-3,
          img_size: int = 352, root: Path = Path(".")) -> None:

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n{'='*55}")
    print(f"  PraNet Training on Kvasir-SEG")
    print(f"  Device:     {device}")
    print(f"  Epochs:     {epochs}")
    print(f"  Batch size: {batch_size}")
    print(f"  Image size: {img_size}x{img_size}")
    print(f"{'='*55}")

    images_dir = root / "data" / "kvasir-seg" / "images"
    masks_dir  = root / "data" / "kvasir-seg" / "masks"

    if not images_dir.exists():
        print("[ERROR] Kvasir-SEG not found. Run: python src/download_kvasir.py")
        sys.exit(1)

    # 80/20 train/val split
    all_paths = sorted([p for p in images_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS])
    n_train   = int(0.8 * len(all_paths))
    train_imgs = images_dir
    val_imgs   = images_dir

    full_dataset = KvasirSEGDataset(images_dir, masks_dir, img_size=img_size, augment=True)
    val_dataset  = KvasirSEGDataset(images_dir, masks_dir, img_size=img_size, augment=False)

    # Use first 800 for train, last 200 for val
    train_set = torch.utils.data.Subset(full_dataset, range(n_train))
    val_set   = torch.utils.data.Subset(val_dataset,  range(n_train, len(full_dataset)))

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True,  num_workers=0, pin_memory=True)
    val_loader   = DataLoader(val_set,   batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=True)

    model     = PraNetMicroRefiner(channels=24).to(device)
    criterion = DiceBCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr * 0.01)

    weights_dir = root / "weights"
    weights_dir.mkdir(exist_ok=True)
    best_dice = 0.0
    best_path = weights_dir / "pranet_kvasir_best.pth"

    for epoch in range(1, epochs + 1):
        # ── Train ──
        model.train()
        train_loss = 0.0
        for imgs, masks in train_loader:
            imgs, masks = imgs.to(device), masks.to(device)
            optimizer.zero_grad()
            logits = model(imgs)
            loss   = criterion(logits, masks)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        scheduler.step()
        train_loss /= len(train_loader)

        # ── Validate ──
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

        print(f"  Epoch [{epoch:3d}/{epochs}] | Loss: {train_loss:.4f} | Val Dice: {mean_dice:.4f} | Val IoU: {mean_iou:.4f} | LR: {lr_now:.6f}", flush=True)

        # Save best model
        if mean_dice > best_dice:
            best_dice = mean_dice
            torch.save(model.state_dict(), best_path)
            print(f"  *** New best Dice: {best_dice:.4f} -> saved to {best_path}")

    print(f"\n{'='*55}")
    print(f"  Training Complete!")
    print(f"  Best Val Dice: {best_dice:.4f}")
    print(f"  Weights saved: {best_path}")
    print(f"  Next step: python src/benchmark_kvasir.py --weights {best_path}")
    print(f"{'='*55}")


def main():
    parser = argparse.ArgumentParser(description="Train PraNet on Kvasir-SEG")
    parser.add_argument("--epochs",    type=int,   default=50)
    parser.add_argument("--batch",     type=int,   default=8)
    parser.add_argument("--lr",        type=float, default=1e-3)
    parser.add_argument("--img_size",  type=int,   default=352)
    args = parser.parse_args()
    root = Path(__file__).parent.parent
    train(epochs=args.epochs, batch_size=args.batch, lr=args.lr, img_size=args.img_size, root=root)


if __name__ == "__main__":
    main()
