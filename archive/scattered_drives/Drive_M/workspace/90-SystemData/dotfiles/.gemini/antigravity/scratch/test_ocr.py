import pymupdf

doc = pymupdf.open(r"C:/Users/imgk3/Downloads/Opus1.pdf")
page = doc[0]

try:
    print("Testing PyMuPDF OCR on page 1...")
    ocr_tp = page.get_textpage_ocr(language='eng')
    text = page.get_text(textpage=ocr_tp)
    print("OCR Result length:", len(text))
    print("OCR First 500 chars:")
    print(text[:500])
except Exception as e:
    print("PyMuPDF OCR Exception:", type(e), e)
