import os
from pathlib import Path

manifest_path = Path("M:/chakramodel/archive/MANIFEST.md")
content = manifest_path.read_text(encoding="utf-8")

parsed = []
for line in content.splitlines():
    line = line.strip()
    if line.startswith("|") and not line.startswith("|--") and not line.startswith("| Original"):
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) >= 2:
            orig = cols[0].replace("`", "")
            arch = cols[1].replace("`", "")
            if arch.startswith("archive/"):
                parsed.append((orig, arch))

print(f"Total manifest entries parsed: {len(parsed)}")

actual_files = set()
for p in Path("M:/chakramodel/archive").rglob("*"):
    if p.is_file() and p.name != "MANIFEST.md" and "__pycache__" not in p.parts:
        rel = p.relative_to(Path("M:/chakramodel")).as_posix()
        actual_files.add(rel)

manifest_files = set(arch for orig, arch in parsed)

print(f"Actual files on disk (excluding MANIFEST.md and pycache): {len(actual_files)}")
print(f"Manifest paths count: {len(manifest_files)}")

missing_on_disk = manifest_files - actual_files
unmanifested = actual_files - manifest_files

print(f"Missing on disk: {missing_on_disk}")
print(f"Unmanifested on disk: {unmanifested}")
