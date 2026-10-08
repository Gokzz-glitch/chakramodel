import os
import sys
import shutil
import subprocess

REPO_ROOT = r"M:\chakramodel"
os.chdir(REPO_ROOT)

def run_git(cmd_args):
    res = subprocess.run(["git"] + cmd_args, capture_output=True, text=True, cwd=REPO_ROOT)
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def is_git_tracked(path):
    rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
    code, out, _ = run_git(["ls-files", rel])
    return code == 0 and len(out) > 0

def safe_move(src_rel, dst_rel):
    src_path = os.path.join(REPO_ROOT, src_rel)
    dst_path = os.path.join(REPO_ROOT, dst_rel)
    if not os.path.exists(src_path):
        return False
    
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    
    if is_git_tracked(src_path):
        code, out, err = run_git(["mv", src_rel.replace("\\", "/"), dst_rel.replace("\\", "/")])
        if code == 0:
            return True
    
    shutil.move(src_path, dst_path)
    return True

# Read root files descriptions from root_files_analysis.txt if available
descriptions = {}
analysis_file = os.path.join(REPO_ROOT, ".agents", "worker_dev", "root_files_analysis.txt")
if os.path.exists(analysis_file):
    with open(analysis_file, "r", encoding="utf-8") as f:
        for line in f:
            if ":::" in line:
                parts = line.strip().split(":::")
                descriptions[parts[0].strip()] = parts[1].strip()

# Categorize
ITERATE_PREFIXES = [
    "build_crossval_", "sod", "pysod", "metrics_engine", "build_matrix", "build_final_matrix",
    "update_nb", "update_kaggle_nb", "update_notebook_gdown", "append_notebook",
    "patch_c6", "kaggle_hardened_pipeline", "generate_bulletproof_", "generate_final_multicell",
    "generate_multi", "generate_autodiscover_", "generate_kaggle_", "run_kaggle",
    "test_wf", "verify_", "fix_", "parse_", "extract_", "create_"
]

def is_iterate_copy(fname):
    base, ext = os.path.splitext(fname)
    for p in ITERATE_PREFIXES:
        if base.startswith(p):
            return True
    return False

root_py_files = sorted([f for f in os.listdir(REPO_ROOT) if f.endswith(".py") and os.path.isfile(os.path.join(REPO_ROOT, f))])

manifest_entries = []

for fname in root_py_files:
    if is_iterate_copy(fname):
        cat = "iterate_copies"
    else:
        cat = "one_off"
    
    dst_rel = f"archive/{cat}/{fname}"
    desc = descriptions.get(fname, "Utility script / analysis script")
    if not desc or desc == "Script utility / root execution script":
        # Generate informative description based on file name
        base = os.path.splitext(fname)[0]
        desc = f"Experimental script for {base.replace('_', ' ')}"
    
    success = safe_move(fname, dst_rel)
    if success:
        manifest_entries.append({
            "filename": fname,
            "category": cat,
            "destination": dst_rel,
            "purpose": desc
        })

# Also check root yolov8x.pt or other root scratch files to archive or preserve
if os.path.exists(os.path.join(REPO_ROOT, "yolov8x.pt")):
    safe_move("yolov8x.pt", "archive/one_off/yolov8x.pt")
    manifest_entries.append({
        "filename": "yolov8x.pt",
        "category": "one_off",
        "destination": "archive/one_off/yolov8x.pt",
        "purpose": "Root YOLOv8x pre-trained checkpoint copy"
    })

# Write archive/MANIFEST.md
manifest_path = os.path.join(REPO_ROOT, "archive", "MANIFEST.md")
os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

with open(manifest_path, "w", encoding="utf-8") as f:
    f.write("# Archive Manifest\n\n")
    f.write("This directory contains historical iteration scripts, version chains, and one-off execution files archived during repository restructuring (R3).\n\n")
    f.write("## Summary\n\n")
    f.write(f"- Total archived files: {len(manifest_entries)}\n")
    f.write(f"- Iteration copies (`archive/iterate_copies/`): {sum(1 for e in manifest_entries if e['category'] == 'iterate_copies')}\n")
    f.write(f"- One-off scripts (`archive/one_off/`): {sum(1 for e in manifest_entries if e['category'] == 'one_off')}\n\n")
    f.write("## 1. Iteration Copies (`archive/iterate_copies/`)\n\n")
    f.write("| Original Filename | Archived Path | Original Purpose / Summary |\n")
    f.write("|-------------------|---------------|----------------------------|\n")
    for e in manifest_entries:
        if e["category"] == "iterate_copies":
            f.write(f"| `{e['filename']}` | `{e['destination']}` | {e['purpose']} |\n")
    f.write("\n## 2. One-Off Scripts (`archive/one_off/`)\n\n")
    f.write("| Original Filename | Archived Path | Original Purpose / Summary |\n")
    f.write("|-------------------|---------------|----------------------------|\n")
    for e in manifest_entries:
        if e["category"] == "one_off":
            f.write(f"| `{e['filename']}` | `{e['destination']}` | {e['purpose']} |\n")

print(f"Archive completed! {len(manifest_entries)} files archived. Manifest generated at archive/MANIFEST.md")
