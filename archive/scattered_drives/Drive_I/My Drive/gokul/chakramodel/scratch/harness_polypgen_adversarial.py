"""
harness_polypgen_adversarial.py - Adversarial Stress Test Harness for verify_polypgen_integrity.py

Author: Challenger PG 1 (Empirical Challenger)
Target: m:\\chakramodel\\verify_polypgen_integrity.py
Scratch root: m:\\chakramodel\\scratch\\polypgen_adversarial_suite
"""

import os
import sys
import io
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(r"m:\chakramodel").resolve()
VERIFY_SCRIPT = PROJECT_ROOT / "verify_polypgen_integrity.py"
SCRATCH_ROOT = PROJECT_ROOT / "scratch" / "polypgen_adversarial_suite"


def create_valid_jpeg(path: Path, width=200, height=200, color=(120, 150, 180)):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=color)
    img.save(path, format="JPEG", quality=90)


def create_valid_mask(path: Path, width=200, height=200):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("L", (width, height), color=0)
    # Draw a non-zero polyp region so extrema[1] > 0
    for x in range(50, 100):
        for y in range(50, 100):
            img.putpixel((x, y), 255)
    img.save(path, format="JPEG", quality=90)


def create_base_dataset(root_dir: Path):
    """Creates a minimal valid PolypGen dataset structure."""
    if root_dir.exists():
        shutil.rmtree(root_dir)
    root_dir.mkdir(parents=True, exist_ok=True)

    # Center C1
    c1_img = root_dir / "data_C1" / "images_C1" / "c1_frame_001.jpg"
    c1_mask = root_dir / "data_C1" / "masks_C1" / "c1_frame_001_mask.jpg"
    c1_overlay = root_dir / "data_C1" / "bbox_image_C1" / "c1_frame_001_mask_bbox.jpg"
    c1_bbox = root_dir / "data_C1" / "bbox_C1" / "c1_frame_001_mask.txt"

    create_valid_jpeg(c1_img, 200, 200, (100, 150, 200))
    create_valid_mask(c1_mask, 200, 200)
    create_valid_jpeg(c1_overlay, 200, 200, (100, 150, 200))
    c1_bbox.parent.mkdir(parents=True, exist_ok=True)
    c1_bbox.write_text("polyp 20 20 80 80\n", encoding="utf-8")

    # Sequence structure required by resolve_dataset_root
    seq_pos = root_dir / "sequenceData" / "positive"
    seq_neg = root_dir / "sequenceData" / "negativeOnly"
    seq_pos.mkdir(parents=True, exist_ok=True)
    seq_neg.mkdir(parents=True, exist_ok=True)

    # Pooled positive directory required by reconciliation
    pooled_img = root_dir / "imagesAll_positive" / "c1_frame_001.jpg"
    create_valid_jpeg(pooled_img, 200, 200, (100, 150, 200))


def run_verification(dataset_dir: Path, report_json: Path):
    cmd = [
        sys.executable,
        str(VERIFY_SCRIPT),
        "--data-dir", str(dataset_dir),
        "--json-report", str(report_json),
        "--workers", "4",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    report_data = None
    if report_json.exists():
        try:
            with open(report_json, "r", encoding="utf-8") as f:
                report_data = json.load(f)
        except Exception as e:
            report_data = {"read_error": str(e)}

    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "report": report_data,
    }


def main():
    print(f"[*] Initializing Adversarial Stress Harness under: {SCRATCH_ROOT}")
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)

    scenarios = {}

    # Scenario 0: Baseline Control (100% Valid)
    print("\n--- Scenario 0: Baseline Valid Control ---")
    s0_dir = SCRATCH_ROOT / "s0_baseline_valid"
    create_base_dataset(s0_dir)
    s0_report = SCRATCH_ROOT / "s0_report.json"
    res0 = run_verification(s0_dir, s0_report)
    scenarios["s0_baseline_valid"] = {
        "description": "Baseline 100% valid synthetic dataset",
        "expected_pass": True,
        "returncode": res0["returncode"],
        "stdout_tail": res0["stdout"].splitlines()[-10:] if res0["stdout"] else [],
        "stderr": res0["stderr"],
        "verdict": res0["report"].get("verdict") if res0["report"] else None,
        "corrupted_count": res0["report"].get("deep_corruption_scan", {}).get("total_corrupted") if res0["report"] else None,
    }
    print(f"Returncode: {res0['returncode']} | Verdict: {scenarios['s0_baseline_valid']['verdict']}")

    # Scenario 1 (Task 2a): 0-byte Image File (.jpg)
    print("\n--- Scenario 1: 0-byte Image File ---")
    s1_dir = SCRATCH_ROOT / "s1_zero_byte"
    create_base_dataset(s1_dir)
    # Inject 0-byte file in images_C1
    bad_file = s1_dir / "data_C1" / "images_C1" / "c1_zero_byte.jpg"
    bad_file.write_bytes(b"")
    # Add dummy matching mask and bbox and pooled so structural check doesn't crash before scan
    create_valid_mask(s1_dir / "data_C1" / "masks_C1" / "c1_zero_byte_mask.jpg")
    (s1_dir / "data_C1" / "bbox_C1" / "c1_zero_byte_mask.txt").write_text("polyp 10 10 50 50\n")
    create_valid_jpeg(s1_dir / "imagesAll_positive" / "c1_zero_byte.jpg")
    s1_report = SCRATCH_ROOT / "s1_report.json"
    res1 = run_verification(s1_dir, s1_report)
    corr_list = res1["report"].get("deep_corruption_scan", {}).get("corrupted_files", []) if res1["report"] else []
    scenarios["s1_zero_byte"] = {
        "description": "0-byte image file (.jpg)",
        "expected_pass": False,
        "returncode": res1["returncode"],
        "verdict": res1["report"].get("verdict") if res1["report"] else None,
        "corrupted_count": len(corr_list),
        "corrupted_details": corr_list,
        "stderr": res1["stderr"],
    }
    print(f"Returncode: {res1['returncode']} | Corrupted files detected: {len(corr_list)}")

    # Scenario 2 (Task 2b): Truncated Image File (header intact, data stream cut short)
    print("\n--- Scenario 2: Truncated Image File ---")
    s2_dir = SCRATCH_ROOT / "s2_truncated"
    create_base_dataset(s2_dir)
    trunc_file = s2_dir / "data_C1" / "images_C1" / "c1_truncated.jpg"
    # Create valid JPEG in memory
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (220, 100, 50)).save(buf, format="JPEG", quality=95)
    valid_bytes = buf.getvalue()
    # Truncate at ~25% of length (keeps SOI header and quantization tables, cuts entropy data before EOI)
    trunc_bytes = valid_bytes[: len(valid_bytes) // 4]
    trunc_file.write_bytes(trunc_bytes)
    create_valid_mask(s2_dir / "data_C1" / "masks_C1" / "c1_truncated_mask.jpg")
    (s2_dir / "data_C1" / "bbox_C1" / "c1_truncated_mask.txt").write_text("polyp 10 10 50 50\n")
    create_valid_jpeg(s2_dir / "imagesAll_positive" / "c1_truncated.jpg")
    s2_report = SCRATCH_ROOT / "s2_report.json"
    res2 = run_verification(s2_dir, s2_report)
    corr_list = res2["report"].get("deep_corruption_scan", {}).get("corrupted_files", []) if res2["report"] else []
    scenarios["s2_truncated"] = {
        "description": "Truncated image file (header intact, data stream cut short)",
        "expected_pass": False,
        "returncode": res2["returncode"],
        "verdict": res2["report"].get("verdict") if res2["report"] else None,
        "corrupted_count": len(corr_list),
        "corrupted_details": corr_list,
        "stderr": res2["stderr"],
    }
    print(f"Returncode: {res2['returncode']} | Corrupted files detected: {len(corr_list)}")

    # Scenario 3 (Task 2c): Completely Garbage Binary disguised as .jpg
    print("\n--- Scenario 3: Completely Garbage Binary ---")
    s3_dir = SCRATCH_ROOT / "s3_garbage_binary"
    create_base_dataset(s3_dir)
    garbage_file = s3_dir / "data_C1" / "images_C1" / "c1_garbage.jpg"
    garbage_file.write_bytes(b"\xDE\xAD\xBE\xEF" * 1024)
    create_valid_mask(s3_dir / "data_C1" / "masks_C1" / "c1_garbage_mask.jpg")
    (s3_dir / "data_C1" / "bbox_C1" / "c1_garbage_mask.txt").write_text("polyp 10 10 50 50\n")
    create_valid_jpeg(s3_dir / "imagesAll_positive" / "c1_garbage.jpg")
    s3_report = SCRATCH_ROOT / "s3_report.json"
    res3 = run_verification(s3_dir, s3_report)
    corr_list = res3["report"].get("deep_corruption_scan", {}).get("corrupted_files", []) if res3["report"] else []
    scenarios["s3_garbage_binary"] = {
        "description": "Completely garbage binary disguised as .jpg",
        "expected_pass": False,
        "returncode": res3["returncode"],
        "verdict": res3["report"].get("verdict") if res3["report"] else None,
        "corrupted_count": len(corr_list),
        "corrupted_details": corr_list,
        "stderr": res3["stderr"],
    }
    print(f"Returncode: {res3['returncode']} | Corrupted files detected: {len(corr_list)}")

    # Scenario 4 (Task 2d - Part 1): Invalid Pascal VOC text file (xmin >= xmax)
    print("\n--- Scenario 4: Invalid VOC Geometry (xmin >= xmax) ---")
    s4_dir = SCRATCH_ROOT / "s4_invalid_geom"
    create_base_dataset(s4_dir)
    bbox_file = s4_dir / "data_C1" / "bbox_C1" / "c1_frame_001_mask.txt"
    # xmin=500, ymin=200, xmax=100, ymax=800 -> xmin >= xmax
    bbox_file.write_text("polyp 500 200 100 800\n", encoding="utf-8")
    s4_report = SCRATCH_ROOT / "s4_report.json"
    res4 = run_verification(s4_dir, s4_report)
    bbox_val = res4["report"].get("bounding_box_validation", {}) if res4["report"] else {}
    scenarios["s4_invalid_geom"] = {
        "description": "Invalid Pascal VOC text file (xmin >= xmax: polyp 500 200 100 800)",
        "expected_pass": False,
        "returncode": res4["returncode"],
        "verdict": res4["report"].get("verdict") if res4["report"] else None,
        "invalid_geometry_boxes": bbox_val.get("invalid_geometry_boxes"),
        "invalid_format_boxes": bbox_val.get("invalid_format_boxes"),
        "stderr": res4["stderr"],
    }
    print(f"Returncode: {res4['returncode']} | Invalid geometry count: {bbox_val.get('invalid_geometry_boxes')}")

    # Scenario 5 (Task 2d - Part 2): Invalid Pascal VOC format / Malformed syntax
    print("\n--- Scenario 5: Invalid VOC Syntax / Format ---")
    s5_dir = SCRATCH_ROOT / "s5_invalid_syntax"
    create_base_dataset(s5_dir)
    bbox_file = s5_dir / "data_C1" / "bbox_C1" / "c1_frame_001_mask.txt"
    # Malformed line with 3 tokens and non-numeric value
    bbox_file.write_text("polyp bad_token 20 80\n", encoding="utf-8")
    s5_report = SCRATCH_ROOT / "s5_report.json"
    res5 = run_verification(s5_dir, s5_report)
    bbox_val = res5["report"].get("bounding_box_validation", {}) if res5["report"] else {}
    scenarios["s5_invalid_syntax"] = {
        "description": "Invalid Pascal VOC format (wrong token count / non-numeric)",
        "expected_pass": False,
        "returncode": res5["returncode"],
        "verdict": res5["report"].get("verdict") if res5["report"] else None,
        "invalid_format_boxes": bbox_val.get("invalid_format_boxes"),
        "stderr": res5["stderr"],
    }
    print(f"Returncode: {res5['returncode']} | Invalid format count: {bbox_val.get('invalid_format_boxes')}")

    # Scenario 6 (Task 2d - Part 3): Wrong Label String (e.g. 'car' or 'not_polyp')
    print("\n--- Scenario 6: Wrong Label String ---")
    s6_dir = SCRATCH_ROOT / "s6_wrong_label"
    create_base_dataset(s6_dir)
    bbox_file = s6_dir / "data_C1" / "bbox_C1" / "c1_frame_001_mask.txt"
    bbox_file.write_text("adenoma_unrecognized 20 20 80 80\n", encoding="utf-8")
    s6_report = SCRATCH_ROOT / "s6_report.json"
    res6 = run_verification(s6_dir, s6_report)
    bbox_val = res6["report"].get("bounding_box_validation", {}) if res6["report"] else {}
    scenarios["s6_wrong_label"] = {
        "description": "Wrong label string ('adenoma_unrecognized' instead of standard polyp/cancer)",
        "expected_pass": "Unknown / Stress Test",
        "returncode": res6["returncode"],
        "verdict": res6["report"].get("verdict") if res6["report"] else None,
        "classes_observed": bbox_val.get("classes_observed"),
        "stderr": res6["stderr"],
    }
    print(f"Returncode: {res6['returncode']} | Classes observed: {bbox_val.get('classes_observed')} | Verdict: {scenarios['s6_wrong_label']['verdict']}")

    # Scenario 7 (Task 2e): Out-of-bounds Coordinates
    print("\n--- Scenario 7: Out-of-bounds Coordinates ---")
    s7_dir = SCRATCH_ROOT / "s7_out_of_bounds"
    create_base_dataset(s7_dir)
    # Image is 200x200, bbox extends to 9999x9999
    bbox_file = s7_dir / "data_C1" / "bbox_C1" / "c1_frame_001_mask.txt"
    bbox_file.write_text("polyp 10 10 9999 9999\n", encoding="utf-8")
    s7_report = SCRATCH_ROOT / "s7_report.json"
    res7 = run_verification(s7_dir, s7_report)
    bbox_val = res7["report"].get("bounding_box_validation", {}) if res7["report"] else {}
    scenarios["s7_out_of_bounds"] = {
        "description": "Out-of-bounds coordinates (xmax=9999 > width=200)",
        "expected_pass": "Should fail, but checking if verdict flags it",
        "returncode": res7["returncode"],
        "verdict": res7["report"].get("verdict") if res7["report"] else None,
        "out_of_bounds_boxes": bbox_val.get("out_of_bounds_boxes"),
        "stderr": res7["stderr"],
    }
    print(f"Returncode: {res7['returncode']} | Out of bounds count: {bbox_val.get('out_of_bounds_boxes')} | Verdict: {scenarios['s7_out_of_bounds']['verdict']}")

    # Scenario 8 (Task 2f - Part 1): Missing Mask
    print("\n--- Scenario 8: Missing Mask File ---")
    s8_dir = SCRATCH_ROOT / "s8_missing_mask"
    create_base_dataset(s8_dir)
    # Delete the mask file
    mask_file = s8_dir / "data_C1" / "masks_C1" / "c1_frame_001_mask.jpg"
    if mask_file.exists():
        mask_file.unlink()
    s8_report = SCRATCH_ROOT / "s8_report.json"
    res8 = run_verification(s8_dir, s8_report)
    scenarios["s8_missing_mask"] = {
        "description": "Missing mask file for an existing image",
        "expected_pass": False,
        "returncode": res8["returncode"],
        "stderr": res8["stderr"][:300] if res8["stderr"] else "",
        "stdout_tail": res8["stdout"].splitlines()[-5:] if res8["stdout"] else [],
    }
    print(f"Returncode: {res8['returncode']} | Stderr: {res8['stderr'][:100]}")

    # Scenario 9 (Task 2f - Part 2): Orphaned Overlay
    print("\n--- Scenario 9: Orphaned Overlay ---")
    s9_dir = SCRATCH_ROOT / "s9_orphaned_overlay"
    create_base_dataset(s9_dir)
    # Add an orphaned overlay in C1 (which has orphan detection)
    orphan_overlay = s9_dir / "data_C1" / "bbox_image_C1" / "extra_orphan_mask_bbox.jpg"
    create_valid_jpeg(orphan_overlay, 200, 200)
    s9_report = SCRATCH_ROOT / "s9_report.json"
    res9 = run_verification(s9_dir, s9_report)
    amb4 = res9["report"].get("structural_ambiguities", {}).get("ambiguity_4_c1_orphan_overlay", {}) if res9["report"] else {}
    scenarios["s9_orphaned_overlay"] = {
        "description": "Orphaned overlay file in data_C1/bbox_image_C1",
        "expected_pass": True,
        "returncode": res9["returncode"],
        "verdict": res9["report"].get("verdict") if res9["report"] else None,
        "orphan_files_detected": amb4.get("orphan_files", []),
        "stderr": res9["stderr"],
    }
    print(f"Returncode: {res9['returncode']} | Orphan overlays detected: {amb4.get('orphan_files')}")

    # Scenario 10 (Composite Stress Test): All Failure Modes Combined
    print("\n--- Scenario 10: Composite Multi-Corruption Dataset ---")
    s10_dir = SCRATCH_ROOT / "s10_composite"
    create_base_dataset(s10_dir)

    # 1. 0-byte file
    (s10_dir / "data_C1" / "images_C1" / "comp_0byte.jpg").write_bytes(b"")
    create_valid_mask(s10_dir / "data_C1" / "masks_C1" / "comp_0byte_mask.jpg")
    (s10_dir / "data_C1" / "bbox_C1" / "comp_0byte_mask.txt").write_text("polyp 10 10 50 50\n")
    create_valid_jpeg(s10_dir / "imagesAll_positive" / "comp_0byte.jpg")

    # 2. Truncated file
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (200, 50, 50)).save(buf, format="JPEG")
    (s10_dir / "data_C1" / "images_C1" / "comp_trunc.jpg").write_bytes(buf.getvalue()[:len(buf.getvalue())//3])
    create_valid_mask(s10_dir / "data_C1" / "masks_C1" / "comp_trunc_mask.jpg")
    (s10_dir / "data_C1" / "bbox_C1" / "comp_trunc_mask.txt").write_text("polyp 10 10 50 50\n")
    create_valid_jpeg(s10_dir / "imagesAll_positive" / "comp_trunc.jpg")

    # 3. Garbage binary file
    (s10_dir / "data_C1" / "images_C1" / "comp_garbage.jpg").write_bytes(b"NON_IMAGE_GARBAGE_CONTENT" * 50)
    create_valid_mask(s10_dir / "data_C1" / "masks_C1" / "comp_garbage_mask.jpg")
    (s10_dir / "data_C1" / "bbox_C1" / "comp_garbage_mask.txt").write_text("polyp 10 10 50 50\n")
    create_valid_jpeg(s10_dir / "imagesAll_positive" / "comp_garbage.jpg")

    # 4. Invalid geometry bbox
    (s10_dir / "data_C1" / "bbox_C1" / "comp_0byte_mask.txt").write_text("polyp 500 200 100 800\n")

    # 5. Out of bounds bbox
    (s10_dir / "data_C1" / "bbox_C1" / "comp_garbage_mask.txt").write_text("polyp 10 10 5000 5000\n")

    s10_report = SCRATCH_ROOT / "s10_report.json"
    res10 = run_verification(s10_dir, s10_report)
    corr_list10 = res10["report"].get("deep_corruption_scan", {}).get("corrupted_files", []) if res10["report"] else []
    bbox_val10 = res10["report"].get("bounding_box_validation", {}) if res10["report"] else {}
    scenarios["s10_composite"] = {
        "description": "Composite suite combining 0-byte, truncated, garbage, invalid bbox geometry, and out-of-bounds",
        "expected_pass": False,
        "returncode": res10["returncode"],
        "verdict": res10["report"].get("verdict") if res10["report"] else None,
        "corrupted_count": len(corr_list10),
        "invalid_geometry_boxes": bbox_val10.get("invalid_geometry_boxes"),
        "out_of_bounds_boxes": bbox_val10.get("out_of_bounds_boxes"),
        "stderr": res10["stderr"],
    }
    print(f"Returncode: {res10['returncode']} | Corrupted count: {len(corr_list10)} | Invalid geom: {bbox_val10.get('invalid_geometry_boxes')}")

    # Output full test results matrix
    results_summary_path = SCRATCH_ROOT / "adversarial_stress_summary.json"
    with open(results_summary_path, "w", encoding="utf-8") as f:
        json.dump(scenarios, f, indent=2)

    print(f"\n[+] Empirical stress testing finished. Summary saved to: {results_summary_path}")


if __name__ == "__main__":
    main()
