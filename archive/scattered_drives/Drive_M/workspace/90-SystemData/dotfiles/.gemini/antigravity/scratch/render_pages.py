import pymupdf

doc = pymupdf.open(r"C:/Users/imgk3/Downloads/Opus1.pdf")
page1 = doc[0]
pix = page1.get_pixmap(dpi=150)
pix.save(r"C:\Users\imgk3\.gemini\antigravity\scratch\page_1.png")

page2 = doc[1]
pix2 = page2.get_pixmap(dpi=150)
pix2.save(r"C:\Users\imgk3\.gemini\antigravity\scratch\page_2.png")

print("Saved page_1.png and page_2.png")
