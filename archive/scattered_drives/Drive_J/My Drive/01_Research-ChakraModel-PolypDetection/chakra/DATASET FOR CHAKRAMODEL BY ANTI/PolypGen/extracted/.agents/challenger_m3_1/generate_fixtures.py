#!/usr/bin/env python3
"""
Adversarial Fixture Generator for PolypGen Verifier Empirical Testing
Author: Challenger 1 (Milestone 3)
"""

import os
from pathlib import Path
import random
import shutil

def generate_fixtures(base_dir: Path):
    print(f"Generating fixtures in: {base_dir}")
    
    # 1. Isolated samples folder
    isolated_dir = base_dir / "isolated_samples"
    isolated_dir.mkdir(parents=True, exist_ok=True)
    
    # Empty directory
    empty_sub = isolated_dir / "empty_directory_sample"
    empty_sub.mkdir(parents=True, exist_ok=True)
    
    # Source legitimate image
    source_img_path = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\data_C1\images_C1\100H0050.jpg")
    if not source_img_path.exists():
        raise FileNotFoundError(f"Source image not found: {source_img_path}")
    
    with open(source_img_path, "rb") as f:
        valid_bytes = f.read()
    
    total_len = len(valid_bytes)
    print(f"Read {total_len} bytes from source legitimate image: {source_img_path.name}")
    
    # Fixture 1: Valid baseline copy
    valid_file = isolated_dir / "valid_baseline.jpg"
    with open(valid_file, "wb") as f:
        f.write(valid_bytes)
    print(f"  Created: {valid_file.name} ({len(valid_bytes)} bytes)")
    
    # Fixture 2: 0-byte file with .jpg extension
    zero_file = isolated_dir / "zero_byte.jpg"
    with open(zero_file, "wb") as f:
        pass
    print(f"  Created: {zero_file.name} (0 bytes)")
    
    # Fixture 3: Random garbage bytes with .jpg extension
    random.seed(42)
    garbage_bytes = bytes([random.randint(0, 255) for _ in range(8192)])
    garbage_file = isolated_dir / "random_garbage.jpg"
    with open(garbage_file, "wb") as f:
        f.write(garbage_bytes)
    print(f"  Created: {garbage_file.name} ({len(garbage_bytes)} bytes)")
    
    # Fixture 4: Truncated / cut-off JPEG (first 25,000 bytes, ~12% of file)
    truncated_bytes = valid_bytes[:25000]
    truncated_file = isolated_dir / "truncated_cutoff.jpg"
    with open(truncated_file, "wb") as f:
        f.write(truncated_bytes)
    print(f"  Created: {truncated_file.name} ({len(truncated_bytes)} bytes)")
    
    # Fixture 5: Valid JPEG with corrupted middle bytes
    # Overwrite 4000 bytes in the middle with 0x00 and random bytes
    mid_start = total_len // 2
    corrupt_mid_bytes = bytearray(valid_bytes)
    for i in range(mid_start, mid_start + 4000):
        corrupt_mid_bytes[i] = 0x00 if (i % 2 == 0) else random.randint(1, 255)
    corrupted_mid_file = isolated_dir / "corrupted_middle_bytes.jpg"
    with open(corrupted_mid_file, "wb") as f:
        f.write(corrupt_mid_bytes)
    print(f"  Created: {corrupted_mid_file.name} ({len(corrupt_mid_bytes)} bytes)")
    
    # Fixture 6: Valid JPEG with corrupted end bytes (strip EOI marker 0xFF 0xD9 and replace last 1500 bytes with random)
    corrupt_end_bytes = bytearray(valid_bytes[:-1500])
    corrupt_end_bytes.extend(bytes([random.randint(0, 255) for _ in range(1500)]))
    corrupted_end_file = isolated_dir / "corrupted_end_bytes.jpg"
    with open(corrupted_end_file, "wb") as f:
        f.write(corrupt_end_bytes)
    print(f"  Created: {corrupted_end_file.name} ({len(corrupt_end_bytes)} bytes)")

    print("All isolated fixtures created successfully.")

if __name__ == "__main__":
    work_dir = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\.agents\challenger_m3_1")
    fixture_root = work_dir / "fixtures"
    generate_fixtures(fixture_root)
