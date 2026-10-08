"""
Zer0wasteX — Indian-condition Data Augmentation Pipeline
Uses Albumentations to simulate real-world Indian waste bin image conditions.

Conditions simulated:
  - Harsh Indian sunlight (high brightness, blown-out highlights)
  - Deep shadow from buildings / overcast monsoon
  - Dusty / dirty lens (blur, noise)
  - Plastic film / water droplets (rainy condition)
  - Mixed / cluttered bin contents (random crop, paste)
  - Low-resolution phone camera shots
  - Tilted / awkward angles
  - Night-time with LED torch

Usage:
    python augment.py --src dataset/merged/images/train --dst dataset/augmented/images/train --factor 4
"""

import os
import cv2
import argparse
import numpy as np
from pathlib import Path
from tqdm import tqdm

import albumentations as A
from albumentations.core.composition import Compose


# ── Core Indian-condition transform pipeline ─────────────────────────────────

def build_indian_condition_pipeline() -> Compose:
    """
    Returns an Albumentations pipeline that aggressively simulates
    the visual conditions found in Indian urban waste environments.
    """
    return A.Compose([

        # ── Lighting ─────────────────────────────────────────────────────────
        A.OneOf([
            # Harsh midday sun (overexposed)
            A.RandomBrightnessContrast(brightness_limit=(0.3, 0.6), contrast_limit=(0.2, 0.4), p=1.0),
            # Deep shadow / indoor
            A.RandomBrightnessContrast(brightness_limit=(-0.5, -0.2), contrast_limit=(-0.2, 0.1), p=1.0),
            # Normal ambient
            A.RandomBrightnessContrast(brightness_limit=(-0.15, 0.15), contrast_limit=(-0.1, 0.2), p=1.0),
        ], p=0.85),

        # Colour temperature shift (Indian sunlight is warmer)
        A.HueSaturationValue(hue_shift_limit=12, sat_shift_limit=40, val_shift_limit=30, p=0.7),

        # ── Weather / Atmosphere ──────────────────────────────────────────────
        A.OneOf([
            # Monsoon rain + water drops
            A.RandomRain(slant_lower=-10, slant_upper=10, drop_length=10,
                         drop_width=1, drop_color=(200, 200, 200), blur_value=3,
                         brightness_coefficient=0.8, rain_type="drizzle", p=1.0),
            # Fog / mist (monsoon / early morning)
            A.RandomFog(fog_coef_lower=0.1, fog_coef_upper=0.35, alpha_coef=0.1, p=1.0),
            # Dust / haze (dry season)
            A.RandomSunFlare(flare_roi=(0, 0, 1, 0.5), angle_lower=0.5,
                              num_flare_circles_lower=3, num_flare_circles_upper=6,
                              src_radius=150, src_color=(255, 220, 60), p=1.0),
        ], p=0.35),

        # ── Camera Quality ────────────────────────────────────────────────────
        # Budget phone camera blur / motion blur (bin photo taken while walking)
        A.OneOf([
            A.MotionBlur(blur_limit=(3, 9), p=1.0),
            A.GaussianBlur(blur_limit=(3, 7), p=1.0),
            A.Defocus(radius=(2, 5), alias_blur=(0.1, 0.5), p=1.0),
        ], p=0.45),

        # Image compression artifacts (WhatsApp/social media compressed images)
        A.ImageCompression(quality_lower=40, quality_upper=85, p=0.5),

        # Digital noise (low-light phone sensor)
        A.GaussNoise(var_limit=(20.0, 100.0), p=0.4),

        # ── Geometry ──────────────────────────────────────────────────────────
        # Tilt / perspective distortion (held phone at angle)
        A.Perspective(scale=(0.05, 0.12), p=0.5),

        # Rotation (waste bins at odd angles, phone rotation)
        A.Rotate(limit=30, border_mode=cv2.BORDER_REFLECT_101, p=0.6),

        # Random crop simulating partial view of bin contents
        A.RandomResizedCrop(height=640, width=640, scale=(0.6, 1.0), ratio=(0.75, 1.33), p=0.5),

        # Horizontal flip (left/right doesn't matter for waste)
        A.HorizontalFlip(p=0.5),

        # ── Occlusion ────────────────────────────────────────────────────────
        # Simulate waste items partially covered by other items
        A.CoarseDropout(
            max_holes=6, max_height=80, max_width=80,
            min_holes=1, min_height=20, min_width=20,
            fill_value=0, p=0.3
        ),

        # ── Final resize ─────────────────────────────────────────────────────
        A.Resize(640, 640),

    ], bbox_params=A.BboxParams(
        format="yolo",
        label_fields=["class_labels"],
        min_visibility=0.3,
    ))


def augment_image(
    img_path: Path,
    label_path: Path,
    out_img_dir: Path,
    out_lbl_dir: Path,
    pipeline: Compose,
    factor: int = 4,
) -> int:
    """Augment a single image+label pair, producing `factor` augmented versions."""
    img = cv2.imread(str(img_path))
    if img is None:
        return 0

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]

    # Parse YOLO label
    bboxes, class_labels = [], []
    if label_path.exists():
        for line in label_path.read_text().strip().splitlines():
            parts = line.strip().split()
            if len(parts) == 5:
                cls = int(parts[0])
                x, y, bw, bh = map(float, parts[1:])
                bboxes.append([x, y, bw, bh])
                class_labels.append(cls)

    produced = 0
    for i in range(factor):
        try:
            if bboxes:
                transformed = pipeline(image=img, bboxes=bboxes, class_labels=class_labels)
            else:
                # No label — still augment image
                solo = A.Compose([t for t in pipeline.transforms if not isinstance(t, A.BboxParams)])
                transformed = {"image": solo(image=img)["image"], "bboxes": [], "class_labels": []}

            aug_img = cv2.cvtColor(transformed["image"], cv2.COLOR_RGB2BGR)
            stem = img_path.stem
            out_img = out_img_dir / f"{stem}_aug{i:03d}{img_path.suffix}"
            out_lbl = out_lbl_dir / f"{stem}_aug{i:03d}.txt"

            cv2.imwrite(str(out_img), aug_img)

            if transformed["bboxes"]:
                lines = []
                for cls, box in zip(transformed["class_labels"], transformed["bboxes"]):
                    x, y, bw, bh = box
                    lines.append(f"{cls} {x:.6f} {y:.6f} {bw:.6f} {bh:.6f}")
                out_lbl.write_text("\n".join(lines))
            else:
                out_lbl.write_text("")

            produced += 1
        except Exception as e:
            print(f"  ⚠️  Augmentation failed for {img_path.name}: {e}")

    return produced


def main():
    parser = argparse.ArgumentParser(description="Indian-condition augmentation pipeline")
    parser.add_argument("--src", "-s", required=True, help="Source images directory")
    parser.add_argument("--dst", "-d", required=True, help="Destination images directory")
    parser.add_argument("--factor", "-f", type=int, default=4, help="Augmentation factor per image")
    args = parser.parse_args()

    src_dir = Path(args.src)
    dst_dir = Path(args.dst)

    out_img_dir = dst_dir
    out_lbl_dir = dst_dir.parent.parent / "labels" / dst_dir.name
    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    pipeline = build_indian_condition_pipeline()

    images = list(src_dir.glob("*.jpg")) + list(src_dir.glob("*.png")) + list(src_dir.glob("*.jpeg"))
    print(f"🔄 Augmenting {len(images)} images × {args.factor} → target: {len(images) * args.factor}")

    total = 0
    for img_path in tqdm(images, desc="Augmenting"):
        lbl_path = img_path.parent.parent.parent / "labels" / img_path.parent.name / (img_path.stem + ".txt")
        total += augment_image(img_path, lbl_path, out_img_dir, out_lbl_dir, pipeline, args.factor)

    print(f"\n✅ Done. {total} augmented images written to {out_img_dir}")


if __name__ == "__main__":
    main()
