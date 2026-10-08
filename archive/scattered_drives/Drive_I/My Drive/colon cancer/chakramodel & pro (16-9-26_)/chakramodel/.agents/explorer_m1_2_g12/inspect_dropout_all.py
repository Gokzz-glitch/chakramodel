import os

repo_root = r"M:\chakramodel"

for root, dirs, files in os.walk(repo_root):
    if any(x in root for x in [".venv", ".git", ".agents"]):
        continue
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                c = fp.read()
            if "enable_mc_dropout" in c or "mc_dropout" in c:
                rel = os.path.relpath(p, repo_root)
                print(f"=== {rel} ===")
                lines = c.splitlines()
                for i, l in enumerate(lines):
                    if any(k in l for k in ["def enable_mc_dropout", "self.drop(", "self.mc_dropout = True", "apply_dropout"]):
                        print(f"  {i+1}: {l.strip()}")
