import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
from chakra_transformer.student_segmenter import ChakraLiveStudent
from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter
from train_pranet import DiceFocalLoss, KvasirSEGDataset


def boundary_map(mask):
    pooled = F.max_pool2d(mask, 3, stride=1, padding=1)
    eroded = -F.max_pool2d(-mask, 3, stride=1, padding=1)
    return (pooled - eroded).clamp(0, 1)


def load_teacher(path, device, backbone_name, pretrained):
    teacher = ChakraTransformerSegmenter(
        backbone_name=backbone_name, pretrained=pretrained
    ).to(device)
    if path:
        checkpoint = torch.load(path, map_location=device)
        state = checkpoint.get("model", checkpoint.get("state_dict", checkpoint))
        missing, unexpected = teacher.load_state_dict(state, strict=False)
        if missing or unexpected:
            raise RuntimeError(
                f"Teacher checkpoint is incompatible: missing={len(missing)}, "
                f"unexpected={len(unexpected)}"
            )
    teacher.eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    return teacher


def main():
    parser = argparse.ArgumentParser(description="Distill Chakra ViT teacher into a live student")
    parser.add_argument("--teacher-checkpoint", type=Path)
    parser.add_argument("--teacher-backbone", default="vit_large_patch16_384")
    parser.add_argument("--teacher-no-pretrained", action="store_true")
    parser.add_argument("--student-backbone", default="mobilenetv3_small_100")
    parser.add_argument("--student-no-pretrained", action="store_true")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--grad-accum", type=int, default=2)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--temperature", type=float, default=2.0)
    parser.add_argument("--img-size", type=int, default=352)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "weights")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for Combo 4 distillation")
    device = torch.device("cuda")
    images = REPO_ROOT / "data/kvasir-seg/images"
    masks = REPO_ROOT / "data/kvasir-seg/masks"
    if not images.exists() or not masks.exists():
        raise FileNotFoundError("Run src/download_kvasir.py or prepare the Kaggle dataset first")

    train_data = KvasirSEGDataset(images, masks, img_size=args.img_size, augment=True)
    val_data = KvasirSEGDataset(images, masks, img_size=args.img_size, augment=False)
    split = int(len(train_data) * 0.8)
    train_loader = DataLoader(
        torch.utils.data.Subset(train_data, range(split)),
        batch_size=args.batch_size, shuffle=True, num_workers=args.workers,
        pin_memory=True, persistent_workers=args.workers > 0,
    )
    val_loader = DataLoader(
        torch.utils.data.Subset(val_data, range(split, len(val_data))),
        batch_size=args.batch_size, shuffle=False, num_workers=args.workers,
        pin_memory=True, persistent_workers=args.workers > 0,
    )

    teacher = load_teacher(
        args.teacher_checkpoint,
        device,
        args.teacher_backbone,
        pretrained=not args.teacher_no_pretrained,
    )
    student = ChakraLiveStudent(
        backbone_name=args.student_backbone,
        pretrained=not args.student_no_pretrained,
    ).to(device)
    optimizer = torch.optim.AdamW(student.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs)
    scaler = torch.cuda.amp.GradScaler()
    segmentation_loss = DiceFocalLoss()
    best_dice = 0.0
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "teacher_backbone": args.teacher_backbone,
        "student_backbone": args.student_backbone,
        "image_size": args.img_size,
        "temperature": args.temperature,
        "loss_weights": {"ground_truth": 0.5, "teacher_logits": 0.4, "boundary": 0.1},
        "seed": args.seed,
    }
    (output / "combo4_distill_config.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    for epoch in range(1, args.epochs + 1):
        student.train()
        optimizer.zero_grad(set_to_none=True)
        running = 0.0
        for step, (images_batch, masks_batch) in enumerate(train_loader):
            images_batch = images_batch.to(device, non_blocking=True)
            masks_batch = masks_batch.to(device, non_blocking=True)
            with torch.no_grad(), torch.cuda.amp.autocast():
                teacher_logits = teacher(images_batch)
            with torch.cuda.amp.autocast():
                student_logits = student(images_batch)
                ground_truth = segmentation_loss(student_logits, masks_batch)
                soft = F.binary_cross_entropy_with_logits(
                    student_logits / args.temperature,
                    torch.sigmoid(teacher_logits / args.temperature),
                ) * args.temperature ** 2
                boundary = F.l1_loss(
                    boundary_map(torch.sigmoid(student_logits)),
                    boundary_map(masks_batch),
                )
                loss = (0.5 * ground_truth + 0.4 * soft + 0.1 * boundary) / args.grad_accum
            scaler.scale(loss).backward()
            if (step + 1) % args.grad_accum == 0 or step + 1 == len(train_loader):
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
            running += loss.item() * args.grad_accum
        scheduler.step()

        student.eval()
        dices = []
        with torch.no_grad():
            for images_batch, masks_batch in val_loader:
                logits = student(images_batch.to(device))
                predictions = (torch.sigmoid(logits).cpu().numpy() > 0.5).astype(np.uint8) * 255
                targets = (masks_batch.numpy() > 0.5).astype(np.uint8) * 255
                for prediction, target in zip(predictions[:, 0], targets[:, 0]):
                    intersection = np.logical_and(prediction, target).sum()
                    dices.append((2 * intersection + 1e-6) / (prediction.sum() + target.sum() + 1e-6))
        mean_dice = float(np.mean(dices))
        print(f"Epoch {epoch}/{args.epochs} loss={running / len(train_loader):.4f} val_dice={mean_dice:.4f}", flush=True)
        checkpoint = {
            "model": student.state_dict(),
            "epoch": epoch,
            "best_dice": best_dice,
            "config": metadata,
        }
        torch.save(student.state_dict(), output / "combo4_student_latest.pth")
        torch.save(checkpoint, output / "combo4_student_latest_checkpoint.pth")
        if mean_dice > best_dice:
            best_dice = mean_dice
            torch.save(student.state_dict(), output / "combo4_student_best.pth")
            checkpoint["best_dice"] = best_dice
            torch.save(checkpoint, output / "combo4_student_best_checkpoint.pth")


if __name__ == "__main__":
    main()
