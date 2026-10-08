import PyPDF2

pdf_path = r"C:/Users/imgk3/Downloads/Opus1.pdf"

reader = PyPDF2.PdfReader(pdf_path)
print("PyPDF2 num_pages:", len(reader.pages))

text_found = False
for i, page in enumerate(reader.pages):
    t = page.extract_text()
    if t and t.strip():
        print(f"PyPDF2 found text on page {i+1}: {repr(t[:100])}")
        text_found = True
        break

if not text_found:
    print("PyPDF2 confirmed: 0 pages have extractable text.")
