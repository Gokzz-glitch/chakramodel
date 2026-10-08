import os
import sys

repo_root = r"M:\chakramodel"
loads = []

for root, dirs, files in os.walk(repo_root):
    # Exclude .venv, .git, and current agent directory
    if any(x in root for x in [".venv", ".git", ".agents"]):
        continue
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, repo_root)
            with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                lines = fp.readlines()
            for i, line in enumerate(lines):
                if "torch.load(" in line:
                    block = "".join(lines[i:min(len(lines), i+3)])
                    has_wo_true = "weights_only=True" in block or "weights_only = True" in block
                    has_wo_false = "weights_only=False" in block or "weights_only = False" in block
                    loads.append({
                        "rel": rel,
                        "line_no": i + 1,
                        "code": line.strip(),
                        "block": block.strip().replace("\n", " "),
                        "weights_only_true": has_wo_true,
                        "weights_only_false": has_wo_false
                    })

print(f"Total torch.load found (excluding .venv, .git, .agents): {len(loads)}")
unguarded = [x for x in loads if not x["weights_only_true"]]
print(f"Total unguarded (without weights_only=True): {len(unguarded)}")

for idx, u in enumerate(unguarded, 1):
    print(f"{idx}. {u['rel']}:{u['line_no']} -> {u['code']}")
