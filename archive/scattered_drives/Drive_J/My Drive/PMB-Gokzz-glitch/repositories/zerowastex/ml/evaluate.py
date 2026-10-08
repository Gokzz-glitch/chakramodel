"""
Zer0wasteX — Model Evaluation & Benchmarking
Calculates precision, recall, mAP@50, and F1 on your test set.
Also runs a confusion matrix and per-class accuracy breakdown.

Usage:
    # Evaluate custom fine-tuned model
    python evaluate.py --weights weights/best.pt --data dataset.yaml

    # Quick benchmark on a folder of images (no labels needed)
    python evaluate.py --weights weights/best.pt --images dataset/test_images/
"""

import argparse
from pathlib import Path


def evaluate_on_dataset(weights: str, data: str, device: str = "cpu"):
    """Run official YOLO validation on the test split."""
    from ultralytics import YOLO

    model = YOLO(weights)
    metrics = model.val(
        data=data,
        split="test",
        device=device,
        conf=0.5,
        iou=0.5,
        plots=True,
        verbose=True,
    )

    map50   = metrics.box.map50
    map5095 = metrics.box.map
    precision = metrics.box.mp
    recall    = metrics.box.mr
    f1        = 2 * (precision * recall) / (precision + recall + 1e-8)

    print("\n" + "═" * 55)
    print("     Zer0wasteX — Evaluation Results")
    print("═" * 55)
    print(f"  mAP@50        : {map50*100:6.2f}%   (target: 90%)")
    print(f"  mAP@50-95     : {map5095*100:6.2f}%")
    print(f"  Precision     : {precision*100:6.2f}%")
    print(f"  Recall        : {recall*100:6.2f}%")
    print(f"  F1 Score      : {f1*100:6.2f}%")
    print("═" * 55)

    gap = 90.0 - (map50 * 100)
    if gap <= 0:
        print(f"  ✅ TARGET MET! mAP@50 = {map50*100:.2f}% ≥ 90%")
    else:
        print(f"  ⚠️  Gap to 90%: {gap:.2f}pp")
        print(f"\n  Suggestions to close the gap:")
        if map50 < 0.75:
            print("    → Add more training images (need at least 500 per class)")
            print("    → Check label quality (use Roboflow label review)")
            print("    → Run: python augment.py --factor 6")
        elif map50 < 0.85:
            print("    → Train for more epochs (try --epochs 200)")
            print("    → Use YOLOv8l instead of YOLOv8m for +3-5% mAP")
            print("    → Add hard-negative mining (misclassified samples)")
        else:
            print("    → Fine-tune confidence threshold (try conf=0.45)")
            print("    → Add test-time augmentation (TTA)")
            print("    → Collect more images from actual Chennai bins")
    print()

    # Per-class breakdown
    if hasattr(metrics.box, "ap_class_index"):
        from waste_classes import WASTE_CLASSES
        print("  Per-class AP@50:")
        for i, ap in enumerate(metrics.box.ap50):
            cls_name = WASTE_CLASSES.get(i, f"class_{i}")
            bar = "█" * int(ap * 20) + "░" * (20 - int(ap * 20))
            status = "✅" if ap >= 0.9 else "⚠️ "
            print(f"    {status} {cls_name:<12} {bar} {ap*100:.1f}%")
        print()

    return metrics


def benchmark_images(weights: str, images_dir: str, device: str = "cpu"):
    """Run inference on a folder of unlabelled images and print class distribution."""
    from ultralytics import YOLO
    from collections import Counter
    from waste_classes import WASTE_CLASSES, CLASS_LABELS

    model = YOLO(weights)
    images = list(Path(images_dir).rglob("*.jpg")) + list(Path(images_dir).rglob("*.png"))
    print(f"\n🔍 Benchmarking {len(images)} images from {images_dir}")

    class_counts = Counter()
    conf_totals  = {}
    n_no_detect  = 0

    for img_path in images:
        results = model.predict(str(img_path), conf=0.35, verbose=False)
        detected = False
        for r in results:
            for box in r.boxes:
                cls_idx = int(box.cls)
                cls_name = WASTE_CLASSES.get(cls_idx, "unknown")
                class_counts[cls_name] += 1
                conf_totals.setdefault(cls_name, []).append(float(box.conf))
                detected = True
        if not detected:
            n_no_detect += 1

    total = sum(class_counts.values())
    print(f"\n  Results ({total} detections across {len(images)} images):\n")
    for cls_name, count in class_counts.most_common():
        avg_conf = sum(conf_totals[cls_name]) / len(conf_totals[cls_name])
        emoji = CLASS_LABELS.get(cls_name, {}).get("emoji", "•")
        bar = "█" * int((count/total) * 30) if total > 0 else ""
        print(f"  {emoji} {cls_name:<12} {bar} {count:>4} detections  (avg conf: {avg_conf:.2f})")

    print(f"\n  No detection: {n_no_detect}/{len(images)} images")


def main():
    parser = argparse.ArgumentParser(description="Zer0wasteX model evaluation")
    parser.add_argument("--weights", "-w", required=True,            help="Path to .pt weights")
    parser.add_argument("--data",    "-d", default="dataset.yaml",   help="Dataset YAML (for validation)")
    parser.add_argument("--images",  "-i", default=None,             help="Image folder for benchmark mode")
    parser.add_argument("--device",        default="cpu",            help="cuda / cpu")
    args = parser.parse_args()

    if args.images:
        benchmark_images(args.weights, args.images, args.device)
    else:
        evaluate_on_dataset(args.weights, args.data, args.device)


if __name__ == "__main__":
    main()
