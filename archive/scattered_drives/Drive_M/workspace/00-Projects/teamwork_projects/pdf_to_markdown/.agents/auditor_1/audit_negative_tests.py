import subprocess
import os
import re
import json

MD_PATH = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\Opus1.md"
with open(MD_PATH, "r", encoding="utf-8") as f:
    original_text = f.read()

test_cases = []

# Negative Test 1: Complete Page Removal (Page 15)
case1_text = re.sub(r'<!-- Page 15 -->.*?<!-- Page 16 -->', '<!-- Page 16 -->', original_text, flags=re.DOTALL)
test_cases.append(("Negative Test 1: Page 15 deletion", case1_text))

# Negative Test 2: Substantive Technical Sentence Removal (e.g. PraNet or Polyp-PVT)
match = re.search(r'([A-Za-z0-9\s,\-\(\)]*PraNet[^\n\r]+)', original_text)
if match:
    target_sentence = match.group(0)
    case2_text = original_text.replace(target_sentence, "")
    test_cases.append(("Negative Test 2: Specific PraNet sentence removal", case2_text))

# Negative Test 3: Number Mutation (alter numerical metrics, e.g. 0.795 or 94.2)
num_match = re.search(r'\b(9\d\.\d+)\b', original_text)
if num_match:
    target_num = num_match.group(1)
    case3_text = original_text.replace(target_num, "11.11", 1)
    test_cases.append(("Negative Test 3: Numeric metric mutation (replace " + target_num + " with 11.11)", case3_text))

# Negative Test 4: End-of-document truncation (remove last 200 lines)
lines = original_text.splitlines()
case4_text = "\n".join(lines[:-200])
test_cases.append(("Negative Test 4: Truncate last 200 lines", case4_text))

results = []

for name, mutated_text in test_cases:
    temp_md = f"temp_negative_{len(results)}.md"
    temp_rep = f"temp_report_{len(results)}.json"
    
    try:
        with open(temp_md, "w", encoding="utf-8") as f:
            f.write(mutated_text)
            
        cmd = [
            "python",
            r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown\verify_conversion.py",
            "--md", temp_md,
            "--report", temp_rep,
            "--offline"
        ]
        
        proc = subprocess.run(cmd, cwd=r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown", capture_output=True, text=True)
        
        # Read report if created
        rep_data = {}
        if os.path.exists(temp_rep):
            with open(temp_rep, "r", encoding="utf-8") as f:
                rep_data = json.load(f)
                
        omitted = rep_data.get("summary", {}).get("omitted_lines_count", 0)
        missing_ctx = rep_data.get("summary", {}).get("missing_context_count", 0)
        num_mismatches = rep_data.get("summary", {}).get("numeric_mismatches_count", 0)
        status = rep_data.get("summary", {}).get("overall_status", "UNKNOWN")
        
        passed_test = (proc.returncode == 1 and (omitted > 0 or missing_ctx > 0 or num_mismatches > 0) and status == "FAIL")
        
        results.append({
            "test_name": name,
            "returncode": proc.returncode,
            "overall_status": status,
            "omitted_lines": omitted,
            "missing_context": missing_ctx,
            "numeric_mismatches": num_mismatches,
            "detected_and_failed": passed_test,
            "stdout_snippet": proc.stdout.splitlines()[-3:] if proc.stdout else []
        })
    finally:
        if os.path.exists(temp_md):
            os.remove(temp_md)
        if os.path.exists(temp_rep):
            os.remove(temp_rep)

print(json.dumps(results, indent=2))
