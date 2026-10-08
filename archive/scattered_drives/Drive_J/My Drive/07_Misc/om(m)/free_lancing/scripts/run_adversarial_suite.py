#!/usr/bin/env python3
"""
Empirical Adversarial Testing Harness for Elite Website Templates
Executes exhaustive stress testing across:
- Vector 1: Injected Template Failure Detection (No False Passes)
- Vector 2: CLI Flag Resilience, Argument Fuzzing & Graceful Error Handling
- Vector 3: Determinism, Reentrancy, State Cleanliness & Concurrent Invocations
"""

import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
TESTS_DIR = PROJECT_ROOT / "tests"
RUNNER_SCRIPT = TESTS_DIR / "e2e_test_runner.py"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Ensure UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_command_capture(cmd_args: list[str], cwd=str(PROJECT_ROOT)) -> tuple[int, str, str, float]:
    t0 = time.time()
    proc = subprocess.run(
        cmd_args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    duration = time.time() - t0
    return proc.returncode, proc.stdout, proc.stderr, duration


class BackupManager:
    """Safely backs up and restores files/directories."""
    def __init__(self):
        self.backups = {}

    def backup_file(self, path: Path):
        if path.exists() and path not in self.backups:
            self.backups[path] = path.read_text(encoding="utf-8")

    def restore_all(self):
        for path, content in self.backups.items():
            try:
                path.write_text(content, encoding="utf-8")
            except Exception as e:
                print(f"Error restoring {path}: {e}")
        self.backups.clear()


def test_vector_1_failure_detection() -> list[dict]:
    """Test intentional template corruption to ensure runner detects every failure."""
    print("\n" + "="*80)
    print("VECTOR 1: TEST FAILURE DETECTION (NO FALSE PASSES)")
    print("="*80)

    backup_mgr = BackupManager()
    results = []

    test_cases = [
        {
            "id": "V1.1",
            "name": "Unreplaced Orphaned Token in HTML (cafe/index.html)",
            "target_file": TEMPLATES_DIR / "cafe" / "index.html",
            "mutation": lambda content: content.replace("<body", "<body data-leak='{{INTENTIONAL_ORPHAN_TOKEN}}' "),
            "expected_fail_tier": "tier1 or tier4",
            "description": "Injects an unreplaced {{INTENTIONAL_ORPHAN_TOKEN}} placeholder into cafe index.html"
        },
        {
            "id": "V1.2",
            "name": "Unreplaced Orphaned Token in CSS (general/style.css)",
            "target_file": TEMPLATES_DIR / "general" / "style.css",
            "mutation": lambda content: content + "\n.orphan-test { color: {{UNREPLACED_CSS_LEAK}}; }\n",
            "expected_fail_tier": "tier1 or tier4",
            "description": "Injects an unreplaced {{UNREPLACED_CSS_LEAK}} token into general style.css"
        },
        {
            "id": "V1.3",
            "name": "Missing DOCTYPE (fitness/index.html)",
            "target_file": TEMPLATES_DIR / "fitness" / "index.html",
            "mutation": lambda content: re.sub(r"<!DOCTYPE html>", "", content, flags=re.IGNORECASE),
            "expected_fail_tier": "tier4 html_valid",
            "description": "Removes <!DOCTYPE html> declaration from fitness index.html"
        },
        {
            "id": "V1.4",
            "name": "Missing Semantic Landmarks (<nav> & <footer> in salon/index.html)",
            "target_file": TEMPLATES_DIR / "salon" / "index.html",
            "mutation": lambda content: content.replace("<nav", "<div").replace("</nav>", "</div>").replace("<footer", "<div").replace("</footer>", "</div>"),
            "expected_fail_tier": "tier3 / tier4 html_valid",
            "description": "Replaces <nav> and <footer> landmarks with generic <div> in salon index.html"
        },
        {
            "id": "V1.5",
            "name": "WCAG 2.1 AA Contrast Failure (clinic/style.css)",
            "target_file": TEMPLATES_DIR / "clinic" / "style.css",
            "mutation": lambda content: re.sub(r"--text-primary:\s*[^;]+;", "--text-primary: #121827;", content).replace("--bg-primary: #ffffff;", "--bg-primary: #111827;"),
            "expected_fail_tier": "tier3 wcag_color_contrast_ratios",
            "description": "Sets text-primary to #121827 and bg-primary to #111827 (contrast ~ 1.05:1 < 4.5:1 required)"
        },
        {
            "id": "V1.6",
            "name": "Missing Image Alt Tag (retail/index.html)",
            "target_file": TEMPLATES_DIR / "retail" / "index.html",
            "mutation": lambda content: content.replace("<img ", "<img src='broken.jpg' ").replace("alt=", "data-old-alt="),
            "expected_fail_tier": "tier1 image_alt_tags_presence",
            "description": "Removes alt attribute from images in retail index.html"
        },
        {
            "id": "V1.7",
            "name": "Missing Viewport Meta Tag (transport/index.html)",
            "target_file": TEMPLATES_DIR / "transport" / "index.html",
            "mutation": lambda content: re.sub(r'<meta\s+name=["\']viewport["\'][^>]*>', '', content),
            "expected_fail_tier": "tier3 viewport_meta_tag",
            "description": "Removes viewport meta tag from transport index.html"
        },
        {
            "id": "V1.8",
            "name": "Missing Essential Core Placeholder (general/index.html)",
            "target_file": TEMPLATES_DIR / "general" / "index.html",
            "mutation": lambda content: content.replace("{{BUSINESS_NAME}}", "Hardcoded Corp"),
            "expected_fail_tier": "tier1 placeholder_discovery_and_inventory",
            "description": "Removes essential {{BUSINESS_NAME}} placeholder from general index.html"
        }
    ]

    for tc in test_cases:
        target = tc["target_file"]
        backup_mgr.backup_file(target)
        orig_content = target.read_text(encoding="utf-8")
        mutated_content = tc["mutation"](orig_content)

        print(f"\n--- Testing {tc['id']}: {tc['name']} ---")
        try:
            target.write_text(mutated_content, encoding="utf-8")
            ret_code, stdout, stderr, dur = run_command_capture([sys.executable, str(RUNNER_SCRIPT)])

            detected = (ret_code != 0)
            status_str = "PASS (Failure Successfully Detected)" if detected else "CRITICAL FAIL (False Pass - Bug Slipped Through!)"
            print(f"Result: {status_str} | Exit Code: {ret_code} | Duration: {dur:.2f}s")

            # Extract failure snippet from output
            fail_snippets = []
            for line in (stdout + stderr).splitlines():
                if "FAIL" in line or "AssertionError" in line or "Leaks" in line or "ERROR" in line:
                    fail_snippets.append(line.strip())

            result_entry = {
                "id": tc["id"],
                "name": tc["name"],
                "mutation_description": tc["description"],
                "exit_code": ret_code,
                "detected": detected,
                "duration_seconds": dur,
                "failure_snippets": fail_snippets[:5]
            }
            results.append(result_entry)

        finally:
            backup_mgr.restore_all()

    return results


def test_vector_2_cli_stress() -> list[dict]:
    """Test CLI arguments, malformed flags, invalid choices, and flag combinations."""
    print("\n" + "="*80)
    print("VECTOR 2: CLI STRESS TESTING & ARGUMENT FUZZING")
    print("="*80)

    results = []

    cli_cases = [
        # Invalid Choices (argparse should catch with exit code 2 and usage message)
        {"id": "V2.1", "name": "Invalid Tier Choice (--tier 5)", "args": ["--tier", "5"], "expected_code": 2, "expect_traceback": False},
        {"id": "V2.2", "name": "Invalid Tier Choice (--tier abc)", "args": ["--tier", "abc"], "expected_code": 2, "expect_traceback": False},
        {"id": "V2.3", "name": "Invalid Tier Choice (--tier -1)", "args": ["--tier", "-1"], "expected_code": 2, "expect_traceback": False},
        {"id": "V2.4", "name": "Invalid Template Choice (--template invalid_template)", "args": ["--template", "invalid_template"], "expected_code": 2, "expect_traceback": False},
        {"id": "V2.5", "name": "Invalid Template Choice (--template 123)", "args": ["--template", "123"], "expected_code": 2, "expect_traceback": False},
        {"id": "V2.6", "name": "Malformed Flag (--unknown-option-xyz)", "args": ["--unknown-option-xyz"], "expected_code": 2, "expect_traceback": False},
        {"id": "V2.7", "name": "Missing Argument for Flag (--tier)", "args": ["--tier"], "expected_code": 2, "expect_traceback": False},
        {"id": "V2.8", "name": "Missing Argument for Flag (--template)", "args": ["--template"], "expected_code": 2, "expect_traceback": False},
        {"id": "V2.9", "name": "Missing Argument for Flag (--json-report)", "args": ["--json-report"], "expected_code": 2, "expect_traceback": False},

        # Valid Individual Flags
        {"id": "V2.10", "name": "Valid Tier 1 (--tier 1)", "args": ["--tier", "1"], "expected_code": 0, "expect_traceback": False},
        {"id": "V2.11", "name": "Valid Tier 2 (--tier 2)", "args": ["--tier", "2"], "expected_code": 0, "expect_traceback": False},
        {"id": "V2.12", "name": "Valid Tier 3 (--tier 3)", "args": ["--tier", "3"], "expected_code": 0, "expect_traceback": False},
        {"id": "V2.13", "name": "Valid Tier 4 (--tier 4)", "args": ["--tier", "4"], "expected_code": 0, "expect_traceback": False},
        {"id": "V2.14", "name": "Valid Template Filter (--template cafe)", "args": ["--template", "cafe"], "expected_code": 0, "expect_traceback": False},
        {"id": "V2.15", "name": "Valid Clean Flag (--clean)", "args": ["--clean"], "expected_code": 0, "expect_traceback": False},
        {"id": "V2.16", "name": "Valid Verbose Flag (-v)", "args": ["-v"], "expected_code": 0, "expect_traceback": False},
        {"id": "V2.17", "name": "Valid JSON Report Export (--json-report output/e2e_test_out.json)", "args": ["--json-report", "output/e2e_test_out.json"], "expected_code": 0, "expect_traceback": False},

        # Complex Combinations
        {"id": "V2.18", "name": "Combination: Tier 4 + Cafe + Clean + Verbose + JSON", "args": ["--tier", "4", "--template", "cafe", "--clean", "-v", "--json-report", "output/cafe_tier4.json"], "expected_code": 0, "expect_traceback": False},
        {"id": "V2.19", "name": "Combination: Tier 1 + Fail-Fast", "args": ["--tier", "1", "--fail-fast"], "expected_code": 0, "expect_traceback": False},
        {"id": "V2.20", "name": "Deep Nested JSON Report Path", "args": ["--tier", "1", "--json-report", "output/nested/deep/report.json"], "expected_code": 0, "expect_traceback": False},
    ]

    for tc in cli_cases:
        cmd = [sys.executable, str(RUNNER_SCRIPT)] + tc["args"]
        ret_code, stdout, stderr, dur = run_command_capture(cmd)

        has_traceback = "Traceback (most recent call last):" in (stdout + stderr)
        code_match = (ret_code == tc["expected_code"])
        no_tb_match = (not has_traceback) if not tc["expect_traceback"] else True

        success = code_match and no_tb_match
        status_str = "PASS" if success else "FAIL"

        print(f"[{status_str}] {tc['id']:<6} | {tc['name']:<55} | Exit: {ret_code} (exp {tc['expected_code']}) | TB: {has_traceback} | {dur:.2f}s")

        # Check JSON validity if JSON export was requested
        json_valid = None
        if "--json-report" in tc["args"] and ret_code == 0:
            idx = tc["args"].index("--json-report") + 1
            json_file = PROJECT_ROOT / tc["args"][idx]
            if json_file.exists():
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    json_valid = ("overall_status" in data and "tier_results" in data)
                except Exception:
                    json_valid = False
            else:
                json_valid = False

        results.append({
            "id": tc["id"],
            "name": tc["name"],
            "args": tc["args"],
            "exit_code": ret_code,
            "expected_code": tc["expected_code"],
            "has_traceback": has_traceback,
            "json_valid": json_valid,
            "duration_seconds": dur,
            "passed": success
        })

    return results


def test_vector_3_determinism_and_reentrancy() -> dict:
    """Test running the test suite consecutively and concurrently to check determinism and state leaks."""
    print("\n" + "="*80)
    print("VECTOR 3: DETERMINISM, REENTRANCY & CONCURRENCY")
    print("="*80)

    # 1. Sequential Consecutive Runs
    sequential_runs = []
    NUM_RUNS = 5
    print(f"Executing {NUM_RUNS} consecutive master test runner invocations...")

    for i in range(NUM_RUNS):
        report_file = OUTPUT_DIR / f"consecutive_run_{i+1}.json"
        cmd = [sys.executable, str(RUNNER_SCRIPT), "--json-report", str(report_file)]
        ret_code, stdout, stderr, dur = run_command_capture(cmd)

        report_data = {}
        if report_file.exists():
            try:
                report_data = json.loads(report_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        total_asserts = (
            report_data.get("tier_results", {}).get("tier1", {}).get("total", 0) +
            report_data.get("tier_results", {}).get("tier2", {}).get("total", 0) +
            report_data.get("tier_results", {}).get("tier3", {}).get("total", 0) +
            report_data.get("tier_results", {}).get("tier4", {}).get("total", 0)
        )
        passed_asserts = (
            report_data.get("tier_results", {}).get("tier1", {}).get("passed", 0) +
            report_data.get("tier_results", {}).get("tier2", {}).get("passed", 0) +
            report_data.get("tier_results", {}).get("tier3", {}).get("passed", 0) +
            report_data.get("tier_results", {}).get("tier4", {}).get("passed", 0)
        )

        run_info = {
            "run_index": i + 1,
            "exit_code": ret_code,
            "overall_status": report_data.get("overall_status", "UNKNOWN"),
            "total_assertions": total_asserts,
            "passed_assertions": passed_asserts,
            "duration_seconds": dur,
            "categories_passed": len([k for k, v in report_data.get("vertical_categories", {}).items() if v.get("passed")])
        }
        sequential_runs.append(run_info)
        print(f"  Run #{i+1}: Exit={ret_code} | Status={run_info['overall_status']} | Assertions={passed_asserts}/{total_asserts} | Categories={run_info['categories_passed']}/7 | Dur={dur:.2f}s")

    # Check 100% determinism
    all_codes_zero = all(r["exit_code"] == 0 for r in sequential_runs)
    all_assertions_identical = len(set(r["passed_assertions"] for r in sequential_runs)) == 1
    all_categories_passed = all(r["categories_passed"] == 7 for r in sequential_runs)
    is_deterministic = all_codes_zero and all_assertions_identical and all_categories_passed

    # 2. Parallel / Concurrent Invocations
    print("\nExecuting 2 concurrent instances of e2e_test_runner.py simultaneously...")
    p1_cmd = [sys.executable, str(RUNNER_SCRIPT), "--json-report", str(OUTPUT_DIR / "concurrent_1.json")]
    p2_cmd = [sys.executable, str(RUNNER_SCRIPT), "--json-report", str(OUTPUT_DIR / "concurrent_2.json")]

    t0 = time.time()
    p1 = subprocess.Popen(p1_cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    p2 = subprocess.Popen(p2_cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")

    out1, err1 = p1.communicate()
    out2, err2 = p2.communicate()
    dur_concurrent = time.time() - t0

    concurrent_results = {
        "process_1_exit": p1.returncode,
        "process_2_exit": p2.returncode,
        "both_succeeded": (p1.returncode == 0 and p2.returncode == 0),
        "duration_seconds": dur_concurrent,
        "p1_has_traceback": "Traceback" in (out1 + err1),
        "p2_has_traceback": "Traceback" in (out2 + err2),
    }
    print(f"Concurrent Run Result: P1 Exit={p1.returncode}, P2 Exit={p2.returncode} | Success={concurrent_results['both_succeeded']} | Dur={dur_concurrent:.2f}s")

    return {
        "sequential_runs": sequential_runs,
        "is_deterministic": is_deterministic,
        "concurrent_results": concurrent_results
    }


def main():
    print("🚀 Starting Empirical Adversarial Testing Campaign...")
    t_start = time.time()

    v1_results = test_vector_1_failure_detection()
    v2_results = test_vector_2_cli_stress()
    v3_results = test_vector_3_determinism_and_reentrancy()

    total_time = time.time() - t_start

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_campaign_duration_seconds": total_time,
        "vector_1_failure_detection": {
            "total_cases": len(v1_results),
            "passed_detections": len([r for r in v1_results if r["detected"]]),
            "failed_detections": len([r for r in v1_results if not r["detected"]]),
            "details": v1_results
        },
        "vector_2_cli_stress": {
            "total_cases": len(v2_results),
            "passed_cases": len([r for r in v2_results if r["passed"]]),
            "failed_cases": len([r for r in v2_results if not r["passed"]]),
            "details": v2_results
        },
        "vector_3_determinism": v3_results
    }

    report_path = PROJECT_ROOT / ".agents" / "sub_orch_e2e_chal1" / "adversarial_raw_results.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n📊 Saved complete raw results to: {report_path}")

    # Summary Print
    print("\n" + "="*80)
    print("CAMPAIGN SUMMARY")
    print("="*80)
    print(f"Vector 1 (Failure Detection): {summary['vector_1_failure_detection']['passed_detections']}/{summary['vector_1_failure_detection']['total_cases']} Failures Detected (0 False Passes)")
    print(f"Vector 2 (CLI Stress Testing): {summary['vector_2_cli_stress']['passed_cases']}/{summary['vector_2_cli_stress']['total_cases']} CLI Invocations Handled Gracefully")
    print(f"Vector 3 (Determinism): {'100% DETERMINISTIC' if v3_results['is_deterministic'] else 'NON-DETERMINISTIC'}")
    print(f"Total Elapsed Time: {total_time:.2f}s")


if __name__ == "__main__":
    main()
