import os
import sys

src_base = r'M:\chakramodel'
gdrive_base = r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel'

print("Comparing M:\chakramodel and I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel ...")

# Compare root files
src_root_files = set(os.listdir(src_base))
gdrive_root_files = set(os.listdir(gdrive_base))

missing_root = src_root_files - gdrive_root_files
extra_root = gdrive_root_files - src_root_files
common_root = src_root_files & gdrive_root_files

print(f"Root items: {len(src_root_files)} in src, {len(gdrive_root_files)} in target")
print(f"Missing in target: {len(missing_root)} -> {missing_root}")
print(f"Extra in target: {len(extra_root)} -> {extra_root}")

# Compare sizes and mtimes for common root files
size_mismatch = []
time_mismatch = []
for f in common_root:
    p_src = os.path.join(src_base, f)
    p_tgt = os.path.join(gdrive_base, f)
    if os.path.isfile(p_src) and os.path.isfile(p_tgt):
        s_sz, s_mt = os.path.getsize(p_src), os.path.getmtime(p_src)
        t_sz, t_mt = os.path.getsize(p_tgt), os.path.getmtime(p_tgt)
        if s_sz != t_sz:
            size_mismatch.append((f, s_sz, t_sz))
        elif abs(s_mt - t_mt) > 2.0:
            time_mismatch.append((f, s_mt, t_mt))

print(f"Root files size mismatches: {len(size_mismatch)}")
for f, s, t in size_mismatch[:10]:
    print(f"  SIZE: {f} (src={s}, tgt={t})")
print(f"Root files time mismatches (same size): {len(time_mismatch)}")
for f, s, t in time_mismatch[:5]:
    print(f"  TIME: {f} (src={s}, tgt={t})")
