import re, json

path = r'C:\Users\imgk3\.gemini\antigravity\brain\2a133901-cfc6-494d-9548-7bd3bef462e2\.system_generated\steps\63\content.md'
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

print("File size:", len(content), "bytes")

# Look for JSON blobs with chat messages
# Claude share pages embed content_blocks / text fields
patterns = [
    r'"content":"([^"]{30,1000})"',
    r'"text":"([^"]{30,1000})"',
    r'"message":"([^"]{30,1000})"',
]

for pat in patterns:
    matches = re.findall(pat, content)
    if matches:
        print(f"\nPattern {pat[:30]} -> {len(matches)} hits")
        for m in matches[:20]:
            cleaned = m.replace('\\n', '\n').replace('\\t', '  ')
            print("  ---")
            print(" ", cleaned[:400])

# Look for snapshot API data embedded
snap = re.findall(r'chat_snapshots[^{]{0,50}({.{100,5000}})', content, re.DOTALL)
print(f"\nSnapshot blobs: {len(snap)}")

# Look for any readable English sentences
sentences = re.findall(r'[A-Z][a-zA-Z0-9 ,.\-_%()]{40,300}[.!?]', content)
print(f"\nReadable sentences: {len(sentences)}")
for s in sentences[:30]:
    print(" ", s)
