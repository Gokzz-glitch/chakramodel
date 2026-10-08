import os
import re
from pathlib import Path

root = Path(r"m:\chakramodel")
skip_dirs = {'.git', '.agents', 'New folder', 'venv', '.venv', '__pycache__', '.ipynb_checkpoints'}

findings = []
# Match actual paths, ignoring regex escape artifacts like \n, \t, \s, \d
patterns = [
    (re.compile(r'[a-zA-Z]:\\(?!n|t|s|d|r|b|f|v|0)[a-zA-Z0-9_-]+'), 'Windows drive path'),
    (re.compile(r'/content/drive/MyDrive/[a-zA-Z0-9_/-]+'), 'Colab MyDrive path'),
    (re.compile(r'torch\.cuda\.is_available\s*=\s*lambda'), 'CUDA mock'),
    (re.compile(r'torch\.device\([\'"]cuda[\'"]\)'), 'Forced CUDA'),
    (re.compile(r'/kaggle/input/[a-zA-Z0-9_/-]+'), 'Kaggle input path'),
    (re.compile(r'/kaggle/working/[a-zA-Z0-9_/-]+'), 'Kaggle working path')
]

for p in root.rglob('*'):
    if any(part in skip_dirs for part in p.parts):
        continue
    if p.suffix in ['.py', '.ipynb']:
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
            for pat, desc in patterns:
                for m in pat.finditer(text):
                    findings.append((str(p.relative_to(root)), desc, m.group(0)))
        except Exception as e:
            pass

print(f"Total repository findings (excluding virtualenvs & agents): {len(findings)}")
by_file = {}
for f, desc, val in findings:
    by_file.setdefault(f, set()).add((desc, val))

for f, issues in sorted(by_file.items()):
    print(f"\n=== {f} ===")
    for desc, val in sorted(issues):
        print(f"  [{desc}] {val}")
