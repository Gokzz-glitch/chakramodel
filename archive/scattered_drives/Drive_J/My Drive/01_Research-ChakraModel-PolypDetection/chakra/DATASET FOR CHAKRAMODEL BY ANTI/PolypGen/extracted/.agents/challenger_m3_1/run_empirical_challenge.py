#!/usr/bin/env python3
"""
Empirical Challenge & Adversarial Test Harness for verify_polypgen.py
Author: Challenger 1 (Milestone 3)
Date: September 2026

Executes rigorous adversarial stress tests against verify_polypgen.py,
testing corruption detection, false positive resistance, empty directory auditing,
thread safety, and error handling.
"""

import concurrent.futures
from dataclasses import asdict
import json
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile
import time
from typing import Dict, List, Any

# Ensure target script can be imported
sys.path.insert(0, r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted")
from verify_polypgen import PolypGenVerifier, ImageVerificationResult

class EmpiricalChallengerHarness:
    def __init__(self):
        self.work_dir = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\.agents\challenger_m3_1")
        self.fixtures_dir = self.work_dir / "fixtures" / "isolated_samples"
        self.mock_dataset_dir = self.work_dir / "fixtures" / "mock_dataset"
        self.real_dataset_root = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")
        self.results: Dict[str, Any] = {}
        self.verifier = PolypGenVerifier(
            target_dir=r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted",
            output_json=str(self.work_dir / "test_run_summary.json"),
            output_md=str(self.work_dir / "test_run_report.md"),
            max_workers=4
        )

    def log(self, msg: str):
        print(f"[TEST HARNESS] {msg}", flush=True)

    def test_01_truncated_jpeg(self) -> Dict[str, Any]:
        self.log("--- Running Test 01: Truncated / Cut-off JPEG ---")
        p = self.fixtures_dir / "truncated_cutoff.jpg"
        assert p.exists(), f"Fixture missing: {p}"
        res = self.verifier.verify_single_image(p)
        passed = (not res.is_valid) and (res.tier_failed == "TIER2_DECOMPRESSION_FAILED") and ("truncated" in res.error_message.lower())
        record = {
            "test_name": "test_01_truncated_jpeg",
            "file": str(p),
            "size_bytes": p.stat().st_size,
            "is_valid": res.is_valid,
            "tier_failed": res.tier_failed,
            "error_message": res.error_message,
            "pass_verdict": passed
        }
        self.log(f"  Result: is_valid={res.is_valid}, tier={res.tier_failed}, error={res.error_message} -> {'PASS' if passed else 'FAIL'}")
        return record

    def test_02_zero_byte_file(self) -> Dict[str, Any]:
        self.log("--- Running Test 02: 0-Byte File ---")
        p = self.fixtures_dir / "zero_byte.jpg"
        assert p.exists(), f"Fixture missing: {p}"
        res = self.verifier.verify_single_image(p)
        passed = (not res.is_valid) and (res.tier_failed == "TIER0_ZERO_BYTE") and ("0 bytes" in res.error_message)
        record = {
            "test_name": "test_02_zero_byte_file",
            "file": str(p),
            "size_bytes": p.stat().st_size,
            "is_valid": res.is_valid,
            "tier_failed": res.tier_failed,
            "error_message": res.error_message,
            "pass_verdict": passed
        }
        self.log(f"  Result: is_valid={res.is_valid}, tier={res.tier_failed}, error={res.error_message} -> {'PASS' if passed else 'FAIL'}")
        return record

    def test_03_random_garbage_bytes(self) -> Dict[str, Any]:
        self.log("--- Running Test 03: Random Garbage Bytes ---")
        p = self.fixtures_dir / "random_garbage.jpg"
        assert p.exists(), f"Fixture missing: {p}"
        res = self.verifier.verify_single_image(p)
        passed = (not res.is_valid) and (res.tier_failed == "TIER1_UNIDENTIFIED_IMAGE")
        record = {
            "test_name": "test_03_random_garbage_bytes",
            "file": str(p),
            "size_bytes": p.stat().st_size,
            "is_valid": res.is_valid,
            "tier_failed": res.tier_failed,
            "error_message": res.error_message,
            "pass_verdict": passed
        }
        self.log(f"  Result: is_valid={res.is_valid}, tier={res.tier_failed}, error={res.error_message} -> {'PASS' if passed else 'FAIL'}")
        return record

    def test_04_corrupted_end_bytes(self) -> Dict[str, Any]:
        self.log("--- Running Test 04: Corrupted End Bytes ---")
        p = self.fixtures_dir / "corrupted_end_bytes.jpg"
        assert p.exists(), f"Fixture missing: {p}"
        res = self.verifier.verify_single_image(p)
        passed = (not res.is_valid) and (res.tier_failed == "TIER2_DECOMPRESSION_FAILED")
        record = {
            "test_name": "test_04_corrupted_end_bytes",
            "file": str(p),
            "size_bytes": p.stat().st_size,
            "is_valid": res.is_valid,
            "tier_failed": res.tier_failed,
            "error_message": res.error_message,
            "pass_verdict": passed
        }
        self.log(f"  Result: is_valid={res.is_valid}, tier={res.tier_failed}, error={res.error_message} -> {'PASS' if passed else 'FAIL'}")
        return record

    def test_05_corrupted_middle_bytes(self) -> Dict[str, Any]:
        self.log("--- Running Test 05: Corrupted Middle Bytes (Dual-Scenario) ---")
        
        # Scenario 5A: Middle bytes with invalid marker sequence (0xFF 0x25)
        # Sourced from mock_dataset
        p_marker = self.mock_dataset_dir / "PolypGen2021_MultiCenterData_v3" / "data_C1" / "images_C1" / "sample_05_corrupt_mid.jpg"
        res_marker = self.verifier.verify_single_image(p_marker)
        passed_marker = (not res_marker.is_valid) and (res_marker.tier_failed == "TIER2_DECOMPRESSION_FAILED")

        # Scenario 5B: Middle bytes overwritten with zero/random bytes (no invalid marker)
        p_subtle = self.fixtures_dir / "corrupted_middle_bytes.jpg"
        res_subtle = self.verifier.verify_single_image(p_subtle)
        # This was empirically found to bypass PIL load() and OpenCV imread()
        passed_subtle = (not res_subtle.is_valid)

        record = {
            "test_name": "test_05_corrupted_middle_bytes",
            "scenario_5A_invalid_marker": {
                "file": str(p_marker),
                "is_valid": res_marker.is_valid,
                "tier_failed": res_marker.tier_failed,
                "error_message": res_marker.error_message,
                "pass_verdict": passed_marker
            },
            "scenario_5B_entropy_corruption_no_marker": {
                "file": str(p_subtle),
                "is_valid": res_subtle.is_valid,
                "tier_failed": res_subtle.tier_failed,
                "error_message": res_subtle.error_message,
                "pass_verdict": passed_subtle,
                "note": "EMPIRICAL FINDING: libjpeg warning 'Corrupt JPEG data: premature end of data segment' printed to stderr, but PIL load() and cv2.imread() do not raise or return None. Detected as FALSE NEGATIVE bypass."
            }
        }
        self.log(f"  Scenario 5A (invalid marker): is_valid={res_marker.is_valid}, tier={res_marker.tier_failed} -> {'PASS' if passed_marker else 'FAIL'}")
        self.log(f"  Scenario 5B (scan entropy corruption): is_valid={res_subtle.is_valid}, tier={res_subtle.tier_failed} -> {'PASS' if passed_subtle else 'FAIL (VULNERABILITY CONFIRMED)'}")
        return record

    def test_06_empty_directory_audit(self) -> Dict[str, Any]:
        self.log("--- Running Test 06: Empty Directory Auditing & .agents Bypass Vulnerability ---")
        
        # Test 6A: Path containing .agents (mock_dataset)
        v_agents = PolypGenVerifier(
            target_dir=str(self.mock_dataset_dir),
            output_json=str(self.work_dir / "dummy.json"),
            output_md=str(self.work_dir / "dummy.md")
        )
        v_agents.audit_filesystem_and_empty_dirs()
        empty_in_agents = list(v_agents.empty_directories)

        # Test 6B: Path outside .agents (isolated temp directory)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_p = Path(tmpdir)
            (tmp_p / "populated_dir").mkdir()
            (tmp_p / "populated_dir" / "file.txt").write_text("content")
            (tmp_p / "empty_dir_1").mkdir()
            (tmp_p / "nested" / "empty_dir_2").mkdir(parents=True)
            v_clean = PolypGenVerifier(
                target_dir=str(tmp_p),
                output_json=str(self.work_dir / "dummy.json"),
                output_md=str(self.work_dir / "dummy.md")
            )
            v_clean.audit_filesystem_and_empty_dirs()
            empty_clean = list(v_clean.empty_directories)

        record = {
            "test_name": "test_06_empty_directory_audit",
            "scenario_6A_inside_agents_path": {
                "target_dir": str(self.mock_dataset_dir),
                "empty_dirs_found_count": len(empty_in_agents),
                "empty_dirs_list": empty_in_agents,
                "vulnerability_reproduced": (len(empty_in_agents) == 0),
                "explanation": "verify_polypgen.py line 313 executes 'if \".agents\" in Path(root).parts: continue'. Because target_dir contains .agents in its absolute path, os.walk skips every directory, finding 0 empty dirs."
            },
            "scenario_6B_clean_path": {
                "empty_dirs_found_count": len(empty_clean),
                "empty_dirs_list": empty_clean,
                "logic_verified": (len(empty_clean) == 2)
            }
        }
        self.log(f"  Scenario 6A (.agents in path): found {len(empty_in_agents)} empty dirs (Bypass confirmed)")
        self.log(f"  Scenario 6B (clean path): found {len(empty_clean)} empty dirs (Logic verified)")
        return record

    def test_07_false_positive_rate(self) -> Dict[str, Any]:
        self.log("--- Running Test 07: False Positive Rate on Legitimate Images (215 Samples) ---")
        random.seed(42)
        sample_targets = []

        # Centers C1 to C6 images and masks
        for c in range(1, 7):
            c_dir = self.real_dataset_root / f"data_C{c}"
            imgs = list((c_dir / f"images_C{c}").glob("*.jpg"))
            masks = list((c_dir / f"masks_C{c}").glob("*.jpg"))
            sample_targets.extend(random.sample(imgs, min(10, len(imgs))))
            sample_targets.extend(random.sample(masks, min(10, len(masks))))

        # sequenceData/negativeOnly
        neg_dirs = list((self.real_dataset_root / "sequenceData" / "negativeOnly").iterdir())
        for nd in random.sample(neg_dirs, min(5, len(neg_dirs))):
            neg_frames = list(nd.glob("*.jpg"))
            sample_targets.extend(random.sample(neg_frames, min(5, len(neg_frames))))

        # sequenceData/positive
        pos_dirs = [d for d in (self.real_dataset_root / "sequenceData" / "positive").iterdir() if d.is_dir()]
        for pd in random.sample(pos_dirs, min(5, len(pos_dirs))):
            s_imgs = list((pd / f"images_{pd.name}").glob("*.jpg"))
            s_masks = list((pd / f"masks_{pd.name}").glob("*.jpg"))
            sample_targets.extend(random.sample(s_imgs, min(5, len(s_imgs))))
            sample_targets.extend(random.sample(s_masks, min(5, len(s_masks))))

        # imagesAll_positive
        all_pos = list((self.real_dataset_root / "imagesAll_positive").glob("*.jpg"))
        sample_targets.extend(random.sample(all_pos, min(20, len(all_pos))))

        t0 = time.perf_counter()
        failures = []
        for p in sample_targets:
            res = self.verifier.verify_single_image(p)
            if not res.is_valid:
                failures.append({"path": str(p), "tier": res.tier_failed, "error": res.error_message})
        elapsed = time.perf_counter() - t0

        record = {
            "test_name": "test_07_false_positive_rate",
            "samples_tested": len(sample_targets),
            "false_positives_count": len(failures),
            "false_positive_rate": len(failures) / len(sample_targets),
            "elapsed_seconds": round(elapsed, 2),
            "failures": failures,
            "pass_verdict": (len(failures) == 0)
        }
        self.log(f"  Tested {len(sample_targets)} images in {elapsed:.2f}s: Failures={len(failures)} -> {'PASS (0% FP)' if len(failures) == 0 else 'FAIL'}")
        return record

    def test_08_batch_concurrency_stress(self) -> Dict[str, Any]:
        self.log("--- Running Test 08: Batch Concurrency & Thread-Safety Stress Test ---")
        # Build batch of 50 images: 40 valid images + 10 corrupt fixtures
        valid_sample = self.fixtures_dir / "valid_baseline.jpg"
        corrupt_samples = [
            self.fixtures_dir / "zero_byte.jpg",
            self.fixtures_dir / "random_garbage.jpg",
            self.fixtures_dir / "truncated_cutoff.jpg",
            self.fixtures_dir / "corrupted_end_bytes.jpg",
            self.mock_dataset_dir / "PolypGen2021_MultiCenterData_v3" / "data_C1" / "images_C1" / "sample_05_corrupt_mid.jpg"
        ]

        batch = [valid_sample] * 40 + corrupt_samples * 2  # Total 50 images, exactly 10 corrupt
        random.seed(99)
        random.shuffle(batch)

        v_batch = PolypGenVerifier(
            target_dir=str(self.work_dir),
            output_json=str(self.work_dir / "dummy.json"),
            output_md=str(self.work_dir / "dummy.md"),
            max_workers=12
        )

        t0 = time.perf_counter()
        results = v_batch.verify_batch(batch, "StressTestBatch")
        elapsed = time.perf_counter() - t0

        passed_count = sum(1 for r in results if r.is_valid)
        corrupted_count = sum(1 for r in results if not r.is_valid)

        success = (len(results) == 50 and passed_count == 40 and corrupted_count == 10)
        record = {
            "test_name": "test_08_batch_concurrency_stress",
            "total_batch_size": len(batch),
            "expected_passed": 40,
            "observed_passed": passed_count,
            "expected_corrupted": 10,
            "observed_corrupted": corrupted_count,
            "elapsed_seconds": round(elapsed, 3),
            "throughput_img_per_sec": round(len(batch) / max(0.001, elapsed), 1),
            "pass_verdict": success
        }
        self.log(f"  Concurrency test (12 workers): Passed={passed_count}/40, Corrupt={corrupted_count}/10 in {elapsed:.3f}s -> {'PASS' if success else 'FAIL'}")
        return record

    def test_09_cli_missing_center_crash_analysis(self) -> Dict[str, Any]:
        self.log("--- Running Test 09: CLI Missing Center Crash Analysis ---")
        # Reproduces unhandled KeyError when a center directory is absent
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            c1 = p / "data_C1"
            (c1 / "images_C1").mkdir(parents=True)
            (c1 / "masks_C1").mkdir(parents=True)
            (c1 / "bbox_C1").mkdir(parents=True)
            (c1 / "bbox_image_C1").mkdir(parents=True)
            
            # Put 1 valid image
            src = self.fixtures_dir / "valid_baseline.jpg"
            (c1 / "images_C1" / "test.jpg").write_bytes(src.read_bytes())
            (c1 / "masks_C1" / "test_mask.jpg").write_bytes(src.read_bytes())

            v_crash = PolypGenVerifier(
                target_dir=str(p),
                output_json=str(self.work_dir / "dummy.json"),
                output_md=str(self.work_dir / "dummy.md")
            )
            v_crash.audit_filesystem_and_empty_dirs()
            v_crash.verify_single_frame_centers()
            
            crashed = False
            crash_error = ""
            try:
                v_crash.generate_reports()
            except KeyError as e:
                crashed = True
                crash_error = f"KeyError: {e}"

        record = {
            "test_name": "test_09_cli_missing_center_crash_analysis",
            "crashed": crashed,
            "crash_exception": crash_error,
            "vulnerability_confirmed": crashed,
            "root_cause": "render_markdown_report assumes every center in self.center_results has 'images_count', but missing centers only record {'status': 'FAIL_DIR_MISSING'}"
        }
        self.log(f"  Missing Center Crash Analysis: crashed={crashed} ({crash_error}) -> {'VULNERABILITY CONFIRMED' if crashed else 'ROBUST'}")
        return record

    def run_all(self):
        self.log("==================================================================")
        self.log("Starting Empirical Challenger Test Suite for Milestone 3")
        self.log("==================================================================")
        
        self.results["test_01"] = self.test_01_truncated_jpeg()
        self.results["test_02"] = self.test_02_zero_byte_file()
        self.results["test_03"] = self.test_03_random_garbage_bytes()
        self.results["test_04"] = self.test_04_corrupted_end_bytes()
        self.results["test_05"] = self.test_05_corrupted_middle_bytes()
        self.results["test_06"] = self.test_06_empty_directory_audit()
        self.results["test_07"] = self.test_07_false_positive_rate()
        self.results["test_08"] = self.test_08_batch_concurrency_stress()
        self.results["test_09"] = self.test_09_cli_missing_center_crash_analysis()

        # Save test results JSON
        out_path = self.work_dir / "empirical_challenge_results.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)
        self.log(f"Saved full test suite results to: {out_path}")

        self.log("==================================================================")
        self.log("All empirical tests executed.")
        self.log("==================================================================")

if __name__ == "__main__":
    harness = EmpiricalChallengerHarness()
    harness.run_all()
