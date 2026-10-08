import os

root = r'D:\15-0926chakramodel versioncontrol\chakramodel'

print(f"=== Structure of {root} ===")
items = sorted(os.listdir(root))
for item in items:
    p = os.path.join(root, item)
    if os.path.isdir(p):
        cnt = sum(len(files) for _, _, files in os.walk(p))
        print(f"  [DIR]  {item:<30} ({cnt} files)")
    else:
        sz = os.path.getsize(p)
        if sz > 10 * 1024 * 1024:
            print(f"  [FILE] {item:<30} ({sz / (1024*1024):.2f} MB)")
