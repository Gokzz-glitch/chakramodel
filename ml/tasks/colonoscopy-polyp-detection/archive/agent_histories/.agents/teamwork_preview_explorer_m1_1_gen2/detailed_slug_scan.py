import re
import os
import json

known_users = [
    'gokulrocky',
    'gokulraj324',
    'debeshjha1',
    'balraj98',
    'ahaan2',
    'ivannikov2002',
    'tamimm91437',
    'nguyenvoquocduong'
]

pattern_known = re.compile(r'\b(' + '|'.join(known_users) + r')/([a-zA-Z0-9_\-]+)', re.I)
pattern_url = re.compile(r'kaggle\.com/datasets/([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)', re.I)
pattern_input = re.compile(r'/kaggle/input/(?:datasets|notebooks)/([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)', re.I)

results = {}

for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.git', '.venv', '__pycache__', 'teamwork_preview_explorer_m1_1_gen2']):
        continue
    for f in files:
        if f.endswith(('.py', '.ipynb', '.json', '.md', '.txt', '.pdf_extracted.json')):
            path = os.path.normpath(os.path.join(root, f))
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                    lines = fp.readlines()
                for line_idx, line in enumerate(lines, 1):
                    found_slugs_in_line = set()
                    for p in [pattern_known, pattern_url, pattern_input]:
                        for m in p.finditer(line):
                            if p == pattern_known:
                                slug = f"{m.group(1).lower()}/{m.group(2).lower()}"
                            else:
                                slug = m.group(1).lower()
                            found_slugs_in_line.add(slug)
                    for slug in found_slugs_in_line:
                        results.setdefault(slug, []).append({
                            'file': path,
                            'line': line_idx,
                            'content': line.strip()
                        })
            except Exception as e:
                pass

output_data = {}
for slug, occurrences in sorted(results.items()):
    files = sorted(set(x['file'] for x in occurrences))
    output_data[slug] = {
        'total_occurrences': len(occurrences),
        'file_count': len(files),
        'files': files,
        'samples': occurrences[:5]
    }

with open('.agents/teamwork_preview_explorer_m1_1_gen2/slug_results.json', 'w', encoding='utf-8') as out:
    json.dump(output_data, out, indent=2)

print(f"Extracted {len(output_data)} unique slugs to slug_results.json")
