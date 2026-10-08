"""
Zer0wasteX — Training Script
Trains YOLOv8m on Indian waste classification dataset to target 90% mAP@50.

Architecture choice:
  - YOLOv8m (medium): best accuracy/speed tradeoff for our use case
  - Nano is too small for 6-class detail; Large is overkill for bin-edge inference
  - Medium hits ~92% mAP on well-balanced datasets (research validated)

Usage:
    # Full training (requires dataset prepared via prepare_dataset.py)
    python train.py --data dataset.yaml --epochs 150 --device cuda

    # Resume from checkpoint
    python train.py --resume runs/train/exp/weights/last.pt

    # Export to ONNX for Raspberry Pi / Jetson deployment
    python train.py --export-only --weights runs/train/exp/weights/best.pt
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime


def check_gpu():
    try:
        import torch
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"🎮 GPU detected: {gpu} ({vram:.1f} GB VRAM)")
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            print("🍎 Apple Silicon MPS detected")
            return "mps"
        else:
            print("⚠️  No GPU detected. Training on CPU (very slow — use Google Colab for GPU).")
            return "cpu"
    except ImportError:
        print("❌ PyTorch not installed. Run: pip install -r requirements.txt")
        sys.exit(1)


def train(args):
    from ultralytics import YOLO

    device = args.device or check_gpu()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"zer0wastex_{timestamp}"

    print(f"\n🚀 Starting Zer0wasteX training")
    print(f"   Model     : YOLOv8m")
    print(f"   Dataset   : {args.data}")
    print(f"   Epochs    : {args.epochs}")
    print(f"   Batch     : {args.batch}")
    print(f"   Device    : {device}")
    print(f"   Run name  : {run_name}\n")

    # Load base model (downloads if not cached)
    model = YOLO("yolov8m.pt")

    # ── Hyperparameters tuned for Indian waste classification ────────────────
    results = model.train(
        data=str(Path(args.data).resolve()),
        epochs=args.epochs,
        imgsz=640,
        batch=args.batch,
        device=device,
        name=run_name,

        # Optimiser
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,            # final lr = lr0 * lrf
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=5,
        warmup_bias_lr=0.1,

        # Regularisation
        dropout=0.0,
        label_smoothing=0.1,  # key for noisy real-world labels

        # Loss weights
        box=7.5,
        cls=0.5,
        dfl=1.5,

        # Compute
        workers=4,
        amp=True,            # mixed precision (2× faster on modern GPU)
        cache=True,          # cache images in RAM for speed

        # Validation
        val=True,
        save_period=10,      # save checkpoint every 10 epochs
        patience=30,         # early stop if no improvement for 30 epochs

        # Logging
        plots=True,
        verbose=True,
        exist_ok=True,
    )

    best_map = results.results_dict.get("metrics/mAP50(B)", 0)
    print(f"\n{'='*50}")
    print(f"✅ Training complete!")
    print(f"   Best mAP@50 : {best_map*100:.2f}%")
    print(f"   Target      : 90.00%")
    print(f"   Status      : {'✅ TARGET MET' if best_map >= 0.90 else '⚠️  Below target — try more data or epochs'}")
    print(f"{'='*50}\n")

    return results


def export(weights_path: str):
    """Export best.pt to ONNX format for edge deployment."""
    from ultralytics import YOLO

    print(f"📦 Exporting {weights_path} to ONNX...")
    model = YOLO(weights_path)

    # Export to ONNX (works on Raspberry Pi, Jetson, OpenCV DNN)
    model.export(format="onnx", imgsz=640, simplify=True, opset=17)
    print("✅ ONNX exported. Copy best.onnx to ml/weights/ for production inference.")

    # Also export to TFLite (Android / mobile)
    try:
        model.export(format="tflite", imgsz=640)
        print("✅ TFLite exported for mobile deployment.")
    except Exception as e:
        print(f"⚠️  TFLite export failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Zer0wasteX YOLOv8m training")
    parser.add_argument("--data",    "-d", default="dataset.yaml", help="Dataset YAML path")
    parser.add_argument("--epochs",  "-e", type=int, default=150,  help="Training epochs")
    parser.add_argument("--batch",   "-b", type=int, default=16,   help="Batch size")
    parser.add_argument("--device",        default=None,            help="cuda / cpu / mps")
    parser.add_argument("--resume",        default=None,            help="Resume from checkpoint")
    parser.add_argument("--export-only",   action="store_true",     help="Skip training, only export")
    parser.add_argument("--weights",       default="runs/train/exp/weights/best.pt")
    args = parser.parse_args()

    if args.export_only:
        export(args.weights)
        return

    if args.resume:
        from ultralytics import YOLO
        model = YOLO(args.resume)
        model.train(resume=True)
        return

    train(args)


if __name__ == "__main__":
    main()
