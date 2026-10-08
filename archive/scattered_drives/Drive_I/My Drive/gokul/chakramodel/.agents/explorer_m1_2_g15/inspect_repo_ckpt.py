import os
import zipfile

def inspect_checkpoint(pth_path):
    print(f"\nInspecting: {pth_path}")
    sz = os.path.getsize(pth_path)
    print(f"  File size: {sz:,} bytes")
    if zipfile.is_zipfile(pth_path):
        with zipfile.ZipFile(pth_path) as z:
            infos = z.infolist()
            print(f"  Zip entries: {len(infos)}")
            pkls = [i for i in infos if i.filename.endswith(".pkl")]
            print(f"  Pickle files: {[i.filename for i in pkls]}")
            storages = [i for i in infos if "data/" in i.filename or "data" in i.filename]
            print(f"  Storage entries: {len(storages)}")
            total_uncomp = sum(i.file_size for i in infos)
            print(f"  Total uncompressed size: {total_uncomp:,} bytes")

inspect_checkpoint(r"M:\chakramodel\weights\checkpoints\chakra_transformer_best.pth")
inspect_checkpoint(r"M:\chakramodel\weights\checkpoints\chakra_transformer_best.pth.bak")
