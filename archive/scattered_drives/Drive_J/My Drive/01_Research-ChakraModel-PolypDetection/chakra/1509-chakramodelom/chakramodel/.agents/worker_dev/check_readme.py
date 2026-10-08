with open("README.md", "r", encoding="utf-8") as f:
    text = f.read()

forbidden = ["new sota", "state-of-the-art", "0.9852", "0.9412", "0.8650"]
found = False
for pattern in forbidden:
    count = text.lower().count(pattern.lower())
    print(f'Pattern "{pattern}": {count} occurrences')
    if count > 0:
        found = True

if not found:
    print("ALL CHECKS PASSED: Zero forbidden strings found in README.md!")
else:
    print("WARNING: Found forbidden strings!")
