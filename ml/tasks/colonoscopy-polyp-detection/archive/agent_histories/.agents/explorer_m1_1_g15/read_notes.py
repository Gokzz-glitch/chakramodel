import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

p1 = r'M:\chakramodel_audit\FULL_AUDIT_REPORT.md'
p2 = r'M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909\READ_THIS_INCOMPLETE.txt'
p3 = r'M:\chakramodelpro\chakra-sync.ps1'

for p in [p1, p2, p3]:
    print('='*60)
    print(f'File: {p}')
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8', errors='ignore') as f:
            print(f.read())
    else:
        print('Not found')
