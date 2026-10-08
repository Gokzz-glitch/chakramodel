import os

files = [
    'cvc-sample-video.zip',
    'polypdb-polyp-raw.zip',
    'hperkvasir-labeled-videos-part2-002.zip',
    'hyperkvasir-labeled-videos-part2-001.zip',
    'hyperkvasir-dataset-first-half-and-and-ld-dataset.zip',
]

drive_base = r'I:\My Drive\1509-chakramodelom\dataet'
local_base = r'M:\chakramodelpro\alldataset'

print('=== SIZE COMPARISON: Google Drive vs Local ===')
print(f'{"File":<55} {"Drive Size":>15} {"Local Size":>15} {"Match":>6}')
print('-' * 95)

for f in files:
    drive_path = os.path.join(drive_base, f)
    local_path = os.path.join(local_base, f)
    
    try:
        drive_size = os.path.getsize(drive_path)
    except Exception as e:
        drive_size = -1
    
    try:
        local_size = os.path.getsize(local_path)
    except Exception as e:
        local_size = -1
    
    match = 'YES' if drive_size == local_size and drive_size > 0 else 'NO'
    print(f'{f:<55} {drive_size:>15,} {local_size:>15,} {match:>6}')

print()
print('=== CHECKING EOCD ON GOOGLE DRIVE SOURCE FILES ===')

for f in files:
    drive_path = os.path.join(drive_base, f)
    try:
        size = os.path.getsize(drive_path)
        with open(drive_path, 'rb') as fh:
            tail_size = min(65536, size)
            fh.seek(-tail_size, 2)
            tail = fh.read()
            eocd = tail.rfind(b'\x50\x4b\x05\x06')
            eocd64 = tail.rfind(b'\x50\x4b\x06\x06')
            has_eocd = eocd >= 0 or eocd64 >= 0
            print(f'{f}: EOCD={eocd >= 0}, EOCD64={eocd64 >= 0} => {"INTACT" if has_eocd else "ALSO BROKEN ON DRIVE"}')
    except Exception as e:
        print(f'{f}: ERROR reading from Drive - {e}')
