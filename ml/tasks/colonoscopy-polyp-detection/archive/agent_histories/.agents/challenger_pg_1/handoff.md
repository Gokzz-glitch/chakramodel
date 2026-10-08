# Handoff Report — Adversarial Empirical Stress-Testing of `verify_polypgen_integrity.py`

## 1. Observation

### 1.1 Target Script and Tested Scenarios
- Target script: `m:\chakramodel\verify_polypgen_integrity.py` (912 lines, 38,479 bytes).
- Execution command for empirical suite:
  ```powershell
  python m:\chakramodel\scratch\harness_polypgen_adversarial.py
  ```
- Summary results stored in: `m:\chakramodel\scratch\polypgen_adversarial_suite\adversarial_stress_summary.json`.

### 1.2 Verbatim Test Matrix Observations

| Scenario ID | Test Condition | Return Code | Observed Verdict | Corruption / Discrepancy Flagged | Script Exception / Output |
|---|---|---|---|---|---|
| `s0_baseline_valid` | Pristine 100% valid synthetic dataset | `0` | `PASS` | `total_corrupted: 0`, `invalid_geometry: 0`, `exact_match: True` | Clean execution |
| `s1_zero_byte` | 0-byte file disguised as `.jpg` (`c1_zero_byte.jpg`) | `1` | `FAIL` | `total_corrupted: 1` | `"error": "0-byte file (empty)"` |
| `s2_truncated` | Truncated JPEG (valid header, cut stream before EOI) | `1` | `FAIL` | `total_corrupted: 1` | `"error": "OSError: Truncated File Read"` |
| `s3_garbage_binary` | Random binary bytes (`0xDEADBEEF...`) disguised as `.jpg` | `1` | `FAIL` | `total_corrupted: 1` | `"error": "UnidentifiedImageError: cannot identify image file ..."` |
| `s4_invalid_geom` | Pascal VOC line with `xmin >= xmax`: `polyp 500 200 100 800` | `1` | `FAIL` | `invalid_geometry_boxes: 1` | Console & JSON report flag invalid geometry |
| `s5_invalid_syntax` | Malformed VOC text file: `polyp bad_token 20 80` | `1` | `FAIL` | `invalid_format_boxes: 1` | Console & JSON report flag invalid format |
| `s6_wrong_label` | Unexpected VOC class label: `adenoma_unrecognized 20 20 80 80` | `0` | `PASS` (False Negative) | `classes_observed: ['adenoma_unrecognized']` | **Excluded from `is_passed`**, returns exit 0 |
| `s7_out_of_bounds` | Out-of-bounds coordinates: `polyp 10 10 9999 9999` (image 200x200) | `0` | `PASS` (False Negative) | `out_of_bounds_boxes: 1` | **Excluded from `is_passed`**, returns exit 0 |
| `s8_missing_mask` | Missing mask for image (`c1_frame_001.jpg` without mask) | `1` | None (Script Crash) | None (Premature unhandled abort) | `AssertionError: Missing mask for image c1_frame_001.jpg in C1: expected c1_frame_001_mask.jpg` |
| `s9_orphaned_overlay` | Extra overlay in C1: `extra_orphan_mask_bbox.jpg` | `0` | `PASS` | `ambiguity_4_c1_orphan_overlay`: flagged in audit | Handled as documented benign author artifact |
| `s10_composite` | 0-byte + truncated + garbage + invalid geom + out-of-bounds | `1` | `FAIL` | `total_corrupted: 3`, `invalid_geometry: 1`, `out_of_bounds: 2` | Fails overall check, exit 1 |
| `s11_c2_orphan` | Extra overlay in C2: `data_C2/bbox_image_C2/c2_orphan_overlay.jpg` | `0` | `PASS` | Scanned in deep scan, but `orphan_files` not audited for C2 | Silently passed |
| `s12_pooled_mismatch` | Extra/missing image in `imagesAll_positive` | `1` | `FAIL` | `exact_match: False` | Failed overall check, exit 1 |

### 1.3 Key Code Observations in `verify_polypgen_integrity.py`

1. **Overall Verdict Predicate (lines 859-864)**:
   ```python
   is_passed = (
       scan_results["total_corrupted"] == 0
       and audit_results["census"]["pooled_images_reconciliation"]["exact_match"]
       and audit_results["bounding_box_validation"]["invalid_format_boxes"] == 0
       and audit_results["bounding_box_validation"]["invalid_geometry_boxes"] == 0
   )
   ```
   Notice that `audit_results["bounding_box_validation"]["out_of_bounds_boxes"] == 0` is **completely absent** from this boolean predicate.

2. **Out-of-Bounds Detection Logic (lines 740-742)**:
   ```python
   if xmin < 0 or ymin < 0 or xmax > img_w or ymax > img_h:
       out_of_bounds_boxes += 1
   ```
   The condition correctly detects out-of-bounds bounding boxes, but because line 859 omits `out_of_bounds_boxes == 0`, the script prints the number of out-of-bounds boxes and then proceeds to output `Overall Verdict : PASS` and `sys.exit(0)`.

3. **Missing Mask Handling (lines 388-395 & 470-476)**:
   ```python
   for img_name in images:
       stem = Path(img_name).stem
       expected_mask_stem = stem[:-1] if (c == 3 and stem.endswith("_")) else stem
       expected_mask = f"{expected_mask_stem}_mask.jpg"
       if expected_mask not in masks:
           raise AssertionError(f"Missing mask for image {img_name} in {c_str}: expected {expected_mask}")
   ```
   This assertion is uncaught in `main()`. When an image lacks its corresponding mask, Python raises `AssertionError`, terminates immediately, and skips JSON report generation and terminal summary rendering.

4. **Class Label Invariance (lines 721-723 & 828)**:
   ```python
   cls_name, xmin_str, ymin_str, xmax_str, ymax_str = parts
   classes_seen.add(cls_name)
   ```
   Any arbitrary string token (e.g. `car`, `typo_polyp`) is accepted into `classes_seen`. There is no class whitelist validation or check in `is_passed`.

---

## 2. Logic Chain

1. **Physical Corruption Defense (Pass)**:
   - Line 97 explicitly checks `size_bytes == 0` and flags empty files immediately.
   - Line 33 sets `ImageFile.LOAD_TRUNCATED_IMAGES = False`.
   - Line 114 executes `im.load()`, forcing complete raster decompression into RAM.
   - When a truncated JPEG is processed, decompression encounters EOF before EOI marker, raising `OSError: Truncated File Read`.
   - When garbage binary data is processed, PIL fails to identify image headers, raising `UnidentifiedImageError`.
   - Both are caught by `verify_single_image()`, returning `valid: False` and appending to `corrupted_files`.
   - Line 860 checks `scan_results["total_corrupted"] == 0`. When corrupted files exist, `is_passed` evaluates to `False`, rendering a `FAIL` verdict and exiting with status code 1.

2. **Bounding Box Geometric & Syntactic Validation (Pass)**:
   - Line 718 validates 5 whitespace-separated tokens per line.
   - Line 725-731 validates that coordinates parse to integers.
   - Line 736 validates `xmin < xmax` and `ymin < ymax`.
   - Lines 862-863 enforce `invalid_format_boxes == 0` and `invalid_geometry_boxes == 0`.
   - Both invalid syntax and inverted coordinates cause `is_passed` to evaluate to `False`, exiting with status code 1.

3. **Out-of-Bounds Bounding Box Vulnerability (Fail / Critical Flaw)**:
   - In Scenario `s7_out_of_bounds`, coordinate `xmax=9999` exceeds image width `200`.
   - Line 741 detects this and increments `out_of_bounds_boxes` from 0 to 1.
   - However, in lines 859-864, `is_passed` evaluates:
     - `scan_results["total_corrupted"] == 0` -> True
     - `exact_match` -> True
     - `invalid_format_boxes == 0` -> True
     - `invalid_geometry_boxes == 0` -> True
     - (No check on `out_of_bounds_boxes`)
   - `is_passed` evaluates to `True`.
   - Line 866 assigns `verdict_status = "PASS"`.
   - Line 907 executes `sys.exit(0)`.
   - **Conclusion**: A dataset containing completely out-of-bounds annotations will receive a clean bill of health (`PASS`, exit 0), silently corrupting downstream training / evaluation pipelines.

4. **Missing Mask Abrupt Crash Vulnerability (Fail / Quality Issue)**:
   - In Scenario `s8_missing_mask`, mask file was deleted.
   - Line 394 executes `raise AssertionError(...)`.
   - `main()` does not catch `AssertionError`.
   - The process crashes with unhandled traceback.
   - No JSON report is written to disk; no telemetry or structured error summary is available for downstream orchestrators or automated quality gates.

---

## 3. Caveats

1. **Review-Only Constraint**: In accordance with the system prompt instructions, no modifications were made to `verify_polypgen_integrity.py`. All tests were run against the target script as-is.
2. **Dataset Root Convention**: The script's directory resolver expects either `PolypGen2021_MultiCenterData_v3` or both `data_C1` and `sequenceData` at the top level. The synthetic test suite generator adheres to this contract.
3. **C1 vs Other Centers for Overlays**: C1 was designed with specific handling for the known orphan overlay `957OLCV1_100H0002_mask_bbox.jpg`. Overlays in C2-C6 are not checked for 1:1 image correspondence by design in the original script.

---

## 4. Conclusion

The `verify_polypgen_integrity.py` script is **highly robust** against physical file corruptions (0-byte, truncated streams, arbitrary garbage binaries) and inverted bounding box geometries (`xmin >= xmax`), correctly flagging every corrupted file and terminating with exit code 1.

However, adversarial stress testing revealed **two significant verification vulnerabilities**:
1. **Critical Defect**: Out-of-bounds bounding boxes (`out_of_bounds_boxes > 0`) and arbitrary/corrupted class labels do **not** trigger a `FAIL` verdict or non-zero exit code due to omission in the `is_passed` predicate (lines 859-864).
2. **Resilience Defect**: Missing mask files trigger an unhandled `AssertionError` crash rather than generating a structured JSON audit failure report.

---

## 5. Verification Method

To independently reproduce and verify all observations and conclusions:

```powershell
# 1. Run the automated adversarial test suite
python m:\chakramodel\scratch\harness_polypgen_adversarial.py

# 2. Inspect the JSON summary of all 11 test scenarios
cat m:\chakramodel\scratch\polypgen_adversarial_suite\adversarial_stress_summary.json

# 3. Specifically verify the out-of-bounds false negative (Scenario 7)
python m:\chakramodel\verify_polypgen_integrity.py --data-dir m:\chakramodel\scratch\polypgen_adversarial_suite\s7_out_of_bounds --json-report m:\chakramodel\scratch\polypgen_adversarial_suite\s7_report.json
echo "Last Exit Code: $LASTEXITCODE"
# Expected: Exit code is 0 and Overall Verdict is PASS, despite 1 out-of-bounds box.
```
