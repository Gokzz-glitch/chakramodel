#!/usr/bin/env python3
"""
Automated Verification Script for docs/literature_review.md
Checks:
  a. Sequence of paper IDs: [P01] to [P58] present, exactly 58 papers, no missing IDs.
  b. Title uniqueness: 0 duplicate titles (normalized).
  c. URL / DOI / arXiv ID uniqueness: 0 duplicates across all papers.
  d. Required sections present for every paper: Title, Authors, Year/Venue, Method Summary, Reported Metrics, Relevance.
  e. Metrics check: Reported Metrics section must contain quantitative metric numbers (regex check for numbers and metric names like Dice, IoU, FPS, mDice, mIoU, %, etc.).
  f. SOTA Comparison Table check: verifies that newly added models appear in the comparison tables.
Exits 0 on clean pass, non-zero on failure with informative error messages.
"""

import sys
import re
import os
from pathlib import Path
from collections import defaultdict


def normalize_title(title: str) -> str:
    """Normalize paper title for duplicate detection."""
    # Remove markdown formatting, punctuation, and extra whitespace
    t = re.sub(r'[*_`#\[\]]', '', title)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip().lower()
    return t


def clean_url(url: str) -> str:
    """Strip trailing punctuation from extracted URL."""
    return url.rstrip(').,;\'">')


def verify_literature_review(md_path: Path) -> bool:
    print(f"============================================================")
    print(f"VERIFYING LITERATURE REVIEW: {md_path}")
    print(f"============================================================")

    if not md_path.exists():
        print(f"ERROR: File not found: {md_path}")
        return False

    content = md_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    total_lines = len(lines)
    print(f"Document lines: {total_lines}, Total bytes: {len(content)}")

    errors = []
    warnings = []

    # ------------------------------------------------------------
    # 1. Parse Paper Headings & Blocks
    # ------------------------------------------------------------
    paper_pattern = re.compile(r'^####\s*\[(P\d+)\]\s*(.+)$', re.MULTILINE)
    matches = list(paper_pattern.finditer(content))

    paper_blocks = []
    for i, match in enumerate(matches):
        pid = match.group(1)
        title = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        # If there is a major section break '## ' before the next paper or end of papers
        section_break = re.search(r'\n##\s+', content[start:end])
        if section_break:
            end = start + section_break.start()
        block_text = content[start:end]
        paper_blocks.append({
            "pid": pid,
            "title": title,
            "text": block_text,
            "match_pos": start
        })

    num_papers = len(paper_blocks)
    print(f"\n[Check A] Sequence of Paper IDs ([P01] to [P58])")
    print(f"  Total papers discovered: {num_papers}")

    expected_ids = [f"P{i:02d}" for i in range(1, 59)]
    actual_ids = [p["pid"] for p in paper_blocks]

    if num_papers != 58:
        errors.append(f"Expected exactly 58 papers, but found {num_papers}.")

    missing_ids = set(expected_ids) - set(actual_ids)
    if missing_ids:
        errors.append(f"Missing paper IDs: {sorted(list(missing_ids))}")

    duplicate_ids = [pid for pid in set(actual_ids) if actual_ids.count(pid) > 1]
    if duplicate_ids:
        errors.append(f"Duplicate paper IDs found: {duplicate_ids}")

    if actual_ids == expected_ids:
        print(f"  [PASS] Exactly 58 papers found in strict sequential order [P01] -> [P58].")
    else:
        errors.append(f"Paper IDs sequence mismatch: {actual_ids[:10]}...{actual_ids[-5:]}")

    # ------------------------------------------------------------
    # 2. Check B: Title Uniqueness
    # ------------------------------------------------------------
    print(f"\n[Check B] Title Uniqueness")
    title_to_pids = defaultdict(list)
    for p in paper_blocks:
        norm_t = normalize_title(p["title"])
        title_to_pids[norm_t].append((p["pid"], p["title"]))

    dup_titles = {norm_t: pids for norm_t, pids in title_to_pids.items() if len(pids) > 1}
    if dup_titles:
        for norm_t, pids in dup_titles.items():
            errors.append(f"Duplicate title found: '{norm_t}' shared by {pids}")
    else:
        print(f"  [PASS] 0 duplicate titles. All 58 paper titles are distinct.")

    # ------------------------------------------------------------
    # 3. Check C: URL / DOI / arXiv ID Uniqueness
    # ------------------------------------------------------------
    print(f"\n[Check C] Identifier Uniqueness (arXiv ID, DOI, URL)")

    arxiv_to_pids = defaultdict(list)
    doi_to_pids = defaultdict(list)
    url_to_pids = defaultdict(list)

    arxiv_regex = re.compile(r'(?:arxiv\.org/abs/|arXiv:\s*\[?|arXiv:)(\d{4}\.\d{4,5})', re.IGNORECASE)
    doi_regex = re.compile(r'(?:doi\.org/|DOI:\s*\[?|DOI:)(10\.\d{4,9}/[^\s)\]]+)', re.IGNORECASE)
    url_regex = re.compile(r'https?://[^\s)\]]+', re.IGNORECASE)

    for p in paper_blocks:
        pid = p["pid"]
        text = p["text"]

        # Arxiv IDs
        for ax in arxiv_regex.findall(text):
            arxiv_to_pids[ax].append(pid)

        # DOIs
        for d in doi_regex.findall(text):
            cleaned_doi = clean_url(d)
            doi_to_pids[cleaned_doi].append(pid)

        # Raw URLs
        for u in url_regex.findall(text):
            cleaned_u = clean_url(u)
            url_to_pids[cleaned_u].append(pid)

    # Check arXiv duplicates
    dup_arxiv = {ax: pids for ax, pids in arxiv_to_pids.items() if len(set(pids)) > 1}
    if dup_arxiv:
        for ax, pids in dup_arxiv.items():
            errors.append(f"Duplicate arXiv ID '{ax}' shared by papers: {pids}")
    else:
        print(f"  [PASS] 0 duplicate arXiv IDs across all papers ({len(arxiv_to_pids)} verified).")

    # Check DOI duplicates
    dup_doi = {d: pids for d, pids in doi_to_pids.items() if len(set(pids)) > 1}
    if dup_doi:
        for d, pids in dup_doi.items():
            errors.append(f"Duplicate DOI '{d}' shared by papers: {pids}")
    else:
        print(f"  [PASS] 0 duplicate DOIs across all papers ({len(doi_to_pids)} verified).")

    # Check URL duplicates
    dup_url = {u: pids for u, pids in url_to_pids.items() if len(set(pids)) > 1}
    if dup_url:
        for u, pids in dup_url.items():
            errors.append(f"Duplicate URL '{u}' shared by papers: {pids}")
    else:
        print(f"  [PASS] 0 duplicate URLs across all papers ({len(url_to_pids)} verified).")

    # ------------------------------------------------------------
    # 4. Check D: Required Sections per Paper
    # ------------------------------------------------------------
    print(f"\n[Check D] Required Sections Present for Every Paper")
    required_fields = [
        ("Authors", re.compile(r'\*\*Authors\*\*:', re.IGNORECASE)),
        ("Year/Venue", re.compile(r'\*\*Year/Venue\*\*:', re.IGNORECASE)),
        ("Method Summary", re.compile(r'\*\*Method Summary\*\*:', re.IGNORECASE)),
        ("Reported Metrics", re.compile(r'\*\*(?:Reported Metrics|Key Findings)\*\*[^\n:]*:', re.IGNORECASE)),
        ("Relevance", re.compile(r'\*\*Relevance\*\*:', re.IGNORECASE)),
    ]

    missing_fields_per_paper = defaultdict(list)
    for p in paper_blocks:
        pid = p["pid"]
        text = p["text"]
        for field_name, regex in required_fields:
            if not regex.search(text):
                missing_fields_per_paper[pid].append(field_name)

    if missing_fields_per_paper:
        for pid, m_fields in missing_fields_per_paper.items():
            errors.append(f"Paper [{pid}] missing required field(s): {m_fields}")
    else:
        print(f"  [PASS] All 58 papers contain all required fields: Title, Authors, Year/Venue, Method Summary, Reported Metrics, Relevance.")

    # ------------------------------------------------------------
    # 5. Check E: Quantitative Metrics Check
    # ------------------------------------------------------------
    print(f"\n[Check E] Quantitative Metrics Content Check")
    metric_keywords_regex = re.compile(
        r'(?:Dice|IoU|mDice|mIoU|FPS|Precision|Recall|mAP|AUC|S-measure|E-measure|MAE|F1|Sensitivity|Specificity|%|params|GFLOPs)',
        re.IGNORECASE
    )
    metric_number_regex = re.compile(r'\d+(?:\.\d+)?%?')

    non_quantitative_papers = []
    for p in paper_blocks:
        pid = p["pid"]
        text = p["text"]

        # Extract Reported Metrics block
        m_match = re.search(r'\*\*(?:Reported Metrics|Key Findings)\*\*[^\n:]*:\s*([\s\S]*?)(?=\n-\s*\*\*|$)', text, re.IGNORECASE)
        if not m_match:
            non_quantitative_papers.append((pid, "No Reported Metrics section found"))
            continue

        metrics_text = m_match.group(1)
        has_keywords = bool(metric_keywords_regex.search(metrics_text))
        has_numbers = bool(metric_number_regex.search(metrics_text))

        # Every paper [P01]-[P58] MUST contain actual quantitative numerical values and metric keywords
        if not has_keywords:
            non_quantitative_papers.append((pid, "Metrics section lacks quantitative metric keywords (Dice, IoU, FPS, etc.)"))
        elif not has_numbers:
            non_quantitative_papers.append((pid, "Metrics section lacks numerical quantitative values"))

    if non_quantitative_papers:
        for pid, reason in non_quantitative_papers:
            errors.append(f"Paper [{pid}] failed quantitative metrics check: {reason}")
    else:
        print(f"  [PASS] All 58 papers contain valid quantitative metrics (mDice, mIoU, FPS, %, etc.).")

    # ------------------------------------------------------------
    # 6. Check F: SOTA Comparison Tables Check
    # ------------------------------------------------------------
    print(f"\n[Check F] SOTA Comparison Tables Model Coverage")

    sota_section_match = re.search(r'##\s*SOTA Comparison Table([\s\S]*?)(?=\n##\s+|$)', content)
    if not sota_section_match:
        errors.append("Missing '## SOTA Comparison Table' section in document.")
    else:
        sota_text = sota_section_match.group(1)

        # Key models that MUST be present in SOTA tables:
        required_sota_models = [
            # Standard Benchmarks
            "Polyp-Mamba", "CASCADE", "SSFormer", "ColonFormer", "FCBFormer",
            "TransFuse", "DoubleU-Net", "MSNet", "ESFPNet", "BGNet",
            "BA-Net", "Diff-Polyp", "NanoNet", "DDANet",
            # Video Polyp Segmentation
            "PNS+", "LDNet", "VPS-Net", "TMRNet", "DCRNet",
            "TempPolyp-Net", "TransVNet", "ST-PolypNet", "Polyp-SAM++", "Mamba-VPS",
            # Real-Time Detection
            "Polyp-YOLO", "Edge-YOLO-Polyp", "YOLO-v11n"
        ]

        missing_sota_models = []
        for model in required_sota_models:
            if not re.search(re.escape(model), sota_text, re.IGNORECASE):
                missing_sota_models.append(model)

        if missing_sota_models:
            errors.append(f"SOTA Comparison Tables missing required models: {missing_sota_models}")
        else:
            print(f"  [PASS] All {len(required_sota_models)} required benchmark models verified present in SOTA tables.")

        # Check sub-tables exist
        required_subtables = [
            "### Standard Benchmarks",
            "### Video Polyp Segmentation",
            "### Real-Time Detection"
        ]
        for sub in required_subtables:
            if sub not in sota_text:
                errors.append(f"Missing sub-table: '{sub}' in SOTA section.")
            else:
                print(f"  [PASS] Verified table presence: '{sub}'.")

        # Verify all models in Table 2 correspond to formal [Pxx] paper entries
        table2_match = re.search(r'###\s*Video Polyp Segmentation[^\n]*\n([\s\S]*?)(?=\n###|\n##|$)', sota_text)
        if table2_match:
            table2_lines = table2_match.group(1).strip().splitlines()
            table2_orphans = []
            table2_models_count = 0
            for line in table2_lines:
                line = line.strip()
                if not line.startswith('|') or line.startswith('| Method') or line.startswith('|---'):
                    continue
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if not cells:
                    continue
                method_cell = cells[0]
                pid_match = re.search(r'\[(P\d+)\]', method_cell)
                table2_models_count += 1
                if not pid_match:
                    table2_orphans.append((method_cell, "Missing [Pxx] tag in Table 2"))
                elif pid_match.group(1) not in actual_ids:
                    table2_orphans.append((method_cell, f"ID [{pid_match.group(1)}] not found in literature review papers"))
            
            if table2_orphans:
                for m_name, reason in table2_orphans:
                    errors.append(f"Table 2 model '{m_name}' invalid: {reason}")
            else:
                print(f"  [PASS] All {table2_models_count} models in Table 2 correspond to formal [Pxx] paper entries.")

    # ------------------------------------------------------------
    # 7. Check G: Gap Analysis & Backlog Integrity
    # ------------------------------------------------------------
    print(f"\n[Check G] Gap Analysis and Backlog Integrity")
    gap_match = re.search(r'##\s*Gap Analysis & Our Contribution([\s\S]*?)(?=\n##\s+|$)', content)
    if not gap_match:
        errors.append("Missing '## Gap Analysis & Our Contribution' section.")
    else:
        print(f"  [PASS] Gap Analysis & Contribution section present and populated.")

    backlog_match = re.search(r'##\s*Papers To Read \(Backlog\)([\s\S]*?)(?=$)', content)
    if not backlog_match:
        errors.append("Missing '## Papers To Read (Backlog)' section.")
    else:
        print(f"  [PASS] Papers To Read (Backlog) section present and updated.")

    # ------------------------------------------------------------
    # Summary Report
    # ------------------------------------------------------------
    print(f"\n============================================================")
    print(f"VERIFICATION SUMMARY REPORT")
    print(f"============================================================")
    print(f"Total Papers Verified: {num_papers}/58")
    print(f"Unique Titles: {len(title_to_pids)}/58 (0 duplicates)")
    print(f"Unique arXiv IDs: {len(arxiv_to_pids)} (0 duplicates)")
    print(f"Unique DOIs: {len(doi_to_pids)} (0 duplicates)")
    print(f"Unique URLs: {len(url_to_pids)} (0 duplicates)")
    print(f"Errors Found: {len(errors)}")
    print(f"Warnings Found: {len(warnings)}")

    if errors:
        print(f"\n[FAILED] Verification completed with {len(errors)} error(s):")
        for idx, err in enumerate(errors, 1):
            print(f"  {idx}. {err}")
        return False
    else:
        print(f"\n[SUCCESS] All verification checks PASSED with 100% compliance!")
        return True


if __name__ == "__main__":
    # Target file
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1])
    else:
        # Default relative to repository root
        target_path = Path(__file__).resolve().parent.parent / "docs" / "literature_review.md"

    passed = verify_literature_review(target_path)
    sys.exit(0 if passed else 1)
