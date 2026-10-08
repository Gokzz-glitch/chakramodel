#!/usr/bin/env python3
"""
CHD Dataset Balancer with Deduplication
Creates balanced train/valid/test splits from CHD and Non-CHD image directories
"""

import os
import shutil
from pathlib import Path
from collections import defaultdict
import random
from typing import Dict, List, Tuple
import json
from datetime import datetime

# ===== CONFIGURATION =====
CHD_PATH = r"C:\Users\imgk3\Downloads\CHD"
NOCHD_PATH = r"C:\Users\imgk3\Downloads\Non_CHD"
OUTPUT_PATH = r"C:\Users\imgk3\Downloads\chd_dataset"

TRAIN_RATIO = 0.70
VALID_RATIO = 0.10
TEST_RATIO = 0.20
RANDOM_SEED = 42

# ===== HELPER FUNCTIONS =====

def get_patient_id(folder_name: str) -> str:
    """Extract patient ID from folder name (e.g., 'aedxf00001rrfgkl0')"""
    return folder_name.strip()

def get_patients(directory: str) -> List[str]:
    """Get all patient folders from a directory"""
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")

    patients = [d for d in os.listdir(directory)
                if os.path.isdir(os.path.join(directory, d))]
    return sorted(patients)

def count_images(patient_path: str) -> int:
    """Count PNG images in a patient folder"""
    return len([f for f in os.listdir(patient_path)
               if f.lower().endswith('.png')])

def analyze_duplicates(chd_patients: List[str], nochd_patients: List[str]) -> Dict:
    """Analyze duplicates between CHD and Non-CHD"""
    chd_set = set(chd_patients)
    nochd_set = set(nochd_patients)

    duplicates = chd_set.intersection(nochd_set)

    return {
        'chd_count': len(chd_patients),
        'nochd_count': len(nochd_patients),
        'duplicate_count': len(duplicates),
        'duplicates': list(duplicates),
        'chd_only': len(chd_set - nochd_set),
        'nochd_only': len(nochd_set - chd_set)
    }

def create_stratified_split(patients: List[str], class_name: str) -> Dict[str, List[str]]:
    """Create train/valid/test split with patient-level stratification"""

    # Shuffle for randomness
    shuffled = patients.copy()
    random.shuffle(shuffled)

    total = len(shuffled)
    train_idx = int(total * TRAIN_RATIO)
    valid_idx = train_idx + int(total * VALID_RATIO)

    train = shuffled[:train_idx]
    valid = shuffled[train_idx:valid_idx]
    test = shuffled[valid_idx:]

    print(f"\n{class_name} Split:")
    print(f"  Train: {len(train)} patients ({len(train)/total*100:.1f}%)")
    print(f"  Valid: {len(valid)} patients ({len(valid)/total*100:.1f}%)")
    print(f"  Test:  {len(test)} patients ({len(test)/total*100:.1f}%)")

    return {'train': train, 'valid': valid, 'test': test}

def copy_images(src_dir: str, patient_id: str, dst_dir: str) -> int:
    """Copy all PNG images from source patient folder to destination"""
    src_patient = os.path.join(src_dir, patient_id)

    if not os.path.exists(src_patient):
        return 0

    count = 0
    for filename in os.listdir(src_patient):
        if filename.lower().endswith('.png'):
            src_file = os.path.join(src_patient, filename)
            dst_file = os.path.join(dst_dir, filename)

            try:
                shutil.copy2(src_file, dst_file)
                count += 1
            except Exception as e:
                print(f"Error copying {src_file}: {e}")

    return count

def create_directory_structure(output_path: str) -> Dict:
    """Create output directory structure"""
    dirs = {
        'chd_train': os.path.join(output_path, 'chd', 'images', 'train'),
        'chd_valid': os.path.join(output_path, 'chd', 'images', 'valid'),
        'chd_test': os.path.join(output_path, 'chd', 'images', 'test'),
        'nochd_train': os.path.join(output_path, 'nonchd', 'images', 'train'),
        'nochd_valid': os.path.join(output_path, 'nonchd', 'images', 'valid'),
        'nochd_test': os.path.join(output_path, 'nonchd', 'images', 'test'),
    }

    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
        print(f"Created: {dir_path}")

    return dirs

def populate_dataset(
    chd_dir: str,
    nochd_dir: str,
    chd_split: Dict,
    nochd_split: Dict,
    output_dirs: Dict
) -> Dict:
    """Copy images to train/valid/test directories"""

    stats = {
        'chd': {'train': 0, 'valid': 0, 'test': 0},
        'nochd': {'train': 0, 'valid': 0, 'test': 0}
    }

    # Copy CHD
    print("\nProcessing CHD patients...")
    for patient in chd_split['train']:
        count = copy_images(chd_dir, patient, output_dirs['chd_train'])
        stats['chd']['train'] += count
    print(f"  Train: {stats['chd']['train']} images from {len(chd_split['train'])} patients")

    for patient in chd_split['valid']:
        count = copy_images(chd_dir, patient, output_dirs['chd_valid'])
        stats['chd']['valid'] += count
    print(f"  Valid: {stats['chd']['valid']} images from {len(chd_split['valid'])} patients")

    for patient in chd_split['test']:
        count = copy_images(chd_dir, patient, output_dirs['chd_test'])
        stats['chd']['test'] += count
    print(f"  Test:  {stats['chd']['test']} images from {len(chd_split['test'])} patients")

    # Copy Non-CHD
    print("\nProcessing Non-CHD patients...")
    for patient in nochd_split['train']:
        count = copy_images(nochd_dir, patient, output_dirs['nochd_train'])
        stats['nochd']['train'] += count
    print(f"  Train: {stats['nochd']['train']} images from {len(nochd_split['train'])} patients")

    for patient in nochd_split['valid']:
        count = copy_images(nochd_dir, patient, output_dirs['nochd_valid'])
        stats['nochd']['valid'] += count
    print(f"  Valid: {stats['nochd']['valid']} images from {len(nochd_split['valid'])} patients")

    for patient in nochd_split['test']:
        count = copy_images(nochd_dir, patient, output_dirs['nochd_test'])
        stats['nochd']['test'] += count
    print(f"  Test:  {stats['nochd']['test']} images from {len(nochd_split['test'])} patients")

    return stats

def write_report(output_path: str, analysis: Dict, stats: Dict) -> None:
    """Write dataset report"""

    report_path = os.path.join(output_path, 'dataset_report.txt')

    total_chd = sum(stats['chd'].values())
    total_nochd = sum(stats['nochd'].values())

    report = f"""
================================================
BALANCED CHD DATASET - CREATION REPORT
================================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SOURCE ANALYSIS:
- CHD Patients: {analysis['chd_count']}
- Non-CHD Patients: {analysis['nochd_count']}
- Duplicate Patients: {analysis['duplicate_count']}
- CHD Only: {analysis['chd_only']}
- Non-CHD Only: {analysis['nochd_only']}

FINAL DATASET STATISTICS:

CHD CLASS:
  Train: {stats['chd']['train']} images
  Valid: {stats['chd']['valid']} images
  Test:  {stats['chd']['test']} images
  Total: {total_chd} images

Non-CHD CLASS:
  Train: {stats['nochd']['train']} images
  Valid: {stats['nochd']['valid']} images
  Test:  {stats['nochd']['test']} images
  Total: {total_nochd} images

DATASET BALANCE:
  Train Set: CHD={stats['chd']['train']} vs Non-CHD={stats['nochd']['train']}
             (Ratio: {stats['chd']['train']/stats['nochd']['train']:.3f}:1)
  Valid Set: CHD={stats['chd']['valid']} vs Non-CHD={stats['nochd']['valid']}
             (Ratio: {stats['chd']['valid']/stats['nochd']['valid']:.3f}:1)
  Test Set:  CHD={stats['chd']['test']} vs Non-CHD={stats['nochd']['test']}
             (Ratio: {stats['chd']['test']/stats['nochd']['test']:.3f}:1)

SPLIT RATIOS:
  Train: {TRAIN_RATIO*100:.0f}%
  Valid: {VALID_RATIO*100:.0f}%
  Test:  {TEST_RATIO*100:.0f}%

OUTPUT DIRECTORY:
{output_path}

DIRECTORY STRUCTURE:
chd_dataset/
├── chd/
│   └── images/
│       ├── train/ ({stats['chd']['train']} images)
│       ├── valid/ ({stats['chd']['valid']} images)
│       └── test/  ({stats['chd']['test']} images)
└── nonchd/
    └── images/
        ├── train/ ({stats['nochd']['train']} images)
        ├── valid/ ({stats['nochd']['valid']} images)
        └── test/  ({stats['nochd']['test']} images)

================================================
"""

    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\n✓ Report saved to: {report_path}")
    print(report)

def main():
    """Main execution"""

    print("=" * 50)
    print("  CHD DATASET BALANCER (Python Version)")
    print("=" * 50)
    print(f"\nSource CHD: {CHD_PATH}")
    print(f"Source Non-CHD: {NOCHD_PATH}")
    print(f"Output: {OUTPUT_PATH}\n")

    # Set random seed for reproducibility
    random.seed(RANDOM_SEED)

    # Step 1: Get patients
    print("Reading patient directories...")
    chd_patients = get_patients(CHD_PATH)
    nochd_patients = get_patients(NOCHD_PATH)

    # Step 2: Analyze duplicates
    print("\n========== ANALYZING DUPLICATES ==========")
    analysis = analyze_duplicates(chd_patients, nochd_patients)
    print(f"CHD Patients: {analysis['chd_count']}")
    print(f"Non-CHD Patients: {analysis['nochd_count']}")
    print(f"Duplicates Found: {analysis['duplicate_count']}")

    if analysis['duplicates']:
        print("\nDuplicate Patients:")
        for pat in analysis['duplicates'][:10]:  # Show first 10
            print(f"  - {pat}")
        if len(analysis['duplicates']) > 10:
            print(f"  ... and {len(analysis['duplicates'])-10} more")

    # Step 3: Create output structure
    print("\n========== CREATING DIRECTORY STRUCTURE ==========")
    output_dirs = create_directory_structure(OUTPUT_PATH)

    # Step 4: Create splits
    print("\n========== CREATING STRATIFIED SPLITS ==========")
    chd_split = create_stratified_split(chd_patients, "CHD")
    nochd_split = create_stratified_split(nochd_patients, "Non-CHD")

    # Step 5: Populate dataset
    print("\n========== COPYING FILES ==========")
    stats = populate_dataset(
        CHD_PATH,
        NOCHD_PATH,
        chd_split,
        nochd_split,
        output_dirs
    )

    # Step 6: Write report
    write_report(OUTPUT_PATH, analysis, stats)

    print("\n✓ Dataset creation complete!" + " " * 10)

if __name__ == "__main__":
    main()
