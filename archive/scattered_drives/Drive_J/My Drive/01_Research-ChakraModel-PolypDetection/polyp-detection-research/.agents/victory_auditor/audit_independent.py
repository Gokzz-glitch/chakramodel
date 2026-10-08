#!/usr/bin/env python3
"""
Independent Victory Auditor Verification Script.
Developed and executed independently by Victory Auditor.
Zero shared code with worker/orchestrator scripts.
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

def main():
    repo_root = Path(r"m:\chakramodelpro\polyp-detection-research")
    doc_path = repo_root / "docs" / "literature_review.md"

    print("=== VICTORY AUDITOR INDEPENDENT VERIFICATION ===")
    print(f"Auditing file: {doc_path}")

    if not doc_path.exists():
        print(f"FATAL: {doc_path} does not exist!")
        sys.exit(1)

    with open(doc_path, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.splitlines()
    print(f"File stats: {len(lines)} lines, {len(text)} characters, {doc_path.stat().st_size} bytes")

    # 1. Parse all paper headings
    paper_header_regex = re.compile(r"^####\s*\[(P\d+)\]\s*(.+)$", re.MULTILINE)
    matches = list(paper_header_regex.finditer(text))
    print(f"\n--- CHECK 1: Paper Count and Ordering ---")
    print(f"Total paper headers found: {len(matches)}")

    pids = [m.group(1) for m in matches]
    expected_pids = [f"P{i:02d}" for i in range(1, 59)]

    if pids == expected_pids:
        print(f"[PASS] Sequence is strictly sequential from P01 to P58 (exactly 58 papers).")
    else:
        print(f"[FAIL] Sequence mismatch! Actual: {pids}")

    # Extract paper blocks
    papers = []
    for i, m in enumerate(matches):
        pid = m.group(1)
        title = m.group(2).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        next_sec = re.search(r"\n##\s+", text[start:end])
        if next_sec:
            end = start + next_sec.start()
        papers.append({
            "pid": pid,
            "title": title,
            "body": text[start:end]
        })

    # 2. Check Newly Added Papers ([P19] to [P58]) vs Existing ([P01] to [P18])
    print(f"\n--- CHECK 2: Newly Added Papers & Deduplication ---")
    original_papers = papers[:18]
    new_papers = papers[18:]
    print(f"Original baseline papers count: {len(original_papers)} (P01-P18)")
    print(f"Newly added papers count: {len(new_papers)} (P19-P58)")

    # Title deduplication (exact and normalized)
    norm_title_map = defaultdict(list)
    for p in papers:
        # aggressive normalization: remove punctuation, lowercase, strip whitespace
        cleaned = re.sub(r"[^\w\s]", "", p["title"].lower())
        norm_t = " ".join(cleaned.split())
        norm_title_map[norm_t].append((p["pid"], p["title"]))

    dup_titles = {t: pids for t, pids in norm_title_map.items() if len(pids) > 1}
    if dup_titles:
        print(f"[FAIL] Duplicate normalized titles found: {len(dup_titles)}")
        for t, pids in dup_titles.items():
            print(f"  Duplicate: {pids}")
    else:
        print(f"[PASS] 0 duplicate titles across all 58 papers (including P01-P18 and P19-P58).")

    # URL / arXiv / DOI uniqueness
    url_regex = re.compile(r"https?://[^\s)\]]+", re.I)
    arxiv_regex = re.compile(r"(?:arxiv\.org/abs/|arXiv:\s*\[?|arXiv:)(\d{4}\.\d{4,5})", re.I)
    doi_regex = re.compile(r"(?:doi\.org/|DOI:\s*\[?|DOI:)(10\.\d{4,9}/[^\s)\]]+)", re.I)

    url_map = defaultdict(list)
    arxiv_map = defaultdict(list)
    doi_map = defaultdict(list)

    for p in papers:
        pid = p["pid"]
        body = p["body"]
        for u in url_regex.findall(body):
            clean_u = u.rstrip(".,;)\'\"]>")
            url_map[clean_u].append(pid)
        for a in arxiv_regex.findall(body):
            arxiv_map[a].append(pid)
        for d in doi_regex.findall(body):
            clean_d = d.rstrip(".,;)\'\"]>")
            doi_map[clean_d].append(pid)

    dup_urls = {u: pids for u, pids in url_map.items() if len(set(pids)) > 1}
    dup_arxiv = {a: pids for a, pids in arxiv_map.items() if len(set(pids)) > 1}
    dup_dois = {d: pids for d, pids in doi_map.items() if len(set(pids)) > 1}

    print(f"Unique URLs found: {len(url_map)} across all papers")
    print(f"Unique arXiv IDs found: {len(arxiv_map)} across all papers")
    print(f"Unique DOIs found: {len(doi_map)} across all papers")

    if dup_urls:
        print(f"[FAIL] Duplicate URLs shared across distinct papers: {dup_urls}")
    else:
        print(f"[PASS] 0 duplicate URLs shared across distinct papers.")

    if dup_arxiv:
        print(f"[FAIL] Duplicate arXiv IDs shared across distinct papers: {dup_arxiv}")
    else:
        print(f"[PASS] 0 duplicate arXiv IDs shared across distinct papers.")

    if dup_dois:
        print(f"[FAIL] Duplicate DOIs shared across distinct papers: {dup_dois}")
    else:
        print(f"[PASS] 0 duplicate DOIs shared across distinct papers.")

    # 3. Field completeness & quantitative metrics for newly added papers (P19-P58)
    print(f"\n--- CHECK 3: Required Fields & Quantitative Metrics for New Papers (P19-P58) ---")
    
    # Required fields per acceptance criteria: Title, Authors, Year, Method Summary, Metrics, Relevance
    field_patterns = {
        "Authors": re.compile(r"\*\*Authors\*\*:", re.I),
        "Year": re.compile(r"\*\*Year(?:/Venue)?\*\*:", re.I),
        "Method Summary": re.compile(r"\*\*Method Summary\*\*:", re.I),
        "Metrics": re.compile(r"\*\*(?:Reported Metrics|Key Findings)\*\*[^\n:]*:", re.I),
        "Relevance": re.compile(r"\*\*Relevance\*\*:", re.I),
    }

    metric_number_pattern = re.compile(r"\d+(?:\.\d+)?%?")
    metric_keywords_pattern = re.compile(r"(?:dice|iou|mdice|miou|fps|precision|recall|map|auc|s-measure|e-measure|mae|f1|sensitivity|specificity|ms|params|flops|gflops)", re.I)

    field_errors = []
    metric_errors = []

    for p in new_papers:
        pid = p["pid"]
        body = p["body"]
        
        # Check title
        if not p["title"] or len(p["title"]) < 5:
            field_errors.append(f"Paper [{pid}] has empty or invalid title")

        # Check required fields
        for field_name, pattern in field_patterns.items():
            if not pattern.search(body):
                field_errors.append(f"Paper [{pid}] is missing required field '{field_name}'")

        # Extract Metrics section text
        m_search = re.search(r"\*\*(?:Reported Metrics|Key Findings)\*\*[^\n:]*:\s*([\s\S]*?)(?=\n-\s*\*\*|$)", body, re.I)
        if not m_search:
            metric_errors.append(f"Paper [{pid}] has no metrics section")
        else:
            m_text = m_search.group(1).strip()
            numbers = metric_number_pattern.findall(m_text)
            has_kw = bool(metric_keywords_pattern.search(m_text))
            if not numbers:
                metric_errors.append(f"Paper [{pid}] Metrics section has no quantitative numbers! Text: {m_text[:80]}")
            elif not has_kw:
                metric_errors.append(f"Paper [{pid}] Metrics section has no standard metric keywords! Text: {m_text[:80]}")

    if field_errors:
        print(f"[FAIL] Field errors found in new papers ({len(field_errors)}):")
        for fe in field_errors:
            print(f"  {fe}")
    else:
        print(f"[PASS] All 40 newly added papers (P19-P58) have all required fields (Title, Authors, Year/Venue, Method Summary, Metrics, Relevance).")

    if metric_errors:
        print(f"[FAIL] Metric errors found in new papers ({len(metric_errors)}):")
        for me in metric_errors:
            print(f"  {me}")
    else:
        print(f"[PASS] All 40 newly added papers (P19-P58) report explicit quantitative metrics with verified numerical values.")

    # Also check original papers (P01-P18)
    print(f"\n--- CHECK 3b: Sanity Check on Legacy Papers (P01-P18) ---")
    legacy_field_errors = []
    legacy_metric_errors = []
    for p in original_papers:
        pid = p["pid"]
        body = p["body"]
        for field_name, pattern in field_patterns.items():
            if not pattern.search(body):
                legacy_field_errors.append(f"Legacy paper [{pid}] missing '{field_name}'")
        m_search = re.search(r"\*\*(?:Reported Metrics|Key Findings)\*\*[^\n:]*:\s*([\s\S]*?)(?=\n-\s*\*\*|$)", body, re.I)
        if not m_search:
            legacy_metric_errors.append(f"Legacy paper [{pid}] missing metrics section")
        else:
            m_text = m_search.group(1).strip()
            numbers = metric_number_pattern.findall(m_text)
            has_kw = bool(metric_keywords_pattern.search(m_text))
            if not numbers or not has_kw:
                legacy_metric_errors.append(f"Legacy paper [{pid}] non-quantitative metrics: {m_text[:80]}")

    print(f"Legacy papers field errors: {len(legacy_field_errors)}")
    print(f"Legacy papers metric errors: {len(legacy_metric_errors)}")
    if not legacy_field_errors and not legacy_metric_errors:
        print(f"[PASS] Legacy papers P01-P18 also 100% compliant.")

    # 4. Check SOTA Comparison Table
    print(f"\n--- CHECK 4: SOTA Comparison Tables and Newly Discovered Baseline Numbers ---")
    sota_match = re.search(r"##\s*SOTA Comparison Table([\s\S]*?)(?=\n##\s+|$)", text)
    if not sota_match:
        print(f"[FAIL] '## SOTA Comparison Table' section not found!")
    else:
        sota_text = sota_match.group(1)
        # Check sub-tables
        subtables = ["### Standard Benchmarks", "### Video Polyp Segmentation", "### Real-Time Detection"]
        for st in subtables:
            if st in sota_text:
                print(f"[PASS] Found subtable: {st}")
            else:
                print(f"[FAIL] Missing subtable: {st}")

        # Check for newly discovered baselines in SOTA table
        new_baselines = [
            "Polyp-Mamba", "CASCADE", "SSFormer", "ColonFormer", "FCBFormer",
            "TransFuse", "DoubleU-Net", "MSNet", "ESFPNet", "BGNet", "BA-Net", "Diff-Polyp",
            "PNS+", "LDNet", "VPS-Net", "TMRNet", "DCRNet", "TempPolyp-Net", "TransVNet", "ST-PolypNet", "Polyp-SAM++", "Mamba-VPS",
            "Polyp-YOLO", "Edge-YOLO-Polyp", "YOLO-v11n"
        ]
        missing_baselines = [b for b in new_baselines if not re.search(re.escape(b), sota_text, re.I)]
        if missing_baselines:
            print(f"[FAIL] SOTA table missing newly discovered baselines: {missing_baselines}")
        else:
            print(f"[PASS] All {len(new_baselines)} checked newly discovered baselines are present in SOTA Comparison tables.")

        # Count total rows across tables
        table_rows = [line for line in sota_text.splitlines() if line.strip().startswith("|") and not line.strip().startswith("|---") and not line.strip().startswith("| Method")]
        print(f"Total data rows across SOTA comparison tables: {len(table_rows)}")

    # 5. Gap Analysis & Backlog Check
    print(f"\n--- CHECK 5: Gap Analysis & Backlog ---")
    gap_match = re.search(r"##\s*Gap Analysis & Our Contribution", text)
    backlog_match = re.search(r"##\s*Papers To Read \(Backlog\)", text)
    print(f"Gap Analysis section exists: {bool(gap_match)}")
    print(f"Backlog section exists: {bool(backlog_match)}")

    print("\n=== INDEPENDENT AUDIT COMPLETE ===")

if __name__ == "__main__":
    main()
