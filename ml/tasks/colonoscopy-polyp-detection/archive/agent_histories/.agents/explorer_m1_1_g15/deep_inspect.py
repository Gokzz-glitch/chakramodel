import os
import sys

paths = [
    r'M:\chakramodel',
    r'D:\15-0926chakramodel versioncontrol',
    r'D:\15-0926chakramodel versioncontrol\chakramodel',
    r'D:\15-0926chakramodel versioncontrol\chakramodel\chakramodel',
    r'M:\chakramodel_audit',
    r'M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909',
    r'I:\My Drive\chakramodel & pro (16-9-26_)',
    r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel',
    r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodelpro',
    r'M:\chakramodelpro'
]

for p in paths:
    print('=' * 60)
    print(f'PATH: {p}')
    if os.path.exists(p):
        try:
            items = sorted(os.listdir(p))
            print(f'Total items: {len(items)}')
            dirs = [i for i in items if os.path.isdir(os.path.join(p, i))]
            files = [i for i in items if not os.path.isdir(os.path.join(p, i))]
            print(f'  Directories ({len(dirs)}): {dirs[:10]}')
            if len(dirs) > 10:
                print(f'    ... and {len(dirs)-10} more dirs')
            print(f'  Files ({len(files)}): {files[:10]}')
            if len(files) > 10:
                print(f'    ... and {len(files)-10} more files')
        except Exception as e:
            print(f'  Error: {e}')
    else:
        print('  Status: DOES NOT EXIST')
