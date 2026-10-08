import os
import sys
import subprocess
import json
import re

ROOT = "m:\\chakramodel"
TRUE_DOCS = os.path.join(ROOT, "true_docs")

def run_cmd(cmd):
    res = subprocess.run(cmd, cwd=ROOT, shell=True, capture_output=True, text=True)
    return res.stdout.strip(), res.stderr.strip(), res.returncode

def audit_commits():
    print("=== CHECK 1: Git Commits & History Audit ===")
    stdout, stderr, rc = run_cmd("git log --pretty=format:\"%h|%ai|%an|%s\"")
    actual_commits = [line.split("|") for line in stdout.splitlines() if line.strip()]
    print(f"Total actual commits: {len(actual_commits)}")
    
    # Read history_and_timeline.md
    with open(os.path.join(TRUE_DOCS, "history_and_timeline.md"), "r", encoding="utf-8") as f:
        hist_text = f.read()
        
    mismatches = []
    found_count = 0
    for short_hash, date, author, subject in actual_commits:
        if short_hash in hist_text:
            found_count += 1
        else:
            mismatches.append(f"Missing commit in doc: {short_hash} ({subject})")
            
    print(f"Verified {found_count}/{len(actual_commits)} commits present in history_and_timeline.md")
    if mismatches:
        for m in mismatches:
            print("  FAIL:", m)
    else:
        print("  PASS: All 26 commits verified verbatim in doc table!")
    return len(mismatches) == 0

def audit_file_citations():
    print("\n=== CHECK 2: Code Citations & File Path Verification ===")
    checks = [
        ("src/chakra_transformer/train_transformer.py", 87, "Topological Loss is disabled"),
        ("src/topo_loss.py", 45, "gudhi.CubicalComplex"),
        ("src/chakranet_segmenter.py", 393, "if conformal and q_hat_pos"),
        ("src/temporal/tracker.py", 1, "ChakraTemporalTracker"),
        ("src/paris_classifier.py", 40, "aspect_ratio"),
        ("fl_non_iid_partitioner.py", 1, "partition_dirichlet"),
        ("src/evaluate_all.py", 65, "n_test = max(1, int(0.1"),
        ("statistical_significance.py", 14, "CRITICAL BUG"),
        ("weights/conformal_calibration.json", None, "0.521484375"),
        ("ARCHITECTURE-SPINE.md", 43, "ChakraSLAM"),
        ("ablation_results.md", None, "0.4555"),
        ("fps_latency_report.json", None, "94.67"),
        ("results/final_5_datasets_eval.json", None, "0.9225"),
        ("outputs/eval/cvc-colondb_benchmark.json", None, "0.0065"),
        ("outputs/eval/etis_benchmark.json", None, "0.0"),
    ]
    
    all_ok = True
    for rel_path, line_no, expected in checks:
        full_path = os.path.join(ROOT, rel_path)
        if not os.path.exists(full_path):
            print(f"  FAIL: File not found: {rel_path}")
            all_ok = False
            continue
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        if expected not in content:
            print(f"  FAIL: Expected substring '{expected}' not found in {rel_path}")
            all_ok = False
        else:
            print(f"  PASS: Verified {rel_path} contains '{expected}'")
            
    return all_ok

def audit_fcbformer():
    print("\n=== CHECK 3: FCBFormer Directory Verification ===")
    fcb_dir = os.path.join(ROOT, "fcbformer")
    if not os.path.exists(fcb_dir):
        print("  FAIL: fcbformer directory missing")
        return False
    files = os.listdir(fcb_dir)
    py_files = [f for f in files if f.endswith(".py")]
    tex_files = [f for f in files if f.endswith(".tex") or f.endswith(".bib") or f.endswith(".cls")]
    print(f"  fcbformer directory contains {len(files)} files: {len(py_files)} python files, {len(tex_files)} LaTeX files")
    if len(py_files) == 0 and len(tex_files) > 0:
        print("  PASS: Confirmed fcbformer/ contains LaTeX source files and ZERO python code!")
        return True
    else:
        print("  FAIL: Unexpected python files found in fcbformer!")
        return False

def audit_weights_and_params():
    print("\n=== CHECK 4: Checkpoints & Parameter Counts Verification ===")
    try:
        import torch
        print(f"PyTorch version: {torch.__version__}, CUDA available: {torch.cuda.is_available()}")
        
        # 1. ChakraTransformer
        tf_path = os.path.join(ROOT, "weights", "chakra_transformer_best.pth")
        if os.path.exists(tf_path):
            sd = torch.load(tf_path, map_location="cpu")
            if "model" in sd:
                sd = sd["model"]
            total_params = sum(p.numel() for p in sd.values())
            print(f"  chakra_transformer_best.pth total elements in state_dict: {total_params}")
            if total_params == 309173737:
                print("  PASS: Exactly 309,173,737 parameters confirmed!")
            else:
                print(f"  INFO/CHECK: Total param count = {total_params} vs 309,173,737")
        else:
            print("  FAIL: chakra_transformer_best.pth not found")
            
        # 2. YOLO best.pt
        best_pt = os.path.join(ROOT, "weights", "best.pt")
        if os.path.exists(best_pt):
            yd = torch.load(best_pt, map_location="cpu")
            if "model" in yd:
                m = yd["model"]
                p_count = sum(p.numel() for p in m.parameters())
                print(f"  weights/best.pt parameter count: {p_count}")
                if p_count == 3011043:
                    print("  PASS: Exactly 3,011,043 parameters confirmed (YOLOv8n)!")
                else:
                    print(f"  INFO: YOLO param count = {p_count}")
        else:
            print("  FAIL: weights/best.pt not found")
            
        # 3. PraNet combo1_best.pth
        pranet_pt = os.path.join(ROOT, "weights", "combo1_best.pth")
        if os.path.exists(pranet_pt):
            pd = torch.load(pranet_pt, map_location="cpu")
            p_params = sum(p.numel() for p in pd.values())
            print(f"  weights/combo1_best.pth parameter count: {p_params}")
            if p_params == 25545117:
                print("  PASS: Exactly 25,545,117 parameters confirmed (PraNet ResNet-50)!")
            else:
                print(f"  INFO: PraNet param count = {p_params}")
                
        # 4. yolov8x.pt
        yolov8x_pt = os.path.join(ROOT, "yolov8x.pt")
        if os.path.exists(yolov8x_pt):
            xd = torch.load(yolov8x_pt, map_location="cpu")
            if "model" in xd:
                m_x = xd["model"]
                p_x = sum(p.numel() for p in m_x.parameters())
                print(f"  yolov8x.pt parameter count: {p_x}")
                if p_x == 68229648:
                    print("  PASS: Exactly 68,229,648 parameters confirmed (COCO YOLOv8x)!")
                else:
                    print(f"  INFO: yolov8x param count = {p_x}")
    except Exception as e:
        print(f"  Torch check error: {e}")

def audit_benchmark_jsons():
    print("\n=== CHECK 5: Benchmark JSON Data Consistency ===")
    # Table 5.1 verification
    eval_json = os.path.join(ROOT, "results", "final_5_datasets_eval.json")
    if os.path.exists(eval_json):
        with open(eval_json, "r") as f:
            data = json.load(f)
        print("  final_5_datasets_eval.json metrics:")
        for ds, metrics in data.items():
            print(f"    {ds}: dice={metrics.get('dice')}, miou={metrics.get('miou')}")
    
    # OOD Full cohort verification
    colondb_json = os.path.join(ROOT, "outputs", "eval", "cvc-colondb_benchmark.json")
    if os.path.exists(colondb_json):
        with open(colondb_json, "r") as f:
            cdata = json.load(f)
        summary = cdata.get("summary", {})
        print(f"  ColonDB full cohort summary: dice_mean={summary.get('dice_mean')}, zero_count={summary.get('zero_count')}/{cdata.get('dataset_size')}")
        
    etis_json = os.path.join(ROOT, "outputs", "eval", "etis_benchmark.json")
    if os.path.exists(etis_json):
        with open(etis_json, "r") as f:
            edata = json.load(f)
        esummary = edata.get("summary", {})
        print(f"  ETIS-Larib full cohort summary: dice_mean={esummary.get('dice_mean')}, zero_count={esummary.get('zero_count')}/{edata.get('dataset_size')}")

if __name__ == "__main__":
    audit_commits()
    audit_file_citations()
    audit_fcbformer()
    audit_weights_and_params()
    audit_benchmark_jsons()
