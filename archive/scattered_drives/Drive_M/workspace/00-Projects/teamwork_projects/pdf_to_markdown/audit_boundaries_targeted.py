"""
audit_boundaries_targeted.py
Targeted boundary audit for pages:
10->11, 54->55, 100->101, 250->251, 350->351
plus full scan across all 424 consecutive page boundaries.
"""

import os
import sys
import json
import re
from difflib import SequenceMatcher

PROJECT_ROOT = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown"
EXTRACTED_PAGES_DIR = os.path.join(PROJECT_ROOT, "extracted_pages")
OPUS1_MD_PATH = os.path.join(PROJECT_ROOT, "Opus1.md")

# Load convert_pdf_to_md functions
sys.path.insert(0, PROJECT_ROOT)
from convert_pdf_to_md import clean_page, deduplicate_overlap, normalize_for_match, line_similarity

def load_page(p_idx):
    fn = os.path.join(EXTRACTED_PAGES_DIR, f"page_{p_idx:03d}.json")
    if not os.path.exists(fn):
        return []
    with open(fn, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def parse_markdown_pages(md_content):
    page_blocks = {}
    pattern = re.compile(r'<!-- Page (\d+) -->')
    splits = pattern.split(md_content)
    for i in range(1, len(splits), 2):
        p_num = int(splits[i])
        content = splits[i+1]
        page_blocks[p_num] = content
    return page_blocks

def analyze_boundary(prev_idx, next_idx, accumulated_prev, md_content, md_pages):
    raw_prev = load_page(prev_idx)
    raw_next = load_page(next_idx)
    
    clean_prev = clean_page(raw_prev)
    clean_next = clean_page(raw_next)
    
    # Run deduplication
    new_lines = deduplicate_overlap(accumulated_prev, clean_next)
    
    # Identify which lines from clean_next were dropped
    # deduplicate_overlap returns clean_next[:start] + clean_next[start+best_len:]
    dropped_lines = []
    # We can determine the dropped block by finding the difference:
    # Let's inspect how many lines were dropped
    dropped_count = len(clean_next) - len(new_lines)
    
    # Check if each dropped line exists in accumulated_prev (tail)
    dropped_details = []
    norm_md = normalize_for_match(md_content)
    
    # Find which specific lines from clean_next are not in new_lines
    # Since new_lines preserves order and slices clean_next:
    for i, line in enumerate(clean_next):
        if line not in new_lines:
            # Check if line was in accumulated_prev
            norm_l = normalize_for_match(line)
            found_in_prev_tail = False
            for prev_l in accumulated_prev[-35:]:
                if line_similarity(line, prev_l) >= 0.75:
                    found_in_prev_tail = True
                    break
            found_in_md = norm_l in norm_md
            dropped_details.append({
                "line": line,
                "found_in_prev_tail": found_in_prev_tail,
                "found_in_full_md": found_in_md,
                "is_genuine_duplicate": found_in_prev_tail
            })
            
    return {
        "prev_idx": prev_idx,
        "next_idx": next_idx,
        "prev_clean_count": len(clean_prev),
        "next_clean_count": len(clean_next),
        "kept_count": len(new_lines),
        "dropped_count": dropped_count,
        "dropped_details": dropped_details,
        "new_lines": new_lines,
        "acc_after": accumulated_prev + new_lines
    }

def main():
    with open(OPUS1_MD_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()
    md_pages = parse_markdown_pages(md_content)
    
    # Accumulate full document state like convert_pdf_to_md does
    accumulated = []
    boundary_results = {}
    
    discrepancies = []
    
    for p in range(425):
        raw = load_page(p)
        cleaned = clean_page(raw)
        new_lines = deduplicate_overlap(accumulated, cleaned)
        
        # Check dropped lines
        if len(cleaned) > len(new_lines):
            for line in cleaned:
                if line not in new_lines:
                    norm_l = normalize_for_match(line)
                    found_in_tail = any(line_similarity(line, pl) >= 0.75 for pl in accumulated[-35:])
                    found_in_md = norm_l in normalize_for_match(md_content)
                    if not found_in_tail and not found_in_md:
                        discrepancies.append((p, line))
                        
        accumulated.extend(new_lines)
        
    print("=== BOUNDARY REPLAY AUDIT COMPLETE ===")
    print(f"Total pages processed: 425")
    print(f"Total deduplicated lines in MD: {len(accumulated)}")
    print(f"Total dropped line discrepancies (lines removed that were NOT genuine duplicates in previous tail): {len(discrepancies)}")
    
    # Now inspect targeted boundaries:
    # 1-indexed pages: 10->11 (0-idx 9->10), 54->55 (0-idx 53->54), 100->101 (0-idx 99->100), 250->251 (0-idx 249->250), 350->351 (0-idx 349->350)
    # Also 0-indexed 10->11, 54->55, 100->101, 250->251, 350->351
    targets = [
        ("1-indexed 10 -> 11 (0-idx 9->10)", 9, 10),
        ("0-indexed 10 -> 11 (1-idx 11->12)", 10, 11),
        ("1-indexed 54 -> 55 (0-idx 53->54)", 53, 54),
        ("0-indexed 54 -> 55 (1-idx 55->56)", 54, 55),
        ("1-indexed 100 -> 101 (0-idx 99->100)", 99, 100),
        ("0-indexed 100 -> 101 (1-idx 101->102)", 100, 101),
        ("1-indexed 250 -> 251 (0-idx 249->250)", 249, 250),
        ("0-indexed 250 -> 251 (1-idx 251->252)", 250, 251),
        ("1-indexed 350 -> 351 (0-idx 349->350)", 349, 350),
        ("0-indexed 350 -> 351 (1-idx 351->352)", 350, 351),
    ]
    
    # Re-run accumulating up to each target and report
    acc_replay = []
    for p in range(425):
        raw = load_page(p)
        cleaned = clean_page(raw)
        
        # Check if p is in targets as next_idx
        for label, p_prev, p_next in targets:
            if p == p_next:
                new_l = deduplicate_overlap(acc_replay, cleaned)
                dropped = [l for l in cleaned if l not in new_l]
                print(f"\n=======================================================")
                print(f"TARGET BOUNDARY: {label}")
                print(f"Previous page {p_prev} clean lines: {len(clean_page(load_page(p_prev)))}")
                print(f"Incoming page {p_next} clean lines: {len(cleaned)}")
                print(f"Deduplicated: kept {len(new_l)}, dropped {len(dropped)}")
                print(f"Previous page tail (last 4 lines):")
                for l in acc_replay[-4:]:
                    print(f"   [PREV TAIL] {repr(l)}")
                print(f"Incoming page head (first 4 lines):")
                for l in cleaned[:4]:
                    print(f"   [INC HEAD]  {repr(l)}")
                print(f"Dropped lines ({len(dropped)}):")
                for d in dropped:
                    in_prev = any(line_similarity(d, pl) >= 0.75 for pl in acc_replay[-35:])
                    print(f"   [DROPPED]   {repr(d)} -> in previous tail? {in_prev}")
                print(f"First 3 kept lines for incoming page:")
                for k in new_l[:3]:
                    print(f"   [KEPT]      {repr(k)}")
                    
        new_lines = deduplicate_overlap(acc_replay, cleaned)
        acc_replay.extend(new_lines)

if __name__ == "__main__":
    main()
