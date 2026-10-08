import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Any

CHROME_PATTERNS = [
    re.compile(r'motorola\s*edge', re.IGNORECASE),
    re.compile(r'edge\s*50\s*fusion', re.IGNORECASE),
    re.compile(r'13\s*Sept(?:ember)?\s*2026', re.IGNORECASE),
    re.compile(r'Write a message', re.IGNORECASE),
    re.compile(r'\bOpus\s*[0-9S]\b', re.IGNORECASE),
    re.compile(r'Ai (?:and )?can make mistakes', re.IGNORECASE),
    re.compile(r'Ai can (?:en|cite)', re.IGNORECASE),
    re.compile(r'Claude is an AI', re.IGNORECASE),
    re.compile(r'cited sources', re.IGNORECASE),
]

def is_chrome_line(line_text: str, y_coord: float = 0.0, max_y: float = 2000.0) -> bool:
    """Detect and filter UI chrome, watermarks, and status bars."""
    cleaned = line_text.strip()
    if not cleaned:
        return True
    
    for pat in CHROME_PATTERNS:
        if pat.search(cleaned):
            return True
            
    # Very bottom watermark/chrome (last 3% of screen)
    if max_y > 0 and y_coord > max_y * 0.95:
        if "motorola" in cleaned.lower() or "fusion" in cleaned.lower():
            return True
            
    return False

def clean_page_lines(page_lines: List[Dict[str, Any]], max_y: float = 2000.0) -> List[str]:
    """Filter chrome and return list of substantive text lines."""
    result = []
    for item in page_lines:
        text = item.get('text', '').strip()
        y = item.get('y', 0.0)
        if not is_chrome_line(text, y, max_y):
            result.append(text)
    return result

def normalize_text_for_matching(text: str) -> str:
    """Normalize text for fuzzy line matching (ignore punctuation, case, whitespace)."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def line_similarity(line_a: str, line_b: str) -> float:
    """Calculate character-level similarity between two normalized lines."""
    norm_a = normalize_text_for_matching(line_a)
    norm_b = normalize_text_for_matching(line_b)
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    return SequenceMatcher(None, norm_a, norm_b).ratio()

def find_overlap(lines_prev: List[str], lines_next: List[str], max_overlap_window: int = 25) -> Tuple[int, int, float]:
    """
    Find best overlap where suffix of lines_prev matches prefix of lines_next.
    Returns (prev_overlap_start, next_overlap_end, confidence).
    Lines from lines_next[next_overlap_end:] should be appended.
    """
    if not lines_prev or not lines_next:
        return 0, 0, 0.0

    best_score = 0.0
    best_prev_start = len(lines_prev)
    best_next_end = 0

    # Search for an overlap of k lines, k from 2 up to min(len, max_overlap_window)
    max_k = min(len(lines_prev), len(lines_next), max_overlap_window)
    
    # Try different offsets in next page (usually starts near line 0..5)
    for next_start in range(min(5, len(lines_next))):
        for k in range(2, max_k + 1):
            if next_start + k > len(lines_next):
                continue
            
            # Suffix of prev: last k lines
            prev_slice = lines_prev[-k:]
            next_slice = lines_next[next_start : next_start + k]
            
            # Calculate match quality across the k lines
            scores = [line_similarity(p, n) for p, n in zip(prev_slice, next_slice)]
            avg_score = sum(scores) / len(scores)
            
            # Require all lines in the block to have reasonable similarity (>0.65)
            # and average similarity > 0.75
            min_score = min(scores)
            if min_score > 0.60 and avg_score > 0.75 and avg_score > best_score:
                best_score = avg_score
                best_prev_start = len(lines_prev) - k
                best_next_end = next_start + k

    return best_prev_start, best_next_end, best_score
