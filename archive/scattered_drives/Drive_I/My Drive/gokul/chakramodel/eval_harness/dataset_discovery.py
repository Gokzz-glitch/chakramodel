"""
dataset_discovery.py
====================
Zero-hardcoding universal dataset scanner.

Recursively scans any root directory (default: /kaggle/input) and
auto-classifies every subfolder as IMAGE, VIDEO, PAIRED (image+mask),
or UNKNOWN. Returns ready-to-use PyTorch Datasets.

NO hardcoded dataset names, paths, or URLs anywhere in this file.
Compliant with ml-integrity-standards.md Rule 6 (Zero Hardcoding).
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

# ── constants ────────────────────────────────────────────────────────────────
IMAGE_EXTS  = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS  = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
MASK_HINTS  = {"mask", "gt", "ground_truth", "label", "seg", "anno"}
SEED        = 42
TARGET_SIZE = (384, 384)   # both models expect 384×384

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

_norm = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])


# ── data-class ────────────────────────────────────────────────────────────────
class DatasetKind(Enum):
    PAIRED_IMAGE = auto()   # image + paired mask found
    IMAGE_ONLY   = auto()   # images, no masks
    VIDEO        = auto()   # mp4 / avi etc.
    UNKNOWN      = auto()


@dataclass
class DatasetMeta:
    name:       str
    root:       Path
    kind:       DatasetKind
    img_paths:  List[Path] = field(default_factory=list)
    mask_paths: List[Path] = field(default_factory=list)   # parallel to img_paths
    video_paths: List[Path] = field(default_factory=list)
    frame_count: int = 0


# ── discovery ─────────────────────────────────────────────────────────────────
def discover(root: str | Path = "/kaggle/input") -> List[DatasetMeta]:
    """
    Recursively scan `root` and return one DatasetMeta per discovered dataset.
    Works on any directory — no dataset names are referenced.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"Input root not found: {root}")

    metas: List[DatasetMeta] = []

    # Each immediate child of root is treated as one dataset
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        meta = _classify(child)
        if meta.kind == DatasetKind.VIDEO:
            print(f"  [DISCOVER] {meta.name:40s} | {meta.kind.name:15s} | SKIPPED (No ground truth masks for video)")
            continue
        if meta.kind != DatasetKind.UNKNOWN and meta.frame_count > 0:
            metas.append(meta)
            print(f"  [DISCOVER] {meta.name:40s} | {meta.kind.name:15s} | {meta.frame_count:6d} frames")

    if not metas:
        raise RuntimeError(f"No usable datasets found under {root}")
    return metas


def _classify(folder: Path) -> DatasetMeta:
    """Walk folder, classify content, build file lists."""
    all_files = list(folder.rglob("*"))
    images  = sorted(p for p in all_files if p.suffix.lower() in IMAGE_EXTS)
    videos  = sorted(p for p in all_files if p.suffix.lower() in VIDEO_EXTS)

    # Heuristic: a file is a "mask" if its parent folder name or filename
    # contains any of the MASK_HINTS strings (case-insensitive).
    def _is_mask(p: Path) -> bool:
        tokens = (p.stem + p.parent.name).lower()
        return any(h in tokens for h in MASK_HINTS)

    masks  = [p for p in images if _is_mask(p)]
    imgs   = [p for p in images if not _is_mask(p)]

    name = folder.name

    if imgs and masks:
        # Try to pair images → masks by matching stem
        paired_imgs, paired_masks = _pair(imgs, masks)
        return DatasetMeta(
            name=name, root=folder,
            kind=DatasetKind.PAIRED_IMAGE,
            img_paths=paired_imgs, mask_paths=paired_masks,
            frame_count=len(paired_imgs),
        )
    elif videos:
        total_frames = 0
        for v in videos:
            cap = cv2.VideoCapture(str(v))
            total_frames += int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
        return DatasetMeta(
            name=name, root=folder,
            kind=DatasetKind.VIDEO,
            video_paths=videos, frame_count=total_frames,
        )
    elif imgs:
        return DatasetMeta(
            name=name, root=folder,
            kind=DatasetKind.IMAGE_ONLY,
            img_paths=imgs, frame_count=len(imgs),
        )
    return DatasetMeta(name=name, root=folder, kind=DatasetKind.UNKNOWN)


def _pair(imgs: List[Path], masks: List[Path]) -> Tuple[List[Path], List[Path]]:
    """Match images to masks by stem; drop unpaired."""
    mask_by_stem = {p.stem.lower().replace("_gt", "").replace("_mask", ""): p
                    for p in masks}
    paired_i, paired_m = [], []
    for img in imgs:
        key = img.stem.lower()
        if key in mask_by_stem:
            paired_i.append(img)
            paired_m.append(mask_by_stem[key])
    return paired_i, paired_m


# ── PyTorch Datasets ──────────────────────────────────────────────────────────
class PairedImageDataset(Dataset):
    """Returns (img_tensor [3,384,384], mask_tensor [1,384,384], path_str)."""

    def __init__(self, meta: DatasetMeta):
        self.imgs  = meta.img_paths
        self.masks = meta.mask_paths

    def __len__(self): return len(self.imgs)

    def __getitem__(self, idx):
        img  = _load_image(self.imgs[idx])
        mask = _load_mask(self.masks[idx])
        return img, mask, str(self.imgs[idx])


class ImageOnlyDataset(Dataset):
    """Returns (img_tensor [3,384,384], dummy_mask [1,384,384], path_str)."""

    def __init__(self, meta: DatasetMeta):
        self.imgs = meta.img_paths

    def __len__(self): return len(self.imgs)

    def __getitem__(self, idx):
        img  = _load_image(self.imgs[idx])
        mask = torch.zeros(1, *TARGET_SIZE)
        return img, mask, str(self.imgs[idx])


class VideoDataset(Dataset):
    """
    Streams every frame from a list of video files.
    Index is (video_idx, frame_idx) linearised.
    """

    def __init__(self, meta: DatasetMeta, max_frames: int = 0):
        self.video_paths = meta.video_paths
        self._index: List[Tuple[int, int]] = []

        for vi, vp in enumerate(self.video_paths):
            cap = cv2.VideoCapture(str(vp))
            n   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            for fi in range(n):
                self._index.append((vi, fi))
                if max_frames and len(self._index) >= max_frames:
                    break
            if max_frames and len(self._index) >= max_frames:
                break

    def __len__(self): return len(self._index)

    def __getitem__(self, idx):
        vi, fi = self._index[idx]
        cap = cv2.VideoCapture(str(self.video_paths[vi]))
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            frame = np.zeros((384, 384, 3), dtype=np.uint8)
        img  = _frame_to_tensor(frame)
        mask = torch.zeros(1, *TARGET_SIZE)
        label = f"{self.video_paths[vi].name}:frame{fi}"
        return img, mask, label


# ── helpers ───────────────────────────────────────────────────────────────────
def _load_image(path: Path) -> torch.Tensor:
    img = cv2.imread(str(path))
    if img is None:
        return torch.zeros(3, *TARGET_SIZE)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, TARGET_SIZE)
    return _norm(img)


def _frame_to_tensor(frame: np.ndarray) -> torch.Tensor:
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame = cv2.resize(frame, TARGET_SIZE)
    return _norm(frame)


def _load_mask(path: Path) -> torch.Tensor:
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return torch.zeros(1, *TARGET_SIZE)
    mask = cv2.resize(mask, TARGET_SIZE, interpolation=cv2.INTER_NEAREST)
    t = torch.from_numpy(mask).float() / 255.0
    return t.unsqueeze(0)


def build_dataloader(meta: DatasetMeta, batch_size: int, num_workers: int) -> DataLoader:
    """Construct the right Dataset and return a maxed-out DataLoader."""
    if meta.kind == DatasetKind.PAIRED_IMAGE:
        ds = PairedImageDataset(meta)
    elif meta.kind == DatasetKind.IMAGE_ONLY:
        ds = ImageOnlyDataset(meta)
    elif meta.kind == DatasetKind.VIDEO:
        ds = VideoDataset(meta)
    else:
        raise ValueError(f"Unknown dataset kind: {meta.kind}")

    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,                # DMA directly to GPU memory
        persistent_workers=(num_workers > 0),
        prefetch_factor=4 if num_workers > 0 else None,  # pre-load 4 batches
        drop_last=False,
    )
