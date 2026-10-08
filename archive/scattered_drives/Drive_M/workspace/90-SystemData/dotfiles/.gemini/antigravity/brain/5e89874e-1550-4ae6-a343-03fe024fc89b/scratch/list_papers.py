import re

with open('m:/chakramodelpro/polyp-detection-research/docs/literature_review.md', 'r', encoding='utf-8') as f:
    text = f.read()

matches = re.findall(r'(### \[P\d+\].*?)(?=\n### \[P|\Z)', text, re.DOTALL)
print(f"Total papers found: {len(matches)}")
for m in matches[:15]:
    header = m.strip().split('\n')[0]
    print(header)
