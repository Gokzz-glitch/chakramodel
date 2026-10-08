import os
import sys
import zipfile
import hashlib
import json

def get_file_info(filepath):
    if not os.path.exists(filepath):
        return {"exists": False}
    size = os.path.getsize(filepath)
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
            sha256.update(chunk)
    return {
        "exists": True,
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest()
    }

def inspect_zip(zip_path):
    if not os.path.exists(zip_path):
        return {"exists": False, "error": f"{zip_path} not found"}
    info = get_file_info(zip_path)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()
            infolist = zf.infolist()
            total_uncompressed = sum(x.file_size for x in infolist)
            has_verify_strict = any("verify_strict.py" in x for x in namelist)
            has_weights = [x for x in namelist if x.endswith('.pth') or x.endswith('.pt')]
            has_datasets = [x for x in namelist if any(d in x.lower() for d in ['dataset', 'cvc', 'kvasir', 'etis', 'colon', 'polyp', 'images', 'masks'])]
            top_level = set()
            for x in namelist:
                parts = x.split('/')
                top_level.add(parts[0])
            
            return {
                "file_info": info,
                "file_count": len(namelist),
                "total_uncompressed_bytes": total_uncompressed,
                "total_uncompressed_mb": round(total_uncompressed / (1024 * 1024), 2),
                "top_level_items": sorted(list(top_level)),
                "has_verify_strict": has_verify_strict,
                "verify_strict_matches": [x for x in namelist if "verify_strict.py" in x],
                "weights_contained": has_weights,
                "dataset_sample_matches": has_datasets[:30],
                "total_dataset_files": len(has_datasets),
                "namelist_sample": namelist[:50],
                "namelist_all": namelist
            }
    except Exception as e:
        return {"exists": True, "error": str(e), "file_info": info}

workspace = "m:\\chakramodel"

results = {}

# 1. Zip files to inspect
zips_to_check = [
    "chakramodel_data_scripts.zip",
    "chakramodel-weights.zip",
    "chakramodel_weights_PRIVATE.zip",
    "ChakraModel_Evaluation_Datasets.zip",
    "ChakraModel_Kaggle_Code.zip",
    "ChakraModel_Kaggle_Verification.zip",
    "Kaggle_ZeroTrust_Code.zip"
]

for z in zips_to_check:
    zp = os.path.join(workspace, z)
    print(f"Inspecting {z}...")
    res = inspect_zip(zp)
    # Don't keep all 1000 file names in print output, keep summary
    res_summary = {k: v for k, v in res.items() if k != "namelist_all"}
    results[z] = res_summary

# 2. Weights directory inspection
weights_dir = os.path.join(workspace, "weights")
weights_info = {}
if os.path.exists(weights_dir):
    for fname in sorted(os.listdir(weights_dir)):
        fpath = os.path.join(weights_dir, fname)
        if os.path.isfile(fpath):
            print(f"Hashing weights/{fname}...")
            weights_info[fname] = get_file_info(fpath)
results["weights_dir"] = weights_info

with open(os.path.join(workspace, ".agents", "explorer_m1_3_g7", "zip_and_weights_summary.json"), "w") as f:
    json.dump(results, f, indent=2)

print("Inspection completed successfully. Results saved to zip_and_weights_summary.json")
