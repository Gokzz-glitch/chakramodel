import os
import pymupdf

pdf_path = r"C:/Users/imgk3/Downloads/Opus1.pdf"
doc = pymupdf.open(pdf_path)

print("Page Image Details (first 10 pages):")
for pno in range(min(10, len(doc))):
    page = doc[pno]
    images = page.get_images()
    print(f"Page {pno + 1}:")
    for img in images:
        xref = img[0]
        base_img = doc.extract_image(xref)
        print(f"  xref: {xref}, ext: {base_img['ext']}, width: {base_img['width']}, height: {base_img['height']}, colorspace: {base_img['colorspace']}, bpc: {base_img['bpc']}")
