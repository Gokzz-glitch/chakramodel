import os
import ctypes

def check_file_attributes(filepath):
    attrs = ctypes.windll.kernel32.GetFileAttributesW(filepath)
    FILE_ATTRIBUTE_OFFLINE = 0x1000
    FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
    is_offline = bool(attrs & FILE_ATTRIBUTE_OFFLINE)
    is_reparse = bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    return is_offline, is_reparse, attrs

sample_paths = [
    r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel\.env',
    r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel\README.md',
    r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel\CVC_ClinicVideoDB_Kaggle.zip'
]

for sp in sample_paths:
    if os.path.exists(sp):
        off, rep, raw = check_file_attributes(sp)
        sz = os.path.getsize(sp)
        print(f"File: {sp}")
        print(f"  Size: {sz} bytes ({sz / (1024*1024):.2f} MB)")
        print(f"  Offline: {off}, Reparse Point: {rep}, Raw Attr: {hex(raw)}")
    else:
        print(f"File does not exist: {sp}")
