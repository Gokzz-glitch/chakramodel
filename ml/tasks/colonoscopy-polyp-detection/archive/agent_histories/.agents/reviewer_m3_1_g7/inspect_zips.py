import zipfile
import hashlib
import os

def file_md5(fname):
    h = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

archives = [
    r"m:\chakramodel\chakramodel_data_scripts.zip",
    r"m:\chakramodel\chakramodel-weights.zip",
    r"m:\chakramodel\chakramodel_weights_PRIVATE.zip"
]

for arch in archives:
    if not os.path.exists(arch):
        print(f"Archive missing: {arch}")
        continue
    size_bytes = os.path.getsize(arch)
    size_mb = size_bytes / (1024 * 1024)
    md5_hash = file_md5(arch)
    print(f"\n==================================================")
    print(f"ARCHIVE: {os.path.basename(arch)}")
    print(f"Size: {size_bytes} bytes ({size_mb:.2f} MB)")
    print(f"MD5: {md5_hash}")
    
    with zipfile.ZipFile(arch, 'r') as zf:
        infolist = zf.infolist()
        print(f"Total entries: {len(infolist)}")
        
        # Check top-level items
        top_levels = set()
        for info in infolist:
            parts = info.filename.split('/')
            top_levels.add(parts[0])
        print(f"Top level entries: {sorted(list(top_levels))}")
        
        # Check weights specifically
        weights = [info.filename for info in infolist if 'chakra_transformer' in info.filename or 'best.pt' in info.filename or 'conformal' in info.filename]
        print(f"Weight entries found ({len(weights)}): {weights[:10]}")
        
        # Check src files
        src_files = [info.filename for info in infolist if info.filename.startswith('src/')]
        print(f"src/ entries count: {len(src_files)}")
        
        # Check data files
        data_files = [info.filename for info in infolist if info.filename.startswith('data/')]
        print(f"data/ entries count: {len(data_files)}")
        
        # First 10 entries
        print("First 8 entries:")
        for info in infolist[:8]:
            print(f"  {info.filename} ({info.file_size} bytes)")
