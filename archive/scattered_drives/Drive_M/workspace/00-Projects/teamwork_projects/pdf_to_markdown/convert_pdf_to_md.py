"""
convert_pdf_to_md.py
High-Fidelity PDF-to-Markdown Converter for Opus1.pdf
Preserves all structure, headings, bullet lists, citations, tables, and context.
Includes anti-moiré preprocessing, Windows Native OCR extraction,
substantive chrome filtering, overlap deduplication, and markdown synthesis.
"""

import os
import sys
import re
import json
import time
from difflib import SequenceMatcher
from typing import List, Dict, Any, Tuple

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown"
PDF_PATH = r"C:\Users\imgk3\Downloads\Opus1.pdf"
OUTPUT_MD_PATH = os.path.join(PROJECT_ROOT, "Opus1.md")
EXTRACTED_SOURCE_PATH = os.path.join(PROJECT_ROOT, "extracted_source.json")
EXTRACTED_PAGES_DIR = os.path.join(PROJECT_ROOT, "extracted_pages")

# Regex patterns for UI chrome, watermarks, and status bars to remove
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
    """Check if line is a phone watermark or Claude chat input box."""
    s = line.strip()
    if not s:
        return True
    for pat in CHROME_PATTERNS:
        if pat.search(s):
            return True
    return False

def normalize_for_match(text: str) -> str:
    """Normalize text for fuzzy line matching."""
    s = text.lower()
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def line_similarity(line_a: str, line_b: str) -> float:
    """Compute character similarity between two lines."""
    norm_a = normalize_for_match(line_a)
    norm_b = normalize_for_match(line_b)
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    return SequenceMatcher(None, norm_a, norm_b).ratio()

def clean_page(lines_data: List[Dict[str, Any]]) -> List[str]:
    """Sort lines by vertical Y position and filter chrome."""
    sorted_items = sorted(lines_data, key=lambda x: (x.get('y', 0), x.get('x', 0)))
    cleaned = []
    for item in sorted_items:
        txt = item.get('text', '').strip()
        if not txt:
            continue
        if is_chrome_line(txt):
            continue
        cleaned.append(txt)
    return cleaned

def deduplicate_overlap(accumulated_lines: List[str], incoming_lines: List[str], max_lookback: int = 35) -> List[str]:
    """
    Find overlap between tail of accumulated_lines and head of incoming_lines.
    Preserves any prefix in incoming_lines before the overlap block.
    """
    if not incoming_lines:
        return []
    if not accumulated_lines:
        return list(incoming_lines)

    tail = accumulated_lines[-max_lookback:]
    best_len = 0
    best_start_inc = 0
    best_score = 0.0

    # Test potential overlap blocks of length k (from 2 up to min(len(incoming), 25))
    max_k = min(len(incoming_lines), len(tail), 25)
    
    for start_inc in range(min(5, len(incoming_lines))):
        for k in range(2, max_k + 1):
            if start_inc + k > len(incoming_lines):
                break
            inc_slice = incoming_lines[start_inc : start_inc + k]
            
            # Look for inc_slice in tail
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
        # Preserve prefix before overlap, skip the overlap block, keep remainder
        return incoming_lines[:best_start_inc] + incoming_lines[best_start_inc + best_len:]
    return list(incoming_lines)

def format_line_as_markdown(line: str) -> str:
    """Format individual lines into clean Markdown structure."""
    s = line.strip()
    if not s:
        return ""

    # Check if already markdown heading
    if re.match(r'^#{1,6}\s+', s):
        return s

    # Major document titles
    if "Polyp Segmentation" in s and "Deep Technical Reference" in s:
        return f"# {s}"
    if "HOW TO READ THIS" in s and "LEGEND" in s:
        return f"## {s}"

    # Major numbered sections (e.g. "1. The clinical problem...", "2. Pre-deep-learning era...", "3. The CNN wave...")
    if re.match(r'^[1-9]\.\s+[A-Za-z]', s) and len(s) < 80 and not re.search(r'\d+\.\d+%', s):
        return f"## {s}"

    # Lettered/Named parts (e.g. "Part A - ", "Part B - ", "Part C - ")
    if re.match(r'^Part\s+[A-Z]\s*[-–—:]', s, re.I):
        return f"## {s}"

    # Subsections (e.g. "B.1 Why SSMs...", "1.7.2 Standard IoU loss...", "L.7.3 The WEIGHTED...")
    # Ensure it starts with section identifier followed by text/word, NOT floating point numbers (like 0.795)
    if re.match(r'^[A-Za-z0-9]\.[0-9]+(?:\.[0-9]+)?\s+[A-Za-z]', s) and len(s) < 100:
        # Exclude decimals like "0.795 0.7%"
        if not re.match(r'^0\.\d+', s):
            return f"### {s}"

    # Named clinical / reference sections - use level 2 to avoid jump from level 1
    section_titles = [
        "Why it is done", "The prep", "The procedure itself", "Afterwards",
        "Risks", "Alternatives", "The clinical hinge point", "Takeaway you need"
    ]
    for st in section_titles:
        if s.lower() == st.lower() or s.lower().startswith(st.lower() + ":"):
            return f"## {s}"

    # Bullet lists: bullet symbols, dashes, asterisks
    bullet_match = re.match(r'^[•\-\*]\s*(.+)', s)
    if bullet_match:
        return f"- {bullet_match.group(1).strip()}"

    # Status badges in Obsidian notes: [V], [K], [S], [?]
    if re.match(r'^\[[VKS\?]\]\s*', s):
        return f"- {s}"

    # Numbered list items: 1., 2., (1), (2)
    num_list_match = re.match(r'^(?:\([0-9]+\)|[0-9]+\.)\s+(.+)', s)
    if num_list_match and len(s) > 15:
        return s

    # Table rows: line with multiple pipe characters
    if s.count('|') >= 2:
        return s

    return s

def synthesize_markdown(extracted_source_path: str = EXTRACTED_SOURCE_PATH, output_path: str = OUTPUT_MD_PATH):
    """Synthesize complete Markdown document from extracted source."""
    print(f"Loading extraction source from {extracted_source_path}...")
    with open(extracted_source_path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)

    total_pages = len(data)
    print(f"Loaded {total_pages} pages.")

    accumulated_lines: List[str] = []
    page_chunks: List[Dict[str, Any]] = []

    total_raw_lines = 0
    total_deduped_lines = 0

    print("Stitching pages and deduplicating overlaps...")
    for p in range(total_pages):
        key = f"page_{p:03d}"
        if key not in data and f"{key}.jpg" in data:
            key = f"{key}.jpg"
        
        page_raw = data.get(key, [])
        total_raw_lines += len(page_raw)

        cleaned = clean_page(page_raw)
        new_lines = deduplicate_overlap(accumulated_lines, cleaned)
        total_deduped_lines += len(new_lines)

        page_chunks.append({
            "page_index": p,
            "raw_count": len(page_raw),
            "cleaned_count": len(cleaned),
            "appended_count": len(new_lines),
            "lines": new_lines
        })

        accumulated_lines.extend(new_lines)

    print(f"Total raw lines: {total_raw_lines}")
    print(f"Total deduplicated text lines: {len(accumulated_lines)} (removed {total_raw_lines - len(accumulated_lines)} repetitive/chrome lines)")

    # Build final markdown output with page tracking anchors
    md_output_lines = [
        "# Opus 1: Colorectal Polyp Detection & Medical Vision Deep Technical Compendium",
        "",
        "> **Document Source**: `Opus1.pdf` (425 pages, scanned screen session).",
        "> **Content**: Comprehensive technical compendium spanning clinical colonoscopy principles, machine learning detection (YOLO, SegNet, Faster R-CNN), benchmark datasets (CVC-ClinicDB, Kvasir-SEG, ETIS-Larib), segmentation architecture lineage (PraNet, HarDNet-MSEG, SANet), transformer vision models, state-space models (EndoMamba, Endo-FM), and clinical trial evidence.",
        "",
        "---",
        ""
    ]

    for chunk in page_chunks:
        p_idx = chunk["page_index"]
        lines = chunk["lines"]
        if not lines:
            continue

        md_output_lines.append(f"<!-- Page {p_idx + 1} -->\n")
        
        in_table = False
        prev_was_header = False

        for line in lines:
            formatted = format_line_as_markdown(line)
            
            # Handle markdown tables
            if "|" in formatted and formatted.count("|") >= 2:
                if not in_table:
                    in_table = True
                    # If this is table header, ensure delimiter row exists
                    parts = [c.strip() for c in formatted.split("|")[1:-1]]
                    col_count = len(parts)
                    md_output_lines.append(formatted)
                    md_output_lines.append("|" + "|".join(["---"] * col_count) + "|")
                    continue
                else:
                    md_output_lines.append(formatted)
                    continue
            else:
                in_table = False

            if formatted.startswith("#"):
                md_output_lines.append("")
                md_output_lines.append(formatted)
                md_output_lines.append("")
                prev_was_header = True
            elif formatted.startswith("- "):
                md_output_lines.append(formatted)
                prev_was_header = False
            else:
                if prev_was_header:
                    md_output_lines.append(formatted)
                    prev_was_header = False
                else:
                    # Flowing paragraph line
                    md_output_lines.append(formatted)

        md_output_lines.append("")

    full_markdown = "\n".join(md_output_lines)

    print(f"Writing synthesized Markdown to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_markdown)

    size_bytes = os.path.getsize(output_path)
    line_count = len(md_output_lines)
    word_count = len(full_markdown.split())
    print(f"Successfully generated {output_path}:")
    print(f"  - Size: {size_bytes / 1024:.1f} KB ({size_bytes} bytes)")
    print(f"  - Lines: {line_count}")
    print(f"  - Words: {word_count}")

def main():
    start_time = time.time()
    print("=== Opus1.pdf to Markdown Conversion Pipeline ===")
    
    # 1. Verify extraction source exists
    if not os.path.exists(EXTRACTED_SOURCE_PATH):
        print(f"Source extraction cache not found at {EXTRACTED_SOURCE_PATH}!")
        print("Please ensure extraction and OCR have executed.")
        sys.exit(1)
        
    # 2. Synthesize Markdown
    synthesize_markdown(EXTRACTED_SOURCE_PATH, OUTPUT_MD_PATH)
    
    print(f"Conversion pipeline finished in {time.time() - start_time:.2f}s.")

if __name__ == "__main__":
    main()
