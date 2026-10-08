import zipfile
import os
import struct

files = [
    'cvc-sample-video.zip',
    'polypdb-polyp-raw.zip',
    'hperkvasir-labeled-videos-part2-002.zip',
    'hyperkvasir-labeled-videos-part2-001.zip',
    'hyperkvasir-dataset-first-half-and-and-ld-dataset.zip',
]

base = r'M:\chakramodelpro\alldataset'

for f in files:
    path = os.path.join(base, f)
    size = os.path.getsize(path)
    print(f'--- {f} ---')
    print(f'  Size: {size:,} bytes ({size/1024**3:.2f} GB)')
    
    with open(path, 'rb') as fh:
        # Check header
        fh.seek(0)
        magic = fh.read(4)
        is_pk = magic == b'\x50\x4b\x03\x04'
        print(f'  Header: {magic.hex()} (valid PK: {is_pk})')
        
        # Check tail for EOCD signature
        tail_size = min(65536, size)
        fh.seek(-tail_size, 2)
        tail = fh.read()
        
        eocd_pos = tail.rfind(b'\x50\x4b\x05\x06')
        eocd64_pos = tail.rfind(b'\x50\x4b\x06\x06')
        eocd64_locator = tail.rfind(b'\x50\x4b\x06\x07')
        
        na = 'N/A'
        eocd_offset = str(len(tail) - eocd_pos) if eocd_pos >= 0 else na
        print(f'  EOCD (PK0506): found={eocd_pos >= 0}, bytes_from_end={eocd_offset}')
        print(f'  EOCD64 (PK0606): found={eocd64_pos >= 0}')
        print(f'  EOCD64 Locator (PK0607): found={eocd64_locator >= 0}')
    
    # Try Python zipfile
    try:
        zf = zipfile.ZipFile(path, 'r')
        entries = len(zf.namelist())
        print(f'  Python zipfile: OK, {entries} entries')
        zf.close()
    except Exception as e:
        print(f'  Python zipfile: FAILED - {e}')
    
    print()
