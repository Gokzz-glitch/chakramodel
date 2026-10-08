import json
import re
import sys
import os

sys.path.insert(0, os.path.abspath("."))
from verify_conversion import is_chrome, extract_numbers, parse_markdown_pages


def run_audit():
    print("Loading extracted_source.json...")
    with open("extracted_source.json", "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    print("Loading Opus1.md...")
    with open("Opus1.md", "r", encoding="utf-8") as f:
        md_text = f.read()

    md_pages = parse_markdown_pages(md_text)
    total_pages = len(data)
    print(f"Total source pages: {total_pages}, Parsed MD pages: {len(md_pages)}")

    # Sample pages with high metric count (tables)
    sample_pages = [81, 92, 97, 98, 330, 335, 336, 341, 16, 23, 24, 25, 110, 151, 178, 215, 264, 321, 326]

    print(f"\n--- Checking Sample Benchmark & Equation Pages ({len(sample_pages)} pages) ---")
    
    total_sample_numbers = 0
    sample_missing = []

    for p in sample_pages:
        p_key = f"page_{p:03d}"
        items = data.get(p_key, [])
        page_md = md_pages.get(p, "")
        surrounding_md = md_pages.get(p-1, "") + "\n" + page_md + "\n" + md_pages.get(p+1, "")
        
        page_numbers = []
        for it in items:
            txt = it.get('text', '').strip()
            if not is_chrome(txt):
                nums = extract_numbers(txt)
                for n in nums:
                    if len(n) > 1: # multi-digit or decimals/percentages
                        page_numbers.append((n, txt))
        
        page_missing = []
        for n, orig_line in page_numbers:
            total_sample_numbers += 1
            if n not in surrounding_md:
                page_missing.append((n, orig_line))
                sample_missing.append((p, n, orig_line))

        print(f"Page {p+1} (key: {p_key}): {len(page_numbers)} numbers extracted. Missing: {len(page_missing)}")
        if page_missing:
            for n, l in page_missing[:5]:
                print(f"   MISSING: '{n}' from line: '{l}'")

    print(f"\nTotal sample numbers checked: {total_sample_numbers}")
    print(f"Total sample missing: {len(sample_missing)}")

    # Full document numeric audit
    print("\n--- Full Document Numeric Audit ---")
    doc_total_numbers = 0
    doc_missing = []
    
    for p in range(total_pages):
        p_key = f"page_{p:03d}"
        items = data.get(p_key, [])
        page_md = md_pages.get(p, "")
        surrounding_md = md_pages.get(p-1, "") + "\n" + page_md + "\n" + md_pages.get(p+1, "")

        for it in items:
            txt = it.get('text', '').strip()
            if not is_chrome(txt):
                for n in extract_numbers(txt):
                    if len(n) > 1:
                        doc_total_numbers += 1
                        if n not in surrounding_md:
                            doc_missing.append((p, n, txt))

    print(f"Total substantive numbers in full document: {doc_total_numbers}")
    print(f"Total missing numbers across entire document: {len(doc_missing)}")
    if doc_missing:
        print("Sample missing numbers in full doc:")
        for p, n, l in doc_missing[:15]:
            print(f"   Page {p+1}: '{n}' in line: '{l[:60]}'")

if __name__ == "__main__":
    run_audit()
