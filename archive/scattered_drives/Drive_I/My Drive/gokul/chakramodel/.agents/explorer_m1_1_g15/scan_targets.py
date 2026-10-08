import os
import sys

targets = [
    r'D:\15-0926chakramodel versioncontrol\chakramodel',
    r'I:\My Drive\chakramodel & pro (16-9-26_)',
    r'M:\chakramodel_audit',
    r'M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909',
    r'M:\chakramodelpro'
]

def scan_target(target_path):
    print(f"\n{'='*70}")
    print(f"Target: {target_path}")
    print(f"{'='*70}")
    if not os.path.exists(target_path):
        print("  Status: DOES NOT EXIST")
        return

    try:
        items = sorted(os.listdir(target_path))
        print(f"  Top-level items count: {len(items)}")
    except Exception as e:
        print(f"  Error reading directory: {e}")
        return

    top_dirs = []
    root_files_count = 0
    root_files_size = 0
    total_files = 0
    total_size = 0
    large_files = []

    for item in items:
        p = os.path.join(target_path, item)
        if os.path.isdir(p):
            cnt = 0
            sz = 0
            try:
                for r, d, files in os.walk(p):
                    for f in files:
                        cnt += 1
                        fp = os.path.join(r, f)
                        try:
                            s = os.path.getsize(fp)
                            sz += s
                            if s >= 50 * 1024 * 1024:
                                large_files.append((fp, s))
                        except Exception:
                            pass
            except Exception as e:
                print(f"  Error walking {item}: {e}")
            top_dirs.append((item, cnt, sz))
            total_files += cnt
            total_size += sz
        else:
            root_files_count += 1
            total_files += 1
            try:
                s = os.path.getsize(p)
                root_files_size += s
                total_size += s
                if s >= 50 * 1024 * 1024:
                    large_files.append((p, s))
            except Exception:
                pass

    print(f"  Total Files: {total_files}, Total Size: {total_size / (1024*1024):.2f} MB ({total_size / (1024**3):.3f} GB)")
    print(f"  Root files: {root_files_count}, size: {root_files_size / (1024*1024):.2f} MB")
    print(f"  Top-level directories ({len(top_dirs)}):")
    for name, cnt, sz in sorted(top_dirs, key=lambda x: x[2], reverse=True)[:15]:
        print(f"    {name:<35} | {cnt:<6} files | {sz / (1024*1024):<10.2f} MB")
    if len(top_dirs) > 15:
        print(f"    ... and {len(top_dirs) - 15} more directories")

    if large_files:
        print(f"  Large files (>= 50 MB) [count: {len(large_files)}]:")
        for fp, s in sorted(large_files, key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {s / (1024*1024):.2f} MB: {fp}")

if __name__ == '__main__':
    for t in targets:
        scan_target(t)
