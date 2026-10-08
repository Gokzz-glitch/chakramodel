#!/usr/bin/env python3
"""
Download PraNet benchmark datasets from Google Drive.
Uses gdown to download the official TestDataset and TrainDataset.

TestDataset (327.2MB): CVC-300, CVC-ClinicDB, CVC-ColonDB, ETIS-LaribPolypDB, Kvasir
TrainDataset (399.5MB): Kvasir-SEG (900) + CVC-ClinicDB (550)
"""

import subprocess
import sys
import os
from pathlib import Path

# Install gdown if not present
try:
    import gdown
except ImportError:
    print("Installing gdown...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown", "-q"])
    import gdown


DOWNLOADS = {
    "TestDataset": {
        "id": "1Y2z7FD5p5y31vkZwQQomXFRB0HutHyao",
        "output": "data/raw/pranet_benchmark/TestDataset.zip",
        "size": "327.2 MB",
        "contains": "CVC-300 (60), CVC-ClinicDB (62), CVC-ColonDB (380), ETIS-LaribPolypDB (196), Kvasir (100)",
    },
    "TrainDataset": {
        "id": "1YiGHLw4iTvKdvbT6MgwO9zcCv8zJ_Bnb",
        "output": "data/raw/pranet_benchmark/TrainDataset.zip",
        "size": "399.5 MB",
        "contains": "Kvasir-SEG (900) + CVC-ClinicDB (550)",
    },
}


def download_dataset(name, info):
    """Download a dataset from Google Drive."""
    output_path = Path(info["output"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"  [{name}] Already downloaded: {output_path}")
        return str(output_path)

    url = f"https://drive.google.com/uc?id={info['id']}"
    print(f"  [{name}] Downloading ({info['size']})...")
    print(f"  Contains: {info['contains']}")

    try:
        gdown.download(url, str(output_path), quiet=False)
        if output_path.exists():
            actual_size = output_path.stat().st_size / 1e6
            print(f"  [{name}] Downloaded: {actual_size:.1f} MB")
            return str(output_path)
        else:
            print(f"  [{name}] FAILED: File not created")
            return None
    except Exception as e:
        print(f"  [{name}] ERROR: {e}")
        return None


def extract_dataset(zip_path, extract_to):
    """Extract a zip archive."""
    import zipfile
    zip_path = Path(zip_path)
    extract_to = Path(extract_to)

    if not zip_path.exists():
        print(f"  Cannot extract: {zip_path} not found")
        return

    print(f"  Extracting {zip_path.name} -> {extract_to}")
    extract_to.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_to)
        total = len(zf.namelist())
        print(f"  Extracted {total} files")


def main():
    print("=" * 60)
    print("  DOWNLOADING PRANET BENCHMARK DATASETS")
    print("  Source: github.com/DengPingFan/PraNet")
    print("=" * 60)

    downloaded = {}
    for name, info in DOWNLOADS.items():
        path = download_dataset(name, info)
        if path:
            downloaded[name] = path

    # Extract downloaded files
    if downloaded:
        print("\n" + "=" * 60)
        print("  EXTRACTING DATASETS")
        print("=" * 60)
        for name, path in downloaded.items():
            extract_to = Path("data/raw/pranet_benchmark")
            extract_dataset(path, extract_to)

    # Verify structure
    print("\n" + "=" * 60)
    print("  VERIFYING STRUCTURE")
    print("=" * 60)

    benchmark_root = Path("data/raw/pranet_benchmark")
    if benchmark_root.exists():
        for d in sorted(benchmark_root.rglob("*")):
            if d.is_dir():
                files = sum(1 for f in d.iterdir() if f.is_file())
                if files > 0:
                    rel = d.relative_to(benchmark_root)
                    print(f"  {rel}: {files} files")

    print("\nDone!")


if __name__ == "__main__":
    main()
