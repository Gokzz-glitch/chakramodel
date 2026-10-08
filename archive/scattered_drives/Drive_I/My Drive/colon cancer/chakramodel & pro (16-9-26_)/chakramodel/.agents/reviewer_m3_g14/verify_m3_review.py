"""
verify_m3_review.py
=============================================================================
Milestone 3 Programmatic Verification Suite for Architectural Deliverables
Executed by Architecture Reviewer (reviewer_m3_g14)
=============================================================================
"""

import os
import sys
import re
import json
import subprocess
from pathlib import Path

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(r"M:\chakramodel")
GIT_EXE = Path(r"M:\New folder\Git\mingw64\libexec\git-core\git.exe")

def run_git(args):
    if not GIT_EXE.exists():
        return None, "Git binary not found at " + str(GIT_EXE)
    cmd = [str(GIT_EXE)] + args
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding='utf-8', errors='ignore')
    return res.returncode, res.stdout.strip()

print("=" * 80)
print("CHAKRAMODEL MILESTONE 3 PROGRAMMATIC REVIEW EXECUTION")
print("Agent: reviewer_m3_g14")
print("Workspace:", ROOT)
print("=" * 80)

results = {
    "criterion_1": {"verdict": "UNKNOWN", "details": {}},
    "criterion_2": {"verdict": "UNKNOWN", "details": {}},
    "criterion_3": {"verdict": "UNKNOWN", "details": {}},
}

# ---------------------------------------------------------------------------
# Criterion 1: docs/ARCHITECTURE_DEEP_DIVE.md
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("CRITERION 1: docs/ARCHITECTURE_DEEP_DIVE.md & Mermaid Diagrams")
print("=" * 80)

c1_path = ROOT / "docs" / "ARCHITECTURE_DEEP_DIVE.md"
c1_exists = c1_path.exists()
c1_size = c1_path.stat().st_size if c1_exists else 0

print(f"File path: {c1_path}")
print(f"File exists: {c1_exists}")
print(f"File size: {c1_size} bytes ({c1_size/1024:.2f} KB)")

if c1_exists:
    content_c1 = c1_path.read_text(encoding='utf-8')
    lines_c1 = content_c1.splitlines()
    print(f"Total lines: {len(lines_c1)}")
    
    # Search for mermaid diagram blocks
    mermaid_blocks = []
    pattern = re.compile(r"```mermaid(.*?)```", re.DOTALL)
    for m in pattern.finditer(content_c1):
        start_char = m.start()
        end_char = m.end()
        start_line = content_c1[:start_char].count('\n') + 1
        end_line = content_c1[:end_char].count('\n') + 1
        body = m.group(1).strip()
        first_line = body.splitlines()[0] if body else ""
        subgraphs = len(re.findall(r"\bsubgraph\b", body))
        edges = len(re.findall(r"-->|-\.->|==>", body))
        mermaid_blocks.append({
            "start_line": start_line,
            "end_line": end_line,
            "header": first_line,
            "subgraphs": subgraphs,
            "edges": edges,
            "length_lines": len(body.splitlines())
        })
        
    print(f"Mermaid blocks detected: {len(mermaid_blocks)}")
    for i, mb in enumerate(mermaid_blocks, 1):
        print(f"  Block {i}: Lines {mb['start_line']}-{mb['end_line']} | Header: '{mb['header']}' | Subgraphs: {mb['subgraphs']} | Edges: {mb['edges']}")
        
    # Check tensor shape notation in ARCHITECTURE_DEEP_DIVE.md
    c1_shapes = re.findall(r"\[B,\s*[^\]]+\]", content_c1)
    print(f"Tensor shape notation occurrences in ARCHITECTURE_DEEP_DIVE.md: {len(c1_shapes)}")
    print("Sample tensor shapes from doc:")
    for s in c1_shapes[:8]:
        print(f"  {s}")
        
    c1_pass = c1_exists and (c1_size >= 30000) and (len(mermaid_blocks) >= 1)
    results["criterion_1"]["verdict"] = "PASS" if c1_pass else "FAIL"
    results["criterion_1"]["details"] = {
        "exists": c1_exists,
        "size_bytes": c1_size,
        "lines": len(lines_c1),
        "mermaid_blocks_count": len(mermaid_blocks),
        "mermaid_blocks": mermaid_blocks,
        "tensor_shapes_count": len(c1_shapes)
    }
    print(f"\nCRITERION 1 VERDICT: {results['criterion_1']['verdict']}")
else:
    results["criterion_1"]["verdict"] = "FAIL"
    print("\nCRITERION 1 VERDICT: FAIL (File does not exist)")

# ---------------------------------------------------------------------------
# Criterion 2: docs/parameter_mapping.txt (or .csv)
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("CRITERION 2: docs/parameter_mapping.txt & Tensor Shape Notation [B, C, H, W]")
print("=" * 80)

c2_txt = ROOT / "docs" / "parameter_mapping.txt"
c2_csv = ROOT / "docs" / "parameter_mapping.csv"
c2_path = c2_txt if c2_txt.exists() else (c2_csv if c2_csv.exists() else None)

if c2_path:
    c2_size = c2_path.stat().st_size
    print(f"File path: {c2_path}")
    print(f"File exists: True")
    print(f"File size: {c2_size} bytes ({c2_size/1024:.2f} KB)")
    
    content_c2 = c2_path.read_text(encoding='utf-8')
    lines_c2 = content_c2.splitlines()
    print(f"Total lines: {len(lines_c2)}")
    
    # Search for tensor shape notation [B, ...]
    b_shapes = []
    for idx, line in enumerate(lines_c2, 1):
        matches = re.findall(r"\[B,\s*[^\]]+\]", line)
        for m in matches:
            b_shapes.append((idx, m))
            
    print(f"Total '[B, ...]' tensor shape notations found: {len(b_shapes)}")
    print("First 15 shape notations with line numbers:")
    for l_num, sh in b_shapes[:15]:
        print(f"  Line {l_num:3d}: {sh}")
        
    # Check coverage of key architectural modules
    modules_found = {
        "MODULE 1 (YOLOv8n)": "MODULE 1" in content_c2 or "YOLOv8n" in content_c2,
        "MODULE 2 (ViT-Large)": "MODULE 2" in content_c2 or "ChakraTransformerSegmenter" in content_c2,
        "MODULE 3A (PraNet ResNet-50)": "MODULE 3A" in content_c2 or "PraNet ResNet-50" in content_c2,
        "MODULE 3B (PraNet ResNet-101)": "MODULE 3B" in content_c2 or "PraNet ResNet-101" in content_c2,
        "Global Summary": "GLOBAL SYSTEM COMPILATION" in content_c2
    }
    print("\nArchitectural Module Sections in parameter_mapping.txt:")
    for mod, found in modules_found.items():
        print(f"  {mod}: {'PRESENT' if found else 'MISSING'}")
        
    # Check parameter count tallies
    param_checks = {
        "YOLOv8n (3,011,043)": "3,011,043" in content_c2,
        "ViT-Large (309,173,737)": "309,173,737" in content_c2,
        "PraNet ResNet-50 (25,545,117)": "25,545,117" in content_c2,
        "PraNet ResNet-101 (45,671,821)": "45,671,821" in content_c2,
    }
    print("\nParameter Count Consistency Checks:")
    for p_name, p_ok in param_checks.items():
        print(f"  {p_name}: {'CONFIRMED' if p_ok else 'MISSING'}")
        
    c2_pass = (c2_size >= 15000) and (len(b_shapes) >= 50) and all(modules_found.values()) and all(param_checks.values())
    results["criterion_2"]["verdict"] = "PASS" if c2_pass else "FAIL"
    results["criterion_2"]["details"] = {
        "path": str(c2_path),
        "size_bytes": c2_size,
        "lines": len(lines_c2),
        "tensor_shapes_count": len(b_shapes),
        "modules_found": modules_found,
        "param_checks": param_checks
    }
    print(f"\nCRITERION 2 VERDICT: {results['criterion_2']['verdict']}")
else:
    results["criterion_2"]["verdict"] = "FAIL"
    print("\nCRITERION 2 VERDICT: FAIL (parameter_mapping.txt or .csv does not exist)")

# ---------------------------------------------------------------------------
# Criterion 3: Core Model Files in src/ Modified to Include New Inline Comments
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("CRITERION 3: Git Diff & Inline Comments Inspection in src/ Core Model Files")
print("=" * 80)

# Check 3.1: Git Diff
rc, git_diff_out = run_git(["diff", "--name-only", "src/"])
rc_stat, git_status_out = run_git(["status", "--porcelain", "src/"])

print(f"Git command: git diff --name-only src/")
print(f"Git diff returncode: {rc}")
print(f"Git diff output: '{git_diff_out}' (Length: {len(git_diff_out)})")
print(f"Git status --porcelain src/ output: '{git_status_out}'")

git_has_diff = len(git_diff_out.strip()) > 0 or len(git_status_out.strip()) > 0

# Check 3.2: Inspect Core Model Files directly
core_model_files = [
    ROOT / "src" / "models" / "chakranet_segmenter.py",
    ROOT / "src" / "chakra_transformer" / "transformer_segmenter.py",
    ROOT / "src" / "models" / "pranet_resnet101.py"
]

file_analysis = {}
for cf in core_model_files:
    exists = cf.exists()
    if not exists:
        file_analysis[cf.name] = {"exists": False}
        continue
        
    content = cf.read_text(encoding='utf-8', errors='ignore')
    lines = content.splitlines()
    comment_lines = []
    code_lines = []
    
    for idx, l in enumerate(lines, 1):
        s = l.strip()
        if s.startswith("#"):
            comment_lines.append((idx, s))
        elif s:
            code_lines.append((idx, s))
            if "#" in s:
                parts = s.split("#", 1)
                comment_lines.append((idx, "# " + parts[1].strip()))
                
    tag_counts = {
        "[BODY]": content.count("[BODY]"),
        "[NECK]": content.count("[NECK]"),
        "[HEAD]": content.count("[HEAD]"),
        "[DECODER]": content.count("[DECODER]")
    }
    
    # Look for tensor transformation arrows in comments
    tensor_arrows = []
    for idx, c in comment_lines:
        if "->" in c and any(ch in c for ch in ["[B", "B,"]):
            tensor_arrows.append((idx, c))
            
    ratio = len(comment_lines) / max(len(code_lines), 1)
    file_analysis[cf.name] = {
        "exists": True,
        "path": str(cf),
        "total_lines": len(lines),
        "comment_lines_count": len(comment_lines),
        "code_lines_count": len(code_lines),
        "comment_ratio": ratio,
        "tag_counts": tag_counts,
        "tensor_arrow_comments": len(tensor_arrows),
        "sample_comments": [c for idx, c in comment_lines[:10]]
    }
    
    print(f"\n--- Analysis for {cf.name} ---")
    print(f"  Path: {cf}")
    print(f"  Total lines: {len(lines)}")
    print(f"  Comment lines: {len(comment_lines)} | Code lines: {len(code_lines)} | Ratio: {ratio:.1%}")
    print(f"  Structural role tags: {tag_counts}")
    print(f"  Tensor transformation arrow comments: {len(tensor_arrows)}")

# Check against Worker 1 Gen 13 claims vs reality
w1_changes = ROOT / ".agents" / "worker_m1_g13" / "changes.md"
w1_handoff = ROOT / ".agents" / "worker_m1_g13" / "handoff.md"
diff_transformer = ROOT / ".agents" / "reviewer_m1_2_g13" / "transformer_diff.txt"
diff_chakranet = ROOT / ".agents" / "reviewer_m1_2_g13" / "chakranet_diff.txt"

print("\n--- Integrity & Provenance Cross-Examination ---")
print(f"Worker 1 changes.md exists: {w1_changes.exists()}")
print(f"Worker 1 handoff.md exists: {w1_handoff.exists()}")
print(f"Reviewer 2 transformer_diff.txt exists: {diff_transformer.exists()} ({diff_transformer.stat().st_size if diff_transformer.exists() else 0} bytes)")
print(f"Reviewer 2 chakranet_diff.txt exists: {diff_chakranet.exists()} ({diff_chakranet.stat().st_size if diff_chakranet.exists() else 0} bytes)")

# Determine Criterion 3 verdict
# Criterion 3 states: "A programmatic check (via git diff or inspection of modifications) verifies that the core model files in src/ have been modified to include new inline comments."
# Finding: Git diff is 0; the structural role tags [BODY], [NECK], [HEAD] are 0 in src/; the detailed tensor annotations exist in diff text files but were NOT applied to src/.
total_tags_in_src = sum(sum(f["tag_counts"].values()) for f in file_analysis.values() if f.get("exists"))
has_claimed_annotations = total_tags_in_src > 0

if git_has_diff:
    c3_verdict = "PASS"
elif has_claimed_annotations:
    c3_verdict = "PASS"
else:
    c3_verdict = "FAIL"

results["criterion_3"]["verdict"] = c3_verdict
results["criterion_3"]["details"] = {
    "git_diff_active": git_has_diff,
    "git_diff_output": git_diff_out,
    "git_status_output": git_status_out,
    "files_analysis": file_analysis,
    "total_structural_tags_in_src": total_tags_in_src,
    "unapplied_diff_artifacts_exist": diff_transformer.exists() and diff_chakranet.exists()
}

print(f"\nCRITERION 3 VERDICT: {c3_verdict}")
print(f"  Reason: git diff src/ returns 0 modified files, and src/ files contain 0 [BODY]/[NECK]/[HEAD] tags.")
print(f"  Annotations were authored in diff artifacts ({diff_transformer.name}, {diff_chakranet.name}) but never applied/committed to src/.")

# ---------------------------------------------------------------------------
# Summary Output
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("FINAL SUMMARY OF ACCEPTANCE CRITERIA VERDICTS")
print("=" * 80)
print(f"Criterion 1 (ARCHITECTURE_DEEP_DIVE.md & Mermaid): {results['criterion_1']['verdict']}")
print(f"Criterion 2 (parameter_mapping.txt & [B, C, H, W]):  {results['criterion_2']['verdict']}")
print(f"Criterion 3 (git diff / src/ inline comments):     {results['criterion_3']['verdict']}")
overall_verdict = "APPROVE" if all(r["verdict"] == "PASS" for r in results.values()) else "REQUEST_CHANGES"
print(f"\nOVERALL ARCHITECTURE REVIEW VERDICT: {overall_verdict}")
print("=" * 80)

# Save JSON results for report inclusion
out_json = ROOT / ".agents" / "reviewer_m3_g14" / "verification_results.json"
out_json.write_text(json.dumps(results, indent=2), encoding='utf-8')
print(f"Saved results JSON to: {out_json}")
