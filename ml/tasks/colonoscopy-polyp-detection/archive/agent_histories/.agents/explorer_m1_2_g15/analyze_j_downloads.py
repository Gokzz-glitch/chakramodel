import json
from pathlib import Path
from collections import Counter

def analyze_j_downloads():
    with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\j_downloads_raw.json", "r", encoding="utf-8") as f:
        items = json.load(f)

    files = [it for it in items if it.get("type") == "file"]
    dirs = [it for it in items if it.get("type") == "dir" and not it.get("excluded")]

    print(f"Total entries: {len(items)}, Files: {len(files)}, Dirs: {len(dirs)}")

    # Check top-level directories
    top_dirs = [d["path"] for d in dirs if d.get("depth") == 0]
    print(f"\nTop-level dirs ({len(top_dirs)}):")
    for d in top_dirs[:20]:
        print(" ", Path(d).name)

    # Extensions count
    ext_counter = Counter(Path(f["name"]).suffix.lower() for f in files)
    print("\nExtensions:")
    for ext, cnt in ext_counter.most_common(15):
        print(f"  {ext or '(no ext)'}: {cnt}")

    # Inspect weights files (.pth, .pt, .onnx, etc.)
    weight_files = [f for f in files if Path(f["name"]).suffix.lower() in {'.pth', '.pt', '.onnx', '.ckpt', '.bin', '.h5'}]
    print(f"\nWeight files ({len(weight_files)}):")
    for wf in weight_files:
        print(f"  {wf['path']} ({wf['size']:,} bytes)")

    # Inspect zip files
    zip_files = [f for f in files if Path(f["name"]).suffix.lower() == '.zip']
    print(f"\nZip files ({len(zip_files)}):")
    for zf in zip_files:
        print(f"  {zf['path']} ({zf['size']:,} bytes)")

    # Inspect eval jsons
    json_files = [f for f in files if Path(f["name"]).suffix.lower() == '.json']
    print(f"\nJSON files ({len(json_files)}):")
    for jf in json_files:
        print(f"  {jf['path']} ({jf['size']:,} bytes)")

    # Notebooks sample
    notebooks = [f for f in files if Path(f["name"]).suffix.lower() == '.ipynb']
    print(f"\nTotal notebooks: {len(notebooks)}")

if __name__ == "__main__":
    analyze_j_downloads()
