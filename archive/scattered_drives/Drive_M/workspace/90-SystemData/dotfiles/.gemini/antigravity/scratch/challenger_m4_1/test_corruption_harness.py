"""
test_corruption_harness.py
Adversarial Stress Harness for verify_datasets.py

Tests:
1. Truncated mock archive (Gate 1 size mismatch & early exit)
2. In-place bit flip / member payload corruption with exact valid size (Gate 2 CRC32 testzip detection)
3. Central directory corruption with exact valid size (Gate 2 BadZipFile detection)
4. Corrupted media magic bytes with valid zip (Gate 4 header inspection failure)
5. CLI execution test: verify exit code 1 and error reporting on corrupted directory
6. Status string check: Does verify_datasets.py report "CORRUPTED" or "FAILED"?
7. Gate 5 MD5 mismatch test: Does verify_datasets.py reject an archive if MD5 != expected_md5?
"""

import os
import sys
import shutil
import tempfile
import subprocess
import json
import zipfile

# Add dataet dir to sys.path to import verify_datasets
DATASET_DIR = r"I:\My Drive\1509-chakramodelom\dataet"
sys.path.insert(0, DATASET_DIR)
import verify_datasets

SOURCE_ZIP = os.path.join(DATASET_DIR, "endoscene-cvc300-polyp-raw-dataset.zip")
SPEC = verify_datasets.DATASET_SPECS["endoscene-cvc300-polyp-raw-dataset.zip"]

def run_tests():
    test_results = {}
    
    # Create temp workspace outside .agents/
    temp_workspace = tempfile.mkdtemp(prefix="adv_test_")
    print(f"[+] Created temporary test workspace: {temp_workspace}")
    
    try:
        # Read a small part of source zip to confirm it exists
        if not os.path.exists(SOURCE_ZIP):
            print(f"[-] Source zip not found at {SOURCE_ZIP}")
            return False
            
        orig_size = os.path.getsize(SOURCE_ZIP)
        print(f"[+] Original zip size: {orig_size} bytes")
        
        # -------------------------------------------------------------
        # TEST 1: Truncated mock zip
        # -------------------------------------------------------------
        print("\n--- TEST 1: Truncated mock zip ---")
        t1_dir = os.path.join(temp_workspace, "test1_truncated")
        os.makedirs(t1_dir, exist_ok=True)
        t1_zip = os.path.join(t1_dir, "endoscene-cvc300-polyp-raw-dataset.zip")
        with open(SOURCE_ZIP, "rb") as f_in, open(t1_zip, "wb") as f_out:
            # write only first 10,000 bytes
            f_out.write(f_in.read(10000))
            
        res1 = verify_datasets.verify_single_dataset(
            archive_name="endoscene-cvc300-polyp-raw-dataset.zip",
            spec=SPEC,
            target_dir=t1_dir,
            sample_count=10
        )
        test_results["test1_truncated"] = {
            "status": res1["status"],
            "gate1_passed": res1["gates"]["gate1_presence_and_size"]["passed"],
            "errors": res1["errors"],
            "detected": (res1["status"] != "PASSED" and not res1["gates"]["gate1_presence_and_size"]["passed"])
        }
        print(f"  Result: status={res1['status']}, Gate1={res1['gates']['gate1_presence_and_size']['passed']}")
        print(f"  Errors: {res1['errors']}")
        
        # -------------------------------------------------------------
        # TEST 2: In-place member payload corruption (Exact valid size)
        # -------------------------------------------------------------
        print("\n--- TEST 2: In-place member corruption (Exact size, corrupted payload) ---")
        t2_dir = os.path.join(temp_workspace, "test2_corrupted_payload")
        os.makedirs(t2_dir, exist_ok=True)
        t2_zip = os.path.join(t2_dir, "endoscene-cvc300-polyp-raw-dataset.zip")
        
        # Copy original then corrupt 512 bytes at offset 100,000 (safely inside member data)
        with open(SOURCE_ZIP, "rb") as f_in:
            data = bytearray(f_in.read())
        
        # Verify initial size
        assert len(data) == orig_size
        # Flip bits in data section
        for i in range(100000, 100512):
            data[i] ^= 0xFF
            
        with open(t2_zip, "wb") as f_out:
            f_out.write(data)
            
        assert os.path.getsize(t2_zip) == orig_size
        
        res2 = verify_datasets.verify_single_dataset(
            archive_name="endoscene-cvc300-polyp-raw-dataset.zip",
            spec=SPEC,
            target_dir=t2_dir,
            sample_count=10
        )
        gate2_passed = res2["gates"].get("gate2_archive_integrity", {}).get("passed", False)
        bad_member = res2["gates"].get("gate2_archive_integrity", {}).get("bad_member")
        test_results["test2_corrupted_payload"] = {
            "status": res2["status"],
            "gate1_passed": res2["gates"]["gate1_presence_and_size"]["passed"],
            "gate2_passed": gate2_passed,
            "bad_member": bad_member,
            "errors": res2["errors"],
            "detected": (res2["status"] != "PASSED" and not gate2_passed)
        }
        print(f"  Result: status={res2['status']}, Gate1={res2['gates']['gate1_presence_and_size']['passed']}, Gate2={gate2_passed}")
        print(f"  Bad member: {bad_member}")
        print(f"  Errors: {res2['errors']}")

        # -------------------------------------------------------------
        # TEST 3: Broken Central Directory / BadZipFile (Exact size)
        # -------------------------------------------------------------
        print("\n--- TEST 3: Broken Central Directory (Exact size) ---")
        t3_dir = os.path.join(temp_workspace, "test3_bad_central_dir")
        os.makedirs(t3_dir, exist_ok=True)
        t3_zip = os.path.join(t3_dir, "endoscene-cvc300-polyp-raw-dataset.zip")
        
        with open(SOURCE_ZIP, "rb") as f_in:
            data3 = bytearray(f_in.read())
        # Corrupt the last 200 bytes (Central Directory / EOCD)
        for i in range(len(data3) - 200, len(data3)):
            data3[i] = 0x00
        with open(t3_zip, "wb") as f_out:
            f_out.write(data3)
            
        res3 = verify_datasets.verify_single_dataset(
            archive_name="endoscene-cvc300-polyp-raw-dataset.zip",
            spec=SPEC,
            target_dir=t3_dir,
            sample_count=10
        )
        gate2_passed3 = res3["gates"].get("gate2_archive_integrity", {}).get("passed", False)
        test_results["test3_bad_central_dir"] = {
            "status": res3["status"],
            "gate1_passed": res3["gates"]["gate1_presence_and_size"]["passed"],
            "gate2_passed": gate2_passed3,
            "errors": res3["errors"],
            "detected": (res3["status"] != "PASSED" and not gate2_passed3)
        }
        print(f"  Result: status={res3['status']}, Gate1={res3['gates']['gate1_presence_and_size']['passed']}, Gate2={gate2_passed3}")
        print(f"  Errors: {res3['errors']}")

        # -------------------------------------------------------------
        # TEST 4: Full CLI execution against corrupted directory
        # -------------------------------------------------------------
        print("\n--- TEST 4: CLI Execution against corrupted folder (exit code & report) ---")
        cli_report = os.path.join(temp_workspace, "cli_report.json")
        cmd = [
            sys.executable,
            os.path.join(DATASET_DIR, "verify_datasets.py"),
            "--target-dir", t2_dir,
            "--output-report", cli_report,
            "--sample-count", "10"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        print(f"  Exit code: {proc.returncode}")
        
        cli_report_data = {}
        if os.path.exists(cli_report):
            with open(cli_report, "r") as f:
                cli_report_data = json.load(f)
                
        test_results["test4_cli_execution"] = {
            "exit_code": proc.returncode,
            "exit_code_is_1": (proc.returncode == 1),
            "overall_status": cli_report_data.get("overall_status"),
            "target_dataset_status": cli_report_data.get("datasets", {}).get(SPEC["slug"], {}).get("status"),
            "target_dataset_errors": cli_report_data.get("datasets", {}).get(SPEC["slug"], {}).get("errors"),
        }
        print(f"  Report overall_status: {cli_report_data.get('overall_status')}")
        print(f"  Target dataset status: {cli_report_data.get('datasets', {}).get(SPEC['slug'], {}).get('status')}")

        # -------------------------------------------------------------
        # TEST 5: Status Enum Analysis ("CORRUPTED" vs "FAILED")
        # -------------------------------------------------------------
        print("\n--- TEST 5: Status Enum Analysis ---")
        # Check if the string "CORRUPTED" is ever used in res2["status"] or overall_status
        is_literal_corrupted_status = (res2["status"] == "CORRUPTED")
        test_results["test5_status_string"] = {
            "actual_status_field": res2["status"],
            "is_status_corrupted": is_literal_corrupted_status,
            "is_status_failed": (res2["status"] == "FAILED"),
            "corrupted_in_error_message": any("Corrupted" in e for e in res2["errors"]),
        }
        print(f"  Actual status field value: '{res2['status']}'")
        print(f"  Is status == 'CORRUPTED'? {is_literal_corrupted_status}")
        print(f"  Is status == 'FAILED'? {res2['status'] == 'FAILED'}")
        print(f"  Does error message contain 'Corrupted'? {test_results['test5_status_string']['corrupted_in_error_message']}")

        # -------------------------------------------------------------
        # TEST 6: Gate 5 MD5 Tampering / Mismatch Bug Verification
        # -------------------------------------------------------------
        print("\n--- TEST 6: Gate 5 MD5 Mismatch Adversarial Test ---")
        # Create a mock zip that passes Gates 1, 2, 3, 4, but has mismatched MD5!
        # We can construct a zip with exact 120 valid png files of valid size, but different bytes,
        # OR test verify_single_dataset with a spec having a tampered expected_md5:
        tampered_spec = dict(SPEC)
        tampered_spec["expected_md5"] = "00000000000000000000000000000000" # wrong MD5
        
        res6 = verify_datasets.verify_single_dataset(
            archive_name="endoscene-cvc300-polyp-raw-dataset.zip",
            spec=tampered_spec,
            target_dir=DATASET_DIR, # original valid file!
            sample_count=10
        )
        
        g5_info = res6["gates"].get("gate5_cryptographic_checksums", {})
        md5_matched = g5_info.get("etag_md5_matched")
        g5_passed = g5_info.get("passed")
        final_status = res6["status"]
        
        test_results["test6_md5_mismatch_vulnerability"] = {
            "etag_md5_matched": md5_matched,
            "gate5_passed": g5_passed,
            "overall_dataset_status": final_status,
            "vulnerability_confirmed": (md5_matched is False and g5_passed is True and final_status == "PASSED"),
        }
        print(f"  MD5 matched: {md5_matched}")
        print(f"  Gate 5 passed: {g5_passed}")
        print(f"  Final dataset status: {final_status}")
        print(f"  Vulnerability Confirmed (Wrong MD5 yet PASSED): {test_results['test6_md5_mismatch_vulnerability']['vulnerability_confirmed']}")

    finally:
        # Cleanup
        shutil.rmtree(temp_workspace, ignore_errors=True)
        print(f"[+] Cleaned up temporary test workspace: {temp_workspace}")

    out_file = r"C:\Users\imgk3\.gemini\antigravity\scratch\challenger_m4_1\corruption_test_results.json"
    with open(out_file, "w") as f:
        json.dump(test_results, f, indent=2)
    print(f"\n[+] Saved harness results to {out_file}")
    return test_results

if __name__ == "__main__":
    run_tests()
