import os

f = r'M:\chakramodelpro\alldataset\hperkvasir-labeled-videos-part2-002.zip'
zero_start = 3_109_027_840
total = os.path.getsize(f)

fh = open(f, 'rb')
for i in range(12):
    pos = zero_start + i * (1024**3)
    if pos >= total:
        break
    fh.seek(pos)
    data = fh.read(16)
    is_zero = (data == b'\x00' * 16)
    gb = round(pos / (1024**3), 1)
    label = "ZERO" if is_zero else "DATA"
    print(f"{gb} GB: {label}")
fh.close()
