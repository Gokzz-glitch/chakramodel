"""
test_adversarial_m3_ac1.py
Adversarial Verification Suite for Milestone 3, Acceptance Criterion 1 (AC1).
Authored independently by Challenger 1 (Milestone 3, Generation 9).

Validates:
1. Exhaustive case-insensitive zero-match scan for forbidden strings:
   ['SOTA', 'State of the Art', 'State-of-the-Art', '0.9852', '0.9412', '0.8650']
2. Honest metric presence: '0.8131' in both manuscript files.
3. Historical fabrications & tail-slice artifacts zero-match scan:
   ['0.9225', '0.9081', '0.8215', '0.7949', '0.7304']
4. Adversarial edge cases:
   - Hyphenation variations (en-dash, em-dash, soft hyphens, multiple hyphens)
   - Obfuscated whitespace (newlines, tabs, multiple spaces, non-breaking spaces, zero-width chars)
   - Acronym variations (S.O.T.A., s-o-t-a, case-insensitive word-boundary)
   - Numeric representations (percentages e.g. 98.52%, stripped decimals .9852, LaTeX math $0.9852$)
   - Hidden text in LaTeX comments (after %)
   - Hidden text in Markdown/HTML comments (<!-- ... -->)
"""

import re
import unicodedata
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

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

TARGET_FILES = {
    "tex": ROOT / "paper" / "main.tex",
    "md": ROOT / "docs" / "paper" / "ChakraModel_Final_Paper.md"
}

@pytest.fixture(scope="module")
def file_contents():
    contents = {}
    for key, path in TARGET_FILES.items():
        assert path.exists(), f"Target file does not exist: {path}"
        contents[key] = path.read_text(encoding="utf-8")
    return contents


# ==============================================================================
# 1. CORE FORBIDDEN STRINGS SCAN (Case-Insensitive Exact Substring)
# ==============================================================================

@pytest.mark.parametrize("file_key", ["tex", "md"])
@pytest.mark.parametrize("forbidden", FORBIDDEN_STRINGS)
def test_forbidden_strings_zero_count(file_contents, file_key, forbidden):
    content = file_contents[file_key]
    matches = list(re.finditer(re.escape(forbidden), content, re.IGNORECASE))
    assert len(matches) == 0, (
        f"Forbidden string '{forbidden}' found {len(matches)} time(s) in {TARGET_FILES[file_key].name}: "
        f"{[m.span() for m in matches]}"
    )


# ==============================================================================
# 2. HONEST METRIC PRESENCE ("0.8131")
# ==============================================================================

@pytest.mark.parametrize("file_key", ["tex", "md"])
def test_honest_metric_presence(file_contents, file_key):
    content = file_contents[file_key]
    matches = list(re.finditer(r"0\.8131", content))
    assert len(matches) >= 1, (
        f"Expected honest metric '0.8131' to be present in {TARGET_FILES[file_key].name}, but found 0 matches."
    )


# ==============================================================================
# 3. HISTORICAL FABRICATIONS & TAIL-SLICE ARTIFACTS SCAN
# ==============================================================================

@pytest.mark.parametrize("file_key", ["tex", "md"])
@pytest.mark.parametrize("artifact", HISTORICAL_FABRICATIONS)
def test_historical_fabrications_zero_count(file_contents, file_key, artifact):
    content = file_contents[file_key]
    matches = list(re.finditer(re.escape(artifact), content, re.IGNORECASE))
    assert len(matches) == 0, (
        f"Historical fabrication / tail-slice artifact '{artifact}' found {len(matches)} time(s) "
        f"in {TARGET_FILES[file_key].name}: {[m.span() for m in matches]}"
    )


# ==============================================================================
# 4. ADVERSARIAL EDGE CASE TESTS
# ==============================================================================

# 4a. Hyphenation and Flexible Whitespace variations for "State of the Art"
@pytest.mark.parametrize("file_key", ["tex", "md"])
def test_adversarial_state_of_the_art_variations(file_contents, file_key):
    """
    Checks for variations such as:
    - state-of-the-art
    - state--of--the--art
    - state - of - the - art
    - state\n- of the art
    - en-dash, em-dash, soft hyphens
    """
    content = file_contents[file_key]
    # Regex matching state + any whitespace/hyphen/dash + of + any ... + the + ... + art
    pattern = re.compile(
        r"\bstate[\s\-_–—\xad]*of[\s\-_–—\xad]*the[\s\-_–—\xad]*art\b",
        re.IGNORECASE
    )
    matches = list(pattern.finditer(content))
    assert len(matches) == 0, (
        f"Found {len(matches)} flexible-whitespace/hyphenation matches for 'state of the art' "
        f"in {TARGET_FILES[file_key].name}: {[m.group() for m in matches]}"
    )


# 4b. SOTA Acronym variations (S.O.T.A., s-o-t-a, word boundary sota)
@pytest.mark.parametrize("file_key", ["tex", "md"])
def test_adversarial_sota_acronym_variations(file_contents, file_key):
    """
    Checks for SOTA with periods (S.O.T.A.), hyphens (S-O-T-A), or isolated word \bSOTA\b
    """
    content = file_contents[file_key]
    # Match SOTA with optional dots or hyphens: \bS\.?O\.?T\.?A\.?\b
    pattern = re.compile(r"\bS[\.\-_–—]?O[\.\-_–—]?T[\.\-_–—]?A\.?\b", re.IGNORECASE)
    matches = list(pattern.finditer(content))
    assert len(matches) == 0, (
        f"Found {len(matches)} SOTA acronym variation matches in {TARGET_FILES[file_key].name}: "
        f"{[m.group() for m in matches]}"
    )


# 4c. Percentage forms of forbidden numbers (98.52%, 94.12%, 86.50%, 86.5%)
@pytest.mark.parametrize("file_key", ["tex", "md"])
@pytest.mark.parametrize("pct_str", [
    "98.52%", "94.12%", "86.50%", "86.5%",
    "92.25%", "90.81%", "82.15%", "79.49%", "73.04%"
])
def test_adversarial_percentage_variations(file_contents, file_key, pct_str):
    content = file_contents[file_key]
    # Strip % and match optional whitespace before % or LaTeX \%
    num_part = pct_str.rstrip("%")
    escaped_num = re.escape(num_part)
    pattern = re.compile(rf"{escaped_num}\s*(?:%|\\%)")
    matches = list(pattern.finditer(content))
    assert len(matches) == 0, (
        f"Found forbidden percentage form '{pct_str}' {len(matches)} time(s) "
        f"in {TARGET_FILES[file_key].name}: {[m.group() for m in matches]}"
    )


# 4d. Stripped decimal forms (.9852, .9412, .8650, etc.)
@pytest.mark.parametrize("file_key", ["tex", "md"])
@pytest.mark.parametrize("num", ["0.9852", "0.9412", "0.8650", "0.9225", "0.9081", "0.8215", "0.7949", "0.7304"])
def test_adversarial_stripped_decimals(file_contents, file_key, num):
    content = file_contents[file_key]
    stripped = num[1:]  # e.g. ".9852"
    # Ensure it's not preceded by a digit (which would make it a different number like 1.9852)
    pattern = re.compile(rf"(?<!\d){re.escape(stripped)}(?!\d)")
    matches = list(pattern.finditer(content))
    assert len(matches) == 0, (
        f"Found stripped decimal '{stripped}' {len(matches)} time(s) "
        f"in {TARGET_FILES[file_key].name}: {[m.group() for m in matches]}"
    )


# 4e. LaTeX Comments Scan (Hidden strings behind %)
def test_adversarial_latex_comments_scan(file_contents):
    """
    Extracts all comments from paper/main.tex and asserts no forbidden or obsolete strings exist in comments.
    """
    content = file_contents["tex"]
    lines = content.splitlines()
    comment_lines = []
    for idx, line in enumerate(lines, 1):
        # Match % not preceded by \ (which would be escaped \%)
        comment_match = re.search(r"(?<!\\)%(.*)$", line)
        if comment_match:
            comment_text = comment_match.group(1)
            comment_lines.append((idx, comment_text))

    all_forbidden = FORBIDDEN_STRINGS + HISTORICAL_FABRICATIONS
    found_in_comments = []
    for line_no, comment in comment_lines:
        for f in all_forbidden:
            if re.search(re.escape(f), comment, re.IGNORECASE):
                found_in_comments.append((line_no, f, comment.strip()))

    assert len(found_in_comments) == 0, (
        f"Forbidden strings found in LaTeX comments in paper/main.tex: {found_in_comments}"
    )


# 4f. Markdown Comments Scan (Hidden strings in <!-- ... -->)
def test_adversarial_markdown_comments_scan(file_contents):
    """
    Extracts all HTML/markdown comments from docs/paper/ChakraModel_Final_Paper.md
    and asserts no forbidden or obsolete strings exist inside comments.
    """
    content = file_contents["md"]
    comments = re.findall(r"<!--(.*?)-->", content, re.DOTALL)

    all_forbidden = FORBIDDEN_STRINGS + HISTORICAL_FABRICATIONS
    found_in_comments = []
    for c in comments:
        for f in all_forbidden:
            if re.search(re.escape(f), c, re.IGNORECASE):
                found_in_comments.append((f, c.strip()))

    assert len(found_in_comments) == 0, (
        f"Forbidden strings found in Markdown comments in docs/paper/ChakraModel_Final_Paper.md: {found_in_comments}"
    )


# 4g. Unicode Obfuscation / Zero-Width Character Injection Check
@pytest.mark.parametrize("file_key", ["tex", "md"])
def test_adversarial_unicode_and_zero_width_normalization(file_contents, file_key):
    """
    Normalizes text (removing zero-width spaces, joiners, formatting chars)
    and re-runs forbidden checks to ensure tokens were not hidden with invisible characters.
    """
    raw_content = file_contents[file_key]
    # Strip zero-width characters: \u200b (ZWSP), \u200c (ZWNJ), \u200d (ZWJ), \ufeff (BOM)
    cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff\xad]", "", raw_content)
    # Normalize unicode forms (NFKD, NFC)
    cleaned_nfkd = unicodedata.normalize("NFKD", cleaned)

    for forbidden in FORBIDDEN_STRINGS:
        matches = list(re.finditer(re.escape(forbidden), cleaned_nfkd, re.IGNORECASE))
        assert len(matches) == 0, (
            f"Hidden forbidden string '{forbidden}' discovered after Unicode normalization in {TARGET_FILES[file_key].name}!"
        )


# 4h. Semantic Alignment: Competent baseline framing check
@pytest.mark.parametrize("file_key", ["tex", "md"])
def test_competent_baseline_framing_check(file_contents, file_key):
    content = file_contents[file_key]
    assert "competent baseline" in content.lower(), (
        f"Manuscript {TARGET_FILES[file_key].name} must frame the work as a 'competent baseline'."
    )


# 4i. Adversarial check for unhedged superiority / boastful superlative claims
@pytest.mark.parametrize("file_key", ["tex", "md"])
def test_no_unhedged_superiority_claims(file_contents, file_key):
    content = file_contents[file_key]
    lines = content.splitlines()

    # Suspicious words that indicate boastful or unverified claims if not negated
    suspicious_patterns = [
        r"\boutperforms?\b",
        r"\bsuperior\b",
        r"\bsurpasses?\b",
        r"\bunprecedented\b",
        r"\bgroundbreaking\b",
        r"\bpeerless\b",
        r"\bunrivaled\b"
    ]

    for idx, line in enumerate(lines, 1):
        for pat in suspicious_patterns:
            if re.search(pat, line, re.IGNORECASE):
                # Must be explicitly negated or hedged (e.g. "not", "rather than", "does not attempt to")
                lower = line.lower()
                is_hedged = any(h in lower for h in [
                    "rather than", "does not attempt", "not attempt", "nor claim",
                    "neither", "not asserting", "does not claim", "relative to leading"
                ])
                assert is_hedged, (
                    f"Unhedged claim found on line {idx} of {TARGET_FILES[file_key].name}: {line.strip()}"
                )


# 4j. Adversarial LaTeX macro / math mode wrappers around numbers
@pytest.mark.parametrize("num", FORBIDDEN_STRINGS[3:] + HISTORICAL_FABRICATIONS)
def test_adversarial_latex_math_and_macros(file_contents, num):
    tex = file_contents["tex"]
    # Check for \textbf{num}, \mathbf{num}, $num$, {num}
    escaped = re.escape(num)
    patterns = [
        rf"\${escaped}\$",
        rf"\\textbf\{{{escaped}\}}",
        rf"\\mathbf\{{{escaped}\}}",
        rf"\\underline\{{{escaped}\}}",
        rf"\\textit\{{{escaped}\}}"
    ]
    for pat in patterns:
        m = re.findall(pat, tex)
        assert len(m) == 0, f"Forbidden number {num} found inside LaTeX macro {pat} in paper/main.tex"


# 4k. Transparent disclosure of ETIS-Larib catastrophic failure (0.0000)
@pytest.mark.parametrize("file_key", ["tex", "md"])
def test_etis_larib_catastrophic_disclosure(file_contents, file_key):
    content = file_contents[file_key]
    assert "0.0000" in content, (
        f"{TARGET_FILES[file_key].name} must disclose 0.0000 DSC on ETIS-Larib."
    )
    assert "ETIS-Larib" in content or "etis-larib" in content.lower(), (
        f"{TARGET_FILES[file_key].name} must explicitly name ETIS-Larib."
    )

