import pymupdf

print("=== Opus.pdf ===")
doc = pymupdf.open(r"J:\My Drive\downloads\Opus.pdf")
print(f"Pages: {doc.page_count}")
for i in [0, 1, 2, 100, 200, 424]:
    if i < doc.page_count:
        pg = doc[i]
        imgs = pg.get_images(full=True)
        txt = pg.get_text().strip()
        rect = pg.rect
        print(f"  Page {i+1}: {len(imgs)} images, text_len={len(txt)}, size={rect.width:.0f}x{rect.height:.0f}")
if doc.page_count > 0:
    page = doc[0]
    images = page.get_images(full=True)
    if images:
        xref = images[0][0]
        img = doc.extract_image(xref)
        ext = img["ext"]
        w = img["width"]
        h = img["height"]
        print(f"  First image: {ext}, {w}x{h}")
doc.close()

print("\n=== mid.pdf ===")
doc = pymupdf.open(r"J:\My Drive\downloads\mid.pdf")
print(f"Pages: {doc.page_count}")
for i in range(min(5, doc.page_count)):
    pg = doc[i]
    imgs = pg.get_images(full=True)
    txt = pg.get_text().strip()
    rect = pg.rect
    print(f"  Page {i+1}: {len(imgs)} images, text_len={len(txt)}, size={rect.width:.0f}x{rect.height:.0f}")
if doc.page_count > 0:
    page = doc[0]
    images = page.get_images(full=True)
    if images:
        xref = images[0][0]
        img = doc.extract_image(xref)
        ext = img["ext"]
        w = img["width"]
        h = img["height"]
        print(f"  First image: {ext}, {w}x{h}")
doc.close()
