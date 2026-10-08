"""
Comprehensive Empirical Stress-Testing Harness for ChakraModel Colab/Cloud Pipeline.
Tests:
1. POSIX vs Windows Casing Incompatibilities (fnmatchcase, extensions, Drive folder names)
2. Path Resolution with Spaces, Special Characters, Trailing Slashes, Quotes
3. Missing Directories and Fail-Fast vs Silent Return verification
4. Archive Unpacking Collision and Nesting Pitfalls (weights/ vs weights/weights/)
5. The best.pt Checkpoint Hash Discrepancy Analysis
"""
import os
import sys
import fnmatch
import hashlib
import tempfile
import zipfile
import shutil
from pathlib import Path

# Force UTF-8 stdout
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


def test_posix_casing_sensitivity():
    print("\n" + "="*80)
    print("STRESS TEST 1: POSIX Case-Sensitivity Vulnerabilities (Colab Ubuntu ext4)")
    print("="*80)

    # 1. Drive Directory Discovery Vulnerability in Worker M2 Artifact 1
    # Worker M2's Cell 2 line 525 uses: drive_root.glob('*chakra*')
    sample_drive_names = [
        "chakramodel",
        "ChakraModel",
        "CHAKRAMODEL",
        "chakramodel_collab",
        "ChakraModel_Colab",
        "my_chakramodel_project",
    ]
    pattern = "*chakra*"
    print(f"Testing pattern '{pattern}' against Drive directory variants using POSIX case sensitivity:")
    for name in sample_drive_names:
        # On POSIX (ext4), globbing uses case-sensitive fnmatchcase
        matches_posix = fnmatch.fnmatchcase(name, pattern)
        # On Windows (NTFS), globbing is case-insensitive
        matches_win = fnmatch.fnmatchcase(name.lower(), pattern.lower())
        status = "✅ MATCH" if matches_posix else "❌ BLIND SPOT (Fails on Linux/Colab)"
        print(f"  Folder '{name}': Windows={matches_win}, POSIX={matches_posix} -> {status}")

    # 2. File Extension Casing Vulnerability
    sample_images = [
        "synthetic_0001.png",
        "synthetic_0002.PNG",
        "synthetic_0003.jpg",
        "synthetic_0004.JPG",
        "synthetic_0005.JPEG",
        "synthetic_0006.Png",
    ]
    # In legacy verify_strict.py line 37:
    # list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.tif"))
    print("\nTesting Legacy glob('*.png') on mixed-casing image files under POSIX rules:")
    for img in sample_images:
        legacy_matched = fnmatch.fnmatchcase(img, "*.png") or fnmatch.fnmatchcase(img, "*.jpg")
        lower_matched = Path(img).suffix.lower() in {".png", ".jpg", ".jpeg", ".tif"}
        print(f"  File '{img}': Legacy POSIX glob={legacy_matched}, Lowercase suffix check={lower_matched}")

def test_spaces_and_special_paths():
    print("\n" + "="*80)
    print("STRESS TEST 2: Paths with Spaces, Quotes, and Complex Characters")
    print("="*80)
    test_paths = [
        r"C:\Users\John Doe\My Drive\chakramodel",
        r'"M:\chakramodel\weights\chakra_transformer_best.pth"',
        r"'M:\chakramodel\weights\chakra_transformer_best.pth'",
        r"/content/drive/My Drive/chakramodel_collab",
        r"M:\chakramodel\\weights//chakra_transformer_best.pth",
    ]
    for p_str in test_paths:
        cleaned = p_str.strip('\'"')
        path_obj = Path(cleaned)
        print(f"  Raw: {p_str:<60} -> Cleaned: {str(path_obj)}")

def test_silent_dataset_failure():
    print("\n" + "="*80)
    print("STRESS TEST 3: Silent Dataset Failure Bug in Worker M2 Artifact 2")
    print("="*80)
    # In Worker M2 Artifact 2 (lines 706-711):
    # if not images_dir.exists():
    #     print(f"[ERROR] Images directory not found: {images_dir}")
    #     return None
    # This function returns None without raising an exception!
    def mock_verify_dataset_worker_m2(images_dir: Path):
        if not images_dir.exists():
            print(f"  [ERROR] Images directory not found: {images_dir}")
            return None
        return {"Dice": 0.81}

    def mock_verify_dataset_fail_fast(images_dir: Path):
        if not images_dir.exists():
            raise FileNotFoundError(f"❌ [FAIL-FAST] Images directory does not exist: {images_dir}")
        return {"Dice": 0.81}

    nonexistent_dir = Path("/nonexistent/data/cvc-colondb/images")
    print("Testing Worker M2 behavior on missing dataset:")
    res_m2 = mock_verify_dataset_worker_m2(nonexistent_dir)
    print(f"  Result returned: {res_m2} (Notice: Script proceeds, exit status 0! Masking failure!)")

    print("\nTesting Fail-Fast behavior on missing dataset:")
    try:
        mock_verify_dataset_fail_fast(nonexistent_dir)
    except FileNotFoundError as e:
        print(f"  Exception caught: {e}")
        print("  ✅ Execution halted before downstream metric corruption.")

def test_archive_unpacking_pitfalls():
    print("\n" + "="*80)
    print("STRESS TEST 4: Archive Unpacking Layout Pitfalls & Destructive Overwrites")
    print("="*80)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Scenario A: Unpacking flat chakramodel-weights.zip into /content/
        target_a = tmp / "scenario_a"
        target_a.mkdir()
        # Simulated extraction of chakramodel-weights.zip
        (target_a / "chakra_transformer_best.pth").touch()
        (target_a / "best.pt").touch()
        
        # Scenario B: Unpacking chakramodel_weights_PRIVATE.zip into target with existing weights/
        target_b = tmp / "scenario_b"
        weights_sub = target_b / "weights"
        weights_sub.mkdir(parents=True)
        # If user extracts PRIVATE.zip (which already has weights/) into target_b/weights/
        nested_weights = weights_sub / "weights"
        nested_weights.mkdir()
        (nested_weights / "chakra_transformer_best.pth").touch()

        print("Testing Path Resolutions:")
        print(f"  Scenario A (Flat unpack at root):")
        print(f"    root/weights/chakra_transformer_best.pth exists: {(target_a / 'weights' / 'chakra_transformer_best.pth').exists()}")
        print(f"    root/chakra_transformer_best.pth exists:         {(target_a / 'chakra_transformer_best.pth').exists()}")

        print(f"  Scenario B (Accidental double-nesting weights/weights/):")
        print(f"    root/weights/chakra_transformer_best.pth exists:         {(target_b / 'weights' / 'chakra_transformer_best.pth').exists()}")
        print(f"    root/weights/weights/chakra_transformer_best.pth exists: {(target_b / 'weights' / 'weights' / 'chakra_transformer_best.pth').exists()}")

def test_best_pt_discrepancy():
    print("\n" + "="*80)
    print("STRESS TEST 5: Empirical Check of YOLO Checkpoints (best.pt)")
    print("="*80)
    local_weights = Path(r"m:\chakramodel\weights\best.pt")
    if local_weights.exists():
        size = local_weights.stat().st_size
        h = hashlib.md5(local_weights.read_bytes()).hexdigest()
        print(f"Local disk 'weights/best.pt':")
        print(f"  Size: {size:,} bytes")
        print(f"  MD5:  {h}")
    else:
        print("Local disk 'weights/best.pt' NOT found!")

    # Check chakramodel-weights.zip
    with zipfile.ZipFile(r"m:\chakramodel\chakramodel-weights.zip") as z:
        info = z.getinfo("best.pt")
        h = hashlib.md5(z.read("best.pt")).hexdigest()
        print(f"In 'chakramodel-weights.zip' ('best.pt'):")
        print(f"  Size: {info.file_size:,} bytes")
        print(f"  MD5:  {h}")

    # Check chakramodel_weights_PRIVATE.zip
    with zipfile.ZipFile(r"m:\chakramodel\chakramodel_weights_PRIVATE.zip") as z:
        info = z.getinfo("weights/best.pt")
        h = hashlib.md5(z.read("weights/best.pt")).hexdigest()
        print(f"In 'chakramodel_weights_PRIVATE.zip' ('weights/best.pt'):")
        print(f"  Size: {info.file_size:,} bytes")
        print(f"  MD5:  {h}")

if __name__ == "__main__":
    test_posix_casing_sensitivity()
    test_spaces_and_special_paths()
    test_silent_dataset_failure()
    test_archive_unpacking_pitfalls()
    test_best_pt_discrepancy()
