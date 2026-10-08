import os
import re
from pathlib import Path

src_dir = Path("M:/chakramodel/src")
patterns = [
    (r"return\s+0\.\d+", "Hardcoded float return"),
    (r"return\s+['\"]PASS['\"]", "Hardcoded PASS return"),
    (r"['\"]dice['\"]\s*:\s*0\.\d+", "Hardcoded dice literal"),
    (r"return\s+\{\s*['\"]dice['\"]", "Hardcoded dice dictionary return"),
    (r"def\s+\w+\([^)]*\):\s*(?:pass|\.\.\.)\s*$", "Stub function with pass/..."),
    (r"raise\s+NotImplementedError", "NotImplementedError placeholder")
]

findings = []
for p in src_dir.rglob("*.py"):
    content = p.read_text(encoding="utf-8", errors="ignore")
    for pat, desc in patterns:
        for m in re.finditer(pat, content, re.MULTILINE):
            line_no = content[:m.start()].count("\n") + 1
            matched_text = m.group(0).strip()
            findings.append((str(p.as_posix()), line_no, desc, matched_text))

print(f"Total potential hardcoding matches in src/: {len(findings)}")
for path, line, desc, match in findings:
    print(f"[{desc}] {path}:{line} -> {match}")
