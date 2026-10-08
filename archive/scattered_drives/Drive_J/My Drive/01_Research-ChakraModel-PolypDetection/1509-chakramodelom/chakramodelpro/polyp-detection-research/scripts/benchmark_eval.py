"""
benchmark_eval.py — Full evaluation on the 5 standard polyp segmentation test sets.

Compares your model against published SOTA numbers from:
  PraNet (MICCAI 2020), SANet (ICCV 2021), Polyp-PVT (2021),
  HarDNet-MSEG (2021), MSNet (ICCV 2021), UACANet (ACM MM 2021)

Usage:
    python scripts/benchmark_eval.py \
        --checkpoint path/to/chakra_transformer_best.pth \
        --model_class ChakraTransformer \
        --data_root data/raw \
        --img_size 352

    # To run on a single dataset:
    python scripts/benchmark_eval.py --checkpoint ... --dataset etis

    # To save visual predictions:
    python scripts/benchmark_eval.py --checkpoint ... --save_preds

REQUIREMENTS:
    - pip install torch torchvision opencv-python pillow tqdm scipy
    - Datasets downloaded to data/raw/ (see data/README.md)
    - Your model class importable from src/models/

WHAT YOU NEED TO FILL IN:
    Search for "# TODO" — three places where you plug in your model class.
"""

import argparse
import json
import time
import sys
import logging
from pathlib import Path
from datetime import datetime

import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ─── Published SOTA numbers (PraNet's standard benchmark split) ──────────────
# Source: respective papers; values are mean Dice on each test set.
# These are the numbers YOUR results will be compared against.
SOTA_DICE = {
    "kvasir_test": {
        "U-Net (2015)":         0.818,
        "U-Net++ (2018)":       0.821,
        "PraNet (MICCAI'20)":   0.898,
        "MSNet (ICCV'21)":      0.907,
        "SANet (ICCV'21)":      0.904,
        "UACANet-L (ACM'21)":   0.912,
        "Polyp-PVT (2021)":     0.917,
        "HarDNet-MSEG (2021)":  0.912,
        "SSFormer-L (2022)":    0.917,
        "CFA-Net (2022)":       0.923,
    },
    "clinicdb_test": {
        "U-Net (2015)":         0.823,
        "U-Net++ (2018)":       0.794,
        "PraNet (MICCAI'20)":   0.899,
        "MSNet (ICCV'21)":      0.921,
        "SANet (ICCV'21)":      0.916,
        "UACANet-L (ACM'21)":   0.926,
        "Polyp-PVT (2021)":     0.937,
        "HarDNet-MSEG (2021)":  0.932,
        "SSFormer-L (2022)":    0.906,
        "CFA-Net (2022)":       0.935,
    },
    "colondb": {
        "U-Net (2015)":         0.512,
        "U-Net++ (2018)":       0.483,
        "PraNet (MICCAI'20)":   0.709,
        "MSNet (ICCV'21)":      0.755,
        "SANet (ICCV'21)":      0.752,
        "UACANet-L (ACM'21)":   0.751,
        "Polyp-PVT (2021)":     0.808,
        "HarDNet-MSEG (2021)":  0.731,
        "SSFormer-L (2022)":    0.802,
        "CFA-Net (2022)":       0.799,
    },
    "etis": {
        "U-Net (2015)":         0.398,
        "U-Net++ (2018)":       0.401,
        "PraNet (MICCAI'20)":   0.628,
        "MSNet (ICCV'21)":      0.719,
        "SANet (ICCV'21)":      0.750,
        "UACANet-L (ACM'21)":   0.766,
        "Polyp-PVT (2021)":     0.787,
        "HarDNet-MSEG (2021)":  0.677,
        "SSFormer-L (2022)":    0.796,
        "CFA-Net (2022)":       0.793,
    },
    "cvc300": {
        "U-Net (2015)":         0.710,
        "U-Net++ (2018)":       0.707,
        "PraNet (MICCAI'20)":   0.871,
        "MSNet (ICCV'21)":      0.869,
        "SANet (ICCV'21)":      0.888,
        "UACANet-L (ACM'21)":   0.900,
        "Polyp-PVT (2021)":     0.900,
        "HarDNet-MSEG (2021)":  0.887,
        "SSFormer-L (2022)":    0.895,
        "CFA-Net (2022)":       0.899,
    },
}

# Standard dataset directory names (relative to data_root)
DATASET_DIRS = {
    "kvasir_test":  "Kvasir-SEG/test",
    "clinicdb_test":"CVC-ClinicDB/test",
    "colondb":      "CVC-ColonDB",
    "etis":         "ETIS-LaribPolypDB",
    "cvc300":       "CVC-300",
}

# ─── Metrics ─────────────────────────────────────────────────────────────────

def dice_score(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    pred, gt = pred.astype(bool), gt.astype(bool)
    return float((2.0 * (pred & gt).sum() + eps) / (pred.sum() + gt.sum() + eps))

def iou_score(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    pred, gt = pred.astype(bool), gt.astype(bool)
    return float(((pred & gt).sum() + eps) / ((pred | gt).sum() + eps))

def f_measure(pred: np.ndarray, gt: np.ndarray, beta2: float = 0.3, eps: float = 1e-6) -> float:
    """Weighted F-measure (β²=0.3) — emphasises precision for clinical use."""
    pred, gt = pred.astype(bool), gt.astype(bool)
    tp = (pred & gt).sum()
    fp = (pred & ~gt).sum()
    fn = (~pred & gt).sum()
    precision = (tp + eps) / (tp + fp + eps)
    recall    = (tp + eps) / (tp + fn + eps)
    return float((1 + beta2) * precision * recall / (beta2 * precision + recall + eps))

def s_measure(pred: np.ndarray, gt: np.ndarray, alpha: float = 0.5) -> float:
    """S-measure — structural similarity (Fan et al. ICCV 2017)."""
    pred = pred.astype(float)
    gt   = gt.astype(float)
    # Object-aware component
    def s_object(pred, gt):
        x = pred[gt == 1].mean() if gt.sum() > 0 else 0.0
        sigma_x = pred[gt == 1].std() if gt.sum() > 0 else 0.0
        score_fg = 2 * x / (x**2 + 1 + sigma_x**2 + 1e-6)
        y = pred[gt == 0].mean() if (gt == 0).sum() > 0 else 0.0
        sigma_y = pred[gt == 0].std() if (gt == 0).sum() > 0 else 0.0
        score_bg = 2 * (1 - y) / ((1 - y)**2 + 1 + sigma_y**2 + 1e-6)
        w = gt.sum() / (gt.size + 1e-6)
        return w * score_fg + (1 - w) * score_bg
    # Region-aware: simplified 4-quadrant
    def s_region(pred, gt):
        h, w = gt.shape
        ch, cw = h // 2, w // 2
        scores = []
        for pr, gc in [(pred[:ch,:cw], gt[:ch,:cw]), (pred[:ch,cw:], gt[:ch,cw:]),
                       (pred[ch:,:cw], gt[ch:,:cw]), (pred[ch:,cw:], gt[ch:,cw:])]:
            w_q = gc.sum() / (gt.sum() + 1e-6)
            if gc.sum() > 0 or (gc == 0).sum() > 0:
                scores.append(w_q * s_object(pr, gc))
        return sum(scores)
    return float(alpha * s_object(pred, gt) + (1 - alpha) * s_region(pred, gt))


def measure_fps(model: torch.nn.Module, device: torch.device,
                img_size: int = 352, warmup: int = 20, runs: int = 200) -> float:
    """Proper GPU-synchronized FPS measurement."""
    model.eval()
    dummy = torch.randn(1, 3, img_size, img_size).to(device)
    with torch.no_grad():
        for _ in range(warmup):
            _ = model(dummy)
    if device.type == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(runs):
            _ = model(dummy)
    if device.type == "cuda":
        torch.cuda.synchronize()
    return runs / (time.perf_counter() - t0)


# ─── Dataset ─────────────────────────────────────────────────────────────────

class PolypDataset(torch.utils.data.Dataset):
    """
    Minimal dataset for evaluation — no augmentation, just resize + normalize.
    Expects structure:
        data_root/images/*.jpg (or .png)
        data_root/masks/*.png
    Also handles:
        data_root/images/ + data_root/masks/
        data_root/image/  + data_root/mask/
    """
    IMG_MEAN = [0.485, 0.456, 0.406]
    IMG_STD  = [0.229, 0.224, 0.225]

    def __init__(self, root: Path, img_size: int = 352):
        self.img_size = img_size
        # Try common folder name variants
        img_dir = self._find_subdir(root, ["images", "image", "imgs", "JPEGImages"])
        msk_dir = self._find_subdir(root, ["masks", "mask", "annotations", "SegmentationClass"])
        if img_dir is None or msk_dir is None:
            raise FileNotFoundError(
                f"Could not find image/mask directories under {root}.\n"
                f"Contents: {[d.name for d in root.iterdir() if d.is_dir()]}"
            )
        # Pair images with masks
        img_paths = sorted(img_dir.glob("*.[jJpP][pPnN][gG]*"))
        self.pairs = []
        for img_path in img_paths:
            stem = img_path.stem
            # Try common mask extensions
            for ext in [".png", ".jpg", ".bmp"]:
                msk_path = msk_dir / (stem + ext)
                if msk_path.exists():
                    self.pairs.append((img_path, msk_path))
                    break
        if len(self.pairs) == 0:
            raise FileNotFoundError(f"No image-mask pairs found under {root}")

    @staticmethod
    def _find_subdir(root: Path, candidates: list[str]) -> Path | None:
        for name in candidates:
            d = root / name
            if d.is_dir():
                return d
        return None

    def __len__(self): return len(self.pairs)

    def __getitem__(self, idx):
        img_path, msk_path = self.pairs[idx]
        # Image
        img = Image.open(img_path).convert("RGB").resize(
            (self.img_size, self.img_size), Image.BILINEAR)
        img = np.array(img, dtype=np.float32) / 255.0
        img = (img - self.IMG_MEAN) / self.IMG_STD
        img = torch.from_numpy(img.transpose(2, 0, 1)).float()
        # Mask (original size, for evaluation at native resolution)
        msk_orig = np.array(Image.open(msk_path).convert("L"))
        gt = (msk_orig > 127).astype(np.uint8)
        return img, gt, str(img_path.stem), (gt.shape[0], gt.shape[1])


def collate_fn(batch):
    imgs = torch.stack([b[0] for b in batch])
    gts  = [b[1] for b in batch]
    names = [b[2] for b in batch]
    orig_sizes = [b[3] for b in batch]
    return imgs, gts, names, orig_sizes


# ─── Evaluation ──────────────────────────────────────────────────────────────

def evaluate_dataset(model: torch.nn.Module, dataset_path: Path,
                     img_size: int, device: torch.device,
                     threshold: float = 0.5,
                     save_preds: bool = False,
                     pred_dir: Path = None) -> dict:
    """Run evaluation on one dataset. Returns dict of metric name → mean value."""
    ds = PolypDataset(dataset_path, img_size=img_size)
    loader = torch.utils.data.DataLoader(
        ds, batch_size=1, shuffle=False, num_workers=2,
        collate_fn=collate_fn, pin_memory=(device.type == "cuda")
    )

    dice_scores, iou_scores, fmeas_scores, smeas_scores = [], [], [], []

    model.eval()
    with torch.no_grad():
        for imgs, gts, names, orig_sizes in tqdm(loader, desc=f"  Eval {dataset_path.name}", leave=False):
            imgs = imgs.to(device)
            # Forward pass — handle models that return a tuple (like PraNet: coarse, fine)
            out = model(imgs)
            if isinstance(out, (tuple, list)):
                out = out[-1]   # take final/finest output

            # Resize prediction back to original mask size
            orig_h, orig_w = orig_sizes[0]
            pred_up = F.interpolate(out, size=(orig_h, orig_w), mode="bilinear", align_corners=False)
            pred_prob = torch.sigmoid(pred_up).squeeze().cpu().numpy()
            pred_bin  = (pred_prob >= threshold).astype(np.uint8)
            gt = gts[0]  # batch size = 1

            dice_scores.append(dice_score(pred_bin, gt))
            iou_scores.append(iou_score(pred_bin, gt))
            fmeas_scores.append(f_measure(pred_bin, gt))
            smeas_scores.append(s_measure(pred_prob, gt))

            if save_preds and pred_dir is not None:
                from PIL import Image as PILImage
                pred_dir.mkdir(parents=True, exist_ok=True)
                PILImage.fromarray((pred_bin * 255).astype(np.uint8)).save(
                    pred_dir / f"{names[0]}.png")

    return {
        "n_images":  len(ds),
        "mean_dice": float(np.mean(dice_scores)),
        "mean_iou":  float(np.mean(iou_scores)),
        "mean_fmeasure": float(np.mean(fmeas_scores)),
        "mean_smeasure": float(np.mean(smeas_scores)),
        "per_image_dice": dice_scores,
    }


# ─── Comparison table ────────────────────────────────────────────────────────

def print_comparison_table(results: dict, model_name: str) -> None:
    """Print a clean side-by-side comparison table vs. SOTA."""
    datasets = list(results.keys())
    print("\n" + "=" * 100)
    print("BENCHMARK RESULTS — DICE SCORE (higher = better)")
    print("=" * 100)

    # Header
    col_w = 16
    header = f"{'Method':<30}" + "".join(f"{ds.upper():>{col_w}}" for ds in datasets)
    print(header)
    print("-" * len(header))

    # Collect all method names from SOTA
    all_methods = []
    for ds in datasets:
        for m in SOTA_DICE.get(ds, {}).keys():
            if m not in all_methods:
                all_methods.append(m)

    for method in all_methods:
        row = f"{method:<30}"
        for ds in datasets:
            val = SOTA_DICE.get(ds, {}).get(method)
            row += f"{val:>{col_w}.3f}" if val is not None else f"{'—':>{col_w}}"
        print(row)

    print("-" * len(header))
    # Your model
    your_row = f"{model_name + ' (OURS)':<30}"
    for ds in datasets:
        val = results[ds]["mean_dice"]
        your_row += f"{val:>{col_w}.3f}"
    print(your_row + "  ← YOUR MODEL")

    # Beat count
    print("\n" + "-" * 60)
    print("BEATS SOTA? (on each dataset)")
    print("-" * 60)
    best_pub = {}
    for ds in datasets:
        sota_vals = SOTA_DICE.get(ds, {})
        best_pub[ds] = max(sota_vals.values()) if sota_vals else 0.0
        your_dice = results[ds]["mean_dice"]
        delta = your_dice - best_pub[ds]
        symbol = "✓ BEATS BEST" if delta > 0 else ("≈ TIES" if abs(delta) < 0.001 else "✗ BELOW BEST")
        print(f"  {ds:<20}  Yours={your_dice:.3f}  Best_pub={best_pub[ds]:.3f}  Δ={delta:+.3f}  {symbol}")

    print("\n" + "-" * 60)
    print("OTHER METRICS (your model)")
    print("-" * 60)
    print(f"  {'Dataset':<20}  {'mDice':>8}  {'mIoU':>8}  {'F-meas':>8}  {'S-meas':>8}  {'N':>6}")
    for ds, r in results.items():
        print(f"  {ds:<20}  {r['mean_dice']:>8.3f}  {r['mean_iou']:>8.3f}  "
              f"{r['mean_fmeasure']:>8.3f}  {r['mean_smeasure']:>8.3f}  {r['n_images']:>6}")
    print()


# ─── Load model ──────────────────────────────────────────────────────────────

def load_model(checkpoint_path: Path, model_class_name: str) -> torch.nn.Module:
    """
    Load a model from checkpoint.

    TODO: Import your model class here.
    The model_class_name argument should match one of the classes you add below.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))  # project root

    # ── Model classes ─────────────────────────────────────────────────────────
    # combo1 = ResNet-50 + Asymmetric RFB + PPD + CBAM-Reverse Attention
    #          Identified from combo1_best.pth weight inspection (0 missing keys)
    try:
        from src.models.combo1 import Combo1Model
        _combo1_available = True
    except ImportError:
        try:
            import importlib.util, os
            spec = importlib.util.spec_from_file_location(
                "combo1_model",
                os.path.join(os.path.dirname(__file__), "combo1_model.py")
            )
            _mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_mod)
            Combo1Model = _mod.Combo1Model
            _combo1_available = True
        except Exception:
            _combo1_available = False

    MODEL_REGISTRY = {}
    if _combo1_available:
        MODEL_REGISTRY["combo1"] = Combo1Model

    # TODO 1: Add ChakraTransformer once inspect_weights.py identifies its architecture:
    #   python scripts/inspect_weights.py \
    #     --checkpoint _weights_check/weights/checkpoints/chakra_transformer_best.pth
    # Then implement src/models/chakra_transformer.py and add:
    #   from src.models.chakra_transformer import ChakraTransformer
    #   MODEL_REGISTRY["chakra_transformer"] = ChakraTransformer
    # ─────────────────────────────────────────────────────────────────────────

    # Fallback: try to auto-detect from timm or torchvision
    if model_class_name not in MODEL_REGISTRY:
        # Common open-source baselines for quick comparison
        try:
            if model_class_name == "pranet":
                # If you've cloned PraNet: from models.PraNet_Res2Net import PraNet
                raise ImportError("PraNet not in path — clone from github.com/DengPingFan/PraNet")
            elif model_class_name == "hardnet_mseg":
                raise ImportError("HarDNet-MSEG not in path")
            else:
                raise ValueError(
                    f"Unknown model class: '{model_class_name}'.\n"
                    f"  Add it to MODEL_REGISTRY in load_model() — see TODO 1 above.\n"
                    f"  Run inspect_weights.py first to identify the architecture."
                )
        except ImportError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    model_cls = MODEL_REGISTRY[model_class_name]

    # ── Instantiate model ──────────────────────────────────────────────────
    # combo1 takes no constructor args (ResNet-50 + RFB + CBAM-RA, ch=48 fixed)
    # For ChakraTransformer: add args here once architecture is known
    model = model_cls()
    # ─────────────────────────────────────────────────────────────────────────

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if isinstance(checkpoint, dict):
        sd = (checkpoint.get("state_dict")
              or checkpoint.get("model")
              or checkpoint.get("model_state_dict")
              or checkpoint)
    else:
        sd = checkpoint

    # Strip "module." prefix from DataParallel-wrapped models
    sd = {k.replace("module.", ""): v for k, v in sd.items()}

    missing, unexpected = model.load_state_dict(sd, strict=False)
    if missing:
        logger.warning(f"Missing keys ({len(missing)}): {missing[:5]}...")
    if unexpected:
        logger.warning(f"Unexpected keys ({len(unexpected)}): {unexpected[:5]}...")

    logger.info(f"Loaded weights from {checkpoint_path}")
    return model


# ─── Main ────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Benchmark polyp segmentation model vs. SOTA")
    p.add_argument("--checkpoint",   required=True, help="Path to .pth checkpoint")
    p.add_argument("--model_class",  required=True,
                   help="Model class name (must be registered in load_model())")
    p.add_argument("--data_root",    default="data/raw",
                   help="Root dir containing dataset folders")
    p.add_argument("--img_size",     type=int, default=352)
    p.add_argument("--threshold",    type=float, default=0.5,
                   help="Binary threshold for predictions")
    p.add_argument("--dataset",      default="all",
                   choices=["all"] + list(DATASET_DIRS.keys()),
                   help="Evaluate on one dataset or all five")
    p.add_argument("--save_preds",   action="store_true",
                   help="Save predicted masks to results/sample_predictions/")
    p.add_argument("--no_fps",       action="store_true",
                   help="Skip FPS measurement")
    p.add_argument("--output",       default=None,
                   help="Save JSON results to this path (default: results/metrics/<run>.json)")
    return p.parse_args()


def main():
    args = parse_args()
    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        logger.error(f"Checkpoint not found: {ckpt}")
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    if device.type == "cuda":
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")

    # Load model
    logger.info(f"Loading model: {args.model_class}")
    model = load_model(ckpt, args.model_class)
    model = model.to(device)
    model.eval()

    n_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Model parameters: {n_params/1e6:.2f}M")

    # FPS
    fps = None
    if not args.no_fps:
        logger.info("Measuring FPS...")
        fps = measure_fps(model, device, img_size=args.img_size)
        logger.info(f"FPS: {fps:.1f}")

    # Which datasets to run
    data_root = Path(args.data_root)
    datasets_to_run = (
        {k: v for k, v in DATASET_DIRS.items()}
        if args.dataset == "all"
        else {args.dataset: DATASET_DIRS[args.dataset]}
    )

    results = {}
    for ds_name, ds_subdir in datasets_to_run.items():
        ds_path = data_root / ds_subdir
        if not ds_path.exists():
            logger.warning(f"Dataset path not found, skipping: {ds_path}")
            continue
        logger.info(f"\nEvaluating on {ds_name} ({ds_path})...")
        pred_dir = (Path("results/sample_predictions") / args.model_class / ds_name
                    if args.save_preds else None)
        results[ds_name] = evaluate_dataset(
            model, ds_path, args.img_size, device,
            threshold=args.threshold,
            save_preds=args.save_preds, pred_dir=pred_dir,
        )

    if not results:
        logger.error("No datasets evaluated. Check --data_root and dataset directories.")
        sys.exit(1)

    # Print comparison table
    print_comparison_table(results, args.model_class)

    # FPS summary
    if fps is not None:
        print(f"  Inference speed: {fps:.1f} FPS @ {args.img_size}x{args.img_size} on {device}")
        print(f"  (Real-time threshold: 30 FPS)")

    # Save JSON
    output_path = Path(args.output) if args.output else (
        Path("results/metrics") / f"{args.model_class}_{datetime.now():%Y%m%d_%H%M%S}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    full_results = {
        "model":      args.model_class,
        "checkpoint": str(ckpt),
        "img_size":   args.img_size,
        "threshold":  args.threshold,
        "device":     str(device),
        "fps":        fps,
        "timestamp":  datetime.now().isoformat(),
        "datasets":   {k: {m: v for m, v in r.items() if m != "per_image_dice"}
                       for k, r in results.items()},
        "sota_reference": SOTA_DICE,
    }
    with open(output_path, "w") as f:
        json.dump(full_results, f, indent=2)
    logger.info(f"\nFull results saved to: {output_path}")


if __name__ == "__main__":
    main()
