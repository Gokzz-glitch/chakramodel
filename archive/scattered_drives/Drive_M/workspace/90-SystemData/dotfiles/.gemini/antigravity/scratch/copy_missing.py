import os, sys, time, shutil, zipfile

src_dir = r'I:\My Drive\1509-chakramodelom\dataet'
dst_dir = r'M:\chakramodelpro\alldataset'
CHUNK = 64 * 1024 * 1024  # 64MB chunks

missing = ['ldpolypvideopolyponly.zip', 'polypgen20021-video.zip']

def copy_file_chunked(src_path, dst_path, filename):
    src_size = os.path.getsize(src_path)
    print(f'\n[COPY] {filename} ({src_size/1e9:.3f} GB)', flush=True)
    
    # Check if partial copy exists — resume from where we left off
    start_byte = 0
    if os.path.exists(dst_path):
        dst_size = os.path.getsize(dst_path)
        if dst_size == src_size:
            print(f'  Already complete ({dst_size:,} bytes). Skipping.', flush=True)
            return True
        elif dst_size < src_size:
            start_byte = dst_size
            print(f'  Resuming from byte {dst_size:,} ({dst_size/src_size*100:.1f}%)', flush=True)
    
    t_start = time.time()
    bytes_written = start_byte
    
    try:
        mode = 'ab' if start_byte > 0 else 'wb'
        with open(src_path, 'rb') as sf, open(dst_path, mode) as df:
            sf.seek(start_byte)
            while True:
                chunk = sf.read(CHUNK)
                if not chunk:
                    break
                df.write(chunk)
                df.flush()
                bytes_written += len(chunk)
                pct = bytes_written / src_size * 100
                elapsed = time.time() - t_start
                speed = (bytes_written - start_byte) / elapsed / 1e6 if elapsed > 0 else 0
                remaining = (src_size - bytes_written) / (speed * 1e6) if speed > 0 else 0
                print(f'  {pct:.1f}% | {bytes_written/1e9:.2f}/{src_size/1e9:.2f} GB | {speed:.1f} MB/s | ETA {remaining:.0f}s', flush=True)
    except Exception as e:
        print(f'  ERROR during copy: {e}', flush=True)
        return False
    
    # Verify exact byte count
    final_size = os.path.getsize(dst_path)
    if final_size == src_size:
        print(f'  [VERIFIED] {filename}: {final_size:,} bytes = source exactly', flush=True)
        return True
    else:
        print(f'  [MISMATCH] Expected {src_size:,} got {final_size:,}', flush=True)
        return False

def verify_zip_header(path):
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            members = len(zf.infolist())
        return True, members
    except Exception as e:
        return False, str(e)

print('=== RESILIENT COPY FOR MISSING FILES ===', flush=True)
print(f'Source: {src_dir}', flush=True)
print(f'Dest  : {dst_dir}', flush=True)

results = {}
for f in missing:
    src = os.path.join(src_dir, f)
    dst = os.path.join(dst_dir, f)
    
    if not os.path.exists(src):
        print(f'[ERROR] Source not found: {src}', flush=True)
        results[f] = False
        continue
    
    ok = copy_file_chunked(src, dst, f)
    
    if ok:
        valid, info = verify_zip_header(dst)
        if valid:
            print(f'  [ZIP OK] {f} | {info} members', flush=True)
        else:
            print(f'  [ZIP ERR] {f} | {info}', flush=True)
    
    results[f] = ok

print('\n=== FINAL SUMMARY ===', flush=True)
for f, ok in results.items():
    print(f'  {"[DONE]" if ok else "[FAILED]"} {f}', flush=True)

all_ok = all(results.values())
print(f'\nResult: {"ALL FILES COPIED SUCCESSFULLY" if all_ok else "FAILURES DETECTED"}', flush=True)
sys.exit(0 if all_ok else 1)
