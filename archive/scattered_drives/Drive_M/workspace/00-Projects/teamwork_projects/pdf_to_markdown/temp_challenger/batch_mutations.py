import subprocess
import sys
import json
import os

def test_batch():
    with open("Opus1.md", "r", encoding="utf-8") as f:
        content = f.read()

    targets = [
        ("96.7%", "99.9%"),
        ("12.5%", "99.9%"),
        ("0.984", "0.111"),
        ("8,075", "1,234"),
        ("25 FPS", "99 FPS")
    ]
    
    print("=== BATCH TESTING METRIC MUTATIONS IN SENTENCES ===")
    for orig, mut in targets:
        if orig not in content:
            print(f"Skipping {orig}, not in Opus1.md")
            continue
        mut_content = content.replace(orig, mut, 1)
        temp_md = "temp_challenger/test_batch_mut.md"
        temp_rep = "temp_challenger/test_batch_rep.json"
        with open(temp_md, "w", encoding="utf-8") as f:
            f.write(mut_content)

        res = subprocess.run(
            [sys.executable, "verify_conversion.py", "--md", temp_md, "--report", temp_rep, "--offline"],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        with open(temp_rep, "r", encoding="utf-8") as rf:
            rep = json.load(rf)
            
        exit_code = res.returncode
        status = rep["summary"]["overall_status"]
        num_mismatches = rep["summary"]["numeric_mismatches_count"]
        omitted = rep["summary"]["omitted_lines_count"]
        
        print(f"Mutated '{orig}' -> '{mut}': ExitCode={exit_code}, OverallStatus={status}, NumMismatches={num_mismatches}, OmittedLines={omitted}")

if __name__ == "__main__":
    test_batch()
