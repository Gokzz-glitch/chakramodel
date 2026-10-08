import os
from collections import defaultdict

repo_root = r"M:\chakramodel"
by_dir = defaultdict(list)

for root, dirs, files in os.walk(repo_root):
    if any(x in root for x in [".venv", ".git", ".agents"]):
        continue
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, repo_root)
            top_dir = rel.split(os.sep)[0]
            with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                lines = fp.readlines()
            for i, line in enumerate(lines):
                if "torch.load(" in line:
                    block = "".join(lines[i:min(len(lines), i+3)])
                    has_wo_true = "weights_only=True" in block or "weights_only = True" in block
                    if not has_wo_true:
                        by_dir[top_dir].append((rel, i + 1, line.strip()))

for d, items in sorted(by_dir.items()):
    print(f"{d}: {len(items)} unguarded torch.load calls")
    for r, l, code in items:
        print(f"  {r}:{l} -> {code}")

total = sum(len(v) for v in by_dir.values())
print(f"Total across all top dirs: {total}")
