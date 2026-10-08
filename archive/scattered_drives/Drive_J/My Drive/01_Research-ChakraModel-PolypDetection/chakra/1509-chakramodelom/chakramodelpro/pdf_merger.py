import pymupdf
import datetime
from pathlib import Path

# Config
OUTPUT_PDF = r"M:\chakramodelpro\chakra_combined.pdf"
LINES_PER_PAGE = 55
FONTSIZE = 8.5
LINE_H = 13.5
MARGIN = 50
PAGE_W = 595
PAGE_H = 842

SOURCES = [
    r"J:\My Drive\downloads\finalevelauation summary.pdf",
    r"J:\My Drive\downloads\Opus.pdf",
    r"J:\My Drive\downloads\mid.pdf"
]

def render_text_to_pdf(out_doc, text_path, section_num):
    text_path = Path(text_path)
    if not text_path.exists():
        print(f"[-] Missing: {text_path.name}")
        return
        
    text = text_path.read_text(encoding='utf-8')
    lines = text.split('\n')
    
    # Divider Page
    page = out_doc.new_page(width=PAGE_W, height=PAGE_H)
    page.draw_rect(pymupdf.Rect(0, 0, PAGE_W, PAGE_H), color=None, fill=(0.10, 0.15, 0.35))
    page.insert_text((50, 320), f"Section {section_num}: {text_path.name}", fontname="helvetica-bold",
                     fontsize=24, color=(0.20, 0.30, 0.65))
                     
    # Text pages
    chunks = [lines[i:i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)]
    for chunk in chunks:
        page = out_doc.new_page(width=PAGE_W, height=PAGE_H)
        y = MARGIN
        for i, line in enumerate(chunk):
            if len(line) > 90:
                line = line[:89] + "..."
            page.insert_text((MARGIN, y), line, fontname="courier", fontsize=FONTSIZE, color=(0.05, 0.05, 0.25))
            y += LINE_H

def insert_pdf(out_doc, pdf_path, section_num):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"[-] Missing: {pdf_path.name}")
        return
        
    # Divider Page
    page = out_doc.new_page(width=PAGE_W, height=PAGE_H)
    page.draw_rect(pymupdf.Rect(0, 0, PAGE_W, PAGE_H), color=None, fill=(0.10, 0.15, 0.35))
    page.insert_text((50, 320), f"Section {section_num}: {pdf_path.name}", fontname="helvetica-bold",
                     fontsize=24, color=(0.20, 0.30, 0.65))
                     
    src = pymupdf.open(str(pdf_path))
    out_doc.insert_pdf(src)
    src.close()

def main():
    out_doc = pymupdf.open()
    
    # Cover Page
    page = out_doc.new_page(width=PAGE_W, height=PAGE_H)
    page.draw_rect(pymupdf.Rect(0, 0, PAGE_W, 200), color=None, fill=(0.10, 0.15, 0.35))
    page.insert_text((50, 70), "CHAKRA MODEL PRO", fontname="helvetica-bold", fontsize=28, color=(1, 1, 1))
    
    gen_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    page.insert_text((50, 110), "Final Evaluation Summary Extraction", fontname="helvetica", fontsize=16, color=(1, 1, 1))
    page.insert_text((50, 140), f"Generated: {gen_time}", fontname="helvetica", fontsize=12, color=(0.7, 0.7, 0.8))
    
    page.insert_text((50, 250), "Table of Contents", fontname="helvetica-bold", fontsize=18, color=(0.05, 0.05, 0.25))
    
    y = 290
    for i, src in enumerate(SOURCES, start=1):
        page.insert_text((50, y), f"{i}. {Path(src).name}", fontname="helvetica", fontsize=12, color=(0.05, 0.05, 0.25))
        y += 20
        
    print(f"Building {OUTPUT_PDF}...")
    for i, src in enumerate(SOURCES, start=1):
        if src.endswith('.pdf'):
            insert_pdf(out_doc, src, i)
        else:
            render_text_to_pdf(out_doc, src, i)
            
    out_doc.save(OUTPUT_PDF, garbage=4, deflate=True, deflate_images=True)
    out_doc.close()
    print("[OK] PDF Merge Complete.")

if __name__ == "__main__":
    main()
