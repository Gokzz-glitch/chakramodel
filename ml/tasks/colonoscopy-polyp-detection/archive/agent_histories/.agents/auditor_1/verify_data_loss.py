import subprocess
from pathlib import Path

# Check diff from 5 commits ago to HEAD
out = subprocess.check_output(["git", "diff", "--name-status", "HEAD~5", "HEAD"], text=True)
deletions = []
for line in out.splitlines():
    if line.startswith("D\t"):
        deletions.append(line.split("\t")[1])

print(f"Total net deleted files between HEAD~5 and HEAD: {len(deletions)}")
for d in deletions:
    print(f"Deleted: {d}")
