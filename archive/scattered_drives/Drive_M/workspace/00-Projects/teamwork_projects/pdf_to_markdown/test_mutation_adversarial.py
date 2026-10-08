"""
test_mutation_adversarial.py
Adversarial mutation test harness for Opus1.md and verify_conversion.py oracle.
"""

import os
import sys
import subprocess
import json
import re

PROJECT_ROOT = r"C:\Users\imgk3\teamwork_projects\pdf_to_markdown"
OPUS1_MD = os.path.join(PROJECT_ROOT, "Opus1.md")
VERIFY_SCRIPT = os.path.join(PROJECT_ROOT, "verify_conversion.py")

with open(OPUS1_MD, "r", encoding="utf-8") as f:
    original_md = f.read()

mutations = []

# Mutation 1: Delete a major section header
# e.g. "## 1. The Real-World Deployment Ceiling (Commercial CADe)"
h2_match = re.search(r'(##\s+[^\n\r]+)', original_md)
if h2_match:
    target_h2 = h2_match.group(1)
    m1_content = original_md.replace(target_h2, "", 1)
    mutations.append(("Mutation 1: Major Header Deletion", target_h2, m1_content))

# Mutation 2: Delete a technical paragraph
# e.g. paragraph about PraNet or HarDNet or CSM
para_match = re.search(r'(PraNet \(Fan et al\., MICCAI 2020\)[^\n\r]+\n[^\n\r]+\n[^\n\r]+)', original_md)
if para_match:
    target_para = para_match.group(1)
    m2_content = original_md.replace(target_para, "", 1)
    mutations.append(("Mutation 2: Technical Paragraph Deletion", target_para[:60] + "...", m2_content))

# Mutation 3: Delete an entire page content (Page 20)
page20_match = re.search(r'(<!-- Page 20 -->\n.*?\n)(?=<!-- Page 21 -->)', original_md, re.DOTALL)
if page20_match:
    target_page = page20_match.group(1)
    m3_content = original_md.replace(target_page, "<!-- Page 20 -->\n\n", 1)
    mutations.append(("Mutation 3: Page 20 Complete Content Deletion", "Page 20 body", m3_content))

# Mutation 4: Numeric alteration (change a specific metric like 93.4% or 0.795)
num_match = re.search(r'\b(8\d\.\d+%?)\b', original_md)
if num_match:
    target_num = num_match.group(1)
    m4_content = original_md.replace(target_num, "12.34%", 1)
    mutations.append(("Mutation 4: Numeric Metric Alteration", f"Change {target_num} to 12.34%", m4_content))

# Mutation 5: Heading hierarchy corruption (illegal jump from # to ####)
m5_content = "# Test Top Level\n\n#### Illegal Heading Jump Level 4\n\n" + original_md
mutations.append(("Mutation 5: Heading Hierarchy Illegal Jump (# -> ####)", "# -> ####", m5_content))

# Mutation 6: Subtle single-line deletion (a line without unique numbers)
subtle_line_match = re.search(r'\n([A-Z][a-z\s]{30,60}\.)\n', original_md)
if subtle_line_match:
    target_line = subtle_line_match.group(1)
    m6_content = original_md.replace("\n" + target_line + "\n", "\n", 1)
    mutations.append(("Mutation 6: Subtle Single Sentence Deletion", target_line, m6_content))

results = []

for name, target, mutated_text in mutations:
    temp_md = os.path.join(PROJECT_ROOT, f"temp_mutation_{len(results)}.md")
    temp_rep = os.path.join(PROJECT_ROOT, f"temp_report_{len(results)}.json")
    
    try:
        with open(temp_md, "w", encoding="utf-8") as f:
            f.write(mutated_text)
            
        cmd = [
            "python",
            VERIFY_SCRIPT,
            "--md", temp_md,
            "--report", temp_rep,
            "--offline"
        ]
        
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
        
        report_data = {}
        if os.path.exists(temp_rep):
            with open(temp_rep, "r", encoding="utf-8") as rf:
                report_data = json.load(rf)
                
        summary = report_data.get("summary", {})
        omitted = summary.get("omitted_lines_count", 0)
        missing_ctx = summary.get("missing_context_count", 0)
        num_mismatches = summary.get("numeric_mismatches_count", 0)
        overall_status = summary.get("overall_status", "UNKNOWN")
        error_codes = report_data.get("error_codes", {})
        
        # Did verify_conversion correctly flag and exit 1?
        correctly_flagged = (proc.returncode == 1 and overall_status == "FAIL")
        
        res = {
            "mutation_name": name,
            "target_description": target,
            "exit_code": proc.returncode,
            "overall_status": overall_status,
            "omitted_lines_count": omitted,
            "missing_context_count": missing_ctx,
            "numeric_mismatches_count": num_mismatches,
            "error_codes": error_codes,
            "correctly_flagged_and_exited_1": correctly_flagged,
            "stdout_summary": [l for l in proc.stdout.splitlines() if "Verification" in l or "Status:" in l or "Omitted" in l]
        }
        results.append(res)
        print(f"[{'PASS' if correctly_flagged else 'FAIL'}] {name}: Exit Code={proc.returncode}, Status={overall_status}, Omitted={omitted}, Mismatches={num_mismatches}")
    finally:
        if os.path.exists(temp_md):
            os.remove(temp_md)
        if os.path.exists(temp_rep):
            os.remove(temp_rep)

print("\n=== SUMMARY JSON ===")
print(json.dumps(results, indent=2))
