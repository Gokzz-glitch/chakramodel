import os
import sys

root_py = sorted([f for f in os.listdir('.') if f.endswith('.py') and os.path.isfile(f)])
print(f"Total root .py files: {len(root_py)}")

out_path = os.path.join(os.path.dirname(__file__), "root_files_analysis.txt")
with open(out_path, "w", encoding="utf-8") as out:
    out.write(f"Total root .py files: {len(root_py)}\n")
    for f in root_py:
        doc = ""
        with open(f, "r", encoding="utf-8", errors="ignore") as fp:
            lines = [fp.readline().strip() for _ in range(15)]
        for line in lines:
            if line.startswith(('"""', "'''", "#")):
                cleaned = line.strip("\"'# ")
                if len(cleaned) > 3:
                    doc = cleaned
                    break
        if not doc:
            doc = "Script utility / root execution script"
        out.write(f"{f} ::: {doc}\n")
print("Done writing root_files_analysis.txt")
