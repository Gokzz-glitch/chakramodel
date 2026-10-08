import re
import sys

files = ['paper/main.tex', 'docs/paper/ChakraModel_Final_Paper.md']
forbidden = ['SOTA', 'State of the Art', 'State-of-the-Art', '0.9852', '0.9412', '0.8650']
obsolete = ['0.9225', '0.9081', '0.8215', '0.7949', '0.7304']

for f_path in files:
    print(f"=== Scanning {f_path} ===")
    with open(f_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for term in forbidden:
        matches = list(re.finditer(re.escape(term), content, re.IGNORECASE))
        if matches:
            print(f"  FORBIDDEN MATCH: '{term}' (count: {len(matches)})")
            for m in matches[:5]:
                start = max(0, m.start() - 30)
                end = min(len(content), m.end() + 30)
                print(f"    snippet: ...{content[start:end]!r}...")

    for term in obsolete:
        matches = list(re.finditer(re.escape(term), content, re.IGNORECASE))
        if matches:
            print(f"  OBSOLETE MATCH: '{term}' (count: {len(matches)})")
            for m in matches[:5]:
                start = max(0, m.start() - 30)
                end = min(len(content), m.end() + 30)
                print(f"    snippet: ...{content[start:end]!r}...")

    has_8131 = '0.8131' in content
    print(f"  Contains '0.8131': {has_8131}")
    
    c_base = list(re.finditer(r'competent baseline', content, re.IGNORECASE))
    print(f"  'competent baseline' count: {len(c_base)}")
