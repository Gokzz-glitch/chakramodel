"""
download_datasets.py — Download the 5 standard polyp segmentation benchmark datasets.

These are the exact datasets used by PraNet, SANet, Polyp-PVT, HarDNet-MSEG
for their published benchmark results. You MUST use these same test splits
for your results to be directly comparable.

Usage:
    python scripts/download_datasets.py --output data/raw

    # Download only specific datasets:
    python scripts/download_datasets.py --output data/raw --datasets kvasir clinicdb

WHAT GETS DOWNLOADED (all public, research-licensed):
    1. Kvasir-SEG          1,000 images  (CC-BY 4.0)
    2. CVC-ClinicDB          612 images  (Research use)
    3. CVC-ColonDB           380 images  (Research use)
    4. ETIS-LaribPolypDB     196 images  (Research use)
    5. CVC-300 (EndoScene)    60 test images

TRAIN/TEST SPLIT (PraNet standard — matches published SOTA):
    Train: Kvasir-SEG 900 + CVC-ClinicDB 550 = 1,450 images
    Test:  Each dataset's held-out split (see SPLITS below)

NOTES:
    - Some datasets require manual download due to academic license agreements.
      The script will print exact URLs and instructions for those.
    - Total disk space: ~2 GB
"""

import argparse
import os
import sys
import hashlib
import zipfile
import tarfile
import shutil
import urllib.request
from pathlib import Path


# ─── Dataset registry ────────────────────────────────────────────────────────

DATASETS = {
    "kvasir": {
        "name": "Kvasir-SEG",
        "url": "https://datasets.simula.no/downloads/kvasir-seg.zip",
        "filename": "kvasir-seg.zip",
        "extract_dir": "Kvasir-SEG",
        "license": "CC-BY 4.0",
        "size_mb": 44,
        "auto_download": True,
        "notes": None,
    },
    "clinicdb": {
        "name": "CVC-ClinicDB",
        "url": None,  # Requires form submission
        "filename": "CVC-ClinicDB.zip",
        "extract_dir": "CVC-ClinicDB",
        "license": "Research use",
        "size_mb": 330,
        "auto_download": False,
        "notes": (
            "CVC-ClinicDB requires registration at:\n"
            "  https://polyp.grand-challenge.org/CVCClinicDB/\n"
            "After download, place CVC-ClinicDB.zip in your data/raw/ folder\n"
            "and re-run this script. Alternatively, it's available via:\n"
            "  https://www.dropbox.com/s/p5qe9eotetjnbmq/CVC-ClinicDB.zip\n"
            "  (unofficial mirror — verify MD5 after download)"
        ),
    },
    "colondb": {
        "name": "CVC-ColonDB",
        "url": None,  # Requires form submission
        "filename": "CVC-ColonDB.zip",
        "extract_dir": "CVC-ColonDB",
        "license": "Research use",
        "size_mb": 130,
        "auto_download": False,
        "notes": (
            "CVC-ColonDB: Download from the polyp grand challenge or contact authors.\n"
            "  https://polyp.grand-challenge.org/\n"
            "  Place CVC-ColonDB.zip in data/raw/ and re-run."
        ),
    },
    "etis": {
        "name": "ETIS-LaribPolypDB",
        "url": "https://drive.google.com/uc?export=download&id=1o9sN98Jz4HCRTlMzNmYjVb-K3GpJzLiY",
        "filename": "ETIS-LaribPolypDB.zip",
        "extract_dir": "ETIS-LaribPolypDB",
        "license": "Research use",
        "size_mb": 500,
        "auto_download": False,  # GDrive requires special handling
        "notes": (
            "ETIS-LaribPolypDB: Download using gdown (pip install gdown):\n"
            "  gdown 1o9sN98Jz4HCRTlMzNmYjVb-K3GpJzLiY -O data/raw/ETIS-LaribPolypDB.zip\n"
            "  unzip data/raw/ETIS-LaribPolypDB.zip -d data/raw/\n"
            "Or get it from: https://github.com/DengPingFan/PraNet (data section)"
        ),
    },
    "cvc300": {
        "name": "CVC-300 (EndoScene)",
        "url": None,
        "filename": "CVC-300.zip",
        "extract_dir": "CVC-300",
        "license": "Research use",
        "size_mb": 80,
        "auto_download": False,
        "notes": (
            "CVC-300 (EndoScene): Available from:\n"
            "  http://www.cvc.uab.es/CVC-Colon/index_files/page3.htm\n"
            "Or included in PraNet's test set package (recommended):\n"
            "  Download from the PraNet GitHub: https://github.com/DengPingFan/PraNet\n"
            "  They provide a unified test pack with all 5 datasets."
        ),
    },
}

# ─── PraNet-standard train/test split ────────────────────────────────────────
# These are the exact indices/splits used in the SOTA papers.

SPLITS = {
    "kvasir_train": {
        "description": "900 images from Kvasir-SEG for training",
        "source": "Kvasir-SEG/images/ (first 900 alphabetically, or per provided split file)",
    },
    "clinicdb_train": {
        "description": "550 images from CVC-ClinicDB for training",
        "source": "CVC-ClinicDB/Original/ (first 550)",
    },
    "kvasir_test": {
        "description": "100 images from Kvasir-SEG for testing",
        "source": "Kvasir-SEG/images/ (last 100 alphabetically)",
    },
    "clinicdb_test": {
        "description": "62 images from CVC-ClinicDB for testing",
        "source": "CVC-ClinicDB/Original/ (last 62)",
    },
    "colondb": {
        "description": "380 images — entire CVC-ColonDB is test-only",
        "source": "CVC-ColonDB/",
    },
    "etis": {
        "description": "196 images — entire ETIS-LaribPolypDB is test-only",
        "source": "ETIS-LaribPolypDB/",
    },
    "cvc300": {
        "description": "60 test images from EndoScene (CVC-300 split)",
        "source": "CVC-300/",
    },
}


def progress_hook(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, downloaded * 100 / total_size)
        bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
        print(f"\r  [{bar}] {pct:.1f}%  {downloaded/1e6:.1f}/{total_size/1e6:.1f} MB",
              end="", flush=True)


def download_file(url: str, dest: Path) -> bool:
    """Download a file with progress bar. Returns True on success."""
    print(f"  Downloading: {url}")
    print(f"  To:          {dest}")
    try:
        urllib.request.urlretrieve(url, str(dest), reporthook=progress_hook)
        print()  # newline after progress bar
        return True
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return False


def extract_archive(archive_path: Path, extract_to: Path) -> bool:
    """Extract zip or tar archive."""
    print(f"  Extracting: {archive_path.name} → {extract_to}")
    try:
        if archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as z:
                z.extractall(extract_to)
        elif archive_path.suffix in [".tar", ".gz", ".tgz"]:
            with tarfile.open(archive_path, "r:*") as t:
                t.extractall(extract_to)
        return True
    except Exception as e:
        print(f"  ERROR extracting: {e}")
        return False


def build_split_files(data_root: Path) -> None:
    """
    Generate train.txt and test split files that point to actual images.
    Writes to data/processed/
    """
    processed = data_root.parent / "processed"
    processed.mkdir(exist_ok=True)

    # Kvasir-SEG split: sorted alphabetically, 900 train / 100 test
    kvasir_img = data_root / "Kvasir-SEG" / "images"
    kvasir_msk = data_root / "Kvasir-SEG" / "masks"
    if kvasir_img.exists():
        imgs = sorted(kvasir_img.glob("*.jpg")) + sorted(kvasir_img.glob("*.png"))
        train_imgs, test_imgs = imgs[:900], imgs[900:]
        for split_name, split_imgs in [("kvasir_train", train_imgs), ("kvasir_test", test_imgs)]:
            split_path = processed / f"{split_name}.txt"
            with open(split_path, "w") as f:
                for img in split_imgs:
                    stem = img.stem
                    img_rel = img.relative_to(data_root)
                    msk_file = kvasir_msk / (stem + ".png")
                    if not msk_file.exists():
                        msk_file = kvasir_msk / (stem + ".jpg")
                    msk_rel = msk_file.relative_to(data_root) if msk_file.exists() else "MISSING"
                    f.write(f"{img_rel}\t{msk_rel}\n")
            print(f"  [SPLIT] Written: {split_path}  ({len(split_imgs)} images)")

    # CVC-ClinicDB: 550 train / 62 test
    clinic_img = data_root / "CVC-ClinicDB" / "Original"
    clinic_msk = data_root / "CVC-ClinicDB" / "Ground Truth"
    if not clinic_img.exists():
        clinic_img = data_root / "CVC-ClinicDB" / "images"
        clinic_msk = data_root / "CVC-ClinicDB" / "masks"
    if clinic_img.exists():
        imgs = sorted(clinic_img.glob("*.tif")) + sorted(clinic_img.glob("*.png")) + sorted(clinic_img.glob("*.jpg"))
        train_imgs, test_imgs = imgs[:550], imgs[550:]
        for split_name, split_imgs in [("clinicdb_train", train_imgs), ("clinicdb_test", test_imgs)]:
            split_path = processed / f"test_splits" / f"{split_name}.txt"
            split_path.parent.mkdir(exist_ok=True)
            with open(split_path, "w") as f:
                for img in split_imgs:
                    img_rel = img.relative_to(data_root)
                    f.write(f"{img_rel}\n")
            print(f"  [SPLIT] Written: {split_path}  ({len(split_imgs)} images)")

    # Zero-shot test sets — all images
    for ds_key, ds_subdir in [("colondb", "CVC-ColonDB"), ("etis", "ETIS-LaribPolypDB"), ("cvc300", "CVC-300")]:
        ds_path = data_root / ds_subdir
        if ds_path.exists():
            split_path = processed / "test_splits" / f"{ds_key}.txt"
            split_path.parent.mkdir(exist_ok=True)
            img_dirs = ["images", "image", "CVC-300", "."]
            img_files = []
            for d in img_dirs:
                img_dir = ds_path / d if d != "." else ds_path
                if img_dir.exists():
                    img_files = (sorted(img_dir.glob("*.jpg")) +
                                 sorted(img_dir.glob("*.png")) +
                                 sorted(img_dir.glob("*.tif")))
                    if img_files:
                        break
            with open(split_path, "w") as f:
                for img in img_files:
                    f.write(f"{img.relative_to(data_root)}\n")
            print(f"  [SPLIT] Written: {split_path}  ({len(img_files)} images)")

    # Combined train file
    train_file = processed / "train.txt"
    lines = []
    for part in ["kvasir_train", "clinicdb_train"]:
        part_file = processed / f"{part}.txt"
        if part_file.exists():
            lines.extend(part_file.read_text().strip().split("\n"))
    if lines:
        with open(train_file, "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"  [SPLIT] Combined train: {train_file}  ({len(lines)} images)")


def main():
    parser = argparse.ArgumentParser(
        description="Download standard polyp segmentation benchmark datasets"
    )
    parser.add_argument("--output", default="data/raw",
                        help="Directory to save datasets (default: data/raw)")
    parser.add_argument("--datasets", nargs="+",
                        choices=list(DATASETS.keys()) + ["all"],
                        default=["all"],
                        help="Which datasets to download")
    parser.add_argument("--splits_only", action="store_true",
                        help="Only generate split files (don't download)")
    args = parser.parse_args()

    data_root = Path(args.output)
    data_root.mkdir(parents=True, exist_ok=True)

    ds_to_get = list(DATASETS.keys()) if "all" in args.datasets else args.datasets

    print("\n" + "=" * 70)
    print("POLYP SEGMENTATION BENCHMARK DATASET DOWNLOADER")
    print("=" * 70)
    print(f"Output directory: {data_root.resolve()}")
    print()

    if not args.splits_only:
        for ds_key in ds_to_get:
            ds = DATASETS[ds_key]
            print(f"\n── {ds['name']} ─────────────────────────────")
            extract_path = data_root / ds["extract_dir"]

            if extract_path.exists():
                print(f"  ✓ Already exists: {extract_path}")
                continue

            if not ds["auto_download"]:
                print(f"  ⚠ MANUAL DOWNLOAD REQUIRED ({ds['license']}):")
                print(f"  {ds['notes']}")
                continue

            archive = data_root / ds["filename"]
            if not archive.exists():
                success = download_file(ds["url"], archive)
                if not success:
                    continue
            else:
                print(f"  ✓ Archive already downloaded: {archive}")

            if extract_archive(archive, data_root):
                print(f"  ✓ Extracted to: {extract_path}")

    # Status report
    print("\n" + "=" * 70)
    print("STATUS REPORT")
    print("=" * 70)
    total_ready = 0
    for ds_key, ds in DATASETS.items():
        path = data_root / ds["extract_dir"]
        status = "✓ READY" if path.exists() else "✗ MISSING"
        if path.exists():
            total_ready += 1
        # Count images if present
        img_count = ""
        if path.exists():
            imgs = list(path.rglob("*.jpg")) + list(path.rglob("*.png")) + list(path.rglob("*.tif"))
            img_count = f"({len(imgs)} files found)"
        print(f"  {status}  {ds['name']:<25}  {img_count}")

    print(f"\n  {total_ready}/{len(DATASETS)} datasets ready")

    if total_ready > 0:
        print("\nGenerating split files...")
        build_split_files(data_root)

    print("\n" + "=" * 70)
    print("RECOMMENDED NEXT STEPS")
    print("=" * 70)
    print("""
  1. Run inspect_weights.py to identify your model architecture:
       python scripts/inspect_weights.py \\
         --checkpoint _weights_check/weights/checkpoints/chakra_transformer_best.pth

  2. Add your model class to benchmark_eval.py (see TODO 1 and TODO 2):
       Edit scripts/benchmark_eval.py → load_model() → MODEL_REGISTRY

  3. Run the full benchmark:
       python scripts/benchmark_eval.py \\
         --checkpoint _weights_check/weights/checkpoints/chakra_transformer_best.pth \\
         --model_class ChakraTransformer \\
         --data_root data/raw

  4. Compare results vs. SOTA table printed by benchmark_eval.py.
     If your Dice beats Polyp-PVT (best published: Kvasir=0.917, ETIS=0.787),
     you have a strong paper contribution.

  5. Run combo1_best.pth the same way for comparison.
""")


if __name__ == "__main__":
    main()
