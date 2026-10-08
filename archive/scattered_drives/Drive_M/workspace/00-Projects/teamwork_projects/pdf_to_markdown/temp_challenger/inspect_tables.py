import json
import re
import sys
import os

sys.path.insert(0, os.path.abspath("."))
from verify_conversion import is_chrome, parse_markdown_pages

def inspect_special_chars_and_tables():
    with open("extracted_source.json", "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    with open("Opus1.md", "r", encoding="utf-8") as f:
        md_text = f.read()

    md_pages = parse_markdown_pages(md_text)

    # Let's inspect benchmark tables specifically:
    # E.g. page_081 (Table 2 - Protocol A, Kvasir 312x312, Protocol A four datasets)
    # page_330, page_335
    tables_to_check = [81, 97, 98, 330, 335]
    
    print("=== DEEP DIVE: BENCHMARK TABLES NUMERICAL INTEGRITY ===")
    for p in tables_to_check:
        p_key = f"page_{p:03d}"
        items = data.get(p_key, [])
        page_md = md_pages.get(p, "")
        
        # Extract all floats and percentages
        source_floats = []
        for it in items:
            t = it.get('text', '').strip()
            if not is_chrome(t):
                # match floats like 0.818, 0'818, 96.7%, etc.
                matches = re.findall(r"(?:\d+[\.,']\d+%?|\d+%)", t)
                source_floats.extend(matches)
        
        print(f"\n--- Page {p+1} (Source key: {p_key}) ---")
        print(f"Total float/percentage tokens in source: {len(source_floats)}")
        
        # Check presence of each token in markdown
        missing_in_md = []
        for sf in source_floats:
            # Note: OCR sometimes has 0'818 or 0793
            # Check if exact token is in md, or normalized
            if sf not in page_md:
                # check if present in adjacent pages
                adj = md_pages.get(p-1, "") + "\n" + page_md + "\n" + md_pages.get(p+1, "")
                if sf not in adj:
                    missing_in_md.append(sf)
                    
        print(f"Tokens missing from page MD: {len(missing_in_md)}")
        if missing_in_md:
            print("  Missing tokens:", missing_in_md[:10])

    print("\n=== SPECIAL CHARACTERS & EQUATIONS AUDIT ===")
    # Look for math symbols, greek letters, unicode symbols in source
    special_symbols = set()
    symbol_instances = []
    
    for p_idx, (p_key, items) in enumerate(data.items()):
        for it in items:
            t = it.get('text', '').strip()
            if not is_chrome(t):
                # Find non-ascii characters
                non_ascii = [c for c in t if ord(c) > 127]
                for c in non_ascii:
                    special_symbols.add(c)
                    if len(symbol_instances) < 30:
                        symbol_instances.append((p_key, c, ord(c), t))

    print(f"Total distinct non-ASCII characters in source: {len(special_symbols)}")
    print("Non-ASCII characters found:")
    for c in sorted(special_symbols):
        print(f"  Char: '{c}' (U+{ord(c):04X})")

    # Check how these characters appear in Opus1.md
    print("\nChecking preservation of non-ASCII characters in Opus1.md:")
    md_chars = set(md_text)
    for c in sorted(special_symbols):
        in_md = c in md_chars
        count_src = sum(sum(it.get('text', '').count(c) for it in items if not is_chrome(it.get('text', ''))) for items in data.values())
        count_md = md_text.count(c)
        print(f"  '{c}' (U+{ord(c):04X}): in_src={count_src}, in_md={count_md}, preserved={in_md}")

if __name__ == "__main__":
    inspect_special_chars_and_tables()
