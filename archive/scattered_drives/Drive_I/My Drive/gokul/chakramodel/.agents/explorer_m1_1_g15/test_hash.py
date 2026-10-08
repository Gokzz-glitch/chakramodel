import hashlib
import time

path_m = r'M:\chakramodel\README.md'
path_i = r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel\README.md'

for p in [path_m, path_i]:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while chunk := f.read(64 * 1024):
            h.update(chunk)
    print(f"SHA-256 ({p}):\n  {h.hexdigest()}")
