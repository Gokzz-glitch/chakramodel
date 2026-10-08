import os
import sys
import json
from collections import defaultdict, Counter
from pathlib import Path

DATASET_ROOT = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted")
OUTPUT_DIR = Path(r"m:\chakramodel\.agents\teamwork_preview_explorer_pg_1")

def analyze_extracted():
    print(f"Target dataset root: {DATASET_ROOT}")
    if not DATASET_ROOT.exists():
        print(f"ERROR: {DATASET_ROOT} does not exist!")
        return

    # 1. Top level
    top_level_items = list(DATASET_ROOT.iterdir())
    print("\n--- Top Level in extracted ---")
    for item in top_level_items:
        print(f"  {'[DIR]' if item.is_dir() else '[FILE]'} {item.name}")

    polypgen_dir = DATASET_ROOT / "PolypGen2021_MultiCenterData_v3"
    
    # Analyze PolypGen2021_MultiCenterData_v3 root files
    root_files = []
    root_dirs = []
    for item in polypgen_dir.iterdir():
        if item.is_file():
            root_files.append((item.name, item.stat().st_size))
        else:
            root_dirs.append(item.name)
            
    print("\n--- PolypGen2021_MultiCenterData_v3 Root Files ---")
    for fname, size in sorted(root_files):
        print(f"  {fname:45} | Size: {size:>12,d} bytes")
        
    print("\n--- PolypGen2021_MultiCenterData_v3 Root Dirs ---")
    for dname in sorted(root_dirs):
        print(f"  {dname}")

    # Analyze Center directories: data_C1 to data_C6
    center_stats = {}
    for c_idx in range(1, 7):
        c_dir = polypgen_dir / f"data_C{c_idx}"
        if not c_dir.exists():
            print(f"WARNING: {c_dir} not found!")
            continue
        c_stat = {}
        for sub in c_dir.iterdir():
            if sub.is_dir():
                files = list(sub.iterdir())
                exts = Counter(f.suffix.lower() for f in files if f.is_file())
                subdirs = [f.name for f in files if f.is_dir()]
                hidden = [f.name for f in files if f.name.startswith('.')]
                c_stat[sub.name] = {
                    "total_files": len([f for f in files if f.is_file()]),
                    "extensions": dict(exts),
                    "subdirs": subdirs,
                    "hidden": hidden,
                    "sample_files": [f.name for f in files[:3]]
                }
            elif sub.is_file():
                c_stat[f"FILE:{sub.name}"] = {
                    "size": sub.stat().st_size
                }
        center_stats[f"data_C{c_idx}"] = c_stat

    # Analyze dataDetails_PolypGen_SingleFrames
    single_frames_details_dir = polypgen_dir / "dataDetails_PolypGen_SingleFrames"
    single_frames_details = {}
    if single_frames_details_dir.exists():
        for item in single_frames_details_dir.iterdir():
            if item.is_file():
                single_frames_details[item.name] = item.stat().st_size

    # Analyze codes
    codes_dir = polypgen_dir / "codes"
    codes_files = {}
    if codes_dir.exists():
        for root, dirs, files in os.walk(codes_dir):
            rel = os.path.relpath(root, codes_dir)
            codes_files[rel] = {
                "dirs": dirs,
                "files": files
            }

    # Analyze sequenceData
    seq_dir = polypgen_dir / "sequenceData"
    seq_stats = {"positive": {}, "negativeOnly": {}}
    if seq_dir.exists():
        pos_dir = seq_dir / "positive"
        if pos_dir.exists():
            for s in sorted(pos_dir.iterdir(), key=lambda p: (len(p.name), p.name)):
                if s.is_dir():
                    s_stat = {}
                    for sub in s.iterdir():
                        if sub.is_dir():
                            files = list(sub.iterdir())
                            exts = Counter(f.suffix.lower() for f in files if f.is_file())
                            s_stat[sub.name] = {
                                "file_count": len([f for f in files if f.is_file()]),
                                "extensions": dict(exts)
                            }
                        elif sub.is_file():
                            s_stat[f"FILE:{sub.name}"] = sub.stat().st_size
                    seq_stats["positive"][s.name] = s_stat

        neg_dir = seq_dir / "negativeOnly"
        if neg_dir.exists():
            for s in sorted(neg_dir.iterdir(), key=lambda p: (len(p.name), p.name)):
                if s.is_dir():
                    files = list(s.iterdir())
                    exts = Counter(f.suffix.lower() for f in files if f.is_file())
                    seq_stats["negativeOnly"][s.name] = {
                        "file_count": len([f for f in files if f.is_file()]),
                        "subdirs": [f.name for f in files if f.is_dir()],
                        "extensions": dict(exts)
                    }

    # Analyze imagesAll_positive
    images_all_dir = polypgen_dir / "imagesAll_positive"
    images_all_stats = {}
    if images_all_dir.exists():
        files = list(images_all_dir.iterdir())
        exts = Counter(f.suffix.lower() for f in files if f.is_file())
        hidden = [f.name for f in files if f.name.startswith('.')]
        sample = [f.name for f in files[:5]]
        images_all_stats = {
            "total_files": len(files),
            "extensions": dict(exts),
            "hidden": hidden,
            "sample_files": sample
        }

    # Analyze non-image/non-mask files and anomalies across the dataset
    anomalies = []
    zero_byte_files = []
    hidden_files = []
    
    for root, dirs, files in os.walk(polypgen_dir):
        for f in files:
            full_p = os.path.join(root, f)
            rel_p = os.path.relpath(full_p, polypgen_dir)
            st = os.stat(full_p)
            if st.st_size == 0:
                zero_byte_files.append(rel_p)
            if f.startswith('.'):
                hidden_files.append(rel_p)
            ext = os.path.splitext(f)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.xml', '.txt', '.csv', '.py', '.md', '.html', '.zip']:
                anomalies.append((rel_p, ext, st.st_size))

    result = {
        "dataset_root": str(DATASET_ROOT),
        "top_level_directories": [item.name for item in top_level_items if item.is_dir()],
        "top_level_files": [item.name for item in top_level_items if item.is_file()],
        "polypgen_root_files": root_files,
        "polypgen_root_dirs": root_dirs,
        "center_stats": center_stats,
        "single_frames_details": single_frames_details,
        "codes_files": codes_files,
        "seq_stats": seq_stats,
        "images_all_stats": images_all_stats,
        "zero_byte_files": zero_byte_files,
        "hidden_files_count": len(hidden_files),
        "hidden_files_sample": hidden_files[:20],
        "non_standard_extensions": anomalies
    }

    out_json = OUTPUT_DIR / "polypgen_analysis.json"
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2)
    print(f"\nSaved analysis to {out_json}")

if __name__ == "__main__":
    analyze_extracted()
