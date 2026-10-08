import os, sys, time, zipfile
import requests

datasets = [
    ('gokulraj324/ldpolypvideopolyponly', 'ldpolypvideopolyponly.zip'),
    ('gokulraj324/polypgen20021-video', 'polypgen20021-video.zip')
]

dst_dir = r'M:\chakramodelpro\alldataset'
token = 'KGAT_8dfaf234ad9eb6b91f0c216e712bdc4a'
headers = {'Authorization': f'Bearer {token}'}
CHUNK_SIZE = 1024 * 1024  # 1 MB chunks to prevent blocking

def verify_zip_header(path):
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            members = len(zf.infolist())
        return True, members
    except Exception as e:
        return False, str(e)

results = {}

for ds_path, filename in datasets:
    dst_path = os.path.join(dst_dir, filename)
    url = f'https://www.kaggle.com/api/v1/datasets/download/{ds_path}'
    
    print(f'\n[DOWNLOAD] {filename} from {ds_path}', flush=True)
    
    with requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=10) as r:
        if r.status_code != 200:
            print(f'  [ERROR] Kaggle API returned HTTP {r.status_code}', flush=True)
            results[filename] = False
            continue
            
        total_size = int(r.headers.get('content-length', 0))
        if total_size == 0:
            print('  [ERROR] Zero content length returned', flush=True)
            results[filename] = False
            continue
            
        print(f'  Size: {total_size/1e9:.3f} GB', flush=True)
        
        # Start clean
        if os.path.exists(dst_path):
            if os.path.getsize(dst_path) == total_size:
                print(f'  Already exists with exact size ({total_size:,} bytes).', flush=True)
                results[filename] = True
                continue
            else:
                os.remove(dst_path)
            
        t_start = time.time()
        bytes_written = 0
        last_print = 0
        try:
            with open(dst_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        bytes_written += len(chunk)
                        
                        elapsed = time.time() - t_start
                        if elapsed - last_print >= 5:
                            speed = bytes_written / elapsed / 1e6
                            pct = bytes_written / total_size * 100
                            rem = (total_size - bytes_written) / (speed * 1e6) if speed > 0 else 0
                            print(f'  {pct:.1f}% | {bytes_written/1e9:.2f}/{total_size/1e9:.2f} GB | {speed:.1f} MB/s | ETA {rem:.0f}s', flush=True)
                            last_print = elapsed
                            
        except Exception as e:
            print(f'  [ERROR] Download interrupted: {e}', flush=True)
            results[filename] = False
            continue

    # Verify
    final_size = os.path.getsize(dst_path)
    if final_size == total_size:
        print(f'  [VERIFIED] Size match: {final_size:,} bytes', flush=True)
        ok, info = verify_zip_header(dst_path)
        if ok:
            print(f'  [ZIP OK] {info} members inside archive', flush=True)
            results[filename] = True
        else:
            print(f'  [ZIP ERR] Corruption detected: {info}', flush=True)
            results[filename] = False
    else:
        print(f'  [MISMATCH] Size mismatch. Expected {total_size:,}, got {final_size:,}', flush=True)
        results[filename] = False

print('\n=== FINAL SUMMARY ===', flush=True)
for f, ok in results.items():
    print(f'  {"[DONE]" if ok else "[FAILED]"} {f}', flush=True)

all_ok = all(results.values())
print(f'\nResult: {"ALL DOWNLOADS SUCCESSFUL" if all_ok else "FAILURES DETECTED"}', flush=True)
sys.exit(0 if all_ok else 1)
