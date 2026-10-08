import hashlib
import os

def file_md5(fname):
    h = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

files_to_check = [
    r"m:\chakramodel\weights\chakra_transformer_best.pth",
    r"m:\chakramodel\weights\chakra_transformer_best.pth.bak",
    r"m:\chakramodel\weights\best.pt",
    r"m:\chakramodel\weights\conformal_calibration.json"
]

for f in files_to_check:
    if os.path.exists(f):
        size = os.path.getsize(f)
        md5_val = file_md5(f)
        print(f"{os.path.basename(f)}: size={size}, md5={md5_val}")
    else:
        print(f"{f} does not exist!")
