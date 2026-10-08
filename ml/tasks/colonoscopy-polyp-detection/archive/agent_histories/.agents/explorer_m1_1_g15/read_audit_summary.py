import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

p1 = r'M:\chakramodel_audit\FULL_AUDIT_REPORT.md'
p2 = r'M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909\READ_THIS_INCOMPLETE.txt'

print("=== M:\\chakramodel_audit\\FULL_AUDIT_REPORT.md ===")
if os.path.exists(p1):
    with open(p1, 'r', encoding='utf-8', errors='ignore') as f:
        print(f.read()[:2000])

print("\n=== M:\\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909\\READ_THIS_INCOMPLETE.txt ===")
if os.path.exists(p2):
    with open(p2, 'r', encoding='utf-8', errors='ignore') as f:
        print(f.read())
