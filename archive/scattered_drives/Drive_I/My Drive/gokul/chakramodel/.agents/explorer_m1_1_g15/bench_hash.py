import os
import time
import hashlib

sample_file = r'M:\chakramodel\kaggle_bundle for testing.zip'
if not os.path.exists(sample_file):
    sample_file = r'M:\chakramodel\ChakraModel_Kaggle_Verification.zip'

if os.path.exists(sample_file):
    sz = os.path.getsize(sample_file)
    print(f"Testing on {sample_file} ({sz / (1024*1024):.2f} MB)")

    for chunk_sz in [64 * 1024, 256 * 1024, 1024 * 1024, 4 * 1024 * 1024]:
        t0 = time.perf_counter()
        h = hashlib.sha256()
        with open(sample_file, 'rb') as f:
            while chunk := f.read(chunk_sz):
                h.update(chunk)
        digest = h.hexdigest()
        dt = time.perf_counter() - t0
        speed = (sz / (1024*1024)) / dt
        print(f"Chunk: {chunk_sz // 1024:4d} KB | Time: {dt:.4f}s | Speed: {speed:.1f} MB/s | Hash: {digest[:12]}...")
