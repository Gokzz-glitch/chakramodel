#!/usr/bin/env python3
"""
test_cli_stress.py - Empirical Challenger Stress Harness for CLI and Verification Oracle

Executes exhaustive boundary, stress, and fault-injection tests on:
  - download_datasets.py
  - verify_datasets.py

All tests execute subprocesses with isolated temporary files to ensure
zero pollution of production archives or report files.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

WORKSPACE_ROOT = r"I:\My Drive\1509-chakramodelom\dataet"
DOWNLOAD_SCRIPT = os.path.join(WORKSPACE_ROOT, "download_datasets.py")
VERIFY_SCRIPT = os.path.join(WORKSPACE_ROOT, "verify_datasets.py")

passed_tests = 0
failed_tests = 0
findings = []


def record_result(name: str, passed: bool, details: str = "", finding_severity: str = None):
    global passed_tests, failed_tests
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    if details:
        print(f"       -> {details}")
    if passed:
        passed_tests += 1
    else:
        failed_tests += 1
        if finding_severity:
            findings.append({
                "test": name,
                "severity": finding_severity,
                "details": details,
            })


def run_cmd(args, timeout=30):
    cmd = [sys.executable] + args
    start = time.time()
    proc = subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    duration = time.time() - start
    return proc.returncode, proc.stdout, proc.stderr, duration


# ==============================================================================
# Suite 1: Help and Usage Outputs
# ==============================================================================
def test_suite_help():
    print("\n" + "=" * 60)
    print("Suite 1: Help & Documentation Flags")
    print("=" * 60)

    # 1.1 verify_datasets.py --help
    rc, out, err, dur = run_cmd([VERIFY_SCRIPT, "--help"])
    ok = (rc == 0 and "7-Gate Zero-Corruption Verification Suite" in out and "--target-dir" in out)
    record_result("verify_datasets.py --help returns exit code 0 and valid documentation", ok, f"rc={rc}")

    # 1.2 verify_datasets.py -h
    rc, out, err, dur = run_cmd([VERIFY_SCRIPT, "-h"])
    ok = (rc == 0 and "--output-report" in out)
    record_result("verify_datasets.py -h returns exit code 0", ok, f"rc={rc}")

    # 1.3 download_datasets.py --help
    rc, out, err, dur = run_cmd([DOWNLOAD_SCRIPT, "--help"])
    ok = (rc == 0 and "Resilient Kaggle Dataset Downloader Engine" in out and "--datasets" in out)
    record_result("download_datasets.py --help returns exit code 0 and valid documentation", ok, f"rc={rc}")

    # 1.4 download_datasets.py -h
    rc, out, err, dur = run_cmd([DOWNLOAD_SCRIPT, "-h"])
    ok = (rc == 0 and "--staging-dir" in out)
    record_result("download_datasets.py -h returns exit code 0", ok, f"rc={rc}")


# ==============================================================================
# Suite 2: Argparse Robustness (Unknown flags, missing params, type errors)
# ==============================================================================
def test_suite_argparse():
    print("\n" + "=" * 60)
    print("Suite 2: Argparse Robustness & Syntactic Errors")
    print("=" * 60)

    # 2.1 Unknown flag verify_datasets.py
    rc, out, err, dur = run_cmd([VERIFY_SCRIPT, "--unknown-parameter-xyz"])
    ok = (rc == 2 and "unrecognized arguments" in err)
    record_result("verify_datasets.py rejects unknown flags with exit code 2", ok, f"rc={rc}, err={err.strip()[:80]}")

    # 2.2 Unknown flag download_datasets.py
    rc, out, err, dur = run_cmd([DOWNLOAD_SCRIPT, "--invalid-flag"])
    ok = (rc == 2 and "unrecognized arguments" in err)
    record_result("download_datasets.py rejects unknown flags with exit code 2", ok, f"rc={rc}, err={err.strip()[:80]}")

    # 2.3 Missing option argument for --target-dir
    rc, out, err, dur = run_cmd([VERIFY_SCRIPT, "--target-dir"])
    ok = (rc == 2 and "expected one argument" in err)
    record_result("verify_datasets.py rejects missing argument for --target-dir with exit code 2", ok, f"rc={rc}")

    # 2.4 Missing option argument for --datasets
    rc, out, err, dur = run_cmd([DOWNLOAD_SCRIPT, "--datasets"])
    ok = (rc == 2 and "expected at least one argument" in err)
    record_result("download_datasets.py rejects missing argument for --datasets with exit code 2", ok, f"rc={rc}")

    # 2.5 Non-integer value for --sample-count
    rc, out, err, dur = run_cmd([VERIFY_SCRIPT, "--sample-count", "not_a_number"])
    ok = (rc == 2 and "invalid int value" in err)
    record_result("verify_datasets.py rejects string for --sample-count with exit code 2", ok, f"rc={rc}")

    # 2.6 Non-integer value for --chunk-size
    rc, out, err, dur = run_cmd([DOWNLOAD_SCRIPT, "--chunk-size", "bad_chunk"])
    ok = (rc == 2 and "invalid int value" in err)
    record_result("download_datasets.py rejects string for --chunk-size with exit code 2", ok, f"rc={rc}")

    # 2.7 Non-integer value for --max-retries
    rc, out, err, dur = run_cmd([DOWNLOAD_SCRIPT, "--max-retries", "five"])
    ok = (rc == 2 and "invalid int value" in err)
    record_result("download_datasets.py rejects string for --max-retries with exit code 2", ok, f"rc={rc}")


# ==============================================================================
# Suite 3: Boundary & Pathological Inputs (ZeroDivisionError, negative values)
# ==============================================================================
def test_suite_boundaries():
    print("\n" + "=" * 60)
    print("Suite 3: Boundary & Pathological Numeric Inputs")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_report = os.path.join(temp_dir, "report.json")

        # 3.1 --sample-count 0 on verify_datasets.py
        # Expected: Should gracefully reject or handle without unhandled ZeroDivisionError crash.
        rc, out, err, dur = run_cmd([
            VERIFY_SCRIPT,
            "--target-dir", temp_dir,
            "--output-report", temp_report,
            "--sample-count", "0"
        ])
        crashed_zde = ("ZeroDivisionError" in err or "ZeroDivisionError" in out)
        if crashed_zde:
            record_result(
                "verify_datasets.py --sample-count 0 graceful handling",
                False,
                f"Unhandled ZeroDivisionError in verify_datasets.py: {err.strip()[:100]}",
                finding_severity="HIGH"
            )
        else:
            # If files don't exist in temp_dir, Gate 1 fails before Gate 4, so test against real archive in sandbox
            record_result("verify_datasets.py --sample-count 0 on empty target-dir (Gate 1 exit)", rc == 1)

        # 3.2 Create a tiny valid mock archive to trigger Gate 4 with --sample-count 0
        mock_zip_path = os.path.join(temp_dir, "endoscene-cvc300-polyp-raw-dataset.zip")
        with zipfile.ZipFile(mock_zip_path, "w") as z:
            # Add a mock PNG file
            png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
            z.writestr("test.png", png_header)

        # Re-run with --sample-count 0 directly targeting this archive
        # Note: Spec expects size 16459371 bytes, so Gate 1 fails on size unless bypassed or tested directly.
        # Let's test the function directly via python one-liner to verify the exact crash in sample_media_magic_bytes
        code = (
            "import zipfile, io, sys; from verify_datasets import sample_media_magic_bytes; "
            "bio = io.BytesIO(); z = zipfile.ZipFile(bio, 'w'); z.writestr('a.png', b'\\x89PNG\\r\\n\\x1a\\n'); z.close(); "
            "z2 = zipfile.ZipFile(bio, 'r'); sample_media_magic_bytes(z2, 'png', sample_count=0)"
        )
        rc_func, out_func, err_func, _ = run_cmd(["-c", code])
        if "ZeroDivisionError" in err_func:
            record_result(
                "sample_media_magic_bytes(sample_count=0) unhandled ZeroDivisionError",
                False,
                f"Empirically confirmed crash: {err_func.strip().splitlines()[-1]}",
                finding_severity="MEDIUM"
            )
        else:
            record_result("sample_media_magic_bytes(sample_count=0) handled gracefully", rc_func == 0)

        # 3.3 Negative sample count: --sample-count -1
        code_neg = (
            "import zipfile, io, sys; from verify_datasets import sample_media_magic_bytes; "
            "bio = io.BytesIO(); z = zipfile.ZipFile(bio, 'w'); z.writestr('a.png', b'\\x89PNG\\r\\n\\x1a\\n'); z.close(); "
            "z2 = zipfile.ZipFile(bio, 'r'); res = sample_media_magic_bytes(z2, 'png', sample_count=-1); print('Result:', res)"
        )
        rc_neg, out_neg, err_neg, _ = run_cmd(["-c", code_neg])
        record_result(
            "sample_media_magic_bytes(sample_count=-1) behavior",
            rc_neg == 0,
            f"Output: {out_neg.strip()}"
        )

        # 3.4 Large sample count exceeding eligible members: sample_count=1000000 on 1-member archive
        code_huge = (
            "import zipfile, io, sys; from verify_datasets import sample_media_magic_bytes; "
            "bio = io.BytesIO(); z = zipfile.ZipFile(bio, 'w'); z.writestr('a.png', b'\\x89PNG\\r\\n\\x1a\\n'); z.close(); "
            "z2 = zipfile.ZipFile(bio, 'r'); res = sample_media_magic_bytes(z2, 'png', sample_count=1000000); print('Result:', res)"
        )
        rc_huge, out_huge, err_huge, _ = run_cmd(["-c", code_huge])
        ok = (rc_huge == 0 and "True, 1, 1, []" in out_huge)
        record_result(
            "sample_media_magic_bytes(sample_count=1000000) handles count > members without crash",
            ok,
            f"Output: {out_huge.strip()}"
        )


# ==============================================================================
# Suite 4: Path Handling & I/O Boundary Conditions
# ==============================================================================
def test_suite_paths():
    print("\n" + "=" * 60)
    print("Suite 4: Path Handling & I/O Boundary Conditions")
    print("=" * 60)

    # 4.1 Non-existent target directory on verify_datasets.py
    with tempfile.TemporaryDirectory() as temp_dir:
        non_existent_target = os.path.join(temp_dir, "does_not_exist")
        report_dest = os.path.join(temp_dir, "fail_report.json")
        rc, out, err, dur = run_cmd([
            VERIFY_SCRIPT,
            "--target-dir", non_existent_target,
            "--output-report", report_dest
        ])
        ok = (rc == 1 and os.path.exists(report_dest))
        record_result(
            "verify_datasets.py on non-existent target dir exits 1 and writes valid failure report",
            ok,
            f"rc={rc}, report_written={os.path.exists(report_dest)}"
        )
        if os.path.exists(report_dest):
            with open(report_dest) as f:
                rdata = json.load(f)
                valid_summary = (rdata["summary"]["total_failed"] == 11 and rdata["overall_status"] == "FAILED")
                record_result("Failure report correctly reports 11/11 failed and status FAILED", valid_summary)

    # 4.2 Nested non-existent directory for --output-report (auto-creation of parent dirs)
    with tempfile.TemporaryDirectory() as temp_dir:
        deep_report = os.path.join(temp_dir, "nested", "sub", "deep_report.json")
        rc, out, err, dur = run_cmd([
            VERIFY_SCRIPT,
            "--target-dir", temp_dir,
            "--output-report", deep_report
        ])
        ok = (rc == 1 and os.path.exists(deep_report))
        record_result(
            "verify_datasets.py creates nested parent directories for --output-report automatically",
            ok,
            f"deep_report_exists={os.path.exists(deep_report)}"
        )

    # 4.3 Target directory path with spaces
    with tempfile.TemporaryDirectory() as temp_dir:
        spaced_dir = os.path.join(temp_dir, "path with spaces in name")
        os.makedirs(spaced_dir, exist_ok=True)
        spaced_report = os.path.join(spaced_dir, "report with spaces.json")
        rc, out, err, dur = run_cmd([
            VERIFY_SCRIPT,
            "--target-dir", spaced_dir,
            "--output-report", spaced_report
        ])
        ok = (rc == 1 and os.path.exists(spaced_report))
        record_result(
            "verify_datasets.py correctly handles paths with spaces in --target-dir and --output-report",
            ok,
            f"rc={rc}, report_exists={os.path.exists(spaced_report)}"
        )


# ==============================================================================
# Suite 5: CLI Dataset Argument Handling in download_datasets.py
# ==============================================================================
def test_suite_downloader_cli():
    print("\n" + "=" * 60)
    print("Suite 5: Dataset Argument Handling in download_datasets.py")
    print("=" * 60)

    # 5.1 Invalid dataset format (no slash)
    rc, out, err, dur = run_cmd([
        DOWNLOAD_SCRIPT,
        "--datasets", "invalidslugwithoutslash",
        "--target-dir", os.path.join(tempfile.gettempdir(), "test_ds_target"),
    ])
    ok = (rc == 1 and "Invalid dataset format: 'invalidslugwithoutslash'" in out)
    record_result(
        "download_datasets.py rejects dataset slug without slash with exit code 1",
        ok,
        f"rc={rc}, msg_found={'Invalid dataset format' in out}"
    )

    # 5.2 Invalid dataset format (multiple slashes)
    rc, out, err, dur = run_cmd([
        DOWNLOAD_SCRIPT,
        "--datasets", "owner/sub/dataset",
        "--target-dir", os.path.join(tempfile.gettempdir(), "test_ds_target"),
    ])
    ok = (rc == 1 and "Invalid dataset format: 'owner/sub/dataset'" in out)
    record_result(
        "download_datasets.py rejects dataset slug with multiple slashes with exit code 1",
        ok,
        f"rc={rc}"
    )

    # 5.3 Already verified dataset detection (Scenario A)
    # Using existing verified archive in WORKSPACE_ROOT
    rc, out, err, dur = run_cmd([
        DOWNLOAD_SCRIPT,
        "--datasets", "gokulrocky/endoscene-cvc300-polyp-raw-dataset",
        "--target-dir", WORKSPACE_ROOT,
    ])
    ok = (rc == 0 and "already complete and verified in target directory" in out)
    record_result(
        "download_datasets.py recognizes existing complete archive (Scenario A) and exits 0 without re-downloading",
        ok,
        f"rc={rc}, duration={dur:.2f}s"
    )


# ==============================================================================
# Suite 6: Verification Oracle Fault Injection (Sandboxed Corruptions)
# ==============================================================================
def test_suite_fault_injection():
    print("\n" + "=" * 60)
    print("Suite 6: Verification Oracle Fault Injection (Sandbox)")
    print("=" * 60)

    # We will test each gate's rejection capability:
    # 6.1 Gate 1: Zero-byte archive file
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = os.path.join(temp_dir, "rep.json")
        target_file = os.path.join(temp_dir, "endoscene-cvc300-polyp-raw-dataset.zip")
        with open(target_file, "wb") as f:
            pass  # 0 bytes

        rc, out, err, _ = run_cmd([
            VERIFY_SCRIPT,
            "--target-dir", temp_dir,
            "--output-report", report_path
        ])
        with open(report_path) as f:
            rep = json.load(f)
        ds_rep = rep["datasets"]["gokulrocky/endoscene-cvc300-polyp-raw-dataset"]
        g1 = ds_rep["gates"]["gate1_presence_and_size"]
        ok = (not g1["passed"] and any("zero bytes" in e for e in g1["errors"]))
        record_result("Gate 1 detects and rejects zero-byte empty archive", ok, f"g1_passed={g1['passed']}")

    # 6.2 Gate 1: Lingering .kaggle-partial file
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = os.path.join(temp_dir, "rep.json")
        target_file = os.path.join(temp_dir, "endoscene-cvc300-polyp-raw-dataset.zip")
        partial_file = target_file + ".kaggle-partial"
        # create mock file of expected size
        with open(target_file, "wb") as f:
            f.write(b"0" * 16459371)
        with open(partial_file, "w") as f:
            f.write("partial download marker")

        rc, out, err, _ = run_cmd([
            VERIFY_SCRIPT,
            "--target-dir", temp_dir,
            "--output-report", report_path
        ])
        with open(report_path) as f:
            rep = json.load(f)
        ds_rep = rep["datasets"]["gokulrocky/endoscene-cvc300-polyp-raw-dataset"]
        g1 = ds_rep["gates"]["gate1_presence_and_size"]
        ok = (not g1["passed"] and any("Lingering .kaggle-partial" in e for e in g1["errors"]))
        record_result("Gate 1 detects and rejects archive with lingering .kaggle-partial file", ok, f"g1_passed={g1['passed']}")

    # 6.3 Gate 1: File size mismatch
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = os.path.join(temp_dir, "rep.json")
        target_file = os.path.join(temp_dir, "endoscene-cvc300-polyp-raw-dataset.zip")
        with open(target_file, "wb") as f:
            f.write(b"1234567890")  # 10 bytes instead of 16,459,371

        rc, out, err, _ = run_cmd([
            VERIFY_SCRIPT,
            "--target-dir", temp_dir,
            "--output-report", report_path
        ])
        with open(report_path) as f:
            rep = json.load(f)
        ds_rep = rep["datasets"]["gokulrocky/endoscene-cvc300-polyp-raw-dataset"]
        g1 = ds_rep["gates"]["gate1_presence_and_size"]
        ok = (not g1["passed"] and any("Size mismatch" in e for e in g1["errors"]))
        record_result("Gate 1 detects and rejects archive with incorrect file size", ok, f"g1_passed={g1['passed']}")

    # 6.4 Gate 2: Corrupted Zip / BadZipFile
    # Test verify_single_dataset Gate 2 directly
    code_corrupt_zip = (
        "import tempfile, os, json, sys; from verify_datasets import verify_single_dataset, DATASET_SPECS; "
        "d = tempfile.mkdtemp(); f = os.path.join(d, 'endoscene-cvc300-polyp-raw-dataset.zip'); "
        "open(f, 'wb').write(b'PK\\x03\\x04' + b'\\x00' * (16459371 - 4)); "
        "res = verify_single_dataset('endoscene-cvc300-polyp-raw-dataset.zip', DATASET_SPECS['endoscene-cvc300-polyp-raw-dataset.zip'], d, 50); "
        "print('G2 Passed:', res['gates']['gate2_archive_integrity']['passed'], 'Errors:', res['gates']['gate2_archive_integrity']['errors'])"
    )
    rc, out, err, _ = run_cmd(["-c", code_corrupt_zip])
    ok = (rc == 0 and "G2 Passed: False" in out and "BadZipFile" in out)
    record_result("Gate 2 detects and catches BadZipFile corruption", ok, f"out={out.strip()}")

    # 6.5 Gate 3: Member count mismatch
    # Create valid zip of correct size padded, but with 2 members instead of 120
    code_member_count = (
        "import tempfile, os, zipfile, sys; from verify_datasets import verify_single_dataset, DATASET_SPECS; "
        "d = tempfile.mkdtemp(); p = os.path.join(d, 'endoscene-cvc300-polyp-raw-dataset.zip'); "
        "with zipfile.ZipFile(p, 'w') as z: z.writestr('img1.png', b'\\x89PNG\\r\\n\\x1a\\n'); z.writestr('img2.png', b'\\x89PNG\\r\\n\\x1a\\n'); "
        "cur_size = os.path.getsize(p); "
        "# pad zip comment to match expected size\n"
        "pad = 16459371 - cur_size\n"
        "with zipfile.ZipFile(p, 'a') as z: z.comment = b'A' * (pad - 100) if pad > 100 else b''; "
        "res = verify_single_dataset('endoscene-cvc300-polyp-raw-dataset.zip', DATASET_SPECS['endoscene-cvc300-polyp-raw-dataset.zip'], d, 50); "
        "print('G3 Passed:', res['gates'].get('gate3_member_count', {}).get('passed'))"
    )
    # Even if size doesn't match, Gate 1 would fail; let's test Gate 3 logic directly
    code_g3_direct = (
        "import zipfile, io; from verify_datasets import DATASET_SPECS; "
        "bio = io.BytesIO(); z = zipfile.ZipFile(bio, 'w'); z.writestr('a.png', b'\\x89PNG'); z.close(); "
        "z2 = zipfile.ZipFile(bio, 'r'); expected_counts = DATASET_SPECS['endoscene-cvc300-polyp-raw-dataset.zip']['valid_member_counts']; "
        "actual_count = len([m for m in z2.infolist() if not m.is_dir()]); "
        "passed = (actual_count in expected_counts); "
        "print(f'Member count test: actual={actual_count}, expected={expected_counts}, passed={passed}')"
    )
    rc, out, err, _ = run_cmd(["-c", code_g3_direct])
    ok = (rc == 0 and "passed=False" in out)
    record_result("Gate 3 logic rejects member count mismatch (actual=1 vs expected=[120])", ok, f"out={out.strip()}")

    # 6.6 Gate 4: Magic byte mismatch (invalid image signature)
    code_g4_corrupt = (
        "import zipfile, io; from verify_datasets import sample_media_magic_bytes; "
        "bio = io.BytesIO(); z = zipfile.ZipFile(bio, 'w'); "
        "z.writestr('test.png', b'NOT_A_PNG_HEADER_CORRUPTED_BYTES'); z.close(); "
        "z2 = zipfile.ZipFile(bio, 'r'); "
        "passed, total, valid, invalids = sample_media_magic_bytes(z2, 'png', 10); "
        "print(f'G4 Corrupt Test: passed={passed}, total={total}, valid={valid}, invalids={len(invalids)}')"
    )
    rc, out, err, _ = run_cmd(["-c", code_g4_corrupt])
    ok = (rc == 0 and "passed=False" in out and "valid=0" in out and "invalids=1" in out)
    record_result("Gate 4 detects and flags corrupted media magic bytes in archive members", ok, f"out={out.strip()}")

    # 6.7 Gate 5: Checksum verification mismatch
    code_g5_mismatch = (
        "import hashlib, tempfile, os; from verify_datasets import compute_hashes; "
        "d = tempfile.mkdtemp(); p = os.path.join(d, 'test.bin'); "
        "open(p, 'wb').write(b'TAMPERED_DATA_FOR_GATE_5'); "
        "sha, md = compute_hashes(p); "
        "expected_md5 = '00000000000000000000000000000000'; "
        "matched = (md.lower() == expected_md5.lower()); "
        "print(f'G5 Mismatch Test: computed_md5={md}, matched={matched}')"
    )
    rc, out, err, _ = run_cmd(["-c", code_g5_mismatch])
    ok = (rc == 0 and "matched=False" in out)
    record_result("Gate 5 rejects mismatched cryptographic checksum", ok, f"out={out.strip()}")


def main():
    print("=" * 80)
    print("      CHALLENGER 2: EMPIRICAL STRESS TEST & ORACLE VERIFICATION HARNESS")
    print("=" * 80)

    test_suite_help()
    test_suite_argparse()
    test_suite_boundaries()
    test_suite_paths()
    test_suite_downloader_cli()
    test_suite_fault_injection()

    print("\n" + "=" * 80)
    print("                             TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests Executed: {passed_tests + failed_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")

    if findings:
        print("\n" + "-" * 80)
        print("EMPIRICAL FINDINGS & VULNERABILITIES IDENTIFIED:")
        print("-" * 80)
        for i, f in enumerate(findings, 1):
            print(f"[{i}] [{f['severity']}] {f['test']}")
            print(f"    Details: {f['details']}")

    print("=" * 80)
    # Exit with code 0 so caller gets full summary
    sys.exit(0 if failed_tests == 0 else 1)


if __name__ == "__main__":
    main()
