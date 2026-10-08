import json

with open(r"m:\chakramodel\.agents\teamwork_preview_explorer_m1_2_gen2\deep_dive_metrics.json", "r") as f:
    d = json.load(f)

print("=== 1. ChakraModel_Evaluation_Datasets_zip ===")
for folder, data in d["ChakraModel_Evaluation_Datasets_zip"].items():
    print(f"  {folder}: images={data['images']}, masks={data['masks']}, others={data['others']}, samples={data['files'][:3]}")

print("\n=== 2. Kaggle_Datasets_Upload_dir ===")
for folder, data in d["Kaggle_Datasets_Upload_dir"].items():
    print(f"  {folder}: images={data['images']}, masks={data['masks']}, others={data['others']}, samples={data['files'][:3]}")

print("\n=== 3. weights_archives ===")
for zname, files in d["weights_archives"].items():
    print(f"  Archive: {zname}")
    for f in files:
        print(f"    {f['filename']}: {f['size_mb']} MB ({f['size_bytes']} bytes)")

print("\n=== 4. chakramodel_data_scripts_zip ===")
for folder, data in d["chakramodel_data_scripts_zip"].items():
    print(f"  {folder}: count={data['count']}, samples={data['files'][:3]}")

print("\n=== 5. CVC_SampleVideo_zip ===")
for f in d["CVC_SampleVideo_zip"]:
    print(f"  {f['filename']}: {f['size_mb']} MB ({f['size_bytes']} bytes)")
