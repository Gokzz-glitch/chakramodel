import os

p = r'D:\15-0926chakramodel versioncontrol\chakramodel\chakramodel'
items = sorted(os.listdir(p))
print(f"Items in {p}: {len(items)}")
for item in items:
    full = os.path.join(p, item)
    if os.path.isdir(full):
        cnt = sum(len(files) for _, _, files in os.walk(full))
        print(f"  [DIR]  {item:<30} ({cnt} files)")
    else:
        sz = os.path.getsize(full)
        if sz > 10 * 1024 * 1024:
            print(f"  [FILE] {item:<30} ({sz / (1024*1024):.2f} MB)")
