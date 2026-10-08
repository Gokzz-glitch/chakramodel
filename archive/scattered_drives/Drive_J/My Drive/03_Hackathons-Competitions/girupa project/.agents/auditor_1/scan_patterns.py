import re, glob, os

patterns = ["mock", "fake", "dummy", "sleep", "NotImplemented", "simulate", "hardcode"]
files = glob.glob(r"J:\My Drive\girupa project\*.py") + glob.glob(r"J:\My Drive\girupa project\public\*.js")

matches = 0
for f in files:
    with open(f, "r", encoding="utf-8") as fp:
        lines = fp.readlines()
    for idx, line in enumerate(lines, 1):
        for p in patterns:
            if re.search(r"\b" + p + r"\b", line, re.IGNORECASE):
                print(f"{os.path.basename(f)}:{idx}: [{p}] {line.strip()}")
                matches += 1

print(f"\nTotal suspicious matches found: {matches}")
