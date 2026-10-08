import json
import os
import sys
from pathlib import Path

nb_path = Path("notebooks/Kaggle_Final_Proof_Eval.ipynb")
fixes_path = Path("FIXES.md")

print("=== 1. CHECK FIXES.md ===")
with open(fixes_path, "r", encoding="utf-8") as f:
    fixes_content = f.read()

required_sections = [
    "Root Cause",
    "Exact Lines Changed",
    "Before/After",
    "Evidence from Weight Inspection",
    "Results After Fix"
]

missing_sections = []
for sec in required_sections:
    if sec.lower() not in fixes_content.lower():
        missing_sections.append(sec)

print("Required sections missing:", missing_sections)
print("Contains 2026-09-08:", "2026-09-08" in fixes_content)
print("Contains 'TBD':", "TBD" in fixes_content)

# Check placeholders
import re
placeholders = re.findall(r"\[[A-Z_\s]{3,}\]", fixes_content)
print("Bracketed placeholders like [TBD]:", placeholders)

print("\n=== 2. CHECK NOTEBOOK JSON ===")
with open(nb_path, "r", encoding="utf-8") as f:
    nb_data = json.load(f)

print(f"Total cells: {len(nb_data['cells'])}")
fix_cell_idx = None
for idx, cell in enumerate(nb_data['cells']):
    src = "".join(cell.get("source", []))
    if "CRITICAL FIX VERIFICATION" in src:
        fix_cell_idx = idx
        print(f"Found fix cell at index {idx}:")
        print("--- Source Preview ---")
        lines = src.splitlines()
        for l in lines[:10]:
            print("  ", l)
        print("  ...")
        for l in lines[-10:]:
            print("  ", l)
        print("--- Checks ---")
        print("Has '# CRITICAL FIX VERIFICATION | Timestamp: 2026-09-08':",
              "# CRITICAL FIX VERIFICATION | Timestamp: 2026-09-08" in src)
        print("Strips 'module.':", "replace(\"module.\", \"\")" in src or "replace('module.', '')" in src)
        print("Prints PASS/FAIL:", "PASS:" in src and "FAIL:" in src and "print(status)" in src)

print(f"\nFix cell index: {fix_cell_idx}")
