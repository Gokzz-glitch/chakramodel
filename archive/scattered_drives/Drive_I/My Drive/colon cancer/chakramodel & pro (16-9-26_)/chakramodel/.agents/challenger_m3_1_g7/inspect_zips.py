import os
import sys
import hashlib
import zipfile
from pathlib import Path

ZIPS = [
    r"m:\chakramodel\chakramodel_data_scripts.zip",
    r"m:\chakramodel\chakramodel-weights.zip",
    r"m:\chakramodel\chakramodel_weights_PRIVATE.zip",
]

def get_file_md5(filepath):
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def inspect_zip(zip_path_str):
    p = Path(zip_path_str)
    print(f"\n{'='*80}")
    print(f"FILE: {p.name}")
    print(f"Path: {p}")
    if not p.exists():
        print("❌ FILE NOT FOUND!")
        return
    
    size_bytes = p.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    print(f"Size: {size_bytes:,} bytes ({size_mb:.2f} MiB)")
    print("Computing file MD5...")
    file_md5 = get_file_md5(p)
    print(f"MD5: {file_md5}")

    with zipfile.ZipFile(p, 'r') as z:
        infolist = z.infolist()
        namelist = z.namelist()
        total_files = len(namelist)
        total_uncompressed = sum(info.file_size for info in infolist)
        total_compressed = sum(info.compress_size for info in infolist)
        
        print(f"Total entries in archive: {total_files}")
        print(f"Total uncompressed size: {total_uncompressed:,} bytes ({total_uncompressed/(1024*1024):.2f} MiB)")
        print(f"Total compressed size:   {total_compressed:,} bytes ({total_compressed/(1024*1024):.2f} MiB)")

        # Directory structure analysis
        top_level_prefixes = set()
        for name in namelist:
            parts = name.split('/')
            top_level_prefixes.add(parts[0])
        print(f"Top-level prefixes/files: {sorted(list(top_level_prefixes))}")

        print("\nFirst 15 entries:")
        for name in namelist[:15]:
            print(f"  - {name}")

        # Check for key target assets
        print("\nTarget Asset Search:")
        targets = [
            "chakra_transformer_best.pth",
            "best.pt",
            "conformal_calibration.json",
            "verify_strict.py",
            "chakranet_segmenter.py",
            "metrics_engine_v2.py",
        ]
        found_targets = {}
        for info in infolist:
            basename = Path(info.filename).name
            if basename in targets:
                found_targets[info.filename] = info

        if found_targets:
            for fname, info in sorted(found_targets.items()):
                print(f"  Found '{fname}':")
                print(f"    Size: {info.file_size:,} bytes ({info.file_size/(1024*1024):.2f} MiB)")
                print(f"    CRC: {hex(info.CRC)}")
                # Compute inner MD5 for weights and key scripts
                if info.file_size < 1500 * 1024 * 1024 and info.file_size > 0:
                    with z.open(info) as zf:
                        inner_md5 = hashlib.md5(zf.read()).hexdigest()
                    print(f"    Inner MD5: {inner_md5}")
        else:
            print("  ⚠️ NONE of the key target assets found!")

        # Data directory breakdown
        data_entries = [name for name in namelist if name.startswith("data/")]
        if data_entries:
            print(f"\nData folder present! Total data entries: {len(data_entries)}")
            subdatasets = set()
            for d in data_entries:
                parts = d.split('/')
                if len(parts) > 1 and parts[1]:
                    subdatasets.add(parts[1])
            print(f"Sub-datasets under data/: {sorted(list(subdatasets))}")
            for sd in sorted(list(subdatasets)):
                sd_images = [d for d in data_entries if f"data/{sd}/images/" in d and not d.endswith("/")]
                sd_masks = [d for d in data_entries if f"data/{sd}/masks/" in d and not d.endswith("/")]
                print(f"  - {sd}: {len(sd_images)} images, {len(sd_masks)} masks")

if __name__ == "__main__":
    for z in ZIPS:
        inspect_zip(z)

