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
MAX_FRAMES_PER_DATASET = 2000  # total evenly-distributed sampling budget PER
                                # DATASET FOLDER (shared across every video file
                                # inside it) — NOT per individual video file.
                                # A leaf folder can hold many short clips (e.g.
                                # Hyperkvasir's ~139 clips per part); capping
                                # each clip independently at N still yields
                                # ~139*N total frames, which defeats the point.
                                # This budget is split proportionally across
                                # files by each file's share of raw frames.

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

def _count_video_frames(path: Path) -> int:
    """
    Count frames in a video, robust to containers where OpenCV's
    CAP_PROP_FRAME_COUNT metadata is unreliable (commonly 0 for some
    mp4/H.264 files under opencv-python-headless's bundled FFmpeg build).
    Falls back to an actual grab-loop count when the metadata is 0.
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        return 0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if n > 0:
        cap.release()
        return n
    # Metadata unreliable — count by grabbing frames directly.
    n = 0
    while cap.grab():
        n += 1
    cap.release()
    return n


def _sampling_plan(videos: List[Path], total_budget: int) -> dict:
    """
    Build {video_path: sorted_set_of_wanted_frame_indices} for a WHOLE dataset
    folder's video files, spending `total_budget` frames across ALL of them
    combined (proportional to each file's share of the folder's raw frame
    count), not `total_budget` per individual file.

    Computed once and reused by both discovery (for an accurate frame_count)
    and VideoDataset (for actual decoding), so the number reported at
    discovery time always matches what evaluation actually processes.
    """
    raw_counts = {v: _count_video_frames(v) for v in videos}
    total_raw = sum(raw_counts.values())

    plan = {}
    if total_raw <= 0:
        return {v: set() for v in videos}
    if not total_budget or total_raw <= total_budget:
        # Budget covers everything — take every frame from every file.
        for v, n in raw_counts.items():
            plan[v] = set(range(n))
        return plan

    for v, n in raw_counts.items():
        if n <= 0:
            plan[v] = set()
            continue
        share = max(1, round(total_budget * n / total_raw))
        share = min(share, n)
        step = n / share
        plan[v] = {int(i * step) for i in range(share)}
    return plan


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
    Recursively scan `root` and return one DatasetMeta per LEAF dataset folder.

    A folder is registered as its own dataset the moment it directly contains
    (non-recursively) images or videos — recursion into its subfolders then
    stops there. This keeps sibling benchmarks nested under one Kaggle
    dataset slug (e.g. cvc-clinicdb/, etis-larib/, kvasir-seg/ all sitting
    under one attached "ChakraModel Evaluation Datasets" folder) as separate
    entries instead of being blended into one meta with a shared, collision-
    prone image→mask stem dictionary.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"Input root not found: {root}")

    metas: List[DatasetMeta] = []
    _discover_recursive(root, metas)

    if not metas:
        raise RuntimeError(f"No usable datasets found under {root}")
    return metas


def _discover_recursive(folder: Path, metas: List["DatasetMeta"]) -> None:
    if not folder.is_dir():
        return

    meta = _classify(folder)
    if meta.kind != DatasetKind.UNKNOWN and meta.frame_count > 0:
        metas.append(meta)
        print(f"  [DISCOVER] {meta.name:40s} | {meta.kind.name:15s} | {meta.frame_count:6d} frames")
        return  # this folder IS a dataset — don't also register its children

    if meta.kind == DatasetKind.VIDEO and meta.frame_count == 0 and meta.video_paths:
        print(
            f"  [WARN] {folder.name}: found {len(meta.video_paths)} video file(s) but "
            f"cv2 reported 0 total frames (likely a missing FFmpeg backend in "
            f"opencv-python-headless) — this dataset is being SKIPPED, not because "
            f"it's unsupported. See the note in run_eval.py output."
        )
        return

    # Not a usable leaf itself — recurse into children looking for one.
    try:
        children = sorted(p for p in folder.iterdir() if p.is_dir())
    except (PermissionError, OSError):
        return
    for child in children:
        _discover_recursive(child, metas)


def _classify(folder: Path) -> DatasetMeta:
    """
    Classify content belonging to `folder` as ONE leaf dataset.

    Looks at files directly inside `folder` PLUS one extra level down
    (folder/images/*.jpg, folder/masks/*.png is the single most common
    layout) — but does NOT rglob arbitrarily deep, so a parent folder that
    bundles multiple distinct benchmark subfolders (cvc-clinicdb/,
    etis-larib/, kvasir-seg/) is never treated as one blended dataset here;
    _discover_recursive() instead recurses into each of those and classifies
    them individually.
    """
    try:
        direct_children = list(folder.iterdir())
    except (PermissionError, OSError):
        return DatasetMeta(name=folder.name, root=folder, kind=DatasetKind.UNKNOWN)

    all_files = [p for p in direct_children if p.is_file()]
    for sub in direct_children:
        if sub.is_dir():
            all_files.extend(p for p in sub.iterdir() if p.is_file())

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
        plan = _sampling_plan(videos, MAX_FRAMES_PER_DATASET)
        total_frames = sum(len(idxs) for idxs in plan.values())
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


class VideoDataset(torch.utils.data.IterableDataset):
    """
    Streams frames from a list of video files SEQUENTIALLY (cap.read() in a
    forward loop, never cap.set(CAP_PROP_POS_FRAMES, ...)).

    The old map-style implementation re-opened the video and SEEKED to frame
    `fi` on every single __getitem__ call. For compressed codecs (H.264/VC1)
    a seek forces the decoder back to the nearest keyframe and re-decodes
    forward from there — for a 500K+ frame video that is ~500K individual
    seek-and-decode operations, which is what actually caused multi-hour
    runs with zero output (not just the VC1 decoder warnings themselves).

    The `total_budget` frames are shared across ALL video files in this
    dataset (proportional to each file's raw length via `_sampling_plan`),
    not applied per individual file — a folder holding many short clips
    (e.g. Hyperkvasir's ~139 clips per part) would otherwise still process
    file_count * budget frames, defeating the point of the cap.

    Videos are split across DataLoader workers (each worker owns whole
    videos, decoded sequentially within itself) via get_worker_info().
    """

    def __init__(self, meta: DatasetMeta, total_budget: int = MAX_FRAMES_PER_DATASET):
        self.video_paths = meta.video_paths
        plan_dict = _sampling_plan(self.video_paths, total_budget)
        self._plan: List[Tuple[Path, set]] = [(vp, plan_dict.get(vp, set())) for vp in self.video_paths]
        self._total = sum(len(idxs) for _, idxs in self._plan)

    def __len__(self):
        return self._total

    def __iter__(self) -> Iterator:
        worker_info = torch.utils.data.get_worker_info()
        if worker_info is None:
            my_plan = self._plan
        else:
            # Split whole videos across workers — each worker decodes its
            # own videos sequentially, no cross-worker seeking needed.
            my_plan = self._plan[worker_info.id::worker_info.num_workers]

        for vp, wanted in my_plan:
            if not wanted:
                continue
            cap = cv2.VideoCapture(str(vp))
            if not cap.isOpened():
                continue
            fi = 0
            max_wanted = max(wanted)
            while fi <= max_wanted:
                ok, frame = cap.read()  # sequential decode — no seeking
                if not ok:
                    break
                if fi in wanted:
                    img = _frame_to_tensor(frame)
                    mask = torch.zeros(1, *TARGET_SIZE)
                    label = f"{vp.name}:frame{fi}"
                    yield img, mask, label
                fi += 1
            cap.release()


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
