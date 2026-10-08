import pymupdf

doc = pymupdf.open(r"C:/Users/imgk3/Downloads/Opus1.pdf")
print("Total pages:", len(doc))
p0 = doc[0]
print("Page 0 get_text():", repr(p0.get_text()))
print("Page 0 get_drawings():", len(p0.get_drawings()))
print("Page 0 get_images():", p0.get_images())
print("Page 0 get_fonts():", p0.get_fonts())
print("Page 0 contents:", repr(p0.read_contents()))
