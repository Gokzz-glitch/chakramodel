import os
import sys

source = r'M:\chakramodel'
targets = {
    'D_versioncontrol': r'D:\15-0926chakramodel versioncontrol\chakramodel',
    'I_gdrive': r'I:\My Drive\chakramodel & pro (16-9-26_)',
    'M_audit': r'M:\chakramodel_audit',
    'M_incomplete_backup': r'M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909',
    'M_chakramodelpro': r'M:\chakramodelpro'
}

def get_rel_files(root_dir, ignore_agents=True):
    rel_files = {}
    if not os.path.exists(root_dir):
        return rel_files
    for root, dirs, files in os.walk(root_dir):
        rel_root = os.path.relpath(root, root_dir)
        if ignore_agents:
            if rel_root == '.agents' or rel_root.startswith('.agents' + os.sep):
                continue
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.normpath(os.path.join(rel_root, f)) if rel_root != '.' else f
            try:
                st = os.stat(full_path)
                rel_files[rel_path] = (st.st_size, st.st_mtime)
            except Exception:
                pass
    return rel_files

print("Collecting source files from M:\chakramodel (ignoring .agents)...")
src_files = get_rel_files(source, ignore_agents=True)
print(f"Source total files (excl .agents): {len(src_files)}")

for name, target_path in targets.items():
    print(f"\nComparing Source vs {name} ({target_path})...")
    tgt_files = get_rel_files(target_path, ignore_agents=True)
    print(f"  Target total files (excl .agents): {len(tgt_files)}")

    src_set = set(src_files.keys())
    tgt_set = set(tgt_files.keys())

    missing_in_tgt = src_set - tgt_set
    extra_in_tgt = tgt_set - src_set
    common = src_set & tgt_set

    size_diffs = []
    mtime_diffs = []
    for f in common:
        src_sz, src_mt = src_files[f]
        tgt_sz, tgt_mt = tgt_files[f]
        if src_sz != tgt_sz:
            size_diffs.append((f, src_sz, tgt_sz))
        elif abs(src_mt - tgt_mt) > 1.0: # mtime difference > 1 sec
            mtime_diffs.append((f, src_mt, tgt_mt))

    print(f"  Missing in target: {len(missing_in_tgt)}")
    if missing_in_tgt:
        sample = sorted(list(missing_in_tgt))[:10]
        for s in sample:
            print(f"    - MISSING: {s}")
        if len(missing_in_tgt) > 10:
            print(f"    ... and {len(missing_in_tgt)-10} more missing files")

    print(f"  Extra in target: {len(extra_in_tgt)}")
    if extra_in_tgt:
        sample = sorted(list(extra_in_tgt))[:10]
        for s in sample:
            print(f"    + EXTRA: {s}")
        if len(extra_in_tgt) > 10:
            print(f"    ... and {len(extra_in_tgt)-10} more extra files")

    print(f"  Size differences: {len(size_diffs)}")
    if size_diffs:
        for f, s_sz, t_sz in size_diffs[:10]:
            print(f"    * SIZE DIFF: {f} (src: {s_sz} B, tgt: {t_sz} B)")
        if len(size_diffs) > 10:
            print(f"    ... and {len(size_diffs)-10} more size mismatches")

    print(f"  Timestamp differences (same size): {len(mtime_diffs)}")
    if mtime_diffs:
        for f, s_mt, t_mt in mtime_diffs[:5]:
            print(f"    ~ TIME DIFF: {f} (src: {s_mt}, tgt: {t_mt})")
        if len(mtime_diffs) > 5:
            print(f"    ... and {len(mtime_diffs)-5} more time mismatches")
