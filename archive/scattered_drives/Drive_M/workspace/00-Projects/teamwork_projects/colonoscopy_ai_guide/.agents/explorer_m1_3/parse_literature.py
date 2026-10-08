import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

with open(r'M:\chakramodelpro\polyp-detection-research\docs\literature_review.md', 'r', encoding='utf-8') as f:
    text = f.read()

paper_pattern = re.compile(r'^####\s*\[(P\d+)\]\s*(.+)$', re.MULTILINE)
matches = list(paper_pattern.finditer(text))

print(f"Total matched: {len(matches)}")
for i, m in enumerate(matches):
    pid = m.group(1)
    title = m.group(2).strip()
    start = m.start()
    end = matches[i+1].start() if i+1 < len(matches) else len(text)
    block = text[start:end]
    
    arxiv = re.findall(r'arxiv\.org/abs/([0-9\.]+)', block)
    github = re.findall(r'github\.com/([a-zA-Z0-9_\-\./]+)', block)
    doi = re.findall(r'doi\.org/([^\s\)\"\>]+)', block)
    
    print(f"[{pid}] {title}")
    if arxiv:
        print(f"  arXiv: https://arxiv.org/abs/{arxiv[0]}")
    if doi:
        print(f"  DOI: https://doi.org/{doi[0]}")
    if github:
        clean_gh = github[0].rstrip('.)')
        print(f"  GitHub: https://github.com/{clean_gh}")
