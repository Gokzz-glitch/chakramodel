import os
import hashlib
import zipfile
import io

def sha256_file(path, max_bytes=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        read = 0
        while True:
            chunk = f.read(1024*1024)
            if not chunk:
                break
            if max_bytes and read + len(chunk) > max_bytes:
                h.update(chunk[:max_bytes - read])
                break
            h.update(chunk)
            read += len(chunk)
    return h.hexdigest()

def sha256_zip_entry(zip_path, entry_name):
    h = hashlib.sha256()
    with zipfile.ZipFile(zip_path) as z:
        with z.open(entry_name) as f:
            while True:
                chunk = f.read(1024*1024)
                if not chunk:
                    break
                h.update(chunk)
    return h.hexdigest()

print("Checking repo weights:")
repo_weights = [
    r"M:\chakramodel\weights\checkpoints\chakra_transformer_best.pth",
    r"M:\chakramodel\weights\checkpoints\chakra_transformer_best.pth.bak",
    r"M:\chakramodel\weights\checkpoints\combo1_best.pth",
    r"M:\chakramodel\weights\yolo\best.pt",
    r"M:\chakramodel\weights\yolo\best_backup_20260907.pt",
    r"M:\chakramodel\weights\yolo\yolo_custom_best.pt",
    r"M:\chakramodel\weights\calibration\conformal_calibration.json"
]
for p in repo_weights:
    if os.path.exists(p):
        sz = os.path.getsize(p)
        print(f"  {os.path.basename(p)}: size={sz:,}")

print("\nChecking om-finalkaggle-upload weights:")
c_upload = r"C:\Users\imgk3\Downloads\om-finalkaggle-upload"
if os.path.exists(c_upload):
    with zipfile.ZipFile(c_upload) as z:
        for entry in ["weights/chakra_transformer_best.pth", "weights/best.pt"]:
            info = z.getinfo(entry)
            print(f"  {entry}: size={info.file_size:,}, CRC={hex(info.CRC)}")

print("\nChecking chakramodel_weights_PRIVATE.zip weights:")
priv_zip = r"J:\My Drive\downloads\CHAKRAMODEL_OM_4\chakramodel_weights_PRIVATE.zip"
if os.path.exists(priv_zip):
    with zipfile.ZipFile(priv_zip) as z:
        for info in z.infolist():
            print(f"  {info.filename:40} size={info.file_size:>12,d}  CRC={hex(info.CRC)}")
