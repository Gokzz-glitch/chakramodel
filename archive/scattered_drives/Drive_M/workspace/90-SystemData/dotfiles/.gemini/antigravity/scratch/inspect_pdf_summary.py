import os
import pymupdf

pdf_path = r"C:/Users/imgk3/Downloads/Opus1.pdf"
doc = pymupdf.open(pdf_path)

print(f"Total pages: {len(doc)}")
print(f"Metadata: {doc.metadata}")
print(f"TOC (first 20 entries): {doc.get_toc()[:20]}")

text_pages = 0
image_only_pages = 0
empty_pages = 0

pages_with_text_sample = []

for page_num in range(len(doc)):
    page = doc[page_num]
    text = page.get_text().strip()
    images = page.get_images()
    if text:
        text_pages += 1
        if len(pages_with_text_sample) < 10:
            pages_with_text_sample.append((page_num + 1, len(text), text[:150]))
    elif images:
        image_only_pages += 1
    else:
        empty_pages += 1

print(f"\nSummary across all {len(doc)} pages:")
print(f"  Pages with digital text: {text_pages}")
print(f"  Pages with image only (no text): {image_only_pages}")
print(f"  Completely empty pages: {empty_pages}")

if pages_with_text_sample:
    print(f"\nSamples of text from pages:")
    for pnum, length, snippet in pages_with_text_sample:
        print(f"  Page {pnum} ({length} chars): {repr(snippet)}")
else:
    print("NO PAGES CONTAIN DIGITAL TEXT! It is an image-only / scanned PDF!")
