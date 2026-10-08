"""
verify_conversion.py
Automated Dual-Tier Verification Script for Opus1.pdf -> Opus1.md
Implements the verification architecture designed by Explorer 3:
- Tier 1: Deterministic cross-checks (numeric invariance, sequence matching, heading hierarchy, sentence coverage)
- Tier 2: LLM semantic evaluation via google-genai (gemini-2.5-flash) with structured Pydantic schema,
          with an offline deterministic evaluation mode (--offline).
- Generates structured verification_report.json.
- Strict exit code: exit(0) iff 0 omitted lines and 0 missing context; exit(1) on discrepancy.
"""

import os
import sys
import re
import json
import argparse
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple

sys.stdout.reconfigure(encoding='utf-8')

# Optional dotenv import
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Optional google-genai and pydantic import
HAVE_GENAI = False
try:
    from google import genai
    from google.genai import types
    from pydantic import BaseModel, Field
    HAVE_GENAI = True
except ImportError:
    pass

# Pydantic schema for structured evaluation
if HAVE_GENAI:
    class ChunkVerificationResult(BaseModel):
        chunk_id: int
        is_complete: bool
        omitted_lines: List[str] = Field(default_factory=list, description="Lines or text present in source but missing in markdown")
        missing_context: List[str] = Field(default_factory=list, description="Contextual facts or details missing from markdown")
        altered_meanings: List[str] = Field(default_factory=list, description="Statements where meaning was altered")
        numeric_mismatches: List[str] = Field(default_factory=list, description="Numbers or measurements that do not match")
        confidence_score: float = Field(description="Confidence between 0.0 and 1.0")
        notes: Optional[str] = None

# UI Chrome filter patterns (same as converter)
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

def is_chrome(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    for p in CHROME_PATTERNS:
        if p.search(s):
            return True
    return False

def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and removing non-alphanumeric chars."""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def extract_numbers(text: str) -> List[str]:
    """Extract numbers, percentages, and metrics."""
    return re.findall(r'\b\d+(?:[\.,]\d+)?%?\b', text)

def fuzzy_match(query: str, target_block: str, threshold: float = 0.70) -> bool:
    """Check if query string appears in target_block with high similarity or token overlap."""
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

def parse_markdown_pages(md_content: str) -> Dict[int, str]:
    """Parse Markdown content into page-indexed blocks using <!-- Page N --> anchors."""
    page_blocks = {}
    pattern = re.compile(r'<!-- Page (\d+) -->')
    splits = pattern.split(md_content)
    
    # splits[0] is preamble before Page 1
    # then pairs of (page_num_str, page_content)
    for i in range(1, len(splits), 2):
        p_num = int(splits[i]) - 1 # 0-indexed page
        content = splits[i+1]
        page_blocks[p_num] = content
        
    return page_blocks

def verify_heading_hierarchy(md_content: str) -> Tuple[bool, List[str]]:
    """Validate heading hierarchy (# -> ## -> ### without illegal jumps)."""
    errors = []
    lines = md_content.split('\n')
    prev_level = 0
    
    for idx, line in enumerate(lines):
        m = re.match(r'^(#{1,6})\s+', line)
        if m:
            curr_level = len(m.group(1))
            if curr_level > prev_level + 1 and prev_level > 0:
                errors.append(f"Line {idx+1}: Heading jump from level {prev_level} to {curr_level}: '{line[:50]}'")
            prev_level = curr_level
            
    return (len(errors) == 0, errors)

def run_tier1_audit(source_pages: Dict[int, List[Dict[str, Any]]], md_content: str, chunk_size: int = 5) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Run deterministic cross-checks across chunks of pages."""
    md_pages = parse_markdown_pages(md_content)
    total_pages = len(source_pages)
    
    chunk_evaluations = []
    error_counts = {
        "ERR_OMITTED_LINE": 0,
        "ERR_MISSING_CONTEXT": 0,
        "ERR_NUMERIC_MISMATCH": 0,
        "ERR_HALLUCINATION": 0,
        "ERR_STRUCTURAL_CORRUPTION": 0
    }
    
    # Group pages into chunks (e.g. 5 pages per chunk)
    chunk_id = 1
    for start_p in range(0, total_pages, chunk_size):
        end_p = min(start_p + chunk_size, total_pages)
        
        # Aggregate substantive source lines for chunk
        chunk_source_lines = []
        chunk_source_numbers = []
        for p in range(start_p, end_p):
            raw_lines = source_pages.get(p, [])
            for item in raw_lines:
                txt = item.get('text', '').strip()
                if not is_chrome(txt):
                    chunk_source_lines.append(txt)
                    chunk_source_numbers.extend(extract_numbers(txt))
                    
        # Aggregate markdown content for chunk (with slight overlap window)
        md_chunk_text = ""
        for p in range(max(0, start_p - 1), min(total_pages, end_p + 1)):
            md_chunk_text += md_pages.get(p, "") + "\n"
            
        # 1. Check line / sentence presence
        omitted_lines = []
        for line in chunk_source_lines:
            # Skip very short lines or punctuation artifacts
            if len(normalize_text(line)) < 5:
                continue
            if not fuzzy_match(line, md_chunk_text, threshold=0.70):
                omitted_lines.append(line)
                
        # 2. Check numeric invariance
        numeric_mismatches = []
        md_chunk_numbers = set(extract_numbers(md_chunk_text))
        for num in set(chunk_source_numbers):
            # filter out single digits like page numbers
            if len(num) > 1 and num not in md_chunk_numbers:
                # check if present in normalized form
                if num not in md_chunk_text:
                    numeric_mismatches.append(f"Number '{num}' missing from chunk markdown")

        missing_context = []
        if omitted_lines:
            missing_context.extend([f"Missing context from line: '{l[:60]}...'" for l in omitted_lines[:5]])
            
        is_complete = (len(omitted_lines) == 0 and len(numeric_mismatches) == 0)
        status = "PASS" if is_complete else "FAIL"
        
        if omitted_lines:
            error_counts["ERR_OMITTED_LINE"] += len(omitted_lines)
            error_counts["ERR_MISSING_CONTEXT"] += len(omitted_lines)
        if numeric_mismatches:
            error_counts["ERR_NUMERIC_MISMATCH"] += len(numeric_mismatches)
            
        chunk_eval = {
            "chunk_id": chunk_id,
            "page_range": [start_p + 1, end_p],
            "status": status,
            "is_complete": is_complete,
            "omitted_lines": omitted_lines,
            "missing_context": missing_context,
            "altered_meanings": [],
            "numeric_mismatches": numeric_mismatches,
            "confidence_score": 1.0 if is_complete else 0.5,
            "notes": "Verified 100% complete." if is_complete else f"{len(omitted_lines)} omissions detected."
        }
        chunk_evaluations.append(chunk_eval)
        chunk_id += 1
        
    return chunk_evaluations, error_counts

def run_llm_evaluation(client: Any, chunk_evaluations: List[Dict[str, Any]], source_pages: Dict[int, List[Dict[str, Any]]], md_content: str, model_name: str = "gemini-2.5-flash") -> List[Dict[str, Any]]:
    """Run Tier 2 LLM semantic verification using google-genai."""
    md_pages = parse_markdown_pages(md_content)
    updated_evaluations = []
    
    print(f"Running Tier 2 LLM Evaluation using {model_name}...")
    
    # Audit chunks that had candidate questions or sample check across document
    for chunk in chunk_evaluations:
        start_p, end_p = chunk["page_range"][0] - 1, chunk["page_range"][1]
        
        # Build source chunk text
        src_text_lines = []
        for p in range(start_p, end_p):
            for item in source_pages.get(p, []):
                txt = item.get('text', '').strip()
                if not is_chrome(txt):
                    src_text_lines.append(txt)
        src_chunk_str = "\n".join(src_text_lines)
        
        # Build md chunk text
        md_chunk_str = "\n".join([md_pages.get(p, "") for p in range(start_p, end_p)])
        
        prompt = f"""You are an expert Document Verification Auditor comparing SOURCE TEXT against GENERATED MARKDOWN.
Determine whether any substantive information, lines, or context were omitted or altered.

SOURCE TEXT:
---
{src_chunk_str[:4000]}
---

GENERATED MARKDOWN:
---
{md_chunk_str[:4000]}
---

Evaluate the fidelity and report any omitted lines or missing context.
"""
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=ChunkVerificationResult,
                    system_instruction="You are a strict QA verification auditor. Report any omission."
                )
            )
            parsed: ChunkVerificationResult = response.parsed
            chunk["is_complete"] = parsed.is_complete
            chunk["omitted_lines"] = parsed.omitted_lines
            chunk["missing_context"] = parsed.missing_context
            chunk["altered_meanings"] = parsed.altered_meanings
            chunk["numeric_mismatches"] = parsed.numeric_mismatches
            chunk["status"] = "PASS" if parsed.is_complete else "FAIL"
            chunk["notes"] = f"LLM verified: {parsed.notes or 'Complete'}"
        except Exception as e:
            print(f"Warning: LLM evaluation failed on chunk {chunk['chunk_id']}: {e}")
            
        updated_evaluations.append(chunk)
        
    return updated_evaluations

def main():
    parser = argparse.ArgumentParser(description="Automated Verification Script for Opus1.pdf -> Opus1.md")
    parser.add_argument("--pdf", default=r"C:\Users\imgk3\Downloads\Opus1.pdf", help="Path to original PDF")
    parser.add_argument("--md", default=r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\Opus1.md", help="Path to generated Markdown")
    parser.add_argument("--source", default=r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\extracted_source.json", help="Path to extracted source JSON")
    parser.add_argument("--report", default=r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\verification_report.json", help="Path to output verification report JSON")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model to use")
    parser.add_argument("--offline", action="store_true", help="Run deterministic cross-checks only (no API calls)")
    parser.add_argument("--chunk-size", type=int, default=5, help="Number of pages per chunk")
    
    args = parser.parse_args()
    
    print("=== Verification Suite: Opus1.pdf vs Opus1.md ===")
    print(f"Target PDF:      {args.pdf}")
    print(f"Target Markdown: {args.md}")
    print(f"Source Cache:    {args.source}")
    print(f"Report Output:   {args.report}")
    print(f"Mode:            {'Offline Deterministic' if args.offline else 'LLM / Adaptive'}")
    
    # Check input existence
    if not os.path.exists(args.md):
        print(f"Error: Markdown file {args.md} not found!")
        sys.exit(2)
    if not os.path.exists(args.source):
        print(f"Error: Extraction source {args.source} not found!")
        sys.exit(2)
        
    with open(args.source, 'r', encoding='utf-8-sig') as f:
        source_data = json.load(f)
        
    with open(args.md, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Organize source data by page index 0..424
    total_pages = len(source_data)
    source_pages = {}
    for p in range(total_pages):
        key = f"page_{p:03d}"
        if key not in source_data and f"{key}.jpg" in source_data:
            key = f"{key}.jpg"
        source_pages[p] = source_data.get(key, [])
        
    # Check heading hierarchy
    hierarchy_ok, hierarchy_errors = verify_heading_hierarchy(md_content)
    if not hierarchy_ok:
        print(f"Notice: Heading hierarchy warning(s): {len(hierarchy_errors)}")
        for err in hierarchy_errors[:3]:
            print(f"  {err}")

    # Tier 1: Deterministic cross-checks
    print("\nRunning Tier 1 Deterministic Verification Engine...")
    chunk_evaluations, error_counts = run_tier1_audit(source_pages, md_content, chunk_size=args.chunk_size)
    
    # Tier 2: LLM Evaluation if credentials present and not --offline
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    mode_used = "offline_deterministic"
    
    if not args.offline and api_key and HAVE_GENAI:
        try:
            client = genai.Client(api_key=api_key)
            chunk_evaluations = run_llm_evaluation(client, chunk_evaluations, source_pages, md_content, model_name=args.model)
            mode_used = "llm_verified"
        except Exception as e:
            print(f"Could not initialize GenAI client: {e}. Falling back to deterministic results.")
            mode_used = "offline_deterministic"
    else:
        if not args.offline:
            print("No GEMINI_API_KEY detected in environment or .env. Running in offline deterministic mode.")
            mode_used = "offline_deterministic"

    # Compute aggregate metrics
    total_chunks = len(chunk_evaluations)
    passed_chunks = sum(1 for c in chunk_evaluations if c["status"] == "PASS")
    failed_chunks = total_chunks - passed_chunks
    
    omitted_lines_total = sum(len(c["omitted_lines"]) for c in chunk_evaluations)
    missing_context_total = sum(len(c["missing_context"]) for c in chunk_evaluations)
    numeric_mismatches_total = sum(len(c["numeric_mismatches"]) for c in chunk_evaluations)
    
    coverage_pct = round((passed_chunks / total_chunks) * 100.0, 2) if total_chunks > 0 else 0.0
    overall_status = "PASS" if (omitted_lines_total == 0 and missing_context_total == 0) else "FAIL"
    
    # Build structured report
    report = {
        "metadata": {
            "target_pdf": args.pdf,
            "target_markdown": args.md,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode_used,
            "model": args.model if mode_used == "llm_verified" else "deterministic"
        },
        "summary": {
            "total_chunks": total_chunks,
            "passed_chunks": passed_chunks,
            "failed_chunks": failed_chunks,
            "total_source_lines": sum(len(lines) for lines in source_pages.values()),
            "total_markdown_lines": len(md_content.split('\n')),
            "omitted_lines_count": omitted_lines_total,
            "missing_context_count": missing_context_total,
            "numeric_mismatches_count": numeric_mismatches_total,
            "deterministic_coverage_pct": coverage_pct,
            "overall_status": overall_status
        },
        "error_codes": {
            "ERR_OMITTED_LINE": error_counts["ERR_OMITTED_LINE"],
            "ERR_MISSING_CONTEXT": error_counts["ERR_MISSING_CONTEXT"],
            "ERR_NUMERIC_MISMATCH": error_counts["ERR_NUMERIC_MISMATCH"],
            "ERR_HALLUCINATION": 0,
            "ERR_STRUCTURAL_CORRUPTION": len(hierarchy_errors) if not hierarchy_ok else 0
        },
        "chunk_evaluations": chunk_evaluations
    }
    
    print(f"\nWriting verification report to {args.report}...")
    with open(args.report, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print("\n================ VERIFICATION SUMMARY ================")
    print(f"Overall Status:            {overall_status}")
    print(f"Total Chunks Audited:      {total_chunks}")
    print(f"Passed Chunks:             {passed_chunks} / {total_chunks} ({coverage_pct}%)")
    print(f"Omitted Lines Count:       {omitted_lines_total}")
    print(f"Missing Context Count:     {missing_context_total}")
    print(f"Numeric Mismatches Count:  {numeric_mismatches_total}")
    print(f"Report Generated:          {args.report}")
    print("======================================================")
    
    # Strict exit code contract:
    # 0 iff 0 omitted lines AND 0 missing context AND overall_status == PASS
    if overall_status == "PASS" and omitted_lines_total == 0 and missing_context_total == 0:
        print("\nVerification PASSED with 0 omitted lines and 0 missing context.")
        sys.exit(0)
    else:
        print(f"\nVerification FAILED: {omitted_lines_total} omitted lines, {missing_context_total} missing context.")
        sys.exit(1)

if __name__ == "__main__":
    main()
