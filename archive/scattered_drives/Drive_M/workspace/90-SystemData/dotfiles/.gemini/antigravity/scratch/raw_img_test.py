import pymupdf

doc = pymupdf.open(r"C:/Users/imgk3/Downloads/Opus1.pdf")
img_info = doc.get_page_images(0)[0]
xref = img_info[0]
raw_img = doc.extract_image(xref)
print(f"Extracted image format: {raw_img['ext']}, size: {len(raw_img['image'])} bytes, dims: {raw_img['width']}x{raw_img['height']}")
