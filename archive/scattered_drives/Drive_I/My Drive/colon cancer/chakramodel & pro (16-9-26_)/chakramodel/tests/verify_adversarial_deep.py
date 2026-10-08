"""
Deep Adversarial Verification Scanner for Milestone 3, AC1
Authored by Challenger 1 (Milestone 3, Generation 9).
"""

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEX_PATH = ROOT / "paper" / "main.tex"
MD_PATH = ROOT / "docs" / "paper" / "ChakraModel_Final_Paper.md"

FORBIDDEN_STRINGS = [
    "SOTA",
    "State of the Art",
    "State-of-the-Art",
    "0.9852",
    "0.9412",
    "0.8650"
]

HISTORICAL_FABRICATIONS = [
    "0.9225",
    "0.9081",
    "0.8215",
    "0.7949",
    "0.7304"
]

HONEST_METRICS = [
    "0.8131"
]


def scan_file(filepath: Path):
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    results = {
        "file": str(filepath.relative_to(ROOT)),
        "line_count": len(lines),
        "char_count": len(text),
        "forbidden_matches": {},
        "historical_matches": {},
        "honest_matches": {},
        "edge_cases": {},
        "comments_analysis": {}
    }

    # 1. Forbidden Strings (Case-Insensitive Exact Substring)
    for forbidden in FORBIDDEN_STRINGS:
        matches = []
        pattern = re.compile(re.escape(forbidden), re.IGNORECASE)
        for idx, line in enumerate(lines, 1):
            for m in pattern.finditer(line):
                matches.append({
                    "line": idx,
                    "span": m.span(),
                    "matched_text": m.group(),
                    "line_snippet": line.strip()
                })
        results["forbidden_matches"][forbidden] = {
            "count": len(matches),
            "matches": matches
        }

    # 2. Historical Fabrications & Tail-Slice Artifacts
    for artifact in HISTORICAL_FABRICATIONS:
        matches = []
        pattern = re.compile(re.escape(artifact), re.IGNORECASE)
        for idx, line in enumerate(lines, 1):
            for m in pattern.finditer(line):
                matches.append({
                    "line": idx,
                    "span": m.span(),
                    "matched_text": m.group(),
                    "line_snippet": line.strip()
                })
        results["historical_matches"][artifact] = {
            "count": len(matches),
            "matches": matches
        }

    # 3. Honest Metric Presence
    for honest in HONEST_METRICS:
        matches = []
        pattern = re.compile(re.escape(honest))
        for idx, line in enumerate(lines, 1):
            for m in pattern.finditer(line):
                matches.append({
                    "line": idx,
                    "span": m.span(),
                    "matched_text": m.group(),
                    "line_snippet": line.strip()
                })
        results["honest_matches"][honest] = {
            "count": len(matches),
            "matches": matches
        }

    # 4. Adversarial Edge Cases
    # 4a. Flexible whitespace / hyphens / linebreaks for "State of the Art"
    flex_sota_pattern = re.compile(r"\bstate[\s\-_–—\xad]*of[\s\-_–—\xad]*the[\s\-_–—\xad]*art\b", re.IGNORECASE)
    flex_sota_matches = []
    for m in flex_sota_pattern.finditer(text):
        flex_sota_matches.append({
            "matched_text": m.group(),
            "span": m.span()
        })
    results["edge_cases"]["state_of_the_art_flexible"] = {
        "count": len(flex_sota_matches),
        "matches": flex_sota_matches
    }

    # 4b. Acronym variations: S.O.T.A., s-o-t-a, standalone \bSOTA\b
    acronym_pattern = re.compile(r"\bS[\.\-_–—]?O[\.\-_–—]?T[\.\-_–—]?A\.?\b", re.IGNORECASE)
    acronym_matches = []
    for m in acronym_pattern.finditer(text):
        acronym_matches.append({
            "matched_text": m.group(),
            "span": m.span()
        })
    results["edge_cases"]["sota_acronym_variations"] = {
        "count": len(acronym_matches),
        "matches": acronym_matches
    }

    # 4c. Arbitrary substring search for 'sota'
    sota_sub_matches = [m.span() for m in re.finditer(r"sota", text, re.IGNORECASE)]
    results["edge_cases"]["sota_arbitrary_substring"] = {
        "count": len(sota_sub_matches),
        "spans": sota_sub_matches
    }

    # 4d. Percentage variations
    all_numeric_targets = FORBIDDEN_STRINGS[3:] + HISTORICAL_FABRICATIONS
    pct_matches = []
    for num in all_numeric_targets:
        pct_val = f"{float(num)*100:.2f}"
        pct_alt = f"{float(num)*100:.1f}"
        for p in [pct_val, pct_alt]:
            escaped = re.escape(p)
            for idx, line in enumerate(lines, 1):
                for m in re.finditer(rf"{escaped}\s*(?:%|\\%)", line):
                    pct_matches.append({
                        "line": idx,
                        "matched": m.group(),
                        "target_num": num
                    })
    results["edge_cases"]["percentage_variations"] = {
        "count": len(pct_matches),
        "matches": pct_matches
    }

    # 4e. Stripped decimal variations (.9852, etc.)
    stripped_matches = []
    for num in all_numeric_targets:
        stripped = num[1:]  # .9852
        for idx, line in enumerate(lines, 1):
            for m in re.finditer(rf"(?<!\d){re.escape(stripped)}(?!\d)", line):
                stripped_matches.append({
                    "line": idx,
                    "matched": m.group(),
                    "target_num": num
                })
    results["edge_cases"]["stripped_decimal_variations"] = {
        "count": len(stripped_matches),
        "matches": stripped_matches
    }

    # 4f. Unicode / Zero-width obfuscation
    cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff\xad]", "", text)
    cleaned_nfkd = unicodedata.normalize("NFKD", cleaned)
    unicode_hidden_matches = []
    for f in FORBIDDEN_STRINGS:
        m_list = list(re.finditer(re.escape(f), cleaned_nfkd, re.IGNORECASE))
        if m_list:
            unicode_hidden_matches.append({
                "forbidden": f,
                "count": len(m_list)
            })
    results["edge_cases"]["unicode_hidden_matches"] = {
        "count": len(unicode_hidden_matches),
        "matches": unicode_hidden_matches
    }

    # 5. Comments Scan
    if filepath.suffix == ".tex":
        # Check LaTeX comments
        tex_comment_matches = []
        for idx, line in enumerate(lines, 1):
            cm = re.search(r"(?<!\\)%(.*)$", line)
            if cm:
                c_text = cm.group(1)
                for target in FORBIDDEN_STRINGS + HISTORICAL_FABRICATIONS:
                    if re.search(re.escape(target), c_text, re.IGNORECASE):
                        tex_comment_matches.append({
                            "line": idx,
                            "target": target,
                            "comment_snippet": c_text.strip()
                        })
        results["comments_analysis"] = {
            "type": "latex",
            "matches_found": len(tex_comment_matches),
            "details": tex_comment_matches
        }
    else:
        # Check Markdown/HTML comments
        md_comment_matches = []
        for cm in re.finditer(r"<!--(.*?)-->", text, re.DOTALL):
            c_text = cm.group(1)
            for target in FORBIDDEN_STRINGS + HISTORICAL_FABRICATIONS:
                if re.search(re.escape(target), c_text, re.IGNORECASE):
                    md_comment_matches.append({
                        "target": target,
                        "comment_snippet": c_text.strip()
                    })
        results["comments_analysis"] = {
            "type": "markdown",
            "matches_found": len(md_comment_matches),
            "details": md_comment_matches
        }

    # Context of 'state' occurrences
    state_contexts = []
    for idx, line in enumerate(lines, 1):
        for m in re.finditer(r"\bstate\w*\b", line, re.IGNORECASE):
            state_contexts.append({
                "line": idx,
                "word": m.group(),
                "snippet": line.strip()
            })
    results["state_words"] = {
        "count": len(state_contexts),
        "occurrences": state_contexts
    }

    # Narrative sanity check
    results["competent_baseline_count"] = len(re.findall(r"competent\s+baseline", text, re.IGNORECASE))

    return results


def main():
    tex_res = scan_file(TEX_PATH)
    md_res = scan_file(MD_PATH)

    output = {
        "paper/main.tex": tex_res,
        "docs/paper/ChakraModel_Final_Paper.md": md_res
    }

    report_path = ROOT / "tests" / "adversarial_deep_scan_output.json"
    report_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Adversarial scan completed successfully. Report written to {report_path}")

    # Summary print
    for k, res in output.items():
        print(f"\n==========================================")
        print(f"Summary for: {k}")
        print(f"Lines: {res['line_count']}, Chars: {res['char_count']}")
        print(f"Forbidden Matches Total: {sum(v['count'] for v in res['forbidden_matches'].values())}")
        print(f"Historical Matches Total: {sum(v['count'] for v in res['historical_matches'].values())}")
        print(f"Honest '0.8131' Count: {res['honest_matches']['0.8131']['count']}")
        print(f"Flexible State-of-the-Art Count: {res['edge_cases']['state_of_the_art_flexible']['count']}")
        print(f"SOTA Acronym Count: {res['edge_cases']['sota_acronym_variations']['count']}")
        print(f"SOTA Arbitrary Substring Count: {res['edge_cases']['sota_arbitrary_substring']['count']}")
        print(f"Percentage Variations Count: {res['edge_cases']['percentage_variations']['count']}")
        print(f"Stripped Decimals Count: {res['edge_cases']['stripped_decimal_variations']['count']}")
        print(f"Comments Matches: {res['comments_analysis']['matches_found']}")
        print(f"'competent baseline' mentions: {res['competent_baseline_count']}")
        print(f"'state*' words: {res['state_words']['count']}")
        for sw in res['state_words']['occurrences']:
            safe_snip = sw['snippet'][:80].encode('ascii', errors='replace').decode('ascii')
            print(f"   Line {sw['line']}: {sw['word']} in: {safe_snip}")


if __name__ == "__main__":
    main()
