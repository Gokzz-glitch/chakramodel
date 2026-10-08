import os
import json
import zipfile
from pathlib import Path

def inspect_zips():
    zip_paths = [
        r"C:\Users\imgk3\Downloads\om-finalkaggle-upload",  # zip without extension
    ]
    # Find all .zip in C:\Users\imgk3\Downloads
    for f in Path(r"C:\Users\imgk3\Downloads").glob("*.zip"):
        zip_paths.append(str(f))
    
    # Find all .zip in J:\My Drive\downloads (depth <= 2)
    for p in Path(r"J:\My Drive\downloads").glob("*.zip"):
        zip_paths.append(str(p))
    for p in Path(r"J:\My Drive\downloads").glob("*/*.zip"):
        zip_paths.append(str(p))

    results = {}
    for zp in zip_paths:
        zp_path = Path(zp)
        if not zp_path.exists():
            continue
        try:
            stat = zp_path.stat()
            is_zip = zipfile.is_zipfile(zp)
            if not is_zip:
                results[zp] = {"is_zip": False, "size": stat.st_size}
                continue
            
            with zipfile.ZipFile(zp) as z:
                infolist = z.infolist()
                files_sample = [
                    {"name": info.filename, "size": info.file_size, "compress_size": info.compress_size}
                    for info in infolist
                ]
                results[zp] = {
                    "is_zip": True,
                    "size": stat.st_size,
                    "file_count": len(infolist),
                    "files": files_sample
                }
        except Exception as e:
            results[zp] = {"error": str(e)}

    with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\zip_inventory.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Inspected {len(results)} zip archives.")
    for k, v in results.items():
        print(f"Archive: {k}")
        print(f"  IsZip: {v.get('is_zip')}, Size: {v.get('size')}, FileCount: {v.get('file_count')}")

if __name__ == "__main__":
    inspect_zips()
