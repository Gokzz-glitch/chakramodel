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

print("\n=== 6. kaggle_bundles ===")
for zname, tree in d["kaggle_bundles"].items():
    print(f"  Archive: {zname}")
    for folder, data in tree.items():
        print(f"    {folder}: count={data['count']}, samples={data['files'][:3]}")

print("\n=== 7. YOLO Dirs ===")
for yname, info in d["yolo_dirs"].items():
    print(f"  Directory: {yname}")
    for folder, data in info["tree"].items():
        print(f"    {folder}: count={data['count']}, samples={data['files'][:3]}")
    print(f"  YAML content:\n{info['yaml']}\n")

print("\n=== 8. datasets and data Subdirectories ===")
for dname, subs in d["datasets_and_data_subdirs"].items():
    print(f"  Base directory: {dname}")
    for sname, sdata in subs.items():
        if "type" in sdata and sdata["type"] == "file":
            print(f"    File: {sname} ({sdata['size_bytes']} bytes)")
        else:
            print(f"    Subdir: {sname} -> {sdata['total_files']} files, {sdata['size_mb']} MB | exts={sdata['exts']}")
            print(f"      Inner dirs: {sdata['inner_subdirs_sample'][:5]}")
