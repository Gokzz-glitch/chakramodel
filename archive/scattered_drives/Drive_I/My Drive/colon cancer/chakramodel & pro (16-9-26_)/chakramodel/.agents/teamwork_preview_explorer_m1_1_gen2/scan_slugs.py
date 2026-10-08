import re
import os
import glob

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

# Pattern for known users
pattern_known = re.compile(r'\b(' + '|'.join(known_users) + r')/([a-zA-Z0-9_\-]+)', re.I)

# Pattern for generic kaggle.com/datasets/owner/slug
pattern_url = re.compile(r'kaggle\.com/datasets/([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)', re.I)

# Pattern for /kaggle/input/datasets/owner/slug or /kaggle/input/notebooks/owner/slug
pattern_input = re.compile(r'/kaggle/input/(?:datasets|notebooks)/([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)', re.I)

results = {}

for root, dirs, files in os.walk('.'):
    if '.git' in root or '.venv' in root or '__pycache__' in root:
        continue
    for f in files:
        if f.endswith(('.py', '.ipynb', '.json', '.md', '.txt', '.pdf_extracted.json')):
            path = os.path.normpath(os.path.join(root, f))
            # skip our own agent folder
            if 'teamwork_preview_explorer_m1_1_gen2' in path:
                continue
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                
                # Check known
                for m in pattern_known.finditer(content):
                    slug = f"{m.group(1).lower()}/{m.group(2).lower()}"
                    results.setdefault(slug, []).append((path, m.start()))
                
                # Check url
                for m in pattern_url.finditer(content):
                    slug = m.group(1).lower()
                    results.setdefault(slug, []).append((path, m.start()))
                    
                # Check input
                for m in pattern_input.finditer(content):
                    slug = m.group(1).lower()
                    results.setdefault(slug, []).append((path, m.start()))
            except Exception as e:
                pass

print(f"Total unique slugs found: {len(results)}")
for slug, occurrences in sorted(results.items()):
    files = sorted(set(p for p, pos in occurrences))
    print(f"\nSlug: {slug} (Total references: {len(occurrences)}, Across {len(files)} files)")
    for f in files[:8]:
        print(f"   - {f}")
    if len(files) > 8:
        print(f"   - ... and {len(files) - 8} more files")
