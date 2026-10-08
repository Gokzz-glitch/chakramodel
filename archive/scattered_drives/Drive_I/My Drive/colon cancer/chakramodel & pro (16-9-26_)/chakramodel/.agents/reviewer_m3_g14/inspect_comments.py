import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def analyze_file(filepath):
    print("=" * 80)
    print(f"File: {filepath}")
    if not os.path.exists(filepath):
        print("  [ERROR] File does not exist!")
        return
    size = os.path.getsize(filepath)
    print(f"  Size: {size} bytes")
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    print(f"  Total Lines: {len(lines)}")
    
    inline_comments = []
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            inline_comments.append((idx, stripped))
        elif "#" in line:
            parts = line.split("#", 1)
            inline_comments.append((idx, "# " + parts[1].strip()))
            
    print(f"  Found {len(inline_comments)} inline comment lines.")
    print("  First 25 inline comments:")
    for idx, c in inline_comments[:25]:
        print(f"    Line {idx:3d}: {c}")

analyze_file(r"M:\chakramodel\src\models\chakranet_segmenter.py")
analyze_file(r"M:\chakramodel\src\chakra_transformer\transformer_segmenter.py")
analyze_file(r"M:\chakramodel\src\models\pranet_resnet101.py")
