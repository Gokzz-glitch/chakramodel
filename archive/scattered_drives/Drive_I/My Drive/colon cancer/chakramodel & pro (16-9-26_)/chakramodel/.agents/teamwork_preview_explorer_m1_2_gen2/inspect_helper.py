import os
import sys
import zipfile
import json
from collections import defaultdict
from pathlib import Path

VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}

def analyze_zip(zip_path):
    print(f"=== Analyzing ZIP: {zip_path} ===", flush=True)
    size_bytes = os.path.getsize(zip_path)
    res = {
        "file": zip_path,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "size_gb": round(size_bytes / (1024 * 1024 * 1024), 3),
        "total_files": 0,
        "ext_counts": defaultdict(int),
        "video_files": [],
        "image_count": 0,
        "mask_count": 0,
        "unmasked_image_count": 0,
        "sample_video_names": [],
        "sample_image_names": [],
        "top_dirs": set(),
        "subdirs_depth2": set(),
        "all_dirs": set(),
    }
    
    with open(zip_path, 'rb') as f:
        magic = f.read(64)
    res["magic_bytes_hex"] = magic[:16].hex()
    res["magic_bytes_repr"] = repr(magic[:32])

    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            infolist = z.infolist()
            res["total_entries"] = len(infolist)
            for info in infolist:
                if info.is_dir():
                    res["all_dirs"].add(info.filename)
                    continue
                res["total_files"] += 1
                p = Path(info.filename)
                ext = p.suffix.lower()
                res["ext_counts"][ext] += 1
                
                parts = p.parts
                if len(parts) > 1:
                    res["top_dirs"].add(parts[0])
                if len(parts) > 2:
                    res["subdirs_depth2"].add(f"{parts[0]}/{parts[1]}")
                if len(parts) > 0:
                    res["all_dirs"].add(str(p.parent).replace('\\', '/'))
                    
                is_mask = False
                lower_name = info.filename.lower()
                if any(k in lower_name for k in ['mask', 'groundtruth', 'ground_truth', 'gt', 'truth', 'annotation']):
                    is_mask = True
                    
                if ext in VIDEO_EXTS:
                    res["video_files"].append((info.filename, info.file_size))
                elif ext in IMAGE_EXTS:
                    res["image_count"] += 1
                    if is_mask:
                        res["mask_count"] += 1
                    else:
                        res["unmasked_image_count"] += 1
                    if len(res["sample_image_names"]) < 10:
                        res["sample_image_names"].append(info.filename)
    except Exception as e:
        res["error"] = str(e)
        print(f"Error opening {zip_path}: {e}")

    res["ext_counts"] = dict(res["ext_counts"])
    res["top_dirs"] = sorted(list(res["top_dirs"]))
    res["subdirs_depth2"] = sorted(list(res["subdirs_depth2"]))
    res["all_dirs_count"] = len(res["all_dirs"])
    res["all_dirs"] = sorted(list(res["all_dirs"]))[:50] # sample
    res["video_count"] = len(res["video_files"])
    res["sample_video_names"] = res["video_files"][:15]
    del res["video_files"] # keep sample
    return res

def analyze_dir(dir_path):
    print(f"=== Analyzing DIR: {dir_path} ===", flush=True)
    res = {
        "dir": dir_path,
        "total_files": 0,
        "total_bytes": 0,
        "ext_counts": defaultdict(int),
        "video_files": [],
        "image_count": 0,
        "mask_count": 0,
        "unmasked_image_count": 0,
        "top_dirs": set(),
        "subdirs_depth2": set(),
        "all_dirs": set(),
    }
    
    root_path = Path(dir_path)
    if not root_path.exists():
        res["exists"] = False
        return res
    res["exists"] = True

    for root, dirs, files in os.walk(dir_path):
        rel_root = os.path.relpath(root, dir_path).replace('\\', '/')
        if rel_root != '.':
            res["all_dirs"].add(rel_root)
            parts = rel_root.split('/')
            if len(parts) >= 1:
                res["top_dirs"].add(parts[0])
            if len(parts) >= 2:
                res["subdirs_depth2"].add(f"{parts[0]}/{parts[1]}")
                
        for f in files:
            res["total_files"] += 1
            fp = os.path.join(root, f)
            try:
                sz = os.path.getsize(fp)
            except Exception:
                sz = 0
            res["total_bytes"] += sz
            
            p = Path(f)
            ext = p.suffix.lower()
            res["ext_counts"][ext] += 1
            
            rel_file = os.path.join(rel_root, f).replace('\\', '/').lower()
            is_mask = any(k in rel_file for k in ['mask', 'groundtruth', 'ground_truth', 'gt', 'truth', 'annotation'])
            
            if ext in VIDEO_EXTS:
                res["video_files"].append((os.path.join(rel_root, f).replace('\\', '/'), sz))
            elif ext in IMAGE_EXTS:
                res["image_count"] += 1
                if is_mask:
                    res["mask_count"] += 1
                else:
                    res["unmasked_image_count"] += 1

    res["size_mb"] = round(res["total_bytes"] / (1024 * 1024), 2)
    res["size_gb"] = round(res["total_bytes"] / (1024 * 1024 * 1024), 3)
    res["ext_counts"] = dict(res["ext_counts"])
    res["top_dirs"] = sorted(list(res["top_dirs"]))
    res["subdirs_depth2"] = sorted(list(res["subdirs_depth2"]))
    res["all_dirs_count"] = len(res["all_dirs"])
    res["all_dirs"] = sorted(list(res["all_dirs"]))[:50]
    res["video_count"] = len(res["video_files"])
    res["sample_video_names"] = res["video_files"][:15]
    del res["video_files"]
    return res

if __name__ == '__main__':
    workspace = r"m:\chakramodel"
    target_zips = [
        "CVC_ClinicVideoDB_Kaggle.zip",
        "ChakraModel_Evaluation_Datasets.zip",
        "chakramodel-weights.zip",
        "chakramodel_weights_PRIVATE.zip",
        "chakramodel_data_scripts.zip",
        "CVC_SampleVideo.zip",
        "kaggle_bundle for testing.zip",
        "kaggle_upload.zip",
        "ChakraModel_Kaggle_Code.zip",
        "ChakraModel_Kaggle_Verification.zip",
        "Kaggle_ZeroTrust_Code.zip"
    ]
    target_dirs = [
        "Kaggle_Datasets_Upload",
        "dataset_yolo",
        "dataset_yolo_fixed",
        "datasets",
        "data"
    ]
    
    out = {"zips": {}, "dirs": {}}
    for z in target_zips:
        zp = os.path.join(workspace, z)
        if os.path.exists(zp):
            out["zips"][z] = analyze_zip(zp)
        else:
            out["zips"][z] = {"exists": False}
            
    for d in target_dirs:
        dp = os.path.join(workspace, d)
        out["dirs"][d] = analyze_dir(dp)
        
    out_file = r"m:\chakramodel\.agents\teamwork_preview_explorer_m1_2_gen2\dataset_metrics.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)
    print("Done! Written to", out_file)
