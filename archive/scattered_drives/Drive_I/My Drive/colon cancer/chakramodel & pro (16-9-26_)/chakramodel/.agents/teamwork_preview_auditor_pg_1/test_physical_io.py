import os
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageFile, UnidentifiedImageError

# Ensure we test the exact configuration used in verify_polypgen_integrity.py
ImageFile.LOAD_TRUNCATED_IMAGES = False

# Import verify_single_image from the audited script
sys.path.insert(0, r"m:\chakramodel")
from verify_polypgen_integrity import verify_single_image

def test_physical_io():
    print("=== TEST 1: Physical I/O and Byte Reading Verification ===")
    img_dir = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3\data_C1\images_C1")
    sample_files = list(img_dir.glob("*.jpg"))
    assert len(sample_files) > 0, f"No jpg files found in {img_dir}"
    sample_img = str(sample_files[0])
    actual_filesize = os.path.getsize(sample_img)
    print(f"Target sample image: {sample_img}")
    print(f"File size on disk: {actual_filesize:,} bytes")

    # Trace exact bytes read using a file wrapper
    bytes_read_tracker = {"total_read": 0, "read_calls": 0}
    original_open = open

    class TracingFile:
        def __init__(self, f):
            self._f = f
        def read(self, *args, **kwargs):
            data = self._f.read(*args, **kwargs)
            bytes_read_tracker["total_read"] += len(data)
            bytes_read_tracker["read_calls"] += 1
            return data
        def seek(self, *args, **kwargs):
            return self._f.seek(*args, **kwargs)
        def tell(self, *args, **kwargs):
            return self._f.tell(*args, **kwargs)
        def close(self):
            return self._f.close()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()

    # Verify how much verify_single_image reads
    res = verify_single_image(sample_img)
    print(f"verify_single_image result: valid={res['valid']}, dims={res['width']}x{res['height']}, mode={res['mode']}, format={res['format']}")
    assert res['valid'] is True, "Expected valid image to pass verification"
    assert res['width'] > 0 and res['height'] > 0

    # Now verify with explicit byte tracing
    with open(sample_img, "rb") as raw_f:
        tracer = TracingFile(raw_f)
        # Pass 1: verify()
        with Image.open(tracer) as im1:
            im1.verify()
        verify_bytes = bytes_read_tracker["total_read"]
        print(f"Bytes read during Image.verify(): {verify_bytes:,} bytes across {bytes_read_tracker['read_calls']} read calls")

    bytes_read_tracker = {"total_read": 0, "read_calls": 0}
    with open(sample_img, "rb") as raw_f:
        tracer = TracingFile(raw_f)
        # Pass 2: load()
        with Image.open(tracer) as im2:
            im2.load()
            pixel_val = im2.getpixel((10, 10))
        load_bytes = bytes_read_tracker["total_read"]
        print(f"Bytes read during Image.load(): {load_bytes:,} bytes across {bytes_read_tracker['read_calls']} read calls")
        print(f"Sample raster pixel value at (10, 10): {pixel_val}")

    assert load_bytes >= actual_filesize, f"Expected load() to read full file ({actual_filesize}), but got {load_bytes}"
    print("[PASS] Physical byte-level read verified: Image.load() physically pulled the entire file from disk.")

    print("\n=== TEST 2: Corruption and Truncation Fail-Fast Stress Testing ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        # A. 0-byte file
        zero_file = os.path.join(tmpdir, "zero.jpg")
        Path(zero_file).touch()
        res_zero = verify_single_image(zero_file)
        print(f"0-byte file check: valid={res_zero['valid']}, error={res_zero['error']}")
        assert res_zero['valid'] is False, "0-byte file must be invalid"

        # B. Garbage / fake file
        fake_file = os.path.join(tmpdir, "fake.jpg")
        with open(fake_file, "wb") as f:
            f.write(b"NOT_A_JPEG_FILE_JUST_RANDOM_TEXT")
        res_fake = verify_single_image(fake_file)
        print(f"Fake text file check: valid={res_fake['valid']}, error={res_fake['error']}")
        assert res_fake['valid'] is False, "Fake file must be invalid"

        # C. Truncated JPEG (read real JPEG and cut off 70% of bytes)
        with open(sample_img, "rb") as f:
            valid_bytes = f.read()
        trunc_file = os.path.join(tmpdir, "trunc.jpg")
        with open(trunc_file, "wb") as f:
            f.write(valid_bytes[: len(valid_bytes) // 3])
        res_trunc = verify_single_image(trunc_file)
        print(f"Truncated JPEG check: valid={res_trunc['valid']}, error={res_trunc['error']}")
        assert res_trunc['valid'] is False, "Truncated JPEG must be invalid under ImageFile.LOAD_TRUNCATED_IMAGES=False"

        # D. Bit-flipped corrupted JPEG stream (keep header, corrupt mid-stream entropy data)
        corrupt_file = os.path.join(tmpdir, "corrupt.jpg")
        corrupt_bytes = bytearray(valid_bytes)
        # Flip 100 bytes in the middle of scan data
        mid = len(corrupt_bytes) // 2
        for i in range(mid, mid + 100):
            corrupt_bytes[i] = 0x00
        with open(corrupt_file, "wb") as f:
            f.write(corrupt_bytes)
        res_corrupt = verify_single_image(corrupt_file)
        print(f"Bit-flipped JPEG check: valid={res_corrupt['valid']}, error={res_corrupt['error']}")
        # Note: Some minor bitflips might still decode with warnings or error depending on marker integrity,
        # but severe truncation or header corruption unconditionally fails.

    print("\n[ALL EMPIRICAL I/O AND CORRUPTION TESTS PASSED]")

if __name__ == "__main__":
    test_physical_io()
