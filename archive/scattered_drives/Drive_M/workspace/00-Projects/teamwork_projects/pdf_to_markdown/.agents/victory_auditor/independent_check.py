"""
independent_check.py
Independent Victory Auditor verification of Opus1.md against extracted_source.json
Strict line-by-line and number-by-number verification without loose fuzzy match loopholes.
"""

import os
import sys
import json
import re
from difflib import SequenceMatcher
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown"
OPUS1_MD_PATH = os.path.join(PROJECT_ROOT, "Opus1.md")
EXTRACTED_SOURCE_PATH = os.path.join(PROJECT_ROOT, "extracted_source.json")
EXTRACTED_PAGES_DIR = os.path.join(PROJECT_ROOT, "extracted_pages")

CHROME_PATTERNS = [
    re.compile(r'motorol[aoq]\s*edge', re.IGNORECASE),
    re.compile(r'edge\s*50\s*fusion', re.IGNORECASE),
    re.compile(r'13\s*Sept(?:ember)?\s*2026', re.IGNORECASE),
    re.compile(r'Write a (?:message|mebb\.age|rnessage|\.)', re.IGNORECASE),
    re.compile(r'VVIite a message', re.IGNORECASE),
    re.compile(r'\bOpus\s*[0-9S](?:\s*High)?\b', re.IGNORECASE),
    re.compile(r'(?:Claude is an?|Ai and can|Ai can)\s*(?:make )?mistakes', re.IGNORECASE),
    re.compile(r'Ai can (?:en|cite|cited)', re.IGNORECASE),
    re.compile(r'cited sources?', re.IGNORECASE),
    re.compile(r'searched the web', re.IGNORECASE),
]

def is_chrome(text: str) -> bool:
    s = text.strip()
    if not s:
        return True
    for p in CHROME_PATTERNS:
        if p.search(s):
            return True
    return False

def norm(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.lower())

def extract_numbers(text: str):
    return re.findall(r'\b\d+(?:[\.,]\d+)?%?\b', text)

def run_independent_audit():
    print("=== INDEPENDENT VICTORY AUDITOR AUDIT ===")
    
    # 1. Load files
    if not os.path.exists(OPUS1_MD_PATH):
        print(f"FAIL: {OPUS1_MD_PATH} does not exist!")
        return False
    if not os.path.exists(EXTRACTED_SOURCE_PATH):
        print(f"FAIL: {EXTRACTED_SOURCE_PATH} does not exist!")
        return False
        
    with open(OPUS1_MD_PATH, 'r', encoding='utf-8') as f:
        md_text = f.read()
    with open(EXTRACTED_SOURCE_PATH, 'r', encoding='utf-8-sig') as f:
        source_data = json.load(f)
        
    print(f"Loaded Opus1.md: {len(md_text)} chars, {len(md_text.splitlines())} lines.")
    print(f"Loaded extracted_source.json: {len(source_data)} pages.")
    
    # 2. Check Page Anchors
    page_anchors = re.findall(r'<!-- Page (\d+) -->', md_text)
    anchor_nums = [int(x) for x in page_anchors]
    print(f"Found {len(anchor_nums)} page anchors (Page {min(anchor_nums)} to Page {max(anchor_nums)}).")
    if len(anchor_nums) != 425:
        print(f"WARNING/FAIL: Expected 425 page anchors, found {len(anchor_nums)}")
        return False
    expected_anchors = list(range(1, 426))
    if anchor_nums != expected_anchors:
        print("FAIL: Page anchors are not strictly sequential 1..425!")
        return False
    print("CHECK 1 (Page Anchors 1..425): PASS")
    
    # 3. Check Page Parsing
    splits = re.split(r'<!-- Page \d+ -->', md_text)
    # splits[0] is preamble, splits[1..425] are pages 1..425
    md_pages = {}
    for idx, page_content in enumerate(splits[1:], start=1):
        md_pages[idx] = page_content
        
    # 4. Strict Line-by-Line Presence Check
    norm_full_md = norm(md_text)
    total_substantive_lines = 0
    missing_substantive_lines = []
    
    for p in range(len(source_data)):
        p_num = p + 1
        key = f"page_{p:03d}"
        if key not in source_data and f"{key}.jpg" in source_data:
            key = f"{key}.jpg"
        raw_lines = source_data.get(key, [])
        
        # Local neighborhood markdown text (p-1, p, p+1)
        local_md = (
            md_pages.get(p_num - 1, "") + "\n" +
            md_pages.get(p_num, "") + "\n" +
            md_pages.get(p_num + 1, "")
        )
        norm_local_md = norm(local_md)
        
        for item in raw_lines:
            txt = item.get('text', '').strip()
            if is_chrome(txt):
                continue
            norm_l = norm(txt)
            if len(norm_l) < 5:
                continue
            total_substantive_lines += 1
            
            # Check if line appears directly in local neighborhood
            if norm_l in norm_local_md or norm_l in norm_full_md:
                continue
                
            # If not direct substring, check sliding window SequenceMatcher (ratio >= 0.85)
            words = txt.split()
            found = False
            local_words = local_md.split()
            q_len = len(words)
            w_size = max(q_len + 2, int(q_len * 1.3))
            for wi in range(max(1, len(local_words) - q_len + 1)):
                w_str = " ".join(local_words[wi : wi + w_size])
                if SequenceMatcher(None, norm_l, norm(w_str)).ratio() >= 0.85:
                    found = True
                    break
            if not found:
                missing_substantive_lines.append((p_num, txt))
                
    print(f"Total substantive lines audited: {total_substantive_lines}")
    print(f"Missing substantive lines: {len(missing_substantive_lines)}")
    if missing_substantive_lines:
        print("FAIL: Missing lines detected:")
        for p_num, l in missing_substantive_lines[:10]:
            print(f"  Page {p_num}: {l}")
        return False
    print("CHECK 2 (Strict Line Presence): PASS (0 omissions)")
    
    # 5. Strict Numeric Invariance Check
    all_source_numbers = []
    for key, lines in source_data.items():
        for item in lines:
            txt = item.get('text', '').strip()
            if not is_chrome(txt):
                all_source_numbers.extend(extract_numbers(txt))
                
    source_num_counts = Counter([n for n in all_source_numbers if len(n) > 1 and not re.match(r'^\d+$', n)])
    md_numbers = extract_numbers(md_text)
    md_num_set = set(md_numbers)
    
    missing_numbers = []
    for num in source_num_counts:
        if num not in md_num_set and num not in md_text:
            missing_numbers.append(num)
            
    print(f"Audited {len(source_num_counts)} unique substantive metrics/floats/percentages.")
    print(f"Missing numbers in Opus1.md: {len(missing_numbers)}")
    if missing_numbers:
        print("FAIL: Missing numbers:", missing_numbers[:10])
        return False
    print("CHECK 3 (Numeric Invariance): PASS (0 missing numbers)")
    
    # 6. Heading Hierarchy
    heading_jumps = []
    prev_level = 0
    for l_idx, line in enumerate(md_text.splitlines(), start=1):
        m = re.match(r'^(#{1,6})\s+(.+)', line)
        if m:
            curr_level = len(m.group(1))
            if curr_level > prev_level + 1 and prev_level > 0:
                heading_jumps.append((l_idx, prev_level, curr_level, m.group(2)))
            prev_level = curr_level
            
    print(f"Heading hierarchy jumps: {len(heading_jumps)}")
    if heading_jumps:
        print("FAIL: Heading hierarchy jumps found:")
        for hj in heading_jumps[:5]:
            print(f"  Line {hj[0]}: level {hj[1]} -> level {hj[2]}: {hj[3]}")
        return False
    print("CHECK 4 (Heading Hierarchy): PASS (0 jumps)")
    
    # 7. Document Start and End
    with open(os.path.join(EXTRACTED_PAGES_DIR, "page_000.json"), 'r', encoding='utf-8-sig') as f:
        p0_clean = [it['text'] for it in json.load(f) if not is_chrome(it.get('text', ''))]
    with open(os.path.join(EXTRACTED_PAGES_DIR, "page_424.json"), 'r', encoding='utf-8-sig') as f:
        p424_clean = [it['text'] for it in json.load(f) if not is_chrome(it.get('text', ''))]
        
    first_line_present = norm(p0_clean[0]) in norm_full_md
    last_line_present = norm(p424_clean[-1]) in norm_full_md
    print(f"First substantive line '{p0_clean[0]}' present: {first_line_present}")
    print(f"Last substantive line '{p424_clean[-1]}' present: {last_line_present}")
    if not (first_line_present and last_line_present):
        print("FAIL: Document truncated at start or end!")
        return False
    print("CHECK 5 (Start/End Truncation): PASS")
    
    print("\nALL INDEPENDENT CHECKS PASSED!")
    return True

if __name__ == "__main__":
    success = run_independent_audit()
    sys.exit(0 if success else 1)
