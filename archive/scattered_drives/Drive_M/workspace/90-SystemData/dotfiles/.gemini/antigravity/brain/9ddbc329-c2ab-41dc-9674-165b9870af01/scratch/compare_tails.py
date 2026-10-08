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

for f in files:
    drive_path = os.path.join(drive_base, f)
    local_path = os.path.join(local_base, f)
    size = os.path.getsize(local_path)
    
    # Read last 1024 bytes from both
    print(f'--- {f} ---')
    with open(drive_path, 'rb') as dh, open(local_path, 'rb') as lh:
        dh.seek(-1024, 2)
        lh.seek(-1024, 2)
        drive_tail = dh.read()
        local_tail = lh.read()
        
        if drive_tail == local_tail:
            print('  Last 1024 bytes: IDENTICAL')
        else:
            # Find where they diverge
            for i in range(len(drive_tail)):
                if drive_tail[i] != local_tail[i]:
                    print(f'  Last 1024 bytes: DIFFER at offset {i}')
                    print(f'  Drive tail hex (last 32): {drive_tail[-32:].hex()}')
                    print(f'  Local tail hex (last 32): {local_tail[-32:].hex()}')
                    break
            
            # Check if local tail is all zeros
            zero_count = local_tail.count(b'\x00')
            print(f'  Local tail zero bytes: {zero_count}/{len(local_tail)}')
    print()
