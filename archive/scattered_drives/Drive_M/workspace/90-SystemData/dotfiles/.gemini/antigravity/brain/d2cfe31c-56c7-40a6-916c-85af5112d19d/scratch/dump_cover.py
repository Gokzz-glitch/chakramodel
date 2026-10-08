import pymupdf
doc = pymupdf.open(r"M:\chakramodelpro\chakra_combined.pdf")
page = doc[0]
txt = page.get_text()
print("=== FULL COVER PAGE TEXT ===")
print(repr(txt))
doc.close()
