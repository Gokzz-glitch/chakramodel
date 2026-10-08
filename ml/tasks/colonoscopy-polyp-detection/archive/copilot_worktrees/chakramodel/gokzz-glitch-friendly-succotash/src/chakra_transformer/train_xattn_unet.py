"""Cloud-GPU training entry point for ChakraXAttnUNet.

Example (Kaggle/Colab):
  python src/chakra_transformer/train_xattn_unet.py \
      --images /kaggle/input/polypgen/images --masks /kaggle/input/polypgen/masks \
      --output /kaggle/working/xattn --epochs 60 --batch-size 8
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset, random_split
import torchvision.transforms as T

from xattn_unet import ChakraXAttnUNet


EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


class PairedSegmentationDataset(Dataset):
    def __init__(self, images: Path, masks: Path, size: int, augment: bool) -> None:
        self.images, self.masks, self.size, self.augment = images, masks, size, augment
        self.paths = sorted(p for p in images.rglob("*") if p.suffix.lower() in EXTS)
        self.jitter = T.ColorJitter(.25, .25, .25, .05)
        self.mean = torch.tensor([.485, .456, .406]).view(3, 1, 1)
        self.std = torch.tensor([.229, .224, .225]).view(3, 1, 1)

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        image_path = self.paths[index]
        mask_path = next((self.masks / f"{image_path.stem}{ext}" for ext in EXTS
                          if (self.masks / f"{image_path.stem}{ext}").exists()), None)
        if mask_path is None:
            raise FileNotFoundError(f"No mask for image: {image_path}")
        image = cv2.cvtColor(cv2.imread(str(image_path)), cv2.COLOR_BGR2RGB)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        image = cv2.resize(image, (self.size, self.size), interpolation=cv2.INTER_LINEAR)
        mask = cv2.resize(mask, (self.size, self.size), interpolation=cv2.INTER_NEAREST)
        if self.augment and random.random() > .5:
            image, mask = cv2.flip(image, 1), cv2.flip(mask, 1)
        image_t = torch.from_numpy(image).permute(2, 0, 1).float() / 255
        if self.augment:
            image_t = self.jitter(image_t)
        image_t = (image_t - self.mean) / self.std
        mask_t = torch.from_numpy((mask > 127).astype("float32"))[None]
        return image_t, mask_t


def boundary_target(mask: torch.Tensor) -> torch.Tensor:
    pooled = torch.nn.functional.avg_pool2d(mask, 3, stride=1, padding=1)
    return ((pooled - mask).abs() > .05).float()


def loss_fn(outputs: dict[str, torch.Tensor], target: torch.Tensor) -> torch.Tensor:
    mask_logits = outputs["mask"]
    bce = nn.functional.binary_cross_entropy_with_logits(mask_logits, target)
    probs = mask_logits.sigmoid()
    dice = 1 - (2 * (probs * target).sum((2, 3)) + 1) / (
        probs.sum((2, 3)) + target.sum((2, 3)) + 1
    )
    boundary = nn.functional.binary_cross_entropy_with_logits(
        outputs["boundary"], boundary_target(target)
    )
    return bce + dice.mean() + .25 * boundary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, required=True,
                        help="One split directory, e.g. prepared/images/train")
    parser.add_argument("--masks", type=Path, required=True,
                        help="Matching mask directory, e.g. prepared/masks/train")
    parser.add_argument("--val-images", type=Path,
                        help="Optional leakage-safe validation image directory")
    parser.add_argument("--val-masks", type=Path,
                        help="Optional leakage-safe validation mask directory")
    parser.add_argument("--output", type=Path, default=Path("runs/xattn_unet"))
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--size", type=int, default=352)
    parser.add_argument("--val-fraction", type=float, default=.2)
    parser.add_argument("--grad-accum", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("A CUDA cloud GPU is required; CPU training is intentionally disabled.")
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    train_dataset = PairedSegmentationDataset(args.images, args.masks, args.size, True)
    if bool(args.val_images) != bool(args.val_masks):
        raise ValueError("--val-images and --val-masks must be supplied together")
    if args.val_images and args.val_masks:
        train_set = train_dataset
        val_set = PairedSegmentationDataset(args.val_images, args.val_masks, args.size, False)
    else:
        val_dataset = PairedSegmentationDataset(args.images, args.masks, args.size, False)
        val_len = max(1, int(len(train_dataset) * args.val_fraction))
        train_len = len(train_dataset) - val_len
        indices = torch.randperm(len(train_dataset),
                                 generator=torch.Generator().manual_seed(args.seed)).tolist()
        train_set = torch.utils.data.Subset(train_dataset, indices[:train_len])
        val_set = torch.utils.data.Subset(val_dataset, indices[train_len:])
    device = torch.device("cuda")
    model = ChakraXAttnUNet(image_size=args.size).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs)
    scaler = GradScaler()
    train_loader = DataLoader(train_set, args.batch_size, shuffle=True, num_workers=4,
                              pin_memory=True, persistent_workers=True)
    val_loader = DataLoader(val_set, args.batch_size, shuffle=False, num_workers=4,
                            pin_memory=True, persistent_workers=True)
    args.output.mkdir(parents=True, exist_ok=True)
    best = -1.0
    for epoch in range(1, args.epochs + 1):
        model.train(); optimizer.zero_grad(set_to_none=True)
        for step, (images, masks) in enumerate(train_loader):
            with autocast():
                loss = loss_fn(model(images.to(device, non_blocking=True)),
                               masks.to(device, non_blocking=True)) / args.grad_accum
            scaler.scale(loss).backward()
            if (step + 1) % args.grad_accum == 0:
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True)
        scheduler.step()
        model.eval(); dices = []
        with torch.no_grad():
            for images, masks in val_loader:
                with autocast():
                    probs = model(images.to(device, non_blocking=True))["mask"].sigmoid()
                target = masks.to(device)
                inter = (probs * target).sum((2, 3))
                dices.extend(((2 * inter + 1) / (probs.sum((2, 3)) + target.sum((2, 3)) + 1)).cpu().tolist())
        score = float(np.mean(dices))
        print(f"epoch={epoch:03d} val_dice={score:.4f}", flush=True)
        if score > best:
            best = score
            torch.save({"model": model.state_dict(), "epoch": epoch, "val_dice": score},
                       args.output / "best.pt")


if __name__ == "__main__":
    main()
