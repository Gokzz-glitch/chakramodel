import os

paths = [
    r'M:\chakramodel',
    r'D:\15-0926chakramodel versioncontrol\chakramodel',
    r'M:\chakramodel_audit',
    r'M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909',
    r'I:\My Drive\chakramodel & pro (16-9-26_)',
    r'M:\chakramodelpro'
]

for p in paths:
    print(f"\nListing top-level of: {p}")
    if os.path.exists(p):
        items = sorted(os.listdir(p))
        print(f"Total items: {len(items)}")
        dirs = [i for i in items if os.path.isdir(os.path.join(p, i))]
        files = [i for i in items if not os.path.isdir(os.path.join(p, i))]
        print(f"  Directories ({len(dirs)}): {dirs[:20]}")
        if len(dirs) > 20:
            print(f"    ... +{len(dirs)-20} more dirs")
        print(f"  Files ({len(files)}): {files[:15]}")
        if len(files) > 15:
            print(f"    ... +{len(files)-15} more files")
    else:
        print("Does not exist!")
