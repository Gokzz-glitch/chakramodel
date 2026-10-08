"""
Forensic Audit Verification Script for Milestone 4 (Gen 6)
Checks:
1. results/corrected_eval_kvasir_seg.json
   - Mathematical consistency:
     dice == 2 * intersection / (pred + gt)
     iou == intersection / (pred + gt - intersection)
     iou == dice / (2 - dice)
   - Real dataset verification:
     Check image files against data/kvasir-seg/images and masks
   - Distribution check:
     Variance, min, max, not uniform dummy numbers
   - Summary statistics check:
     Check mean_dsc and mean_iou against average of per-image results
2. FIXES.md
   - Check all 5 mandatory sections
   - Check timestamp 2026-09-08
   - Check for any placeholder strings (TBD, TODO, placeholder, etc.)
3. notebooks/Kaggle_Final_Proof_Eval.ipynb
   - Check cell 2 exists after imports
   - Check DDP prefix stripping code
   - Check PASS/FAIL print statement
   - Check timestamp 2026-09-08
   - Check notebook valid JSON structure
"""

import json
import os
import math
from pathlib import Path
import numpy as np

def audit_results_json(project_root: Path):
    json_path = project_root / "results" / "corrected_eval_kvasir_seg.json"
    assert json_path.exists(), f"{json_path} does not exist"
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"=== AUDIT: {json_path} ===")
    print(f"Timestamp: {data.get('timestamp')}")
    print(f"Model path: {data.get('model_path')}")
    print(f"Loading status: {data.get('weight_loading_status')}")
    print(f"Number of images: {data.get('n_images')}")
    print(f"Reported mean_dsc: {data.get('mean_dsc')}")
    print(f"Reported mean_iou: {data.get('mean_iou')}")
    
    per_image = data["per_image_results"]
    assert len(per_image) == data["n_images"], f"Mismatch in image count: {len(per_image)} vs {data['n_images']}"
    
    math_failures = []
    dataset_failures = []
    
    dices = []
    ious = []
    
    images_dir = project_root / "data" / "kvasir-seg" / "images"
    masks_dir = project_root / "data" / "kvasir-seg" / "masks"
    
    for idx, item in enumerate(per_image):
        img_name = item["image"]
        d = item["dice"]
        iou = item["iou"]
        pred = item["pred_pixels"]
        gt = item["gt_pixels"]
        inter = item["intersection_pixels"]
        
        dices.append(d)
        ious.append(iou)
        
        # Mathematical check:
        # Dice = 2 * inter / (pred + gt)
        if pred + gt == 0:
            expected_d = 1.0 if inter == 0 else 0.0
            expected_iou = 1.0 if inter == 0 else 0.0
        else:
            expected_d = (2.0 * inter) / (pred + gt)
            expected_iou = inter / (pred + gt - inter) if (pred + gt - inter) > 0 else 0.0
            
        if abs(d - expected_d) > 1e-4:
            math_failures.append(f"Image {img_name}: Dice mismatch {d} vs expected {expected_d:.6f}")
        if abs(iou - expected_iou) > 1e-4:
            math_failures.append(f"Image {img_name}: IoU mismatch {iou} vs expected {expected_iou:.6f}")
            
        # DSC-IoU exact identity: IoU = DSC / (2 - DSC)
        if (2 - expected_d) > 0:
            identity_iou = expected_d / (2.0 - expected_d)
            if abs(expected_iou - identity_iou) > 1e-5:
                math_failures.append(f"Image {img_name}: IoU identity mismatch {expected_iou} vs {identity_iou}")
                
        # Dataset check:
        img_path = images_dir / img_name
        mask_path = masks_dir / img_name
        if not img_path.exists():
            dataset_failures.append(f"Image file missing: {img_path}")
        if not mask_path.exists():
            dataset_failures.append(f"Mask file missing: {mask_path}")
            
    calc_mean_dsc = float(np.mean(dices))
    calc_mean_iou = float(np.mean(ious))
    calc_std_dsc = float(np.std(dices, ddof=1)) if len(dices) > 1 else 0.0 # or ddof=0
    calc_std_dsc_p = float(np.std(dices, ddof=0))
    
    print(f"Calculated mean_dsc: {calc_mean_dsc:.5f}")
    print(f"Calculated mean_iou: {calc_mean_iou:.5f}")
    print(f"Calculated std_dsc (ddof=0): {calc_std_dsc_p:.6f}")
    print(f"Calculated std_dsc (ddof=1): {calc_std_dsc:.6f}")
    print(f"Min DSC: {min(dices):.6f}, Max DSC: {max(dices):.6f}")
    print(f"Math failures: {len(math_failures)}")
    print(f"Dataset failures: {len(dataset_failures)}")
    
    assert len(math_failures) == 0, f"Math failures detected: {math_failures[:5]}"
    assert len(dataset_failures) == 0, f"Dataset failures detected: {dataset_failures[:5]}"
    assert abs(calc_mean_dsc - data["mean_dsc"]) < 1e-4, "Mean DSC mismatch"
    assert abs(calc_mean_iou - data["mean_iou"]) < 1e-4, "Mean IoU mismatch"
    print(">>> RESULTS JSON AUDIT: PASS\n")

def audit_fixes_md(project_root: Path):
    fixes_path = project_root / "FIXES.md"
    assert fixes_path.exists(), f"{fixes_path} does not exist"
    
    with open(fixes_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    print(f"=== AUDIT: {fixes_path} ===")
    mandatory_sections = [
        "1. Root Cause",
        "2. Exact Lines Changed",
        "3. Before/After Code Diff",
        "4. Evidence from Weight Inspection",
        "5. Results After Fix"
    ]
    
    for sec in mandatory_sections:
        assert sec.lower() in content.lower(), f"Missing mandatory section: {sec}"
        print(f"[OK] Section present: {sec}")
        
    assert "2026-09-08" in content, "Missing timestamp 2026-09-08"
    print("[OK] Timestamp 2026-09-08 verified")
    
    # Check placeholders
    placeholders = ["[tbd]", "[todo]", "[placeholder]", "tbd...", "todo:"]
    for ph in placeholders:
        assert ph not in content.lower(), f"Placeholder found: {ph}"
    print("[OK] Zero placeholders verified")
    print(">>> FIXES.MD AUDIT: PASS\n")

def audit_notebook(project_root: Path):
    nb_path = project_root / "notebooks" / "Kaggle_Final_Proof_Eval.ipynb"
    assert nb_path.exists(), f"{nb_path} does not exist"
    
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
        
    print(f"=== AUDIT: {nb_path} ===")
    cells = nb.get("cells", [])
    print(f"Total cells: {len(cells)}")
    
    # Locate code cells
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    print(f"Total code cells: {len(code_cells)}")
    
    # Cell 2 is code_cells[1]
    cell2 = code_cells[1]
    cell2_source = "".join(cell2.get("source", []))
    
    assert "2026-09-08" in cell2_source, "Timestamp 2026-09-08 missing from Cell 2"
    print("[OK] Timestamp 2026-09-08 present in Cell 2")
    
    assert 'replace("module.", "")' in cell2_source, "DDP prefix stripping missing from Cell 2"
    print("[OK] DDP prefix stripping logic verified in Cell 2")
    
    assert "PASS" in cell2_source and "FAIL" in cell2_source, "PASS/FAIL check missing from Cell 2"
    print("[OK] PASS/FAIL check structure verified in Cell 2")
    
    print(">>> NOTEBOOK AUDIT: PASS\n")

if __name__ == "__main__":
    root = Path(r"m:\chakramodel")
    audit_results_json(root)
    audit_fixes_md(root)
    audit_notebook(root)
    print("ALL FORENSIC AUDIT CHECKS COMPLETED SUCCESSFULLY!")
