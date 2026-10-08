import fitz

doc = fitz.open(r"m:\chakramodel\COLLABRUNTESTING.pdf")
page = doc[1] # Page 2
pix = page.get_pixmap(dpi=150)
pix.save(r"m:\chakramodel\.agents\reviewer_m3_1_g7\page2.png")
print("Saved page2.png, size:", pix.width, "x", pix.height)

page1 = doc[0]
pix1 = page1.get_pixmap(dpi=150)
pix1.save(r"m:\chakramodel\.agents\reviewer_m3_1_g7\page1.png")
print("Saved page1.png, size:", pix1.width, "x", pix1.height)

page3 = doc[2]
pix3 = page3.get_pixmap(dpi=150)
pix3.save(r"m:\chakramodel\.agents\reviewer_m3_1_g7\page3.png")
print("Saved page3.png, size:", pix3.width, "x", pix3.height)
