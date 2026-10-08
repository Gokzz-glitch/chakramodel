"""
Zer0wasteX — Dataset Downloader
Downloads and merges 3 public waste datasets into a unified YOLO-format dataset.

Datasets used:
  1. TrashNet (GitHub) — 2,527 images, 6 classes
  2. Kaggle Waste Classification (techsash) — 22,500 images, organic + recyclable
  3. TACO (Trash Annotations in Context) — 1,500+ images, outdoor litter

Usage:
    python download_datasets.py --out-dir dataset/raw

Env vars needed:
    KAGGLE_USERNAME, KAGGLE_KEY  (from kaggle.com → Account → API)
"""

import os
import sys
import shutil
import argparse
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

# ── Class remapping to our 6-class taxonomy ──────────────────────────────────
# TrashNet classes → ours
TRASHNET_REMAP = {
    "glass":      "glass",
    "paper":      "paper",
    "cardboard":  "paper",     # merge cardboard → paper
    "plastic":    "plastic",
    "metal":      "metal",
    "trash":      "organic",   # generic trash → organic (conservative)
}

# Kaggle waste-classification-data → ours
KAGGLE_WASTE_REMAP = {
    "O": "organic",    # Organic
    "R": "plastic",    # Recyclable (most recyclable = plastic in Indian context)
}


def download_file(url: str, dest: Path, desc: str = "Downloading") -> Path:
    """Stream download with progress bar."""
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f, tqdm(
        desc=desc, total=total, unit="B", unit_scale=True
    ) as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))
    return dest


def download_trashnet(out_dir: Path):
    """
    Download TrashNet from the public Hugging Face mirror.
    Original: https://github.com/garythung/trashnet
    """
    print("\n📦 Downloading TrashNet dataset...")
    url = "https://huggingface.co/datasets/garythung/trashnet/resolve/main/dataset-resized.zip"
    dest = out_dir / "trashnet.zip"

    try:
        download_file(url, dest, "TrashNet")
    except Exception as e:
        print(f"  ⚠️  Could not download TrashNet automatically: {e}")
        print("  → Please download manually from: https://github.com/garythung/trashnet")
        print(f"  → Extract to: {out_dir / 'trashnet'}")
        return

    extract_dir = out_dir / "trashnet"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(dest, "r") as z:
        z.extractall(extract_dir)
    dest.unlink()
    print(f"  ✅ TrashNet extracted → {extract_dir}")


def download_kaggle_waste(out_dir: Path):
    """
    Download Kaggle Waste Classification dataset.
    Dataset: https://www.kaggle.com/datasets/techsash/waste-classification-data
    Requires KAGGLE_USERNAME and KAGGLE_KEY env vars.
    """
    print("\n📦 Downloading Kaggle Waste Classification dataset...")

    username = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")

    if not username or not key:
        print("  ⚠️  KAGGLE_USERNAME / KAGGLE_KEY not set. Skipping Kaggle dataset.")
        print("  → Set: $env:KAGGLE_USERNAME='your_username'; $env:KAGGLE_KEY='your_key'")
        print("  → Then re-run this script.")
        return

    try:
        import kaggle
        kaggle.api.authenticate()
        kaggle.api.dataset_download_files(
            "techsash/waste-classification-data",
            path=str(out_dir / "kaggle_waste"),
            unzip=True,
            quiet=False,
        )
        print(f"  ✅ Kaggle dataset downloaded → {out_dir / 'kaggle_waste'}")
    except Exception as e:
        print(f"  ❌ Kaggle download failed: {e}")
        print("  → pip install kaggle, set API credentials, and retry.")


def download_taco_subset(out_dir: Path, n_images: int = 500):
    """
    Download a subset of TACO dataset annotations.
    Uses the public TACO API / GitHub raw annotations.
    """
    print(f"\n📦 Downloading TACO subset ({n_images} images)...")
    annotations_url = "https://raw.githubusercontent.com/pedropro/TACO/master/data/annotations.json"
    ann_file = out_dir / "taco" / "annotations.json"

    try:
        download_file(annotations_url, ann_file, "TACO annotations")
        print(f"  ✅ TACO annotations saved → {ann_file}")
        print("  ℹ️  Image download requires: python download_taco.py (see TACO GitHub)")
    except Exception as e:
        print(f"  ⚠️  TACO download failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Zer0wasteX dataset downloader")
    parser.add_argument("--out-dir", "-o", default="dataset/raw", help="Output directory")
    parser.add_argument("--skip-trashnet", action="store_true")
    parser.add_argument("--skip-kaggle", action="store_true")
    parser.add_argument("--skip-taco", action="store_true")
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"📁 Downloading datasets to: {out.resolve()}")

    if not args.skip_trashnet:
        download_trashnet(out)
    if not args.skip_kaggle:
        download_kaggle_waste(out)
    if not args.skip_taco:
        download_taco_subset(out)

    print("\n✅ Download phase complete.")
    print("   Next step: python prepare_dataset.py --raw-dir dataset/raw --out-dir dataset/merged")


if __name__ == "__main__":
    main()
