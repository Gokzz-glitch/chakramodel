"""
test_integrity_comprehensive.py
Adversarial empirical testing of:
1. Dropped lines across all 425 pages
2. Truncated sections (start, end, internal continuity)
3. Phantom text (hallucinated content in Opus1.md not present in any source page)
"""

import os
import sys
import json
import re
from difflib import SequenceMatcher

PROJECT_ROOT = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown"
EXTRACTED_PAGES_DIR = os.path.join(PROJECT_ROOT, "extracted_pages")
OPUS1_MD_PATH = os.path.join(PROJECT_ROOT, "Opus1.md")

sys.path.insert(0, PROJECT_ROOT)
from convert_pdf_to_md import clean_page, normalize_for_match, line_similarity, is_chrome_line

def parse_markdown_pages(md_content):
    page_blocks = {}
    pattern = re.compile(r'<!-- Page (\d+) -->')
    splits = pattern.split(md_content)
    # splits[0] is preamble
    page_blocks[0] = splits[0]
    for i in range(1, len(splits), 2):
        p_num = int(splits[i])
        content = splits[i+1]
        page_blocks[p_num] = content
    return page_blocks

def main():
    print("=== STARTING COMPREHENSIVE INTEGRITY AUDIT ===")
    
    with open(OPUS1_MD_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    md_pages = parse_markdown_pages(md_content)
    print(f"Parsed {len(md_pages) - 1} page blocks from Opus1.md")
    
    # -------------------------------------------------------------
    # 1. TRUNCATION CHECK: Document Start and End
    # -------------------------------------------------------------
    print("\n--- 1. AUDITING DOCUMENT BOUNDARIES (TRUNCATION AUDIT) ---")
    with open(os.path.join(EXTRACTED_PAGES_DIR, "page_000.json"), "r", encoding="utf-8-sig") as f:
        p0_raw = json.load(f)
    p0_clean = clean_page(p0_raw)
    
    with open(os.path.join(EXTRACTED_PAGES_DIR, "page_424.json"), "r", encoding="utf-8-sig") as f:
        p424_raw = json.load(f)
    p424_clean = clean_page(p424_raw)
    
    print(f"Page 1 (page_000) first 3 clean source lines:")
    for l in p0_clean[:3]:
        print(f"   SRC: {l}")
    p1_md = md_pages.get(1, "")
    print(f"Opus1.md Page 1 first 3 lines:")
    for l in [x for x in p1_md.splitlines() if x.strip()][:3]:
        print(f"   MD:  {l}")
        
    print(f"\nPage 425 (page_424) last 3 clean source lines:")
    for l in p424_clean[-3:]:
        print(f"   SRC: {l}")
    p425_md = md_pages.get(425, "")
    print(f"Opus1.md Page 425 last 3 lines:")
    for l in [x for x in p425_md.splitlines() if x.strip()][-3:]:
        print(f"   MD:  {l}")

    # Check if page 1 starts with page 0 first substantive line
    p0_first_norm = normalize_for_match(p0_clean[0])
    p1_md_norm = normalize_for_match(p1_md)
    start_intact = p0_first_norm in p1_md_norm
    
    # Check if page 425 ends with page 424 last substantive line
    p424_last_norm = normalize_for_match(p424_clean[-1])
    p425_md_norm = normalize_for_match(p425_md)
    end_intact = p424_last_norm in p425_md_norm
    
    print(f"\nStart truncation test: {'PASS (intact)' if start_intact else 'FAIL (truncated)'}")
    print(f"End truncation test:   {'PASS (intact)' if end_intact else 'FAIL (truncated)'}")

    # -------------------------------------------------------------
    # 2. DROPPED LINES CHECK (EXHAUSTIVE)
    # -------------------------------------------------------------
    print("\n--- 2. AUDITING ALL 425 PAGES FOR DROPPED SOURCE LINES ---")
    all_source_lines = 0
    missing_lines = []
    
    # Pre-index normalized markdown by page and neighborhood (p-1, p, p+1)
    norm_md_by_page = {}
    for p_num, text in md_pages.items():
        norm_md_by_page[p_num] = normalize_for_match(text)
        
    full_norm_md = normalize_for_match(md_content)

    for p in range(425):
        p_num = p + 1
        with open(os.path.join(EXTRACTED_PAGES_DIR, f"page_{p:03d}.json"), "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        clean = clean_page(raw)
        all_source_lines += len(clean)
        
        # Neighborhood text: p-1, p, p+1
        neighborhood = (
            norm_md_by_page.get(p_num - 1, "") + 
            norm_md_by_page.get(p_num, "") + 
            norm_md_by_page.get(p_num + 1, "")
        )
        
        for line in clean:
            norm_l = normalize_for_match(line)
            if len(norm_l) < 4:
                continue
            if norm_l not in neighborhood:
                # check full md
                if norm_l not in full_norm_md:
                    # check fuzzy similarity
                    words = [w for w in re.findall(r'[a-z0-9]+', line.lower()) if len(w) >= 3]
                    matched = sum(1 for w in words if w in neighborhood)
                    if not (words and matched / len(words) >= 0.75):
                        missing_lines.append((p_num, line))

    print(f"Total substantive source lines checked: {all_source_lines}")
    print(f"Total dropped source lines: {len(missing_lines)}")
    if missing_lines:
        print(f"Sample dropped lines (up to 10):")
        for p_num, l in missing_lines[:10]:
            print(f"  Page {p_num}: {l}")
    else:
        print("EXHAUSTIVE PASS: Zero dropped lines across all 425 pages!")

    # -------------------------------------------------------------
    # 3. PHANTOM TEXT / HALLUCINATION CHECK
    # -------------------------------------------------------------
    print("\n--- 3. AUDITING OPUS1.MD FOR PHANTOM TEXT / HALLUCINATIONS ---")
    # Build complete pool of all cleaned source text
    full_source_norm = ""
    for p in range(425):
        with open(os.path.join(EXTRACTED_PAGES_DIR, f"page_{p:03d}.json"), "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        for item in raw:
            full_source_norm += normalize_for_match(item.get("text", "")) + " "
            
    # Check lines in Opus1.md
    md_lines = md_content.splitlines()
    phantom_candidates = []
    
    preamble_headers = [
        "opus 1 colorectal polyp detection",
        "document source opus1pdf",
        "content comprehensive technical compendium",
        "how to read this legend"
    ]
    
    for idx, line in enumerate(md_lines):
        s = line.strip()
        if not s or s.startswith("<!-- Page") or s.startswith("---") or s.startswith("|---"):
            continue
        # Remove markdown symbols
        cleaned_md_line = re.sub(r'^[#\-\*\|\>\s]+', '', s).strip()
        norm_l = normalize_for_match(cleaned_md_line)
        if len(norm_l) < 10:
            continue
        
        # Check if it's intentional preamble metadata added by converter
        if any(p in norm_l for p in preamble_headers):
            continue
            
        # Check if line appears in source text
        if norm_l not in full_source_norm:
            # Check token overlap
            words = [w for w in re.findall(r'[a-z0-9]+', cleaned_md_line.lower()) if len(w) >= 3]
            if words:
                matched = sum(1 for w in words if w in full_source_norm)
                if matched / len(words) < 0.70:
                    phantom_candidates.append((idx + 1, s))
                    
    print(f"Total markdown lines checked: {len(md_lines)}")
    print(f"Phantom lines detected: {len(phantom_candidates)}")
    if phantom_candidates:
        print("Sample phantom lines:")
        for line_num, text in phantom_candidates[:10]:
            print(f"  Line {line_num}: {text}")
    else:
        print("EXHAUSTIVE PASS: Zero phantom text lines detected in Opus1.md!")

    # -------------------------------------------------------------
    # 4. STRUCTURAL HEADING AUDIT
    # -------------------------------------------------------------
    print("\n--- 4. AUDITING HEADING HIERARCHY IN OPUS1.MD ---")
    heading_errors = []
    prev_h = 0
    for idx, line in enumerate(md_lines):
        m = re.match(r'^(#{1,6})\s+(.+)', line)
        if m:
            lvl = len(m.group(1))
            txt = m.group(2)
            if lvl > prev_h + 1 and prev_h > 0:
                heading_errors.append((idx + 1, prev_h, lvl, txt))
            prev_h = lvl
            
    print(f"Illegal heading jumps found in Opus1.md: {len(heading_errors)}")
    for line_num, p_lvl, c_lvl, txt in heading_errors:
        print(f"  Line {line_num}: Jump from level {p_lvl} to {c_lvl}: '{txt[:50]}'")

if __name__ == "__main__":
    main()
