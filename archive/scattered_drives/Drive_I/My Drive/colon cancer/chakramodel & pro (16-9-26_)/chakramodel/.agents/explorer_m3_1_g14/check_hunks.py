import re
from pathlib import Path

diff_path = Path(r"M:\chakramodel\.agents\reviewer_m1_2_g13\transformer_diff.txt")
diff_lines = diff_path.read_text(encoding="utf-8").splitlines()

# Check @@ lines
hunk_headers = [line for line in diff_lines if line.startswith("@@")]
for h in hunk_headers:
    print(h)
