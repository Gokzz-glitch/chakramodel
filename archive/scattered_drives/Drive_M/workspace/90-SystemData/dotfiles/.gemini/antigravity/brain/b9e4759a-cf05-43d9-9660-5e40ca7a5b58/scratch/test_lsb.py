"""Quick self-test: embed payload into one image, immediately extract it, verify match."""
import sys, os, struct
import numpy as np
from PIL import Image

sys.path.insert(0, r"J:\My Drive\rajapalayam hackathon")

# ── copy helpers from embed/verify ─────────────────────────────────────────
def string_to_bits(text):
    bits = []
    encoded = text.encode("utf-8")
    length_bytes = struct.pack(">I", len(encoded))
    for byte in length_bytes + encoded:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def bits_to_string(bits):
    if len(bits) < 32:
        return ""
    length_bytes = bytes(
        sum(bits[i * 8 + j] << (7 - j) for j in range(8))
        for i in range(4)
    )
    payload_len = struct.unpack(">I", length_bytes)[0]
    if payload_len > 10000 or payload_len < 1:
        return ""
    total_needed = 32 + payload_len * 8
    if len(bits) < total_needed:
        return ""
    payload_bytes = bytes(
        sum(bits[32 + i * 8 + j] << (7 - j) for j in range(8))
        for i in range(payload_len)
    )
    try:
        return payload_bytes.decode("utf-8")
    except:
        return ""

PAYLOAD = "MANDIVISION|DataGenesis2026|Rajapalayam|abc12345|END"
TEST_IMG = r"J:\My Drive\rajapalayam hackathon\processed_dataset\images\cropped_IMG_20260901_173025535_HDR.jpg"
OUT_PNG  = r"J:\My Drive\rajapalayam hackathon\test_watermark_output.png"
OUT_JPG  = r"J:\My Drive\rajapalayam hackathon\test_watermark_output.jpg"

def embed(img_path, payload, out_path):
    with Image.open(img_path) as img:
        img = img.convert("RGB")
        arr = np.array(img, dtype=np.uint8)
        bits = string_to_bits(payload)
        flat_blue = arr[:, :, 2].flatten().copy()
        for i, bit in enumerate(bits):
            flat_blue[i] = (flat_blue[i] & 0xFE) | bit
        arr[:, :, 2] = flat_blue.reshape(arr.shape[0], arr.shape[1])
        Image.fromarray(arr, "RGB").save(out_path)

def extract(img_path):
    with Image.open(img_path) as img:
        img = img.convert("RGB")
        arr = np.array(img, dtype=np.uint8)
        flat_blue = arr[:, :, 2].flatten()
        n = min(len(flat_blue), 5000 * 8 + 32)
        bits = [int(flat_blue[i]) & 1 for i in range(n)]
    return bits_to_string(bits)

# Test PNG (lossless)
embed(TEST_IMG, PAYLOAD, OUT_PNG)
extracted_png = extract(OUT_PNG)
print(f"PNG test:")
print(f"  Embedded : {PAYLOAD}")
print(f"  Extracted: {extracted_png}")
print(f"  MATCH    : {PAYLOAD == extracted_png}")

# Test JPEG (lossy) - shows why it fails
embed(TEST_IMG, PAYLOAD, OUT_JPG)
extracted_jpg = extract(OUT_JPG)
print(f"\nJPEG test (expected to FAIL):")
print(f"  Embedded : {PAYLOAD}")
print(f"  Extracted: {extracted_jpg!r}")
print(f"  MATCH    : {PAYLOAD == extracted_jpg}")
