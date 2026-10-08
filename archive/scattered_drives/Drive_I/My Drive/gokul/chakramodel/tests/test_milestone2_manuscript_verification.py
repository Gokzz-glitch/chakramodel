"""
Test suite for Milestone 2 (Gen 9) manuscript revisions:
Validates paper/main.tex and docs/paper/ChakraModel_Final_Paper.md.
"""

import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

@pytest.fixture
def tex_content():
    p = ROOT / "paper" / "main.tex"
    assert p.exists(), "paper/main.tex must exist"
    return p.read_text(encoding="utf-8")

@pytest.fixture
def md_content():
    p = ROOT / "docs" / "paper" / "ChakraModel_Final_Paper.md"
    assert p.exists(), "docs/paper/ChakraModel_Final_Paper.md must exist"
    return p.read_text(encoding="utf-8")

@pytest.mark.parametrize("forbidden", [
    "SOTA", "State of the Art", "State-of-the-Art",
    "0.9852", "0.9412", "0.8650"
])
def test_zero_matches_forbidden_strings_tex(tex_content, forbidden):
    matches = list(re.finditer(re.escape(forbidden), tex_content, re.IGNORECASE))
    assert len(matches) == 0, f"Found {len(matches)} matches of forbidden '{forbidden}' in paper/main.tex"

@pytest.mark.parametrize("forbidden", [
    "SOTA", "State of the Art", "State-of-the-Art",
    "0.9852", "0.9412", "0.8650"
])
def test_zero_matches_forbidden_strings_md(md_content, forbidden):
    matches = list(re.finditer(re.escape(forbidden), md_content, re.IGNORECASE))
    assert len(matches) == 0, f"Found {len(matches)} matches of forbidden '{forbidden}' in docs/paper/ChakraModel_Final_Paper.md"

@pytest.mark.parametrize("obsolete", [
    "0.9225", "0.9081", "0.8215", "0.7949", "0.7304"
])
def test_zero_matches_obsolete_strings_tex(tex_content, obsolete):
    matches = list(re.finditer(re.escape(obsolete), tex_content, re.IGNORECASE))
    assert len(matches) == 0, f"Found {len(matches)} matches of obsolete '{obsolete}' in paper/main.tex"

@pytest.mark.parametrize("obsolete", [
    "0.9225", "0.9081", "0.8215", "0.7949", "0.7304"
])
def test_zero_matches_obsolete_strings_md(md_content, obsolete):
    matches = list(re.finditer(re.escape(obsolete), md_content, re.IGNORECASE))
    assert len(matches) == 0, f"Found {len(matches)} matches of obsolete '{obsolete}' in docs/paper/ChakraModel_Final_Paper.md"

def test_presence_of_honest_metric_08131(tex_content, md_content):
    assert "0.8131" in tex_content, "0.8131 must be present in paper/main.tex"
    assert "0.8131" in md_content, "0.8131 must be present in docs/paper/ChakraModel_Final_Paper.md"

def test_competent_baseline_abstract_and_conclusion_tex(tex_content):
    abs_match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex_content, re.DOTALL)
    assert abs_match is not None, "\\begin{abstract} block not found in paper/main.tex"
    assert "competent baseline" in abs_match.group(1).lower(), "Abstract in paper/main.tex must contain 'competent baseline'"

    conc_match = re.search(r"\\section\{Conclusion\}(.*?)(?:\\end\{document\}|$)", tex_content, re.DOTALL)
    assert conc_match is not None, "\\section{Conclusion} block not found in paper/main.tex"
    assert "competent baseline" in conc_match.group(1).lower(), "Conclusion in paper/main.tex must contain 'competent baseline'"

def test_competent_baseline_abstract_and_conclusion_md(md_content):
    abs_match = re.search(r"## Abstract(.*?)(?:### 1\.1 Key Contributions|## 1\. Introduction)", md_content, re.DOTALL)
    assert abs_match is not None, "## Abstract section not found in docs/paper/ChakraModel_Final_Paper.md"
    assert "competent baseline" in abs_match.group(1).lower(), "Abstract in docs/paper/ChakraModel_Final_Paper.md must contain 'competent baseline'"

    conc_match = re.search(r"## 6\. Conclusion and Limitations(.*?)(?:## Reproducibility|## References|$)", md_content, re.DOTALL)
    assert conc_match is not None, "## 6. Conclusion and Limitations section not found in docs/paper/ChakraModel_Final_Paper.md"
    assert "competent baseline" in conc_match.group(1).lower(), "Conclusion in docs/paper/ChakraModel_Final_Paper.md must contain 'competent baseline'"

def test_literature_acknowledgment(tex_content, md_content):
    assert re.search(r"0\.90\+", tex_content) is not None, "paper/main.tex must acknowledge ~0.90+ Dice for leading models"
    assert re.search(r"0\.90\+", md_content) is not None, "docs/paper/ChakraModel_Final_Paper.md must acknowledge ~0.90+ Dice for leading models"

def test_latex_lifo_stack_validity(tex_content):
    tokens = re.findall(r"\\(begin|end)\{([a-zA-Z*]+)\}", tex_content)
    stack = []
    for tag_type, env_name in tokens:
        if tag_type == "begin":
            stack.append(env_name)
        else:
            assert len(stack) > 0, f"\\end{{{env_name}}} encountered with empty stack"
            popped = stack.pop()
            assert popped == env_name, f"Environment mismatch: \\begin{{{popped}}} closed by \\end{{{env_name}}}"
    assert len(stack) == 0, f"Unclosed environments: {stack}"
