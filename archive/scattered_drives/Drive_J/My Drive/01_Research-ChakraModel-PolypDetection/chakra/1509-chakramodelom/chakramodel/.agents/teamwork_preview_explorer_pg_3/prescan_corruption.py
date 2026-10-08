import os
import sys
from pathlib import Path
import json
from PIL import Image

BASE_DIR = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")

corruption_report = {
    "total_jpg": 0,
    "corrupt_jpg": [],
    "truncated_jpg": [],
    "zero_byte_jpg": [],
    "total_txt": 0,
    "unreadable_txt": [],
    "zero_byte_txt": [],
    "total_csv": 0,
    "unreadable_csv": [],
    "empty_csv": []
}

print("=== STARTING FAST CORRUPTION PRE-SCAN ===")

Image.MAX_IMAGE_PIXELS = None

for root, _, files in os.walk(BASE_DIR):
    for f in files:
        fp = Path(root) / f
        f_lower = f.lower()
        if f_lower.endswith(".jpg"):
            corruption_report["total_jpg"] += 1
            if fp.stat().st_size == 0:
                corruption_report["zero_byte_jpg"].append(str(fp.relative_to(BASE_DIR)))
                continue
            # Try fast header decode with PIL
            try:
                with Image.open(fp) as im:
                    im.verify()
            except Exception as e:
                corruption_report["corrupt_jpg"].append({
                    "file": str(fp.relative_to(BASE_DIR)),
                    "error": str(e)
                })
        elif f_lower.endswith(".txt"):
            corruption_report["total_txt"] += 1
            if fp.stat().st_size == 0:
                corruption_report["zero_byte_txt"].append(str(fp.relative_to(BASE_DIR)))
            else:
                try:
                    with open(fp, "r", encoding="utf-8", errors="strict") as tf:
                        _ = tf.read()
                except Exception as e:
                    corruption_report["unreadable_txt"].append({
                        "file": str(fp.relative_to(BASE_DIR)),
                        "error": str(e)
                    })
        elif f_lower.endswith(".csv"):
            corruption_report["total_csv"] += 1
            if fp.stat().st_size == 0:
                corruption_report["empty_csv"].append(str(fp.relative_to(BASE_DIR)))

print(f"Scanned {corruption_report['total_jpg']} JPGs, {corruption_report['total_txt']} TXTs, {corruption_report['total_csv']} CSVs.")
print(f"Corrupt JPGs: {len(corruption_report['corrupt_jpg'])}")
print(f"Zero-byte JPGs: {len(corruption_report['zero_byte_jpg'])}")
print(f"Unreadable TXTs: {len(corruption_report['unreadable_txt'])}")
print(f"Zero-byte TXTs: {len(corruption_report['zero_byte_txt'])}")

out_p = Path(r"m:\chakramodel\.agents\teamwork_preview_explorer_pg_3\corruption_prescan.json")
with open(out_p, "w", encoding="utf-8") as f:
    json.dump(corruption_report, f, indent=2)

print("Pre-scan complete.")
