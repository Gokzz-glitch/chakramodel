import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

root = Path("m:/chakramodel")

def check_citation(filepath, query):
    p = root / filepath
    if not p.exists():
        print(f"{filepath} does not exist")
        return
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    matches = [(i+1, line) for i, line in enumerate(lines) if query.lower() in line.lower()]
    print(f"=== {filepath} ({len(matches)} matches for '{query}') ===")
    for lno, text in matches[:5]:
        print(f"  L{lno}: {text.strip()[:100]}")

print("--- Script Citations Verification ---")
check_citation("build_master_eval_notebook.py", "sun-seg")
check_citation("build_master_eval_notebook.py", "ldpolyp")
check_citation("build_master_eval_notebook.py", "polypdb")
check_citation("build_crossval_v5.py", "cvc-300")
check_citation("build_crossval_v5.py", "etis-larib")
check_citation("REPORT.txt", "cvc-clinicvideodb")
check_citation("REPORT.txt", "sun-seg")
check_citation("REPORT.txt", "ldpolypvideo")
check_citation("cross_dataset_report.md", "etis-larib")
