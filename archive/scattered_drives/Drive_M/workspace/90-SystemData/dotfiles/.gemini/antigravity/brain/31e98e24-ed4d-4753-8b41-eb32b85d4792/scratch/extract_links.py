import re

with open(r'C:\Users\imgk3\.gemini\antigravity\brain\31e98e24-ed4d-4753-8b41-eb32b85d4792\.system_generated\steps\170\content.md', encoding='utf-8') as f:
    content = f.read()

# Find context around each drive link
links = re.finditer(r'https://drive\.google\.com/file/d/([^/]+)/view', content)
seen = set()
for match in links:
    file_id = match.group(1)
    if file_id in seen:
        continue
    seen.add(file_id)
    # Get surrounding text (100 chars before and after)
    start = max(0, match.start() - 200)
    end = min(len(content), match.end() + 100)
    context = content[start:end].replace('\n', ' ').strip()
    # Clean up HTML
    context = re.sub(r'<[^>]+>', ' ', context)
    context = re.sub(r'\s+', ' ', context).strip()
    print(f"ID: {file_id}")
    print(f"  Context: ...{context[-300:]}...")
    print()
