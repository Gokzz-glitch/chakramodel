"""
eval_engine.py
==============
Core evaluation engine.

Strategy: MAXIMUM STRESS on ALL hardware simultaneously.
- ViT-Large and PraNet run in PARALLEL CUDA streams (or separate GPUs).
- CPU preprocessing saturates all cores via DataLoader workers.
- FP16 autocast everywhere — no FP32 fallbacks.
- torch.compile enabled if PyTorch >= 2.0.
- Non-blocking GPU transfers throughout.
- Metrics computed on-GPU with torch ops — zero numpy round-trips during inference.

INTEGRITY: No hardcoded model paths beyond what is passed in as CLI args.
Compliant with ml-integrity-standards.md Rules 3, 4, 5, 6.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

# Internal modules
from dataset_discovery import DatasetMeta, build_dataloader
from resource_monitor import ResourceMonitor

# ── GPU topology detection ────────────────────────────────────────────────────
N_GPUS = torch.cuda.device_count()
DEVICE_VIT   = torch.device("cuda:0" if N_GPUS >= 1 else "cpu")
DEVICE_PRANET = torch.device("cuda:1" if N_GPUS >= 2 else DEVICE_VIT)
MULTI_GPU    = N_GPUS >= 2

print(f"[Engine] Detected {N_GPUS} GPU(s).")
print(f"[Engine] ViT-Large → {DEVICE_VIT} | PraNet → {DEVICE_PRANET}")
print(f"[Engine] Multi-GPU parallel mode: {MULTI_GPU}")


# ── model loading (strict, with provenance logging) ──────────────────────────
def _load_checkpoint(model: nn.Module, ckpt_path: str | Path, device: torch.device) -> nn.Module:
    """
    Load a .pth checkpoint with full integrity checks.
    Compliant with ml-integrity-standards.md Rule 1 (strict loading) and
    Rule 5 (safe serialization).
    """
    ckpt_path = Path(ckpt_path)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    sd = torch.load(str(ckpt_path), map_location=device, weights_only=True)

    # Unwrap DDP `module.` prefix if present
    if all(k.startswith("module.") for k in sd.keys()):
        sd = {k[len("module."):]: v for k, v in sd.items()}

    # Known layer renames between older checkpoints and the current model
    # definition. `ppd_pred` -> `ppd_out`: PraNet's global-guidance prediction
    # head (nn.Conv2d producing s_g, which seeds the entire ra4->ra3->ra2
    # reverse-attention cascade) was renamed at some point. Without this
    # remap, strict=False silently random-initializes this load-bearing head
    # every run instead of raising OR loading the real trained weights that
    # are sitting right there in the checkpoint under the old name.
    _key_renames = {
        "ppd_pred.weight": "ppd_out.weight",
        "ppd_pred.bias":   "ppd_out.bias",
    }
    model_keys = set(model.state_dict().keys())
    for old_key, new_key in _key_renames.items():
        if old_key in sd and new_key not in sd and new_key in model_keys:
            sd[new_key] = sd.pop(old_key)
            print(f"  [FIX] Remapped renamed checkpoint key: {old_key} -> {new_key}")

    missing, unexpected = model.load_state_dict(sd, strict=False)

    # Rule 1 (strict loading): a missing/unexpected key in the DECODER/HEAD is an
    # architecture mismatch, not a benign partial load — it means this checkpoint
    # was trained with a different model class than the one being evaluated, and
    # silently continuing randomly-initializes the head, producing plausible but
    # meaningless Dice/IoU numbers (see ml-integrity-standards.md §6 incident:
    # DSC crashed to 0.1835 from exactly this kind of silent prefix mismatch).
    # Backbone-only partial loads (e.g. pretrained-encoder init) are still allowed.
    _head_prefixes = ("decode_head", "stage1", "stage2", "stage3", "stage4", "head", "decoder", "ppd", "ra1", "ra2", "ra3", "ra4")
    bad_missing    = [k for k in missing    if k.startswith(_head_prefixes)]
    bad_unexpected = [k for k in unexpected if k.startswith(_head_prefixes)]
    if bad_missing or bad_unexpected:
        raise RuntimeError(
            f"Checkpoint/model architecture mismatch loading {ckpt_path.name}: "
            f"decoder/head keys do not match model definition.\n"
            f"  Missing (head/decoder):    {bad_missing}\n"
            f"  Unexpected (head/decoder): {bad_unexpected}\n"
            f"This checkpoint was almost certainly trained with a different decoder "
            f"architecture. Refusing to load with strict=False on head/decoder keys — "
            f"loading would silently randomly-initialize the head and produce invalid metrics."
        )

    if missing:
        print(f"  [WARN] Missing keys in {ckpt_path.name} (non-head, allowed): {missing[:5]}{'...' if len(missing)>5 else ''}")
    if unexpected:
        print(f"  [WARN] Unexpected keys in {ckpt_path.name} (non-head, allowed): {unexpected[:5]}{'...' if len(unexpected)>5 else ''}")
    if not missing and not unexpected:
        print(f"  [OK] {ckpt_path.name} loaded clean (no missing/unexpected keys).")

    model = model.to(device).eval()

    # torch.compile — fuses kernels, reduces launch overhead
    pt_version = tuple(int(x) for x in torch.__version__.split(".")[:2] if x.isdigit())
    if pt_version >= (2, 0):
        try:
            model = torch.compile(model, mode="default", fullgraph=False)
            print(f"  [OK] torch.compile applied to {ckpt_path.name}.")
        except Exception as e:
            print(f"  [WARN] torch.compile failed ({e}), using eager mode.")
    return model


def load_models(
    vit_ckpt: str | Path,
    pranet_ckpt: str | Path,
) -> Tuple[nn.Module, nn.Module]:
    """
    Import model classes dynamically (keeps this file free of hard imports)
    and load weights onto their designated devices.
    """
    # Add project src to path dynamically — no hardcoded paths
    project_root = Path(__file__).resolve().parents[1]
    for candidate in ["src", "src/chakra_transformer", "src/models"]:
        p = project_root / candidate
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))

    # ViT-Large segmenter
    from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter
    vit = ChakraTransformerSegmenter()
    print(f"\n[Engine] Loading ViT-Large from {Path(vit_ckpt).name} → {DEVICE_VIT}")
    vit = _load_checkpoint(vit, vit_ckpt, DEVICE_VIT)

    # PraNet
    from models.pranet_resnet101 import PraNetResNet101
    pranet = PraNetResNet101()
    print(f"[Engine] Loading PraNet from {Path(pranet_ckpt).name} → {DEVICE_PRANET}")
    pranet = _load_checkpoint(pranet, pranet_ckpt, DEVICE_PRANET)

    return vit, pranet


# ── per-batch metric ops (GPU-native) ─────────────────────────────────────────
def _dice(pred_bin: torch.Tensor, gt: torch.Tensor, eps: float = 1e-7) -> torch.Tensor:
    """Batch-level Dice. pred_bin and gt are [B,1,H,W] binary tensors."""
    inter = (pred_bin * gt).sum(dim=(1, 2, 3))
    union = pred_bin.sum(dim=(1, 2, 3)) + gt.sum(dim=(1, 2, 3))
    return ((2 * inter + eps) / (union + eps)).mean()


def _boundary_iou(pred_bin: torch.Tensor, gt: torch.Tensor, eps: float = 1e-7) -> torch.Tensor:
    """Approximate boundary IoU via dilation difference on GPU."""
    kernel = torch.ones(1, 1, 3, 3, device=pred_bin.device)
    p_boundary = (F.conv2d(pred_bin.float(), kernel, padding=1) > 0).float() - pred_bin.float()
    g_boundary = (F.conv2d(gt.float(),       kernel, padding=1) > 0).float() - gt.float()
    inter = (p_boundary * g_boundary).sum(dim=(1, 2, 3))
    union = (p_boundary + g_boundary - p_boundary * g_boundary).sum(dim=(1, 2, 3))
    return ((inter + eps) / (union + eps)).mean()


def _specificity_fpr(pred_bin: torch.Tensor, gt: torch.Tensor, eps: float = 1e-7) -> Tuple[torch.Tensor, torch.Tensor]:
    """Returns (Specificity, FPR) computed on GPU."""
    tn = ((1 - pred_bin) * (1 - gt)).sum(dim=(1, 2, 3))
    fp = (pred_bin * (1 - gt)).sum(dim=(1, 2, 3))
    neg = tn + fp + eps
    spec = (tn / neg).mean()
    fpr  = (fp / neg).mean()
    return spec, fpr


# ── CUDA stream parallel inference ────────────────────────────────────────────
def _infer_parallel(
    vit:    nn.Module,
    pranet: nn.Module,
    imgs:   torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor, float, float]:
    """
    Run ViT and PraNet on the same batch SIMULTANEOUSLY using two CUDA streams.
    If multi-GPU: each model sees images on its own device (no bus contention).
    Returns (vit_prob, pranet_prob, vit_latency_ms, pranet_latency_ms).
    All ops under FP16 autocast — no FP32 fallbacks.
    """
    # Non-blocking transfers to each model's device
    imgs_vit    = imgs.to(DEVICE_VIT,    non_blocking=True)
    imgs_pranet = imgs.to(DEVICE_PRANET, non_blocking=True)

    # Dedicated CUDA streams
    s_vit    = torch.cuda.Stream(device=DEVICE_VIT)
    s_pranet = torch.cuda.Stream(device=DEVICE_PRANET)

    vit_out    = [None]
    pranet_out = [None]
    vit_ms     = [0.0]
    pranet_ms  = [0.0]

    with torch.cuda.stream(s_vit):
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            t0 = time.perf_counter()
            logits = vit(imgs_vit)
            # Handle multi-output models (some return tuple)
            if isinstance(logits, (list, tuple)):
                logits = logits[0]
            vit_out[0]  = torch.sigmoid(logits).detach()
            vit_ms[0]   = (time.perf_counter() - t0) * 1000

    with torch.cuda.stream(s_pranet):
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            t0 = time.perf_counter()
            out = pranet(imgs_pranet)
            if isinstance(out, (list, tuple)):
                out = out[-1]   # PraNet returns multi-scale; take finest
            pranet_out[0] = torch.sigmoid(out).detach()
            pranet_ms[0]  = (time.perf_counter() - t0) * 1000

    # Synchronise both streams before reading results
    torch.cuda.synchronize(DEVICE_VIT)
    torch.cuda.synchronize(DEVICE_PRANET)

    return vit_out[0], pranet_out[0], vit_ms[0], pranet_ms[0]


# ── main evaluation loop ──────────────────────────────────────────────────────
def evaluate_dataset(
    meta:         DatasetMeta,
    vit:          nn.Module,
    pranet:       nn.Module,
    monitor:      ResourceMonitor,
    threshold:    float = 0.45,
) -> Dict:
    """
    Evaluate one dataset with both models. Returns a result dict.
    Batch size and num_workers are read live from ResourceMonitor.
    """
    print(f"\n{'='*70}")
    print(f"[Eval] Dataset : {meta.name}  ({meta.frame_count} frames, {meta.kind.name})")
    print(f"{'='*70}")

    vit_dice_acc    = vit_biou_acc    = vit_spec_acc    = vit_fpr_acc    = 0.0
    pranet_dice_acc = pranet_biou_acc = pranet_spec_acc = pranet_fpr_acc = 0.0
    vit_latencies:    List[float] = []
    pranet_latencies: List[float] = []
    n_batches = 0

    dataset_start = time.perf_counter()

    # Rebuild loader each dataset — batch size may have grown since last run
    batch_size  = monitor.recommended_batch_size
    num_workers = monitor.recommended_num_workers
    loader = build_dataloader(meta, batch_size=batch_size, num_workers=num_workers)
    print(f"[Eval] Initial batch={batch_size}, workers={num_workers}")

    for batch_idx, (imgs, masks, _) in enumerate(loader):
        # Fetch updated batch from monitor (may have grown mid-dataset)
        new_bs = monitor.recommended_batch_size
        if new_bs != batch_size:
            # Rebuild loader with new batch size if it changed significantly
            if abs(new_bs - batch_size) >= 4:
                batch_size = new_bs
                loader = build_dataloader(meta, batch_size=batch_size, num_workers=num_workers)
                print(f"[Eval] Batch size ramped → {batch_size}")

        vit_prob, pranet_prob, vit_ms, pranet_ms = _infer_parallel(vit, pranet, imgs)

        # Resize masks to match output if needed
        gt_vit    = masks.to(DEVICE_VIT,    non_blocking=True)
        gt_pranet = masks.to(DEVICE_PRANET, non_blocking=True)
        if gt_vit.shape[-2:] != vit_prob.shape[-2:]:
            gt_vit = F.interpolate(gt_vit, size=vit_prob.shape[-2:], mode="nearest")
        if gt_pranet.shape[-2:] != pranet_prob.shape[-2:]:
            gt_pranet = F.interpolate(gt_pranet, size=pranet_prob.shape[-2:], mode="nearest")

        # Binarise
        vit_bin    = (vit_prob    > threshold).float()
        pranet_bin = (pranet_prob > threshold).float()
        gt_vit_bin    = (gt_vit    > 0.5).float()
        gt_pranet_bin = (gt_pranet > 0.5).float()

        # Accumulate metrics (GPU tensors → Python scalars only when aggregating)
        vit_dice_acc    += _dice(vit_bin, gt_vit_bin).item()
        vit_biou_acc    += _boundary_iou(vit_bin, gt_vit_bin).item()
        vs, vf           = _specificity_fpr(vit_bin, gt_vit_bin)
        vit_spec_acc    += vs.item();  vit_fpr_acc    += vf.item()

        pranet_dice_acc    += _dice(pranet_bin, gt_pranet_bin).item()
        pranet_biou_acc    += _boundary_iou(pranet_bin, gt_pranet_bin).item()
        ps, pf              = _specificity_fpr(pranet_bin, gt_pranet_bin)
        pranet_spec_acc    += ps.item(); pranet_fpr_acc += pf.item()

        vit_latencies.append(vit_ms)
        pranet_latencies.append(pranet_ms)
        n_batches += 1

        if batch_idx % 20 == 0:
            hw = monitor.latest_readings
            print(
                f"  batch {batch_idx:5d} | "
                f"ViT {vit_ms:6.1f}ms | PraNet {pranet_ms:6.1f}ms | "
                f"VRAM {hw.get('max_gpu_vram_pct',0):.0f}% | "
                f"CPU {hw.get('cpu_pct',0):.0f}% | bs={hw.get('batch_size',batch_size)}"
            )

    total_s = time.perf_counter() - dataset_start

    if n_batches == 0:
        return {"dataset": meta.name, "error": "no_batches"}

    vit_lat_arr    = np.array(vit_latencies)
    pranet_lat_arr = np.array(pranet_latencies)

    def fps(lat_arr, bs): return (1000.0 / lat_arr.mean()) * bs if lat_arr.mean() > 0 else 0.0

    result = {
        "dataset":     meta.name,
        "dataset_kind": meta.kind.name,
        "frame_count":  meta.frame_count,
        "total_runtime_s": round(total_s, 2),
        "vit_large": {
            "dice":         round(vit_dice_acc    / n_batches, 6),
            "boundary_iou": round(vit_biou_acc    / n_batches, 6),
            "specificity":  round(vit_spec_acc    / n_batches, 6),
            "fpr":          round(vit_fpr_acc     / n_batches, 6),
            "fps_avg":      round(fps(vit_lat_arr, batch_size), 2),
            "fps_p95":      round((1000.0 / np.percentile(vit_lat_arr, 95)) * batch_size, 2),
            "latency_avg_ms": round(float(vit_lat_arr.mean()), 2),
        },
        "pranet": {
            "dice":         round(pranet_dice_acc    / n_batches, 6),
            "boundary_iou": round(pranet_biou_acc    / n_batches, 6),
            "specificity":  round(pranet_spec_acc    / n_batches, 6),
            "fpr":          round(pranet_fpr_acc     / n_batches, 6),
            "fps_avg":      round(fps(pranet_lat_arr, batch_size), 2),
            "fps_p95":      round((1000.0 / np.percentile(pranet_lat_arr, 95)) * batch_size, 2),
            "latency_avg_ms": round(float(pranet_lat_arr.mean()), 2),
        },
        "hw_snapshot": monitor.latest_readings,
    }
    return result


def run_full_evaluation(
    datasets:    List[DatasetMeta],
    vit:         nn.Module,
    pranet:      nn.Module,
    monitor:     ResourceMonitor,
    output_dir:  Path,
    threshold:   float = 0.45,
) -> Path:
    """
    Evaluate all datasets and write timestamped JSON.
    Every metric comes from real tensor computations — no interpolation.
    Compliant with ml-integrity-standards.md Rule 3 (Metric Provenance).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"evaluation_results_{ts}.json"

    all_results = []
    for meta in datasets:
        res = evaluate_dataset(meta, vit, pranet, monitor, threshold)
        all_results.append(res)
        # Write incrementally — never lose data on crash
        with open(out_path, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"[Eval] Results saved → {out_path}")

    return out_path
