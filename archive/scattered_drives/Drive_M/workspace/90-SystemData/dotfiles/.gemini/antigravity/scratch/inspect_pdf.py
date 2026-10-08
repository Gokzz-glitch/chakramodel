import os
import pymupdf

pdf_path = r"C:/Users/imgk3/Downloads/Opus1.pdf"
print(f"File exists: {os.path.exists(pdf_path)}")
if not os.path.exists(pdf_path):
    print("Error: Target PDF does not exist!")
    exit(1)

file_size = os.path.getsize(pdf_path)
print(f"File size: {file_size} bytes ({file_size / 1024:.2f} KB)")

doc = pymupdf.open(pdf_path)
print(f"Page count: {len(doc)}")
print(f"Metadata: {doc.metadata}")
print(f"TOC: {doc.get_toc()}")

print("\n--- Page by Page Overview ---")
font_counts = {}
for page_num in range(len(doc)):
    page = doc[page_num]
    rect = page.rect
    text = page.get_text()
    blocks = page.get_text("blocks")
    tables = page.find_tables()
    images = page.get_images()
    drawings = page.get_drawings()
    
    print(f"\nPage {page_num + 1}: Rect={rect}, Blocks={len(blocks)}, Tables={len(tables.tables)}, Images={len(images)}, Drawings={len(drawings)}, TextChars={len(text)}")
    
    # Check fonts used on page
    text_page = page.get_text("dict")
    page_fonts = set()
    for block in text_page.get("blocks", []):
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    font_key = (span["font"], round(span["size"], 1), span["flags"])
                    font_counts[font_key] = font_counts.get(font_key, 0) + len(span["text"])
                    page_fonts.add((span["font"], round(span["size"], 1)))
    print(f"  Fonts detected: {sorted(list(page_fonts))}")
    print(f"  First 200 chars: {repr(text[:200])}")

print("\n--- Document Font Frequency ---")
for (font, size, flags), count in sorted(font_counts.items(), key=lambda x: x[1], reverse=True)[:15]:
    flags_desc = []
    if flags & 2: flags_desc.append("italic")
    if flags & 16: flags_desc.append("bold")
    print(f"Font: {font:<30} Size: {size:<6} Flags: {flags} ({', '.join(flags_desc) or 'regular'}) Chars: {count}")
