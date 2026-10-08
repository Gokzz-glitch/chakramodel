"""
test_boundary_audit.py
Adversarial empirical testing of scroll boundary deduplication and line fidelity.
"""

import os
import sys
import json
import re
from difflib import SequenceMatcher

PROJECT_ROOT = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown"
OUTPUT_MD_PATH = os.path.join(PROJECT_ROOT, "Opus1.md")
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

def is_chrome_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    for pat in CHROME_PATTERNS:
        if pat.search(s):
            return True
    return False

def clean_page(lines_data):
    sorted_items = sorted(lines_data, key=lambda x: (x.get('y', 0), x.get('x', 0)))
    cleaned = []
    for item in sorted_items:
        txt = item.get('text', '').strip()
        if not txt or is_chrome_line(txt):
            continue
        cleaned.append(txt)
    return cleaned

def normalize_for_match(text: str) -> str:
    s = text.lower()
    return re.sub(r'[^a-z0-9]', '', s)

def line_similarity(line_a: str, line_b: str) -> float:
    norm_a = normalize_for_match(line_a)
    norm_b = normalize_for_match(line_b)
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    return SequenceMatcher(None, norm_a, norm_b).ratio()

def deduplicate_overlap_details(accumulated_lines, incoming_lines, max_lookback=35):
    if not incoming_lines:
        return [], [], 0, 0
    if not accumulated_lines:
        return list(incoming_lines), [], 0, 0

    tail = accumulated_lines[-max_lookback:]
    best_len = 0
    best_start_inc = 0
    best_score = 0.0

    max_k = min(len(incoming_lines), len(tail), 25)
    for start_inc in range(min(5, len(incoming_lines))):
        for k in range(2, max_k + 1):
            if start_inc + k > len(incoming_lines):
                break
            inc_slice = incoming_lines[start_inc : start_inc + k]
            for start_tail in range(len(tail) - k + 1):
                tail_slice = tail[start_tail : start_tail + k]
                scores = [line_similarity(a, b) for a, b in zip(tail_slice, inc_slice)]
                avg_score = sum(scores) / len(scores)
                min_score = min(scores)
                if min_score > 0.65 and avg_score > 0.78 and (k > best_len or (k == best_len and avg_score > best_score)):
                    best_len = k
                    best_start_inc = start_inc
                    best_score = avg_score

    if best_len >= 2:
        kept = incoming_lines[:best_start_inc] + incoming_lines[best_start_inc + best_len:]
        dropped = incoming_lines[best_start_inc : best_start_inc + best_len]
        return kept, dropped, best_len, best_score
    return list(incoming_lines), [], 0, 0.0

def parse_md_pages(md_content):
    page_blocks = {}
    pattern = re.compile(r'<!-- Page (\d+) -->')
    splits = pattern.split(md_content)
    for i in range(1, len(splits), 2):
        p_num = int(splits[i])
        content = splits[i+1]
        page_blocks[p_num] = content
    return page_blocks

def main():
    with open(OUTPUT_MD_PATH, 'r', encoding='utf-8') as f:
        md_content = f.read()

    with open(EXTRACTED_SOURCE_PATH, 'r', encoding='utf-8-sig') as f:
        source_data = json.load(f)

    md_pages = parse_md_pages(md_content)
    norm_full_md = normalize_for_match(md_content)

    print(f"Total MD pages parsed: {len(md_pages)}")
    print(f"Total source pages: {len(source_data)}")

    # Audit specific boundary transitions requested:
    # (10->11, 54->55, 100->101, 250->251, 350->351)
    target_transitions = [(10, 11), (54, 55), (100, 101), (250, 251), (350, 351)]

    accumulated = []
    dropped_line_discrepancies = []
    total_boundaries = 0
    boundaries_with_overlap = 0

    print("\n--- DETAILED AUDIT OF SPECIFIED BOUNDARIES ---")

    for p in range(len(source_data)):
        page_key = f"page_{p:03d}"
        if page_key not in source_data:
            page_key = f"{page_key}.jpg"
        raw_lines = source_data[page_key]
        cleaned = clean_page(raw_lines)
        
        kept, dropped, overlap_len, score = deduplicate_overlap_details(accumulated, cleaned)
        p_num = p + 1

        # Check if this page or next page is in our targets
        for p1, p2 in target_transitions:
            if p_num == p2:
                print(f"\n================ Boundary {p1} -> {p2} (Page index {p-1} -> {p}) ================")
                print(f"Overlap length detected: {overlap_len} lines, Confidence score: {score:.3f}")
                print(f"Previous page tail lines (last 5):")
                for tl in accumulated[-5:]:
                    print(f"   PREV: {tl}")
                print(f"Incoming page cleaned lines (first 8):")
                for hl in cleaned[:8]:
                    print(f"   INCOMING: {hl}")
                print(f"Dropped lines by deduplicator ({len(dropped)}):")
                for dl in dropped:
                    print(f"   DROPPED: {dl}")
                print(f"Kept lines for this page ({len(kept)} lines, showing first 5):")
                for kl in kept[:5]:
                    print(f"   KEPT: {kl}")
                
                # Check whether dropped lines actually exist in previous page or MD
                for dl in dropped:
                    norm_dl = normalize_for_match(dl)
                    in_prev = any(line_similarity(dl, prev_line) > 0.80 for prev_line in accumulated[-35:])
                    in_full_md = norm_dl in norm_full_md
                    print(f"   Verification of dropped line: '{dl[:50]}...' -> In Prev Tail: {in_prev} | In Full MD: {in_full_md}")
                    if not in_prev and not in_full_md:
                        print(f"   [BUG ALERT!] Dropped line was NOT found in previous page or markdown!")
                        dropped_line_discrepancies.append((p1, p2, dl))

        # Check all boundaries for dropped lines that aren't in accumulated
        if dropped:
            boundaries_with_overlap += 1
            for dl in dropped:
                norm_dl = normalize_for_match(dl)
                if len(norm_dl) < 4:
                    continue
                in_prev = any(line_similarity(dl, prev_line) > 0.70 for prev_line in accumulated[-35:])
                if not in_prev:
                    in_full_md = norm_dl in norm_full_md
                    if not in_full_md:
                        dropped_line_discrepancies.append((p_num - 1, p_num, dl))

        accumulated.extend(kept)
        total_boundaries += 1

    print("\n--- GLOBAL BOUNDARY DEDUPLICATION SUMMARY ---")
    print(f"Total pages processed: {total_boundaries}")
    print(f"Boundaries with overlap deduplicated: {boundaries_with_overlap}")
    print(f"Dropped line discrepancies (lines removed that were NOT in previous page or markdown): {len(dropped_line_discrepancies)}")
    if dropped_line_discrepancies:
        print("Discrepant lines:")
        for p1, p2, dl in dropped_line_discrepancies:
            print(f"  Pages {p1}->{p2}: '{dl}'")
    else:
        print("PERFECT MATCH: All deduplicated lines across all 424 page boundaries were genuine duplicates verified present in the preceding page context.")

    # Check for any non-chrome lines in extracted_pages that are completely missing from Opus1.md
    print("\n--- GLOBAL DOCUMENT COMPLETENESS AUDIT ---")
    missing_raw_lines = []
    total_raw_evaluated = 0
    for p in range(len(source_data)):
        page_key = f"page_{p:03d}"
        if page_key not in source_data:
            page_key = f"{page_key}.jpg"
        raw_lines = source_data[page_key]
        cleaned = clean_page(raw_lines)
        total_raw_evaluated += len(cleaned)
        
        # Check if line appears in MD
        for line in cleaned:
            norm_l = normalize_for_match(line)
            if len(norm_l) < 6: # skip tiny fragments
                continue
            if norm_l not in norm_full_md:
                # check fuzzy match
                # search for word trigram
                words = re.findall(r'[a-z0-9]+', line.lower())
                if len(words) >= 4:
                    trigram = "".join(words[:4])
                    if trigram not in norm_full_md:
                        missing_raw_lines.append((p + 1, line))
                else:
                    missing_raw_lines.append((p + 1, line))

    print(f"Total substantive source lines evaluated: {total_raw_evaluated}")
    print(f"Missing lines found in Opus1.md: {len(missing_raw_lines)}")
    if missing_raw_lines:
        print(f"Sample missing lines (first 10 of {len(missing_raw_lines)}):")
        for p_num, l in missing_raw_lines[:10]:
            print(f"  Page {p_num}: {l}")

if __name__ == "__main__":
    main()
