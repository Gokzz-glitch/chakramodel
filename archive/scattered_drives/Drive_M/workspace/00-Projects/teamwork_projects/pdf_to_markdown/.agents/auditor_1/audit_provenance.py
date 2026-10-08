import os
import json
import cv2
import hashlib

def get_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

print("=== FORENSIC ARTIFACT PROVENANCE AUDIT ===")

# 1. Source PDF
pdf_path = r"C:\Users\imgk3\Downloads\Opus1.pdf"
print(f"Source PDF path: {pdf_path}")
print(f"  Exists: {os.path.exists(pdf_path)}")
print(f"  Size: {os.path.getsize(pdf_path)} bytes")
print(f"  SHA-256: {get_hash(pdf_path)}")

# 2. Extracted JPEG files
temp_ocr_dir = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\temp_ocr"
jpg_files = [f for f in os.listdir(temp_ocr_dir) if f.endswith(".jpg")]
print(f"\nExtracted JPEG images in temp_ocr: {len(jpg_files)} files")
sample_jpg = os.path.join(temp_ocr_dir, "page_000.jpg")
img0 = cv2.imread(sample_jpg)
print(f"  Sample page_000.jpg resolution: {img0.shape[1]}x{img0.shape[0]} ({img0.shape[2]} channels)")

# 3. Individual page OCR JSON files
extracted_pages_dir = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\extracted_pages"
json_files = [f for f in os.listdir(extracted_pages_dir) if f.endswith(".json")]
print(f"\nExtracted page OCR JSON files: {len(json_files)} files")

# Check coordinate alignment
with open(os.path.join(extracted_pages_dir, "page_000.json"), "r", encoding="utf-8-sig") as f:
    page0_ocr = json.load(f)

print(f"  Sample page_000.json line count: {len(page0_ocr)}")
print("  Sample lines with coordinates:")
for l in page0_ocr[:4]:
    print(f"    - Text: '{l.get('text')}' (x={l.get('x')}, y={l.get('y')}, w={l.get('w')}, h={l.get('h')})")

# 4. Master extracted_source.json
source_json_path = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\extracted_source.json"
print(f"\nMaster extracted_source.json:")
print(f"  Exists: {os.path.exists(source_json_path)}")
print(f"  Size: {os.path.getsize(source_json_path)} bytes")
print(f"  SHA-256: {get_hash(source_json_path)}")
with open(source_json_path, "r", encoding="utf-8-sig") as f:
    master_data = json.load(f)
print(f"  Total page entries in master JSON: {len(master_data)}")

# Cross-verify page count and consistency between individual JSONs and master JSON
matching_pages = 0
for idx in range(len(master_data)):
    k = f"page_{idx:03d}"
    single_path = os.path.join(extracted_pages_dir, f"{k}.json")
    if os.path.exists(single_path):
        with open(single_path, "r", encoding="utf-8-sig") as sf:
            single_data = json.load(sf)
        if len(single_data) == len(master_data[k]):
            matching_pages += 1

print(f"  Master JSON vs Individual JSON exact line count match: {matching_pages}/{len(master_data)} pages")

# 5. Output Markdown Opus1.md
md_path = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\Opus1.md"
print(f"\nOutput Markdown Opus1.md:")
print(f"  Exists: {os.path.exists(md_path)}")
print(f"  Size: {os.path.getsize(md_path)} bytes")
print(f"  SHA-256: {get_hash(md_path)}")
with open(md_path, "r", encoding="utf-8") as f:
    md_text = f.read()
lines = md_text.splitlines()
words = md_text.split()
print(f"  Total lines: {len(lines)}")
print(f"  Total words: {len(words)}")

# Check anchors
anchors = [l for l in lines if l.startswith("<!-- Page ")]
print(f"  Total '<!-- Page N -->' anchors: {len(anchors)}")

print("\nProvenance verification complete.")
