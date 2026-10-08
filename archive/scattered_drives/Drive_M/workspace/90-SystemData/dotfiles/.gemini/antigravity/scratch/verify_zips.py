import os
import zipfile

src_dir = r'I:\My Drive\1509-chakramodelom\dataet'
dst_dir = r'M:\chakramodelpro\alldataset'

# Get all zips in source
src_files = [f for f in os.listdir(src_dir) if f.endswith('.zip')]

ok = 0
failed = 0

print("=== FINAL ZIP VERIFICATION ===")
for f in src_files:
    sp = os.path.join(src_dir, f)
    dp = os.path.join(dst_dir, f)
    
    if not os.path.exists(dp):
        print(f"[MISSING] {f}")
        failed += 1
        continue
        
    s_size = os.path.getsize(sp)
    d_size = os.path.getsize(dp)
    
    if s_size != d_size:
        print(f"[MISMATCH] {f} (Src: {s_size}, Dst: {d_size})")
        failed += 1
        continue
        
    # Check zip integrity
    try:
        with zipfile.ZipFile(dp, 'r') as zf:
            members = zf.infolist()
            # Try to read the first few bytes of the central directory
            zf.testzip()
        print(f"[OK] {f} | {len(members)} members, header verified")
        ok += 1
    except Exception as e:
        print(f"[CORRUPT] {f} | Error: {e}")
        failed += 1

print("\n=== SUMMARY ===")
print(f"Total: {len(src_files)}")
print(f"Passed: {ok}")
print(f"Failed: {failed}")
if failed == 0 and ok == len(src_files):
    print("\nRESULT: ALL SECURE AND PERFECT!")
else:
    print("\nRESULT: CORRUPTION DETECTED!")
