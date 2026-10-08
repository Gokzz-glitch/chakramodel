import os
import sys

def scan_dir(root_path):
    print(f"=== Scanning: {root_path} ===")
    if not os.path.exists(root_path):
        print("  Path does NOT exist!")
        return

    dirs = []
    root_files_count = 0
    root_files_size = 0
    large_files = []

    try:
        items = sorted(os.listdir(root_path))
    except Exception as e:
        print(f"  Error reading directory: {e}")
        return

    for item in items:
        p = os.path.join(root_path, item)
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
                            if s >= 50 * 1024 * 1024:  # >= 50MB
                                large_files.append((fp, s))
                        except Exception:
                            pass
            except Exception as e:
                print(f"  Error walking {item}: {e}")
            dirs.append((item, cnt, sz))
        else:
            root_files_count += 1
            try:
                s = os.path.getsize(p)
                root_files_size += s
                if s >= 50 * 1024 * 1024:
                    large_files.append((p, s))
            except Exception:
                pass

    total_files = root_files_count + sum(d[1] for d in dirs)
    total_size = root_files_size + sum(d[2] for d in dirs)

    print(f"Root files count: {root_files_count}, size: {root_files_size / (1024*1024):.2f} MB")
    print(f"{'Directory':<45} | {'Files':<8} | {'Size (MB)':<12} | {'Size (GB)':<10}")
    print("-" * 80)
    for name, cnt, sz in dirs:
        print(f"{name:<45} | {cnt:<8} | {sz / (1024*1024):<12.2f} | {sz / (1024**3):<10.3f}")
    print("=" * 80)
    print(f"{'TOTAL':<45} | {total_files:<8} | {total_size / (1024*1024):<12.2f} | {total_size / (1024**3):<10.3f}\n")

    if large_files:
        print(f"Large files (>= 50 MB) [count: {len(large_files)}]:")
        for fp, s in sorted(large_files, key=lambda x: x[1], reverse=True)[:30]:
            print(f"  {s / (1024*1024):.2f} MB: {fp}")
        print()

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else r'M:\chakramodel'
    scan_dir(target)
