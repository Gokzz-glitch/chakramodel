"""
╔══════════════════════════════════════════════════════════════╗
║         MANDIVISION — WATERMARK EMBEDDER v1.0               ║
║   Steganographic Proof-of-Ownership for Dataset Images       ║
║   Data Genesis 2026 Hackathon — Team Rajapalayam            ║
╚══════════════════════════════════════════════════════════════╝

HOW IT WORKS
------------
Uses Least Significant Bit (LSB) steganography to invisibly encode
an ownership signature into every image's blue channel.

The human eye cannot detect changes of ±1 in a pixel's blue value.
But a computer can extract that hidden bit-stream and reconstruct
the exact string we encoded — proving the image belongs to this team.

Payload format:
  MANDIVISION|DataGenesis2026|Rajapalayam|{8-char sha256}|END

OUTPUT
------
  watermarked_dataset/   — watermarked copies of all processed images
  watermark_manifest.json — cryptographic log (sha256 before/after, payload)

USAGE
-----
  python embed_watermark.py
"""

import os
import sys
import json
import hashlib
import struct
import numpy as np
from datetime import datetime
from PIL import Image

# Force UTF-8 output on Windows (prevents emoji encoding crashes)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Configuration ─────────────────────────────────────────────────────────────
SOURCE_DIR   = r"J:\My Drive\rajapalayam hackathon\processed_dataset\images"
OUTPUT_DIR   = r"J:\My Drive\rajapalayam hackathon\watermarked_dataset"
MANIFEST_OUT = r"J:\My Drive\rajapalayam hackathon\watermark_manifest.json"

TEAM_TAG     = "MANDIVISION"
EVENT_TAG    = "DataGenesis2026"
LOCATION_TAG = "Rajapalayam"
END_MARKER   = "END"

# ── Helpers ───────────────────────────────────────────────────────────────────

def sha256_file(path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_payload(img_hash_short: str) -> str:
    """Construct the ownership payload string."""
    return f"{TEAM_TAG}|{EVENT_TAG}|{LOCATION_TAG}|{img_hash_short}|{END_MARKER}"


def string_to_bits(text: str) -> list:
    """Convert a UTF-8 string to a flat list of bits (MSB first)."""
    bits = []
    encoded = text.encode("utf-8")
    # Prepend 4-byte length header so decoder knows when to stop
    length_bytes = struct.pack(">I", len(encoded))
    for byte in length_bytes + encoded:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def embed_lsb(image_path: str, payload: str, out_path: str) -> bool:
    """
    Embed `payload` into the blue channel of the image using LSB steganography.
    Returns True on success, False if the image is too small.
    """
    try:
        with Image.open(image_path) as img:
            # Work in RGB
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            else:
                img = img.convert("RGB")

            arr = np.array(img, dtype=np.uint8)  # shape: (H, W, 3)
            H, W, C = arr.shape

            bits = string_to_bits(payload)
            capacity = H * W  # one bit per pixel in blue channel

            if len(bits) > capacity:
                print(f"   [WARN] Image too small for payload: {os.path.basename(image_path)} "
                      f"({capacity} < {len(bits)} bits needed)")
                return False

            # Embed: modify LSB of blue channel (index 2)
            flat_blue = arr[:, :, 2].flatten().copy()
            for i, bit in enumerate(bits):
                flat_blue[i] = (flat_blue[i] & 0xFE) | bit  # clear LSB then set it

            arr[:, :, 2] = flat_blue.reshape(H, W)

            result_img = Image.fromarray(arr, "RGB")
            # MUST save as PNG (lossless) — JPEG compression destroys LSBs!
            # compress_level=0 = store only (fastest, still lossless)
            result_img.save(out_path, "PNG", compress_level=0)

        return True

    except Exception as e:
        print(f"   [ERROR] Embed error on {os.path.basename(image_path)}: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  MANDIVISION — WATERMARK EMBEDDER v1.0")
    print("  Invisible Steganographic Proof-of-Ownership")
    print("=" * 65)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Gather source images
    source_images = sorted([
        f for f in os.listdir(SOURCE_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    if not source_images:
        print(f"\n[ERROR] No images found in: {SOURCE_DIR}")
        print("   Run auto_annotate.py first to generate the processed dataset.")
        return

    print(f"\n[SRC]  Source : {SOURCE_DIR}")
    print(f"[DST]  Output : {OUTPUT_DIR}")
    print(f"[IMG]  Images : {len(source_images)} found\n")

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "team": TEAM_TAG,
        "event": EVENT_TAG,
        "location": LOCATION_TAG,
        "total_images": len(source_images),
        "images": []
    }

    success_count = 0
    fail_count    = 0

    for idx, fname in enumerate(source_images):
        src_path = os.path.join(SOURCE_DIR, fname)
        # Output as PNG (lossless) — preserves LSB bits exactly
        base_name = os.path.splitext(fname)[0]
        out_fname = base_name + ".png"
        dst_path  = os.path.join(OUTPUT_DIR, out_fname)

        # Compute original hash
        orig_hash = sha256_file(src_path)

        # Build payload using first 8 chars of hash
        payload = build_payload(orig_hash[:8])

        # Embed
        ok = embed_lsb(src_path, payload, dst_path)

        if ok:
            watermarked_hash = sha256_file(dst_path)
            manifest["images"].append({
                "filename":           out_fname,
                "source_filename":    fname,
                "sha256_original":    orig_hash,
                "sha256_watermarked": watermarked_hash,
                "payload":            payload,
                "status":             "WATERMARKED"
            })
            success_count += 1
        else:
            manifest["images"].append({
                "filename":           out_fname,
                "source_filename":    fname,
                "sha256_original":    orig_hash,
                "sha256_watermarked": None,
                "payload":            None,
                "status":             "FAILED"
            })
            fail_count += 1

        # Progress
        if (idx + 1) % 20 == 0 or (idx + 1) == len(source_images):
            pct = (idx + 1) / len(source_images) * 100
            filled = int(pct // 4)
            bar = "#" * filled + "-" * (25 - filled)
            print(f"   [{bar}] {idx+1}/{len(source_images)}  ({pct:.0f}%)", end="\r")

    print()  # newline after progress bar

    # Write manifest
    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print(f"  [DONE] WATERMARKING COMPLETE")
    print(f"  Embedded  : {success_count}/{len(source_images)} images")
    print(f"  Failed    : {fail_count}/{len(source_images)} images")
    print(f"  Manifest  : {MANIFEST_OUT}")
    print(f"  Output    : {OUTPUT_DIR}")
    print("=" * 65)
    print()
    print("  Next step -> python verify_watermark.py")
    print()


if __name__ == "__main__":
    main()
