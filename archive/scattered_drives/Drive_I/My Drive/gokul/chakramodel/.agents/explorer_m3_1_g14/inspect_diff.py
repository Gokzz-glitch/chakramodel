import os
from pathlib import Path

diff_path = Path(r"M:\chakramodel\.agents\reviewer_m1_2_g13\transformer_diff.txt")
src_path = Path(r"M:\chakramodel\src\chakra_transformer\transformer_segmenter.py")

print("Diff exists:", diff_path.exists())
print("Src exists:", src_path.exists())

# Read diff content
diff_lines = diff_path.read_text(encoding="utf-8").splitlines()

# Let's see diff header and hunks
print(f"Diff total lines: {len(diff_lines)}")
for i, line in enumerate(diff_lines[:15]):
    print(f"{i}: {line}")
