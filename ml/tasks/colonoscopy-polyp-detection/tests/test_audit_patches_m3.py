#!/usr/bin/env python3
r"""
Programmatic validation and assertion script for Milestone 3 Audit Patches.
Validates all 14 patch documents in M:\chakramodel_audit\patches\ and
verifies FULL_AUDIT_REPORT.md.
"""

import os
import re
import sys
from pathlib import Path

AUDIT_DIR = Path(r"M:\chakramodel_audit")
REPORT_PATH = AUDIT_DIR / "FULL_AUDIT_REPORT.md"
PATCHES_DIR = AUDIT_DIR / "patches"

EXPECTED_PATCHES = [
    "PATCH_01_no_skip_connections.md",
    "PATCH_02_dead_imagenet_head.md",
    "PATCH_03_dead_code.md",
    "PATCH_04_oom_fallback.md",
    "PATCH_05_tta_enabled_by_default.md",
    "PATCH_06_unguarded_torch_load.md",
    "PATCH_07_strict_false_state_dict.md",
    "PATCH_08_conformal_formula_sign.md",
    "PATCH_09_mc_dropout_collapse.md",
    "PATCH_10_contradictory_calibration_qhat.md",
    "PATCH_11_unpinned_dependencies.md",
    "PATCH_12_ci_lacking_src_coverage.md",
    "PATCH_13_unrecoverable_training_batches.md",
    "PATCH_14_headline_metric_artifact_absence.md",
]

def test_full_audit_report_exists():
    assert REPORT_PATH.exists(), f"Missing FULL_AUDIT_REPORT.md at {REPORT_PATH}"
    size = REPORT_PATH.stat().st_size
    assert size > 1000, f"FULL_AUDIT_REPORT.md is suspiciously small: {size} bytes"
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert len(content) > 1000
    print(f"[OK] FULL_AUDIT_REPORT.md verified ({size} bytes)")

def test_all_14_patches():
    failures = []
    parsed_records = []

    for patch_name in EXPECTED_PATCHES:
        patch_path = PATCHES_DIR / patch_name
        if not patch_path.exists():
            failures.append(f"{patch_name}: File does not exist")
            continue

        content = patch_path.read_text(encoding="utf-8")

        # 1. Contains unified diff (```diff codeblock)
        has_diff = "```diff" in content
        if not has_diff:
            failures.append(f"{patch_name}: Missing unified diff (```diff codeblock)")

        # 2. Contains proof log with Return Code: 0 or exit 0
        has_proof_0 = bool(
            re.search(r"Return\s*Code[:=\s]+0\b", content, re.IGNORECASE) or
            re.search(r"\bexit\s*(?:code\s*[:=\s]*)?0\b", content, re.IGNORECASE) or
            "Return Code: 0" in content or
            "exit 0" in content.lower()
        )
        if not has_proof_0:
            failures.append(f"{patch_name}: Missing proof log with Return Code: 0 or exit 0")

        # 3. Contains severity
        sev_match = re.search(r"(?:Severity|Impact)[:\s*]+([^\n\r\|]+)", content, re.IGNORECASE)
        has_severity = bool(sev_match)
        severity_val = sev_match.group(1).strip() if sev_match else None
        if not has_severity:
            failures.append(f"{patch_name}: Missing severity specification")

        # 4. Contains exact location / file
        loc_match = re.search(r"(?:File(?:\(s\))?|Location|Target|Path)[:\s*]+([^\n\r\|]+)", content, re.IGNORECASE)
        has_location = bool(loc_match)
        location_val = loc_match.group(1).strip() if loc_match else None
        if not has_location:
            failures.append(f"{patch_name}: Missing exact location specification")

        parsed_records.append({
            "name": patch_name,
            "has_diff": has_diff,
            "has_proof_0": has_proof_0,
            "severity": severity_val,
            "location": location_val,
            "size": patch_path.stat().st_size
        })

    print(f"\nAudit of {len(EXPECTED_PATCHES)} Patch Files:")
    print("-" * 100)
    for r in parsed_records:
        print(f"{r['name']:<48} | Diff: {str(r['has_diff']):<5} | Proof0: {str(r['has_proof_0']):<5} | Sev: {str(r['severity'])[:15]:<15} | Loc: {str(r['location'])[:30]}")
    print("-" * 100)

    if failures:
        print("\n[FAILURES DETECTED]:")
        for f in failures:
            print(f"  - {f}")
        assert False, f"Patch verification failed with {len(failures)} errors."
    else:
        print(f"\n[OK] All {len(EXPECTED_PATCHES)} patch documents satisfied all assertions!")

if __name__ == "__main__":
    print("Testing FULL_AUDIT_REPORT.md...")
    test_full_audit_report_exists()
    print("\nTesting 14 Patch Documents...")
    test_all_14_patches()
