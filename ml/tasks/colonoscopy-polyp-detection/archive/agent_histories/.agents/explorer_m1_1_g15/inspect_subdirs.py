import os

targets = [
    r'M:\chakramodel_audit',
    r'M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909',
    r'M:\chakramodelpro',
    r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel_audit',
    r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909',
    r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodelpro',
    r'I:\My Drive\chakramodel & pro (16-9-26_)\chakramodel'
]

for t in targets:
    print('='*70)
    print(f'Inspecting: {t}')
    if not os.path.exists(t):
        print('  DOES NOT EXIST')
        continue
    for root, dirs, files in os.walk(t):
        rel = os.path.relpath(root, t)
        level = rel.count(os.sep)
        if level <= 2:
            print(f'  [{rel}] dirs: {len(dirs)}, files: {len(files)}')
            for f in files[:5]:
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                    print(f'    - {f} ({sz} bytes)')
                except Exception:
                    pass
            if len(files) > 5:
                print(f'    ... and {len(files)-5} more files')
