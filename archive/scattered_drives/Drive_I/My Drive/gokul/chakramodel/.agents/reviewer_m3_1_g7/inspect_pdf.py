import fitz

doc = fitz.open(r"m:\chakramodel\COLLABRUNTESTING.pdf")
for page_idx in range(len(doc)):
    page = doc[page_idx]
    print(f"Page {page_idx+1} rect: {page.rect}")
    print(f"Page {page_idx+1} font list: {page.get_fonts()}")
    text_words = page.get_text("words")
    print(f"Page {page_idx+1} word count: {len(text_words)}")
    drawings = page.get_drawings()
    print(f"Page {page_idx+1} drawing count: {len(drawings)}")
    # check textpage
    tp = page.get_textpage()
    raw_dict = page.get_text("rawdict")
    blocks = raw_dict.get("blocks", [])
    print(f"Page {page_idx+1} rawdict blocks: {len(blocks)}")
    for b in blocks[:5]:
        print("  block type:", b.get("type"))
        if b.get("type") == 0:
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    print("    span text:", repr(s.get("text")))
