#!/usr/bin/env python3
"""
Adversarial Challenge & Stress-Test Suite for Polyp Detection Literature Review
Executed by Challenger 1 (critic / specialist)

Tests:
1. Fuzzy title matching (SequenceMatcher, Token Set Jaccard, Levenshtein ratio)
2. Identifier uniqueness & integrity (arXiv ID, DOI, URL collision detection)
3. Deep metric scan across all P01-P58 (quantitative vs vague qualitative placeholders)
4. Execution and audit of scripts/verify_literature_review.py
"""

import sys
import re
import os
from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = PROJECT_ROOT / "docs" / "literature_review.md"
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify_literature_review.py"


def normalize_title(title: str) -> str:
    t = re.sub(r'[*_`#\[\]]', '', title)
    t = re.sub(r'[^\w\s]', ' ', t)
    return ' '.join(t.lower().split())


def get_tokens(title: str) -> set:
    norm = normalize_title(title)
    # filter out very short stopwords
    stopwords = {'a', 'an', 'the', 'in', 'on', 'for', 'of', 'and', 'with', 'to', 'using', 'based', 'via', 'from'}
    return {w for w in norm.split() if w not in stopwords and len(w) > 1}


def parse_papers(content: str):
    paper_pattern = re.compile(r'^####\s*\[(P\d+)\]\s*(.+)$', re.MULTILINE)
    matches = list(paper_pattern.finditer(content))
    papers = []
    for i, match in enumerate(matches):
        pid = match.group(1)
        title = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        # stop if section break occurs
        sec_match = re.search(r'\n##\s+', content[start:end])
        if sec_match:
            end = start + sec_match.start()
        block_text = content[start:end]
        papers.append({
            "pid": pid,
            "title": title,
            "text": block_text,
            "start": start,
            "end": end
        })
    return papers


def test_fuzzy_titles(papers):
    print("=================================================================")
    print("TEST 1: FUZZY TITLE MATCHING & DUPLICATE DETECTION")
    print("=================================================================")
    
    exact_duplicates = defaultdict(list)
    for p in papers:
        norm = normalize_title(p["title"])
        exact_duplicates[norm].append((p["pid"], p["title"]))
    
    exact_dups = {k: v for k, v in exact_duplicates.items() if len(v) > 1}
    if exact_dups:
        print(f"[FAIL] Exact normalized duplicate titles found: {len(exact_dups)}")
        for k, v in exact_dups.items():
            print(f"  - '{k}': {v}")
    else:
        print("[PASS] 0 exact title duplicates.")

    high_sim_pairs = []
    for i in range(len(papers)):
        p1 = papers[i]
        t1_norm = normalize_title(p1["title"])
        tok1 = get_tokens(p1["title"])
        for j in range(i + 1, len(papers)):
            p2 = papers[j]
            t2_norm = normalize_title(p2["title"])
            tok2 = get_tokens(p2["title"])
            
            seq_ratio = SequenceMatcher(None, t1_norm, t2_norm).ratio()
            jaccard = len(tok1 & tok2) / len(tok1 | tok2) if (tok1 | tok2) else 0.0
            
            # Sort tokens similarity
            s1 = ' '.join(sorted(t1_norm.split()))
            s2 = ' '.join(sorted(t2_norm.split()))
            token_sort_ratio = SequenceMatcher(None, s1, s2).ratio()

            score = max(seq_ratio, jaccard, token_sort_ratio)
            if score >= 0.55:
                high_sim_pairs.append({
                    "p1": (p1["pid"], p1["title"]),
                    "p2": (p2["pid"], p2["title"]),
                    "seq_ratio": seq_ratio,
                    "jaccard": jaccard,
                    "token_sort": token_sort_ratio,
                    "max_score": score
                })

    high_sim_pairs.sort(key=lambda x: x["max_score"], reverse=True)
    print(f"Total title pairs compared: {len(papers)*(len(papers)-1)//2}")
    print(f"Candidate near-duplicate pairs (similarity >= 0.55): {len(high_sim_pairs)}")
    for item in high_sim_pairs:
        p1 = item["p1"]
        p2 = item["p2"]
        print(f"  * Score {item['max_score']:.3f} | [{p1[0]}] '{p1[1]}' vs [{p2[0]}] '{p2[1]}'")
        print(f"    (seq={item['seq_ratio']:.3f}, jaccard={item['jaccard']:.3f}, token_sort={item['token_sort']:.3f})")
    
    critical_title_dups = [item for item in high_sim_pairs if item["max_score"] >= 0.70]
    print(f"\nPairs with similarity >= 0.70: {len(critical_title_dups)}")
    print("TOP 15 HIGHEST SIMILARITY TITLE PAIRS:")
    for item in high_sim_pairs[:15]:
        p1 = item["p1"]
        p2 = item["p2"]
        print(f"  * Score {item['max_score']:.3f} | [{p1[0]}] '{p1[1]}' vs [{p2[0]}] '{p2[1]}'")
        print(f"    (seq={item['seq_ratio']:.3f}, jaccard={item['jaccard']:.3f}, token_sort={item['token_sort']:.3f})")

    return exact_dups, critical_title_dups, high_sim_pairs


def test_identifiers(papers):
    print("\n=================================================================")
    print("TEST 2: IDENTIFIER INTEGRITY (arXiv ID, DOI, URLs)")
    print("=================================================================")
    
    arxiv_regex = re.compile(r'(?:arxiv\.org/abs/|arXiv:\s*\[?|arXiv:)(\d{4}\.\d{4,5})', re.IGNORECASE)
    doi_regex = re.compile(r'(?:doi\.org/|DOI:\s*\[?|DOI:)(10\.\d{4,9}/[^\s)\]]+)', re.IGNORECASE)
    url_regex = re.compile(r'https?://[^\s)\]]+', re.IGNORECASE)

    arxiv_map = defaultdict(list)
    doi_map = defaultdict(list)
    url_map = defaultdict(list)

    for p in papers:
        pid = p["pid"]
        text = p["text"]

        for ax in arxiv_regex.findall(text):
            arxiv_map[ax].append(pid)

        for d in doi_regex.findall(text):
            cleaned = d.rstrip(').,;\'">')
            doi_map[cleaned].append(pid)

        for u in url_regex.findall(text):
            cleaned_u = u.rstrip(').,;\'">')
            url_map[cleaned_u].append(pid)

    dup_arxiv = {k: v for k, v in arxiv_map.items() if len(set(v)) > 1}
    dup_doi = {k: v for k, v in doi_map.items() if len(set(v)) > 1}
    dup_url = {k: v for k, v in url_map.items() if len(set(v)) > 1}

    print(f"Discovered arXiv IDs: {len(arxiv_map)}")
    print(f"Discovered DOIs: {len(doi_map)}")
    print(f"Discovered URLs: {len(url_map)}")

    if dup_arxiv:
        print(f"[FAIL] Duplicate arXiv IDs: {dup_arxiv}")
    else:
        print("[PASS] 0 duplicate arXiv IDs.")

    if dup_doi:
        print(f"[FAIL] Duplicate DOIs: {dup_doi}")
    else:
        print("[PASS] 0 duplicate DOIs.")

    if dup_url:
        print(f"[FAIL] Duplicate URLs: {dup_url}")
    else:
        print("[PASS] 0 duplicate URLs.")

    # Check for missing citations/links
    missing_links = []
    for p in papers:
        has_arxiv = bool(arxiv_regex.search(p["text"]))
        has_doi = bool(doi_regex.search(p["text"]))
        has_url = bool(url_regex.search(p["text"]))
        if not (has_arxiv or has_doi or has_url):
            missing_links.append(p["pid"])

    if missing_links:
        print(f"[WARN] Papers without any arXiv / DOI / URL identifier: {missing_links}")
    else:
        print("[PASS] Every paper has at least one direct verifiable identifier/link.")

    return dup_arxiv, dup_doi, dup_url, missing_links


def test_metric_placeholders(papers):
    print("\n=================================================================")
    print("TEST 3: AUDIT OF METRICS AND VAGUE QUALITATIVE PLACEHOLDERS")
    print("=================================================================")
    
    # Qualitative vague phrases indicating missing hard numbers
    vague_phrases = [
        "superior performance",
        "superiority over",
        "state-of-the-art accuracy",
        "exact numbers in full paper",
        "need to read full paper",
        "not in arxiv abstract",
        "higher generalisation",
        "significant improvement",
        "outperforms existing methods",
        "promising results"
    ]

    metric_kw_regex = re.compile(r'(?:Dice|IoU|mDice|mIoU|FPS|Precision|Recall|mAP|AUC|S-measure|E-measure|MAE)', re.IGNORECASE)
    number_regex = re.compile(r'\d+(?:\.\d+)?%?')

    paper_metric_status = []

    for p in papers:
        pid = p["pid"]
        text = p["text"]

        # Search for metrics section using flexible header matching
        m_match = re.search(r'\*\*(?:Reported Metrics|Key Findings)\*\*[^\n:]*:\s*([\s\S]*?)(?=\n-\s*\*\*|$)', text, re.IGNORECASE)
        
        if not m_match:
            # Check if there is any mention of metrics in the text
            paper_metric_status.append({
                "pid": pid,
                "title": p["title"],
                "status": "MISSING_SECTION",
                "reason": "No Reported Metrics or Key Findings header found",
                "raw": ""
            })
            continue

        m_text = m_match.group(1).strip()
        has_kw = bool(metric_kw_regex.search(m_text))
        has_num = bool(number_regex.search(m_text))

        # Check for vague phrases
        found_vague = [phrase for phrase in vague_phrases if phrase in m_text.lower()]

        # Check if numbers are just general numbers or actual performance scores
        # Count numbers
        numbers = number_regex.findall(m_text)

        if "n/a (dataset paper)" in m_text.lower():
            status = "DATASET_PAPER"
        elif found_vague and len(numbers) < 2:
            status = "VAGUE_PLACEHOLDER"
        elif not has_num:
            status = "NO_NUMERICAL_DATA"
        elif found_vague and len(numbers) >= 2:
            status = "PARTIAL_WITH_QUALITATIVE_NOTE"
        else:
            status = "QUANTITATIVE_VERIFIED"

        paper_metric_status.append({
            "pid": pid,
            "title": p["title"],
            "status": status,
            "vague_phrases": found_vague,
            "has_kw": has_kw,
            "has_num": has_num,
            "numbers_found": numbers,
            "raw": m_text[:120].replace('\n', ' ')
        })

    status_counts = defaultdict(int)
    for p in paper_metric_status:
        status_counts[p["status"]] += 1

    print(f"Metric Status Breakdown across all {len(papers)} papers:")
    for status, cnt in sorted(status_counts.items()):
        print(f"  - {status}: {cnt}")

    flagged_papers = [p for p in paper_metric_status if p["status"] in ("MISSING_SECTION", "NO_NUMERICAL_DATA", "VAGUE_PLACEHOLDER")]
    if flagged_papers:
        print(f"\n[ALERT] Papers with Missing/Vague Qualitative Placeholders: {len(flagged_papers)}")
        for p in flagged_papers:
            print(f"  * [{p['pid']}] ({p['status']}): {p['title']}")
            if 'vague_phrases' in p and p['vague_phrases']:
                print(f"    Vague phrases detected: {p['vague_phrases']}")
            print(f"    Snippet: {p.get('raw', '')}")
    else:
        print("\n[PASS] No papers with completely missing or purely qualitative placeholders.")

    return paper_metric_status, flagged_papers


def test_verify_script_execution():
    print("\n=================================================================")
    print("TEST 4: EXECUTION & DISSECTION OF verify_literature_review.py")
    print("=================================================================")
    
    proc = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)],
        capture_output=True,
        text=True
    )
    
    print(f"Exit Code: {proc.returncode}")
    print(f"Output lines: {len(proc.stdout.splitlines())}")
    
    # Parse errors reported by the script
    script_errors = []
    for line in proc.stdout.splitlines():
        if re.search(r'^\s*\d+\.\s+Paper\s+\[P\d+\]', line):
            script_errors.append(line.strip())

    print(f"Script reported errors count: {len(script_errors)}")
    for err in script_errors:
        print(f"  - {err}")

    # Root cause analysis
    print("\n--- ROOT CAUSE ANALYSIS OF SCRIPT FAILURES ---")
    
    # Inspect regex in verify_literature_review.py
    with open(VERIFY_SCRIPT, encoding='utf-8') as f:
        v_code = f.read()

    field_regex = re.search(r'\("Reported Metrics",\s*(re\.compile\([^\)]+\))\)', v_code)
    extract_regex = re.search(r'm_match\s*=\s*(re\.search\([^\)]+\))', v_code)
    
    print(f"Script Field Regex: {field_regex.group(1) if field_regex else 'Not found'}")
    print(f"Script Extraction Regex: {extract_regex.group(1) if extract_regex else 'Not found'}")

    return proc.returncode, script_errors


if __name__ == "__main__":
    with open(DOC_PATH, encoding="utf-8") as f:
        content = f.read()

    papers = parse_papers(content)
    print(f"Parsed {len(papers)} paper entries from {DOC_PATH.name}")

    exact_dups, crit_titles, all_fuzzy = test_fuzzy_titles(papers)
    dup_ax, dup_doi, dup_url, missing_links = test_identifiers(papers)
    metric_status, flagged_metrics = test_metric_placeholders(papers)
    exit_code, script_errors = test_verify_script_execution()

    print("\n=================================================================")
    print("SUMMARY OF ADVERSARIAL CHALLENGE FINDINGS")
    print("=================================================================")
    print(f"1. Near-duplicate titles (sim >= 0.75): {len(crit_titles)}")
    print(f"2. Duplicate identifiers: {len(dup_ax)} arXiv, {len(dup_doi)} DOI, {len(dup_url)} URL")
    print(f"3. Flagged papers with missing/vague metrics: {len(flagged_metrics)}")
    print(f"4. verify_literature_review.py execution: Exit code {exit_code}, {len(script_errors)} errors")
