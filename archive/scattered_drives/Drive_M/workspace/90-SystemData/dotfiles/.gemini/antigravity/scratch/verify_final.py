import os, zipfile, sys

base = r'I:\My Drive\1509-chakramodelom\dataet'
zips = sorted([f for f in os.listdir(base) if f.endswith('.zip')])

print('=== FINAL VERIFICATION REPORT ===', flush=True)
print('Directory:', base, flush=True)
print('Total ZIPs found:', len(zips), flush=True)
print(flush=True)

passed, failed = 0, 0
total_bytes = 0

for z in zips:
    path = os.path.join(base, z)
    size = os.path.getsize(path)
    total_bytes += size
    sys.stdout.write(f'Checking {z} ({size/1e9:.2f} GB)... ')
    sys.stdout.flush()
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            bad = zf.testzip()
            count = len(zf.infolist())
        if bad is None:
            print(f'PASS | {count:,} files | CRC OK', flush=True)
            passed += 1
        else:
            print(f'FAIL | CORRUPT: {bad}', flush=True)
            failed += 1
    except Exception as e:
        print(f'FAIL | ERROR: {e}', flush=True)
        failed += 1

print(flush=True)
print('=== SUMMARY ===', flush=True)
print(f'Total size : {total_bytes/1e9:.2f} GB', flush=True)
print(f'Passed     : {passed}/{len(zips)}', flush=True)
print(f'Failed     : {failed}/{len(zips)}', flush=True)
status = 'ALL CLEAN - ZERO CORRUPTION' if failed == 0 else 'CORRUPTION DETECTED'
print(f'Status     : {status}', flush=True)
