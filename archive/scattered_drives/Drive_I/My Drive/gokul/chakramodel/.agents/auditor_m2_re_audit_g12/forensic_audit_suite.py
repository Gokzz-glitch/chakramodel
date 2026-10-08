"""
Milestone 2 Forensic Re-Audit Suite
Agent: auditor_m2_re_audit_g12
Target: M:\\chakramodel\\tests\\adversarial\\

Conducts empirical verification for the 4 forensic integrity checks:
1. Check for Hardcoding: AST inspection + dynamic baseline (exit 1) + dynamic patched (exit 0).
2. Check for Facades/Mocks: Verification that live repository files and parameters are parsed.
3. Check for Execution Safety & Isolation: AST inspection for network, downloads, destructive file ops.
4. Check for Codebase Immutability: git diff HEAD -- src/ and git status --porcelain src/.
"""

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

REPO_ROOT = Path(r"M:\chakramodel")
ADV_DIR = REPO_ROOT / "tests" / "adversarial"
GIT_EXE = r"C:\Users\imgk3\AppData\Local\GitHubDesktop\app-3.6.3\resources\app\git\cmd\git.exe"

TEST_SCRIPTS = [
    "test_flaw_01_no_skip_connections.py",
    "test_flaw_02_dead_imagenet_head.py",
    "test_flaw_03_dead_code.py",
    "test_flaw_04_oom_fallback.py",
    "test_flaw_05_tta_enabled_by_default.py",
    "test_flaw_06_unguarded_torch_load.py",
    "test_flaw_07_strict_false_state_dict.py",
    "test_flaw_08_conformal_formula_sign.py",
    "test_flaw_09_mc_dropout_collapse.py",
    "test_flaw_10_contradictory_calibration_qhat.py",
    "test_flaw_11_unpinned_dependencies.py",
    "test_flaw_12_ci_lacking_src_coverage.py",
    "test_flaw_13_unrecoverable_training_batches.py",
    "test_flaw_14_headline_metric_artifact_absence.py",
]

def check_1_hardcoding_inspection():
    print("=== RUNNING CHECK 1: HARDCODING INSPECTION ===")
    results = {
        "ast_analysis": {},
        "baseline_runs": {},
        "patched_runs": {},
        "all_ast_clean": True,
        "all_baseline_exit_1": True,
        "all_patched_exit_0": True,
        "verdict": "PENDING"
    }

    # AST analysis for blind sys.exit(1)
    for sname in TEST_SCRIPTS:
        fpath = ADV_DIR / sname
        tree = ast.parse(fpath.read_text(encoding="utf-8"), filename=str(fpath))
        
        # Look for unconditional module-level sys.exit(1)
        module_level_exits = []
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                func_name = ""
                if isinstance(call.func, ast.Attribute) and call.func.attr == "exit":
                    func_name = "sys.exit"
                elif isinstance(call.func, ast.Name) and call.func.id == "exit":
                    func_name = "exit"
                if func_name:
                    args_val = [ast.unparse(a) for a in call.args]
                    module_level_exits.append(f"{func_name}({', '.join(args_val)})")

        # Count total branching / verification logic
        branches = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.If, ast.Try, ast.For, ast.While)))
        exit_calls = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                if (isinstance(n.func, ast.Attribute) and n.func.attr == "exit") or \
                   (isinstance(n.func, ast.Name) and n.func.id in ("exit", "quit")):
                    exit_calls.append(ast.unparse(n))

        is_clean = len(module_level_exits) == 0 and branches > 0 and len(exit_calls) >= 1
        results["ast_analysis"][sname] = {
            "module_level_unconditional_exits": module_level_exits,
            "branching_nodes_count": branches,
            "exit_calls": exit_calls,
            "is_genuine_logic": is_clean
        }
        if not is_clean:
            results["all_ast_clean"] = False

    # Baseline execution: all must exit 1 on current unpatched codebase
    for sname in TEST_SCRIPTS:
        fpath = ADV_DIR / sname
        t0 = time.perf_counter()
        proc = subprocess.run([sys.executable, str(fpath)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        dt = round(time.perf_counter() - t0, 3)
        results["baseline_runs"][sname] = {
            "exit_code": proc.returncode,
            "duration_s": dt,
            "stdout_snippet": proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "",
            "detected": proc.returncode == 1
        }
        if proc.returncode != 1:
            results["all_baseline_exit_1"] = False

    # Patched execution: all must exit 0 when provided patched inputs
    with tempfile.TemporaryDirectory() as tmpdir:
        tpath = Path(tmpdir)

        # 1. Patched chakranet_segmenter.py with skip connections
        p1 = tpath / "patched_flaw_01.py"
        p1.write_text("""
import torch
import torch.nn as nn
class ChakraNetMicroRefiner(nn.Module):
    def __init__(self):
        super().__init__()
        self.skip_convs = nn.ModuleList([nn.Conv2d(1024, 128, 1)])
        self.up1 = nn.ConvTranspose2d(1024, 256, 4, 4)
    def forward(self, x):
        return [self.skip_convs[0](x)]
""", encoding="utf-8")
        res1 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_01_no_skip_connections.py"), "--target-file", str(p1)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_01_no_skip_connections.py"] = {"exit_code": res1.returncode, "pass": res1.returncode == 0}

        # 2. Patched num_classes=0
        p2 = tpath / "patched_flaw_02.py"
        p2.write_text("""
import timm
class M:
    def __init__(self):
        self.backbone = timm.create_model('vit_large_patch16_384', pretrained=True, num_classes=0)
""", encoding="utf-8")
        res2 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_02_dead_imagenet_head.py"), "--target-file", str(p2)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_02_dead_imagenet_head.py"] = {"exit_code": res2.returncode, "pass": res2.returncode == 0}

        # 3. Patched without dead classes
        p3 = tpath / "patched_flaw_03.py"
        p3.write_text("""
import torch.nn as nn
class ChakraNetMicroRefiner(nn.Module):
    pass
""", encoding="utf-8")
        res3 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_03_dead_code.py"), "--target-file", str(p3)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_03_dead_code.py"] = {"exit_code": res3.returncode, "pass": res3.returncode == 0}

        # 4. Patched without self.to('cpu') in forward
        p4 = tpath / "patched_flaw_04.py"
        p4.write_text("""
import torch.nn as nn
class ChakraNetMicroRefiner(nn.Module):
    def forward(self, x):
        return x * 2
""", encoding="utf-8")
        res4 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_04_oom_fallback.py"), "--target-file", str(p4)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_04_oom_fallback.py"] = {"exit_code": res4.returncode, "pass": res4.returncode == 0}

        # 5. Patched with use_tta=False default
        p5 = tpath / "patched_flaw_05.py"
        p5.write_text("""
class ChakraNet:
    def __init__(self, use_tta: bool = False):
        self.use_tta = use_tta
    def segment_roi(self):
        return getattr(self, 'use_tta', False)
""", encoding="utf-8")
        res5 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_05_tta_enabled_by_default.py"), "--target-file", str(p5)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_05_tta_enabled_by_default.py"] = {"exit_code": res5.returncode, "pass": res5.returncode == 0}

        # 6. Patched torch.load with weights_only=True
        p6 = tpath / "patched_flaw_06.py"
        p6.write_text("""
import torch
sd = torch.load("model.pth", map_location="cpu", weights_only=True)
""", encoding="utf-8")
        res6 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_06_unguarded_torch_load.py"), "--target-file", str(p6)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_06_unguarded_torch_load.py"] = {"exit_code": res6.returncode, "pass": res6.returncode == 0}

        # 7. Patched load_state_dict raising on missing keys
        p7 = tpath / "patched_flaw_07.py"
        p7.write_text("""
class ChakraNet:
    def load(self, sd):
        missing, unexpected = self.model.load_state_dict(sd, strict=False)
        if missing or unexpected:
            raise RuntimeError("Mismatch!")
""", encoding="utf-8")
        res7 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_07_strict_false_state_dict.py"), "--target-file", str(p7)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_07_strict_false_state_dict.py"] = {"exit_code": res7.returncode, "pass": res7.returncode == 0}

        # 8. Patched canonical formula
        p8 = tpath / "patched_flaw_08.py"
        p8.write_text("""
score_pos = (1.0 - prob_resized) + variance
score_neg = prob_resized + variance
""", encoding="utf-8")
        res8 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_08_conformal_formula_sign.py"), "--target-file", str(p8)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_08_conformal_formula_sign.py"] = {"exit_code": res8.returncode, "pass": res8.returncode == 0}

        # 9. Patched MC dropout metrics
        p9 = tpath / "patched_flaw_09.json"
        p9.write_text('{"mean_uncertainty": 0.042}', encoding="utf-8")
        res9 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_09_mc_dropout_collapse.py"), "--target-file", str(p9)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_09_mc_dropout_collapse.py"] = {"exit_code": res9.returncode, "pass": res9.returncode == 0}

        # 10. Patched reconciled calibration metrics
        p10_c = tpath / "calib.json"
        p10_c.write_text('{"q_hat_pos": 0.521484375}', encoding="utf-8")
        p10_m = tpath / "metrics.json"
        p10_m.write_text('{"conformal_status": "DEPRECATED_SUPERSEDED: Replaced by canonical calibration"}', encoding="utf-8")
        res10 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_10_contradictory_calibration_qhat.py"), "--calib-file", str(p10_c), "--metrics-file", str(p10_m)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_10_contradictory_calibration_qhat.py"] = {"exit_code": res10.returncode, "pass": res10.returncode == 0}

        # 11. Patched requirements pinned
        p11 = tpath / "requirements.txt"
        p11.write_text("torch==2.1.2\ntimm==0.9.12\nnumpy==1.24.3\n", encoding="utf-8")
        res11 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_11_unpinned_dependencies.py"), "--target-file", str(p11)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_11_unpinned_dependencies.py"] = {"exit_code": res11.returncode, "pass": res11.returncode == 0}

        # 12. Patched CI workflow with src/ coverage
        p12 = tpath / "test.yml"
        p12.write_text("""
jobs:
  lint:
    steps:
      - run: flake8 src/ tests/
  test:
    steps:
      - run: pytest tests/
""", encoding="utf-8")
        res12 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_12_ci_lacking_src_coverage.py"), "--target-file", str(p12)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_12_ci_lacking_src_coverage.py"] = {"exit_code": res12.returncode, "pass": res12.returncode == 0}

        # 13. Patched provenance doc
        p13_doc = tpath / "TRAINING_PROVENANCE.md"
        p13_doc.write_text("Reconciles 2376 batches and caveats zero-shot generalization.", encoding="utf-8")
        res13 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_13_unrecoverable_training_batches.py"), "--doc-file", str(p13_doc)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_13_unrecoverable_training_batches.py"] = {"exit_code": res13.returncode, "pass": res13.returncode == 0}

        # 14. Patched FIXES.md and HONEST_METRICS.md
        p14_fixes = tpath / "FIXES.md"
        p14_fixes.write_text("Mean DSC: 0.8023", encoding="utf-8")
        p14_honest = tpath / "HONEST_METRICS.md"
        p14_honest.write_text("Retracted metrics: 0.7304 unsubstantiated.", encoding="utf-8")
        res14 = subprocess.run([sys.executable, str(ADV_DIR / "test_flaw_14_headline_metric_artifact_absence.py"), "--target-file", str(p14_fixes), "--honest-metrics", str(p14_honest)], capture_output=True, text=True, cwd=str(REPO_ROOT))
        results["patched_runs"]["test_flaw_14_headline_metric_artifact_absence.py"] = {"exit_code": res14.returncode, "pass": res14.returncode == 0}

    for k, v in results["patched_runs"].items():
        if not v["pass"]:
            results["all_patched_exit_0"] = False

    all_pass = results["all_ast_clean"] and results["all_baseline_exit_1"] and results["all_patched_exit_0"]
    results["verdict"] = "PASS" if all_pass else "FAIL"
    print(f"Check 1 Verdict: {results['verdict']} (AST Clean: {results['all_ast_clean']}, Baseline 14/14 Exit 1: {results['all_baseline_exit_1']}, Patched 14/14 Exit 0: {results['all_patched_exit_0']})")
    return results

def check_2_facades_and_mocks():
    print("\n=== RUNNING CHECK 2: FACADES AND MOCKS DETECTION ===")
    results = {
        "files_checked": {},
        "empirical_values": {},
        "verdict": "PENDING"
    }

    # 1. Inspect checkpoint num_batches_tracked
    ckpt_path = REPO_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth"
    results["files_checked"]["checkpoint"] = {"path": str(ckpt_path), "exists": ckpt_path.exists(), "size_bytes": ckpt_path.stat().st_size if ckpt_path.exists() else 0}
    if ckpt_path.exists():
        import torch
        sd = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        nb1 = sd.get("module.decode_head.1.num_batches_tracked")
        nb2 = sd.get("module.decode_head.4.num_batches_tracked")
        nb1_val = int(nb1.item()) if nb1 is not None else None
        nb2_val = int(nb2.item()) if nb2 is not None else None
        results["empirical_values"]["num_batches_tracked_1"] = nb1_val
        results["empirical_values"]["num_batches_tracked_4"] = nb2_val
        results["empirical_values"]["num_batches_tracked_match_expected_2376"] = (nb1_val == 2376 and nb2_val == 2376)
        print(f"Checkpoint num_batches_tracked: {nb1_val}, {nb2_val} (Matches 2376: {results['empirical_values']['num_batches_tracked_match_expected_2376']})")

    # 2. Inspect unguarded torch.load calls across repository
    unguarded_calls = []
    target_dirs = ["src", "scripts", "kaggle_package", "kaggle_bundle"]
    for td in target_dirs:
        tdp = REPO_ROOT / td
        if not tdp.exists():
            continue
        for root, _, files in os.walk(tdp):
            for file in files:
                if file.endswith(".py"):
                    fp = Path(root) / file
                    try:
                        content = fp.read_text(encoding="utf-8", errors="ignore")
                        tree = ast.parse(content, filename=str(fp))
                    except Exception:
                        continue
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            is_torch_load = False
                            if isinstance(node.func, ast.Attribute) and node.func.attr == "load":
                                if isinstance(node.func.value, ast.Name) and node.func.value.id == "torch":
                                    is_torch_load = True
                            if is_torch_load:
                                # Check if weights_only=True
                                wo = False
                                for kw in node.keywords:
                                    if kw.arg == "weights_only" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                        wo = True
                                if not wo:
                                    unguarded_calls.append(f"{fp.relative_to(REPO_ROOT)}:{node.lineno}")

    results["empirical_values"]["unguarded_torch_load_count"] = len(unguarded_calls)
    results["empirical_values"]["unguarded_torch_load_sample"] = unguarded_calls[:5]
    print(f"Unguarded torch.load calls found across repository: {len(unguarded_calls)} (Expected: 31-32)")

    # 3. Inspect contradictory calibration files
    calib_file = REPO_ROOT / "weights" / "calibration" / "conformal_calibration.json"
    metrics_file = REPO_ROOT / "results" / "combo1_metrics.json"
    results["files_checked"]["conformal_calibration"] = {"path": str(calib_file), "exists": calib_file.exists()}
    results["files_checked"]["combo1_metrics"] = {"path": str(metrics_file), "exists": metrics_file.exists()}

    if calib_file.exists() and metrics_file.exists():
        cdata = json.loads(calib_file.read_text(encoding="utf-8"))
        mdata = json.loads(metrics_file.read_text(encoding="utf-8"))
        q_hat_pos = cdata.get("q_hat_pos")
        threshold = mdata.get("conformal", {}).get("alpha_5", {}).get("threshold")
        mean_unc = mdata.get("mean_uncertainty")
        ratio = (q_hat_pos / threshold) if (threshold and q_hat_pos) else None
        results["empirical_values"]["q_hat_pos"] = q_hat_pos
        results["empirical_values"]["combo1_threshold"] = threshold
        results["empirical_values"]["qhat_discrepancy_ratio"] = ratio
        results["empirical_values"]["mean_uncertainty"] = mean_unc
        ratio_str = f"{ratio:.1f}x" if ratio is not None else "None"
        print(f"Calibration discrepancy: q_hat_pos={q_hat_pos}, combo1_threshold={threshold}, ratio={ratio_str}")
        print(f"MC dropout mean_uncertainty in combo1: {mean_unc}")

    # 4. Inspect headline metric in FIXES.md vs results artifact
    fixes_path = REPO_ROOT / "FIXES.md"
    eval_res_path = REPO_ROOT / "results" / "corrected_eval_kvasir_seg.json"
    results["files_checked"]["FIXES.md"] = {"path": str(fixes_path), "exists": fixes_path.exists()}
    results["files_checked"]["corrected_eval_kvasir_seg"] = {"path": str(eval_res_path), "exists": eval_res_path.exists()}
    if fixes_path.exists() and eval_res_path.exists():
        ftxt = fixes_path.read_text(encoding="utf-8")
        claim_07304 = "0.7304" in ftxt
        edata = json.loads(eval_res_path.read_text(encoding="utf-8"))
        actual_dsc = edata.get("mean_dsc")
        results["empirical_values"]["fixes_contains_0_7304"] = claim_07304
        results["empirical_values"]["actual_mean_dsc_in_artifact"] = actual_dsc
        print(f"Headline metric audit: '0.7304' in FIXES.md: {claim_07304}, actual mean_dsc: {actual_dsc}")

    all_pass = (
        results["files_checked"]["checkpoint"]["exists"] and
        results["empirical_values"].get("num_batches_tracked_match_expected_2376", False) and
        30 <= results["empirical_values"].get("unguarded_torch_load_count", 0) <= 35 and
        results["empirical_values"].get("qhat_discrepancy_ratio", 0) > 1000 and
        results["empirical_values"].get("mean_uncertainty", 1.0) < 1e-10 and
        results["empirical_values"].get("fixes_contains_0_7304", False)
    )
    results["verdict"] = "PASS" if all_pass else "FAIL"
    print(f"Check 2 Verdict: {results['verdict']}")
    return results

def check_3_execution_safety():
    print("\n=== RUNNING CHECK 3: EXECUTION SAFETY & ISOLATION ===")
    results = {
        "scripts_audited": {},
        "network_violations": [],
        "file_write_violations": [],
        "destructive_violations": [],
        "verdict": "PENDING"
    }

    all_scripts = TEST_SCRIPTS + ["run_all_adversarial_tests.py", "test_adversarial_dim_param_audit.py"]
    prohibited_modules = {"requests", "urllib", "http", "socket", "aiohttp", "httpx", "ftplib", "urllib3"}
    prohibited_write_attrs = {"write_text", "write_bytes", "unlink", "rmdir"}

    for sname in all_scripts:
        fpath = ADV_DIR / sname
        content = fpath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(fpath))
        
        script_info = {
            "network_imports": [],
            "write_calls": [],
            "destructive_calls": [],
            "safe": True
        }

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_root = alias.name.split(".")[0]
                    if mod_root in prohibited_modules:
                        script_info["network_imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_root = node.module.split(".")[0]
                    if mod_root in prohibited_modules:
                        script_info["network_imports"].append(node.module)

            # Check calls
            elif isinstance(node, ast.Call):
                # Check for open(..., 'w'/'a'/'x'/'+')
                is_open = False
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    is_open = True
                if is_open and len(node.args) >= 2:
                    mode_arg = node.args[1]
                    if isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
                        mode_str = mode_arg.value
                        if any(c in mode_str for c in ("w", "a", "x", "+")):
                            # Check if writing outside tests directory or safe result writing
                            script_info["write_calls"].append(f"open(..., '{mode_str}') at line {node.lineno}")

                # Check attribute calls like write_text, unlink
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in prohibited_write_attrs:
                        script_info["write_calls"].append(f"{node.func.attr} at line {node.lineno}")
                    if node.func.attr in ("remove", "rmdir", "rmtree"):
                        script_info["destructive_calls"].append(f"{node.func.attr} at line {node.lineno}")

        # Note: in test_adversarial_dim_param_audit.py, writing its own json report is checked
        # But let's see for the 14 detection scripts + runner: they must have 0 write calls
        if sname in TEST_SCRIPTS or sname == "run_all_adversarial_tests.py":
            if script_info["write_calls"] or script_info["network_imports"] or script_info["destructive_calls"]:
                script_info["safe"] = False
        else:
            # For dim param audit, only writing its own test result json is acceptable
            if script_info["network_imports"] or script_info["destructive_calls"]:
                script_info["safe"] = False

        results["scripts_audited"][sname] = script_info
        if script_info["network_imports"]:
            results["network_violations"].append({sname: script_info["network_imports"]})
        if sname in TEST_SCRIPTS and script_info["write_calls"]:
            results["file_write_violations"].append({sname: script_info["write_calls"]})
        if script_info["destructive_calls"]:
            results["destructive_violations"].append({sname: script_info["destructive_calls"]})

    all_safe = len(results["network_violations"]) == 0 and \
               len(results["file_write_violations"]) == 0 and \
               len(results["destructive_violations"]) == 0

    results["verdict"] = "PASS" if all_safe else "FAIL"
    print(f"Check 3 Verdict: {results['verdict']} (Network violations: {len(results['network_violations'])}, Write violations in 14 tests: {len(results['file_write_violations'])}, Destructive violations: {len(results['destructive_violations'])})")
    return results

def check_4_codebase_immutability():
    print("\n=== RUNNING CHECK 4: CODEBASE IMMUTABILITY CHECK ===")
    results = {
        "git_diff_cmd": f"{GIT_EXE} diff HEAD -- src/",
        "git_status_cmd": f"{GIT_EXE} status --porcelain src/",
        "diff_output": "",
        "status_output": "",
        "diff_bytes": 0,
        "status_lines": 0,
        "is_src_clean": False,
        "verdict": "PENDING"
    }

    # Run git diff HEAD -- src/
    p_diff = subprocess.run([GIT_EXE, "diff", "HEAD", "--", "src/"], capture_output=True, text=True, cwd=str(REPO_ROOT))
    diff_out = p_diff.stdout
    diff_bytes = len(diff_out.encode("utf-8"))

    # Run git status --porcelain src/
    p_status = subprocess.run([GIT_EXE, "status", "--porcelain", "src/"], capture_output=True, text=True, cwd=str(REPO_ROOT))
    status_out = p_status.stdout
    status_lines = [l for l in status_out.splitlines() if l.strip()]

    results["diff_output"] = diff_out
    results["status_output"] = status_out
    results["diff_bytes"] = diff_bytes
    results["status_lines"] = len(status_lines)
    results["is_src_clean"] = (diff_bytes == 0 and len(status_lines) == 0)
    results["verdict"] = "PASS" if results["is_src_clean"] else "FAIL"

    print(f"Check 4 Result:")
    print(f"  diff bytes: {diff_bytes}")
    print(f"  status lines: {len(status_lines)}")
    print(f"  is_src_clean: {results['is_src_clean']}")
    print(f"Check 4 Verdict: {results['verdict']}")
    return results

def run_master_runner():
    print("\n=== RUNNING MASTER RUNNER EXECUTION ===")
    runner_path = ADV_DIR / "run_all_adversarial_tests.py"
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, str(runner_path)], capture_output=True, text=True, cwd=str(REPO_ROOT))
    dt = round(time.perf_counter() - t0, 3)
    return {
        "exit_code": proc.returncode,
        "duration_s": dt,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "pass": proc.returncode == 0
    }

def main():
    print("Starting Milestone 2 Forensic Re-Audit...")
    c1 = check_1_hardcoding_inspection()
    c2 = check_2_facades_and_mocks()
    c3 = check_3_execution_safety()
    c4 = check_4_codebase_immutability()
    runner = run_master_runner()

    overall_verdict = "CLEAN" if (c1["verdict"] == "PASS" and c2["verdict"] == "PASS" and c3["verdict"] == "PASS" and c4["verdict"] == "PASS") else "INTEGRITY VIOLATION"

    final_results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "auditor": "auditor_m2_re_audit_g12",
        "working_directory": r"M:\chakramodel\.agents\auditor_m2_re_audit_g12",
        "target": r"M:\chakramodel\tests\adversarial",
        "binary_verdict": overall_verdict,
        "checks": {
            "check_1_hardcoding": c1,
            "check_2_facades_mocks": c2,
            "check_3_safety_isolation": c3,
            "check_4_codebase_immutability": c4
        },
        "master_runner": runner
    }

    out_file = Path(r"M:\chakramodel\.agents\auditor_m2_re_audit_g12\audit_results.json")
    out_file.write_text(json.dumps(final_results, indent=2), encoding="utf-8")
    print(f"\nAudit results successfully saved to {out_file}")
    print(f">>> FINAL FORENSIC VERDICT: {overall_verdict} <<<")

if __name__ == "__main__":
    main()
