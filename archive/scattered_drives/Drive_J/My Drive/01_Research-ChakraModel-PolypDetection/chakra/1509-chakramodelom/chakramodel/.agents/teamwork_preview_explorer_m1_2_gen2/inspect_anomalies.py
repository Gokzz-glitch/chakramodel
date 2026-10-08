import os
import struct
import json

workspace = r"m:\chakramodel"

# 1. Inspect data/datasets_archive/
print("=== data/datasets_archive ===")
archive_dir = os.path.join(workspace, "data", "datasets_archive")
if os.path.exists(archive_dir):
    for f in os.listdir(archive_dir):
        fp = os.path.join(archive_dir, f)
        sz = os.path.getsize(fp)
        print(f"  {f}: {round(sz/(1024*1024), 2)} MB ({sz} bytes)")

# 2. Inspect data/cvc-colondb
print("\n=== data/cvc-colondb ===")
colondb_dir = os.path.join(workspace, "data", "cvc-colondb")
if os.path.exists(colondb_dir):
    for root, dirs, files in os.walk(colondb_dir):
        rel = os.path.relpath(root, colondb_dir)
        print(f"  {rel}: {len(files)} files")
        if files:
            sample_f = os.path.join(root, files[0])
            print(f"    Sample: {files[0]}, size: {os.path.getsize(sample_f)} bytes")
            # Check if 0 bytes or small
            with open(sample_f, 'rb') as sf:
                print(f"    Sample header: {sf.read(16).hex()}")

# 3. List all 88 entries in CVC_ClinicVideoDB_Kaggle.zip
print("\n=== CVC_ClinicVideoDB_Kaggle.zip full entries ===")
cvc_zip = os.path.join(workspace, "CVC_ClinicVideoDB_Kaggle.zip")
entries = []
with open(cvc_zip, 'rb') as f:
    while True:
        pos = f.tell()
        sig = f.read(4)
        if sig != b'PK\x03\x04':
            break
        hdr = f.read(26)
        version, flags, method, mod_time, mod_date, crc32, comp_size, uncomp_size, name_len, extra_len = struct.unpack('<HHHHHIIIHH', hdr)
        name = f.read(name_len).decode('utf-8', errors='replace')
        extra = f.read(extra_len)
        actual_comp = comp_size
        actual_uncomp = uncomp_size
        if comp_size == 0xFFFFFFFF or uncomp_size == 0xFFFFFFFF:
            idx = 0
            while idx + 4 <= len(extra):
                tag, tag_sz = struct.unpack('<HH', extra[idx:idx+4])
                if tag == 0x0001:
                    zdata = extra[idx+4:idx+4+tag_sz]
                    o = 0
                    if uncomp_size == 0xFFFFFFFF and o + 8 <= len(zdata):
                        actual_uncomp = struct.unpack('<Q', zdata[o:o+8])[0]
                        o += 8
                    if comp_size == 0xFFFFFFFF and o + 8 <= len(zdata):
                        actual_comp = struct.unpack('<Q', zdata[o:o+8])[0]
                        o += 8
                    break
                idx += 4 + tag_sz
        entries.append({
            "name": name,
            "comp_bytes": actual_comp,
            "uncomp_bytes": actual_uncomp,
            "comp_mb": round(actual_comp / (1024*1024), 2),
            "uncomp_mb": round(actual_uncomp / (1024*1024), 2),
            "offset": pos
        })
        # If actual_comp is 0 (like that zip64 placeholder), we need to know where next PK0304 is
        if actual_comp == 0 and name.endswith('.zip'):
            # search for next header
            print(f"Warning: {name} has actual_comp=0 in local header")
            # we already know it was at 12528682767 and goes to end or whatever
            break
        f.seek(actual_comp, 1)

print(f"Total parsed entries: {len(entries)}")
# Group by extension
ext_counts = {}
for e in entries:
    ext = os.path.splitext(e["name"])[1].lower()
    ext_counts[ext] = ext_counts.get(ext, 0) + 1
print("Extension counts:", ext_counts)
print("Entries:")
for e in entries:
    print(f"  {e['name']}: {e['uncomp_mb']} MB (compressed: {e['comp_mb']} MB)")
