"""
test_oracle_flaw.py
Demonstrates the exact flaw in verify_conversion.py's fuzzy_match oracle.
"""

import sys
import os
import re
from difflib import SequenceMatcher

# Import or reproduce fuzzy_match from verify_conversion.py
def normalize_text(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.lower())

def verify_conversion_fuzzy_match(query: str, target_block: str, threshold: float = 0.70) -> bool:
    norm_q = normalize_text(query)
    if not norm_q or len(norm_q) < 4:
        return True
    norm_target = normalize_text(target_block)
    if norm_q in norm_target:
        return True
    
    # Token-level overlap for significant keywords
    q_tokens = [w for w in re.findall(r'[a-z0-9]+', query.lower()) if len(w) >= 3]
    if len(q_tokens) >= 3:
        matched_tokens = sum(1 for t in q_tokens if t in norm_target)
        if matched_tokens / len(q_tokens) >= 0.60:
            return True
    
    # Sliding window search over target tokens
    target_words = target_block.split()
    q_len = len(query.split())
    window_size = max(q_len + 3, int(q_len * 1.5))
    
    for i in range(max(1, len(target_words) - q_len + 1)):
        window = " ".join(target_words[i : i + window_size])
        norm_w = normalize_text(window)
        if SequenceMatcher(None, norm_q, norm_w).ratio() >= threshold:
            return True
    return False

# Test with the dropped line from page 11
dropped_line = "50-80% of PCCRC cases to lesions that were present but overlooked"

# Load Opus1.md
with open(r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\Opus1.md", "r", encoding="utf-8") as f:
    md_content = f.read()

# Check if dropped_line is actually in Opus1.md
print("Is dropped line literally in Opus1.md?", dropped_line in md_content)

# Get Chunk 3 (pages 10-15) from Opus1.md
pattern = re.compile(r'<!-- Page (\d+) -->')
splits = pattern.split(md_content)
page_blocks = {}
for i in range(1, len(splits), 2):
    p_num = int(splits[i]) - 1
    page_blocks[p_num] = splits[i+1]

chunk_text = ""
for p in range(9, 16): # pages 10 to 16
    chunk_text += page_blocks.get(p, "") + "\n"

oracle_result = verify_conversion_fuzzy_match(dropped_line, chunk_text)
print(f"verify_conversion.py fuzzy_match result for dropped line: {oracle_result}")

q_tokens = [w for w in re.findall(r'[a-z0-9]+', dropped_line.lower()) if len(w) >= 3]
norm_target = normalize_text(chunk_text)
matched_tokens = [t for t in q_tokens if t in norm_target]
print(f"Total tokens >= 3 in query: {q_tokens}")
print(f"Matched tokens in target chunk: {matched_tokens}")
print(f"Token match ratio: {len(matched_tokens)} / {len(q_tokens)} = {len(matched_tokens)/len(q_tokens):.2f}")
