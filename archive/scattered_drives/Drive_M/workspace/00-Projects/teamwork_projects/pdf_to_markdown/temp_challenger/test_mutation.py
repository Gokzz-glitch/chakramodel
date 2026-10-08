import subprocess
import sys
import json
import os

def test_numerical_mutation():
    print("=== TEST: Numerical Mutation in verify_conversion.py ===")
    
    # Read original Opus1.md
    with open("Opus1.md", "r", encoding="utf-8") as f:
        content = f.read()

    # Find a specific unique metric to mutate
    # For example, "0.810" on Page 82, or "96.7%" on Page 2
    target_metric = "96.7%"
    mutated_metric = "99.9%"
    
    if target_metric not in content:
        print(f"Error: Target metric {target_metric} not found in Opus1.md")
        return

    mutated_content = content.replace(target_metric, mutated_metric, 1)
    
    temp_md_path = "temp_challenger/Opus1_mutated_num.md"
    temp_report_path = "temp_challenger/report_mutated_num.json"
    
    with open(temp_md_path, "w", encoding="utf-8") as f:
        f.write(mutated_content)
        
    print(f"Created mutated markdown: replaced '{target_metric}' with '{mutated_metric}'")
    
    # Run verify_conversion.py with mutated file
    cmd = [
        sys.executable,
        "verify_conversion.py",
        "--md", temp_md_path,
        "--report", temp_report_path,
        "--offline"
    ]
    
    print("Executing verify_conversion.py...")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    
    print("\n--- Return Code ---")
    print(f"Exit code: {res.returncode}")
    
    print("\n--- Standard Output (Tail) ---")
    stdout_lines = res.stdout.strip().splitlines()
    for line in stdout_lines[-20:]:
        print(line)
        
    print("\n--- Verification Report Inspection ---")
    if os.path.exists(temp_report_path):
        with open(temp_report_path, "r", encoding="utf-8") as rf:
            report_data = json.load(rf)
            
        print("Summary:")
        print(json.dumps(report_data.get("summary"), indent=2))
        print("Error codes:")
        print(json.dumps(report_data.get("error_codes"), indent=2))
        
        err_numeric = report_data.get("error_codes", {}).get("ERR_NUMERIC_MISMATCH", 0)
        overall_status = report_data.get("summary", {}).get("overall_status")
        numeric_count = report_data.get("summary", {}).get("numeric_mismatches_count", 0)
        
        print("\n=== CRITICAL AUDIT VERDICT ===")
        print(f"ERR_NUMERIC_MISMATCH flagged in error_codes: {err_numeric}")
        print(f"numeric_mismatches_count in summary: {numeric_count}")
        print(f"Overall status in summary: {overall_status}")
        print(f"Process exit code: {res.returncode}")
        
        if numeric_count > 0 and res.returncode == 0:
            print("\n[CRITICAL VULNERABILITY CONFIRMED]: verify_conversion.py flags ERR_NUMERIC_MISMATCH but STILL EXITS WITH CODE 0 (PASS)!")
        elif numeric_count > 0 and res.returncode == 1:
            print("\n[PASS]: Verification script successfully rejected numerical mutation with exit code 1.")
        else:
            print("\n[WARNING]: Mutation was not detected by numeric check.")

    else:
        print("Report was not generated!")

if __name__ == "__main__":
    test_numerical_mutation()
