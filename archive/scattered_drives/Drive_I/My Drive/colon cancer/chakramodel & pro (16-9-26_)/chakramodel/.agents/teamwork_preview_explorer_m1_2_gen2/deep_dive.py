import os
import zipfile
import json
from pathlib import Path
from collections import defaultdict

workspace = r"m:\chakramodel"
report = {}

# 1. ChakraModel_Evaluation_Datasets.zip and Kaggle_Datasets_Upload
def inspect_eval_datasets():
    print("Inspecting ChakraModel_Evaluation_Datasets.zip...")
    zpath = os.path.join(workspace, "ChakraModel_Evaluation_Datasets.zip")
    tree = defaultdict(lambda: {"images": 0, "masks": 0, "others": 0, "files": []})
    with zipfile.ZipFile(zpath, 'r') as z:
        for info in z.infolist():
            if info.is_dir(): continue
            p = info.filename.replace('\\', '/')
            parts = p.split('/')
            folder = '/'.join(parts[:-1]) if len(parts) > 1 else 'root'
            fname = parts[-1].lower()
            if 'mask' in fname or 'mask' in folder.lower() or 'groundtruth' in fname:
                tree[folder]["masks"] += 1
            elif any(fname.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp']):
                tree[folder]["images"] += 1
            else:
                tree[folder]["others"] += 1
            if len(tree[folder]["files"]) < 5:
                tree[folder]["files"].append(parts[-1])
    return {k: dict(v) for k, v in tree.items()}

report["ChakraModel_Evaluation_Datasets_zip"] = inspect_eval_datasets()

# 2. Inspect Kaggle_Datasets_Upload directory
def inspect_kaggle_upload_dir():
    print("Inspecting Kaggle_Datasets_Upload dir...")
    dpath = os.path.join(workspace, "Kaggle_Datasets_Upload")
    tree = defaultdict(lambda: {"images": 0, "masks": 0, "others": 0, "files": []})
    for root, dirs, files in os.walk(dpath):
        rel = os.path.relpath(root, dpath).replace('\\', '/')
        for f in files:
            fl = f.lower()
            if 'mask' in fl or 'mask' in rel.lower() or 'groundtruth' in fl:
                tree[rel]["masks"] += 1
            elif any(fl.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp']):
                tree[rel]["images"] += 1
            else:
                tree[rel]["others"] += 1
            if len(tree[rel]["files"]) < 5:
                tree[rel]["files"].append(f)
    return {k: dict(v) for k, v in tree.items()}

report["Kaggle_Datasets_Upload_dir"] = inspect_kaggle_upload_dir()

# 3. Weights archives
def inspect_weights():
    print("Inspecting weights zips...")
    res = {}
    for zname in ["chakramodel-weights.zip", "chakramodel_weights_PRIVATE.zip"]:
        zp = os.path.join(workspace, zname)
        file_list = []
        with zipfile.ZipFile(zp, 'r') as z:
            for info in z.infolist():
                if info.is_dir(): continue
                file_list.append({
                    "filename": info.filename,
                    "size_bytes": info.file_size,
                    "size_mb": round(info.file_size / (1024*1024), 2)
                })
        res[zname] = file_list
    return res

report["weights_archives"] = inspect_weights()

# 4. chakramodel_data_scripts.zip
def inspect_data_scripts():
    print("Inspecting chakramodel_data_scripts.zip...")
    zp = os.path.join(workspace, "chakramodel_data_scripts.zip")
    tree = defaultdict(lambda: {"count": 0, "files": []})
    with zipfile.ZipFile(zp, 'r') as z:
        for info in z.infolist():
            if info.is_dir(): continue
            p = info.filename.replace('\\', '/')
            parts = p.split('/')
            folder = '/'.join(parts[:-1]) if len(parts) > 1 else 'root'
            tree[folder]["count"] += 1
            if len(tree[folder]["files"]) < 6:
                tree[folder]["files"].append(parts[-1])
    return {k: dict(v) for k, v in tree.items()}

report["chakramodel_data_scripts_zip"] = inspect_data_scripts()

# 5. CVC_SampleVideo.zip
def inspect_sample_video():
    print("Inspecting CVC_SampleVideo.zip...")
    zp = os.path.join(workspace, "CVC_SampleVideo.zip")
    with zipfile.ZipFile(zp, 'r') as z:
        return [{"filename": i.filename, "size_bytes": i.file_size, "size_mb": round(i.file_size/(1024*1024), 2)} for i in z.infolist() if not i.is_dir()]

report["CVC_SampleVideo_zip"] = inspect_sample_video()

# 6. kaggle_bundle for testing.zip and kaggle_upload.zip
def inspect_kaggle_bundles():
    print("Inspecting kaggle bundles...")
    res = {}
    for zname in ["kaggle_bundle for testing.zip", "kaggle_upload.zip"]:
        zp = os.path.join(workspace, zname)
        tree = defaultdict(lambda: {"count": 0, "files": []})
        with zipfile.ZipFile(zp, 'r') as z:
            for info in z.infolist():
                if info.is_dir(): continue
                p = info.filename.replace('\\', '/')
                parts = p.split('/')
                folder = '/'.join(parts[:-1]) if len(parts) > 1 else 'root'
                tree[folder]["count"] += 1
                if len(tree[folder]["files"]) < 5:
                    tree[folder]["files"].append(parts[-1])
        res[zname] = {k: dict(v) for k, v in tree.items()}
    return res

report["kaggle_bundles"] = inspect_kaggle_bundles()

# 7. dataset_yolo and dataset_yolo_fixed
def inspect_yolo_dirs():
    print("Inspecting YOLO dirs...")
    res = {}
    for dname in ["dataset_yolo", "dataset_yolo_fixed"]:
        dp = os.path.join(workspace, dname)
        tree = defaultdict(lambda: {"count": 0, "files": []})
        data_yaml = None
        for root, dirs, files in os.walk(dp):
            rel = os.path.relpath(root, dp).replace('\\', '/')
            for f in files:
                tree[rel]["count"] += 1
                if len(tree[rel]["files"]) < 5:
                    tree[rel]["files"].append(f)
                if f in ["data.yaml", "dataset.yaml"]:
                    try:
                        with open(os.path.join(root, f), 'r', encoding='utf-8') as yf:
                            data_yaml = yf.read()
                    except Exception as e:
                        data_yaml = str(e)
        res[dname] = {"tree": {k: dict(v) for k, v in tree.items()}, "yaml": data_yaml}
    return res

report["yolo_dirs"] = inspect_yolo_dirs()

# 8. datasets and data dirs breakdown
def inspect_datasets_and_data():
    print("Inspecting datasets and data subdirectories...")
    res = {}
    for dname in ["datasets", "data"]:
        dp = os.path.join(workspace, dname)
        subdirs_summary = {}
        # List immediate subdirectories
        for item in os.listdir(dp):
            ip = os.path.join(dp, item)
            if os.path.isdir(ip):
                sub_files = 0
                sub_bytes = 0
                exts = defaultdict(int)
                sample_files = []
                inner_dirs = []
                for r, ds, fs in os.walk(ip):
                    rel_r = os.path.relpath(r, ip).replace('\\', '/')
                    if rel_r != '.' and rel_r not in inner_dirs and len(inner_dirs) < 10:
                        inner_dirs.append(rel_r)
                    for f in fs:
                        sub_files += 1
                        fp = os.path.join(r, f)
                        try:
                            sub_bytes += os.path.getsize(fp)
                        except: pass
                        ext = Path(f).suffix.lower()
                        exts[ext] += 1
                        if len(sample_files) < 5:
                            sample_files.append(os.path.join(rel_r, f).replace('\\', '/'))
                subdirs_summary[item] = {
                    "total_files": sub_files,
                    "size_mb": round(sub_bytes / (1024*1024), 2),
                    "exts": dict(exts),
                    "inner_subdirs_sample": inner_dirs,
                    "sample_files": sample_files
                }
            else:
                subdirs_summary[item] = {
                    "type": "file",
                    "size_bytes": os.path.getsize(ip)
                }
        res[dname] = subdirs_summary
    return res

report["datasets_and_data_subdirs"] = inspect_datasets_and_data()

out_path = r"m:\chakramodel\.agents\teamwork_preview_explorer_m1_2_gen2\deep_dive_metrics.json"
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2)
print("Deep dive complete! Saved to", out_path)
