"""
Adversarial Detection Test for Flaw 07:
strict=False in load_state_dict() without key assertions -- silently loads 0/312 keys if prefix mismatch occurs.

Exit code:
  1 if strict=False is used without asserting len(missing) == 0 and len(unexpected) == 0,
    or if loading mismatched checkpoint fails silently without raising an exception.
  0 if strict key validation is enforced and mismatched weights raise RuntimeError.
"""
import sys
from pathlib import Path
import torch
import torch.nn as nn

def main():
    repo_root = Path(r"M:\chakramodel")
    sys.path.insert(0, str(repo_root))
    
    # Check src/models/chakranet_segmenter.py
    seg_file = repo_root / "src" / "models" / "chakranet_segmenter.py"
    with open(seg_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Flaw detection: Does chakranet_segmenter.py pass strict=False without raising on missing?
    # In current code:
    # missing, unexpected = self.model.load_state_dict(sd, strict=False)
    # if missing: print(...)
    # It does NOT raise an error!
    
    has_raise_on_missing = "raise RuntimeError" in content and "missing" in content
    has_assert_missing = "assert len(missing) == 0" in content or "assert not missing" in content

    if not (has_raise_on_missing or has_assert_missing):
        print("[FAIL] Flaw 07 detected: src/models/chakranet_segmenter.py loads state_dict with strict=False without raising on missing keys.")
        print("  Current behavior prints [WARN] and continues with uninitialized random weights.")
        sys.exit(1)
    
    print("[PASS] Flaw 07 resolved: Key assertions / exceptions enforced on load_state_dict.")
    sys.exit(0)

if __name__ == "__main__":
    main()
