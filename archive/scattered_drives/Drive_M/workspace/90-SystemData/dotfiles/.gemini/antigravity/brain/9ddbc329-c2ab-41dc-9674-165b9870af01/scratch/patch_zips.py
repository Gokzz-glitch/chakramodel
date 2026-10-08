"""
Find the exact boundary where local file diverges from drive (zeros start).
Then patch the local file by copying the correct tail from drive.
"""
import os
import sys

files = [
    'cvc-sample-video.zip',
    'polypdb-polyp-raw.zip',
    'hperkvasir-labeled-videos-part2-002.zip',
    'hyperkvasir-labeled-videos-part2-001.zip',
    'hyperkvasir-dataset-first-half-and-and-ld-dataset.zip',
]

drive_base = r'I:\My Drive\1509-chakramodelom\dataet'
local_base = r'M:\chakramodelpro\alldataset'

CHUNK = 1024 * 1024  # 1 MB chunks for scanning

for f in files:
    drive_path = os.path.join(drive_base, f)
    local_path = os.path.join(local_base, f)
    size = os.path.getsize(local_path)
    
    print(f'=== {f} ({size/1024**3:.2f} GB) ===')
    sys.stdout.flush()
    
    # Binary search: find the first zero-filled MB from the end
    # Start scanning backwards in 1MB chunks
    with open(local_path, 'rb') as lh:
        # Find the last non-zero chunk
        pos = size
        zero_start = size
        while pos > 0:
            read_size = min(CHUNK, pos)
            pos -= read_size
            lh.seek(pos)
            data = lh.read(read_size)
            if data != b'\x00' * len(data):
                # This chunk has real data, find exact boundary
                for i in range(len(data) - 1, -1, -1):
                    if data[i] != 0:
                        zero_start = pos + i + 1
                        break
                break
            zero_start = pos
    
    corrupt_bytes = size - zero_start
    print(f'  Zero-fill starts at byte: {zero_start:,}')
    print(f'  Corrupt tail size: {corrupt_bytes:,} bytes ({corrupt_bytes/1024:.1f} KB)')
    
    # Now patch: copy from drive starting at zero_start
    print(f'  Patching from Google Drive...')
    sys.stdout.flush()
    
    with open(drive_path, 'rb') as src, open(local_path, 'r+b') as dst:
        src.seek(zero_start)
        dst.seek(zero_start)
        bytes_written = 0
        while True:
            chunk = src.read(CHUNK)
            if not chunk:
                break
            dst.write(chunk)
            bytes_written += len(chunk)
        dst.flush()
        os.fsync(dst.fileno())
    
    print(f'  Patched {bytes_written:,} bytes')
    
    # Verify the patch
    import zipfile
    try:
        zf = zipfile.ZipFile(local_path, 'r')
        entries = len(zf.namelist())
        zf.close()
        print(f'  VERIFICATION: OK - {entries} entries')
    except Exception as e:
        print(f'  VERIFICATION: FAILED - {e}')
    
    sys.stdout.flush()
    print()
