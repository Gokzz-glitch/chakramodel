import os

p = r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel'
print(f"=== Scanning {p} ===")
items = sorted(os.listdir(p))
print(f"Top-level items: {len(items)}")
dirs = [i for i in items if os.path.isdir(os.path.join(p, i))]
files = [i for i in items if not os.path.isdir(os.path.join(p, i))]
print(f"Dirs count: {len(dirs)}")
print(f"Files count: {len(files)}")

# Check top dirs
for d in dirs[:15]:
    dp = os.path.join(p, d)
    cnt = 0
    sz = 0
    try:
        for r, ds, fs in os.walk(dp):
            cnt += len(fs)
            for f in fs:
                try:
                    sz += os.path.getsize(os.path.join(r, f))
                except Exception:
                    pass
    except Exception as e:
        pass
    print(f"  {d:<30} | {cnt:<6} files | {sz/(1024*1024):<10.2f} MB")
