"""
Adversarial Detection Test for Flaw 08:
Sign-flipped conformal formula in the inference path vs canonical formula.

Exit code:
  1 if src/models/chakranet_segmenter.py inlines the sign-flipped formula:
       score_pos = 1.0 - (prob_resized + variance)   [subtraction of variance]
       score_neg = prob_resized - variance
  0 if inference uses the canonical conformal formula:
       score_pos = (1.0 - prob) + variance          [addition of variance]
       score_neg = prob + variance
"""
import re
import sys
from pathlib import Path

def main():
    repo_root = Path(r"M:\chakramodel")
    seg_file = repo_root / "src" / "models" / "chakranet_segmenter.py"
    
    with open(seg_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Look for the buggy inlined formulas
    buggy_pos_patterns = [
        r"1\.0\s*-\s*\(\s*prob_resized\s*\+\s*variance\s*\)",
        r"score_pos\s*=\s*1\.0\s*-\s*\(\s*prob_resized\s*\+\s*variance\s*\)"
    ]
    buggy_neg_patterns = [
        r"score_neg\s*=\s*prob_resized\s*-\s*variance"
    ]

    has_buggy_pos = any(re.search(pat, content) for pat in buggy_pos_patterns)
    has_buggy_neg = any(re.search(pat, content) for pat in buggy_neg_patterns)

    if has_buggy_pos or has_buggy_neg:
        print("[FAIL] Flaw 08 detected: Sign-flipped conformal formula found in src/models/chakranet_segmenter.py:")
        if has_buggy_pos:
            print("  - score_pos = 1.0 - (prob_resized + variance)  <-- Variance is subtracted instead of added!")
        if has_buggy_neg:
            print("  - score_neg = prob_resized - variance          <-- Variance is subtracted instead of added!")
        print("  Canonical formula requires (1.0 - prob) + variance and prob + variance.")
        sys.exit(1)
    
    print("[PASS] Flaw 08 resolved: Inference conformal formula matches canonical calibration formula.")
    sys.exit(0)

if __name__ == "__main__":
    main()
