#!/usr/bin/env python3
"""
Master Adversarial Test Runner for ChakraModel Repository.

Executes all 14 automated adversarial detection scripts in tests/adversarial/.
Verifies that all 14 tests reliably detect their respective flaws on the current codebase
and exit with code 1 (flaw exposed).

Exit Codes:
  0: All 14 adversarial tests detected their target flaws (all exited with code 1).
  1: One or more tests failed to detect the flaw (exited 0 or encountered error/crash).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Ensure UTF-8 output even on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ADVERSARIAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = ADVERSARIAL_DIR.parent.parent

TEST_SUITE = [
    {
        "id": "Flaw 01",
        "script": "test_flaw_01_no_skip_connections.py",
        "title": "No Decoder Skip Connections (16x16 px finest detail)",
        "expected_code": 1
    },
    {
        "id": "Flaw 02",
        "script": "test_flaw_02_dead_imagenet_head.py",
        "title": "Dead ImageNet Classifier Head (~1.025M parameters)",
        "expected_code": 1
    },
    {
        "id": "Flaw 03",
        "script": "test_flaw_03_dead_code.py",
        "title": "75 Lines Uninstantiated Dead Code (BasicConv2d, RFB, RA)",
        "expected_code": 1
    },
    {
        "id": "Flaw 04",
        "script": "test_flaw_04_oom_fallback.py",
        "title": "Live self.to('cpu') Device Mutation in forward() OOM Handler",
        "expected_code": 1
    },
    {
        "id": "Flaw 05",
        "script": "test_flaw_05_tta_enabled_by_default.py",
        "title": "TTA Enabled by Default (3x Latency, Conflated Metrics)",
        "expected_code": 1
    },
    {
        "id": "Flaw 06",
        "script": "test_flaw_06_unguarded_torch_load.py",
        "title": "31 Unguarded torch.load() Calls (Missing weights_only=True)",
        "expected_code": 1
    },
    {
        "id": "Flaw 07",
        "script": "test_flaw_07_strict_false_state_dict.py",
        "title": "Unchecked strict=False in load_state_dict() (Silent 0/312 Keys)",
        "expected_code": 1
    },
    {
        "id": "Flaw 08",
        "script": "test_flaw_08_conformal_formula_sign.py",
        "title": "Sign-Flipped Conformal Formula in Inference vs Calibration",
        "expected_code": 1
    },
    {
        "id": "Flaw 09",
        "script": "test_flaw_09_mc_dropout_collapse.py",
        "title": "MC-Dropout Variance Collapse (~2.85e-15 FP Roundoff Noise)",
        "expected_code": 1
    },
    {
        "id": "Flaw 10",
        "script": "test_flaw_10_contradictory_calibration_qhat.py",
        "title": "Contradictory Calibration q_hat Files (71,183x Discrepancy)",
        "expected_code": 1
    },
    {
        "id": "Flaw 11",
        "script": "test_flaw_11_unpinned_dependencies.py",
        "title": "Unpinned Floating '>=' Dependencies (timm, torch, numpy)",
        "expected_code": 1
    },
    {
        "id": "Flaw 12",
        "script": "test_flaw_12_ci_lacking_src_coverage.py",
        "title": "CI Never Lints or Executes Unit Tests for src/",
        "expected_code": 1
    },
    {
        "id": "Flaw 13",
        "script": "test_flaw_13_unrecoverable_training_batches.py",
        "title": "Unrecoverable Training Data Composition (2376 vs 330 Batches)",
        "expected_code": 1
    },
    {
        "id": "Flaw 14",
        "script": "test_flaw_14_headline_metric_artifact_absence.py",
        "title": "Headline Metric 0.7304 Has No Producing Artifact (Prose Only)",
        "expected_code": 1
    },
]


def extract_summary_line(output: str) -> str:
    """Extract a concise diagnostic line from test output."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("[FAIL]") or line.startswith("FAIL:"):
            return line
    for line in lines:
        if "detected" in line.lower() or "error" in line.lower():
            return line
    return lines[-1] if lines else "No output"


def run_all_tests():
    print("=" * 90)
    print("MASTER ADVERSARIAL TEST RUNNER: 14 FLAWS AUDIT")
    print(f"Repository Root: {REPO_ROOT}")
    print(f"Test Directory:  {ADVERSARIAL_DIR}")
    print("=" * 90)
    print()

    results = []
    all_passed = True
    start_total = time.time()

    for item in TEST_SUITE:
        script_path = ADVERSARIAL_DIR / item["script"]
        flaw_id = item["id"]
        title = item["title"]

        print(f"Running [{flaw_id}] {item['script']} ...", end=" ", flush=True)

        if not script_path.exists():
            print("MISSING SCRIPT!")
            results.append({
                "id": flaw_id,
                "script": item["script"],
                "title": title,
                "exit_code": -1,
                "status": "MISSING",
                "summary": "Script file not found",
                "duration": 0.0
            })
            all_passed = False
            continue

        t0 = time.time()
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        duration = time.time() - t0

        stdout_combined = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        summary = extract_summary_line(stdout_combined)

        if proc.returncode == item["expected_code"]:
            status = "DETECTED"
            print(f"DETECTED (Exit {proc.returncode}) [{duration:.2f}s]")
        else:
            status = "FAILED"
            all_passed = False
            print(f"FAILED (Exit {proc.returncode}, Expected {item['expected_code']}) [{duration:.2f}s]")

        results.append({
            "id": flaw_id,
            "script": item["script"],
            "title": title,
            "exit_code": proc.returncode,
            "status": status,
            "summary": summary,
            "duration": duration
        })

    total_duration = time.time() - start_total
    print()
    print("=" * 90)
    print("ADVERSARIAL DETECTION AUDIT SUMMARY")
    print("=" * 90)
    print(f"{'#':<9} | {'Script Name':<42} | {'Exit':<5} | {'Status':<12} | {'Duration':<8}")
    print("-" * 90)

    detected_count = 0
    for r in results:
        status_display = "[DETECTED]" if r["status"] == "DETECTED" else "[MISSED]"
        if r["status"] == "DETECTED":
            detected_count += 1
        print(f"{r['id']:<9} | {r['script']:<42} | {r['exit_code']:<5} | {status_display:<12} | {r['duration']:>5.2f}s")

    print("-" * 90)
    print(f"Total Flaws Tested:      {len(TEST_SUITE)}")
    print(f"Flaws Detected (Exit 1): {detected_count} / {len(TEST_SUITE)}")
    print(f"Total Execution Time:    {total_duration:.2f}s")
    print("=" * 90)

    if all_passed:
        print()
        print(">>> ALL 14 ADVERSARIAL FLAWS SUCCESSFULLY EXPOSED ON CURRENT CODEBASE (14/14 Exit 1)!")
        print("    Baseline state confirmed: all targeted architectural, mathematical, security, and")
        print("    provenance defects are deterministically identified.")
        sys.exit(0)
    else:
        print()
        print(">>> ADVERSARIAL AUDIT INCOMPLETE: One or more flaws failed to trigger expected exit code 1.")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
