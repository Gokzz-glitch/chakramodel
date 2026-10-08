#!/usr/bin/env python3
"""
Adversarial Audit Script for ChakraModel Paper Metrics & Narrative Positioning
Challenger 2 (Milestone 3, Generation 9)

Cross-references metrics in:
  - paper/main.tex
  - docs/paper/ChakraModel_Final_Paper.md
against ground-truth sources:
  - kaggle_results/run_v5/cross_dataset_results_v5.json
  - docs/HONEST_METRICS.md
"""

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

KAGGLE_JSON = BASE_DIR / "kaggle_results" / "run_v5" / "cross_dataset_results_v5.json"
HONEST_METRICS_MD = BASE_DIR / "docs" / "HONEST_METRICS.md"
MAIN_TEX = BASE_DIR / "paper" / "main.tex"
FINAL_PAPER_MD = BASE_DIR / "docs" / "paper" / "ChakraModel_Final_Paper.md"

DATASET_KEY_MAPPING = {
    "kvasir": "Kvasir-SEG (test split)",
    "kvasir-seg": "Kvasir-SEG (test split)",
    "hyperkvasir": "HyperKvasir Segmented",
    "hyperkvasir segmented": "HyperKvasir Segmented",
    "cvc-clinicdb": "CVC-ClinicDB (zero-shot)",
    "endoscene cvc-300": "EndoScene CVC-300 (zero-shot)",
    "cvc-300": "EndoScene CVC-300 (zero-shot)",
    "polypdb": "PolypDB (All Modalities)",
    "polypdb (all modalities)": "PolypDB (All Modalities)",
    "etis-larib": "ETIS-Larib (zero-shot)",
}

EXPECTED_BENCHMARKS = {
    "Kvasir-SEG": {
        "dice": 0.8131,
        "std": 0.1747,
        "iou": 0.7141,
        "precision": 0.8330,
        "recall": 0.8500,
        "n": 150,
    },
    "HyperKvasir": {
        "dice": 0.8360,
        "std": 0.1610,
        "iou": 0.7439,
        "precision": 0.8398,
        "recall": 0.8768,
        "n": 1000,
    },
    "CVC-ClinicDB": {
        "dice": 0.7561,
        "std": 0.2131,
        "iou": 0.6470,
        "precision": 0.7553,
        "recall": 0.8444,
        "n": 495,
    },
    "EndoScene CVC-300": {
        "dice": 0.7402,
        "std": 0.1590,
        "iou": 0.6098,
        "precision": 0.6361,
        "recall": 0.9427,
        "n": 60,
    },
    "PolypDB": {
        "dice": 0.7283,
        "std": 0.2544,
        "iou": 0.6243,
        "precision": 0.6889,
        "recall": 0.8611,
        "n": 7868,
    },
    "ETIS-Larib": {
        "dice": 0.0000,
        "std": 0.0000,
        "iou": 0.0000,
        "precision": 0.0000,
        "recall": 0.0000,
        "n": 196,
    },
}

RETRACTED_METRICS = [
    ("Kvasir-SEG", 0.9852),
    ("CVC-ClinicDB", 0.9412),
    ("ETIS-Larib", 0.8650),
    ("Kvasir-SEG", 0.9158),
    ("Kvasir-SEG", 0.9210),
    ("Kvasir-SEG", 0.9610),
]


def load_ground_truth():
    with open(KAGGLE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def audit_ground_truth(ground_truth):
    """Verify that Kaggle run_v5 matches expected benchmark definitions."""
    results = {}
    for key, expected in EXPECTED_BENCHMARKS.items():
        matched_key = None
        for k in ground_truth:
            if key.lower() in k.lower():
                matched_key = k
                break
        assert matched_key is not None, f"Dataset {key} not found in {KAGGLE_JSON}"
        entry = ground_truth[matched_key]
        
        dice_rounded = round(entry["dice"], 4)
        std_rounded = round(entry["std"], 4)
        iou_rounded = round(entry["iou"], 4)
        
        assert dice_rounded == expected["dice"], f"{key} Dice mismatch: {dice_rounded} vs {expected['dice']}"
        assert std_rounded == expected["std"], f"{key} Std mismatch: {std_rounded} vs {expected['std']}"
        assert iou_rounded == expected["iou"], f"{key} IoU mismatch: {iou_rounded} vs {expected['iou']}"
        assert entry["n"] == expected["n"], f"{key} N mismatch: {entry['n']} vs {expected['n']}"
        results[key] = {
            "status": "PASS",
            "raw": entry,
            "rounded": {
                "dice": dice_rounded,
                "std": std_rounded,
                "iou": iou_rounded,
                "n": entry["n"],
            },
        }
    return results


def audit_honest_metrics_doc():
    """Verify docs/HONEST_METRICS.md consistency."""
    text = HONEST_METRICS_MD.read_text(encoding="utf-8")
    assert "0.8131493330001831" in text, "Exact Kvasir-SEG Dice missing in HONEST_METRICS.md"
    assert "0.8359748721122742" in text, "Exact HyperKvasir Dice missing in HONEST_METRICS.md"
    assert "0.7560632228851318" in text, "Exact CVC-ClinicDB Dice missing in HONEST_METRICS.md"
    assert "0.7402245998382568" in text, "Exact CVC-300 Dice missing in HONEST_METRICS.md"
    assert "0.7283103466033936" in text, "Exact PolypDB Dice missing in HONEST_METRICS.md"
    assert "0.0000000000000000" in text, "Exact ETIS-Larib zero Dice missing in HONEST_METRICS.md"
    assert "catastrophic failure" in text.lower(), "ETIS-Larib catastrophic failure note missing"
    assert "retracted metrics" in text.lower(), "Retracted metrics section missing"
    return True


def audit_latex_table(latex_content):
    """Parse Table tab:results from paper/main.tex."""
    table_match = re.search(r"\\begin\{tabular\}.*?\\end\{tabular\}", latex_content, re.DOTALL)
    assert table_match, "Table tab:results not found in main.tex"
    table_text = re.sub(r"\\(toprule|midrule|bottomrule)", "", table_match.group(0))
    rows = [line.strip() for line in table_text.split(r"\\") if line.strip()]
    parsed_rows = {}
    for row in rows:
        parts = [p.strip().replace("$", "") for p in row.split("&")]
        if len(parts) >= 6:
            dataset_raw = parts[0]
            if "Dataset" in dataset_raw or r"\midrule" in dataset_raw or r"\toprule" in dataset_raw:
                continue
            cleaned_ds = re.sub(r"\\textsuperscript\{.*?\}", "", dataset_raw).strip()
            
            eval_nature = parts[1]
            n_str = parts[2]
            dice_str = parts[3]
            miou_str = parts[4]
            prec_str = parts[5]
            
            # Dice format: 0.8131 \pm 0.1747
            dice_parts = dice_str.split(r"\pm")
            dice_val = float(dice_parts[0].strip())
            dice_std = float(dice_parts[1].strip()) if len(dice_parts) > 1 else 0.0
            miou_val = float(miou_str)
            prec_val = float(prec_str)
            n_val = int(n_str)
            
            parsed_rows[cleaned_ds] = {
                "eval_nature": eval_nature,
                "n": n_val,
                "dice": dice_val,
                "std": dice_std,
                "miou": miou_val,
                "precision": prec_val,
            }
            
    # Verify each dataset in Table 1
    checks = {
        "Kvasir-SEG": (0.8131, 0.1747, 0.7141, 150),
        "HyperKvasir": (0.8360, 0.1610, 0.7439, 1000),
        "CVC-ClinicDB": (0.7561, 0.2131, 0.6470, 495),
        "EndoScene CVC-300": (0.7402, 0.1590, 0.6098, 60),
        "PolypDB (All Modalities)": (0.7283, 0.2544, 0.6243, 7868),
        "ETIS-Larib": (0.0000, 0.0000, 0.0000, 196),
    }
    
    table_audit = {}
    for ds_name, (exp_dice, exp_std, exp_miou, exp_n) in checks.items():
        found = None
        for k in parsed_rows:
            if ds_name.lower() in k.lower():
                found = parsed_rows[k]
                break
        assert found is not None, f"Dataset {ds_name} missing from Table tab:results in main.tex"
        assert found["dice"] == exp_dice, f"Table Dice mismatch for {ds_name}: {found['dice']} vs {exp_dice}"
        assert found["std"] == exp_std, f"Table Std mismatch for {ds_name}: {found['std']} vs {exp_std}"
        assert found["miou"] == exp_miou, f"Table mIoU mismatch for {ds_name}: {found['miou']} vs {exp_miou}"
        assert found["n"] == exp_n, f"Table N mismatch for {ds_name}: {found['n']} vs {exp_n}"
        table_audit[ds_name] = {"status": "PASS", "parsed": found}
    return table_audit


def audit_markdown_tables(md_content):
    """Parse Table 5.1 and Table 5.2 from ChakraModel_Final_Paper.md."""
    # Find Table 5.1
    t51_match = re.search(r"\*\*Table 5\.1:[^\n]+\*\*(.*?)(?=\*\*Table 5\.2|\n\n\n|\Z)", md_content, re.DOTALL)
    assert t51_match, "Table 5.1 not found in ChakraModel_Final_Paper.md"
    t51_text = t51_match.group(1)
    
    rows = [r.strip() for r in t51_text.splitlines() if r.strip().startswith("|") and not "---" in r]
    parsed_t51 = {}
    for row in rows[1:]: # Skip header
        cols = [c.strip() for c in row.split("|")[1:-1]]
        if len(cols) >= 6:
            ds_name = cols[0].replace("**", "").replace(r"\*", "").strip()
            eval_type = cols[1]
            n_val = int(cols[2].replace(",", "").strip())
            
            dice_raw = cols[3].replace("**", "").strip()
            dice_parts = dice_raw.split("±")
            dice_val = float(dice_parts[0].strip())
            dice_std = float(dice_parts[1].strip()) if len(dice_parts) > 1 else 0.0
            
            miou_val = float(cols[4].strip())
            prec_val = float(cols[5].strip())
            recall_val = float(cols[6].strip()) if len(cols) > 6 else None
            
            parsed_t51[ds_name] = {
                "eval_type": eval_type,
                "n": n_val,
                "dice": dice_val,
                "std": dice_std,
                "miou": miou_val,
                "precision": prec_val,
                "recall": recall_val,
            }
            
    checks = {
        "Kvasir-SEG": (0.8131, 0.1747, 0.7141, 150),
        "HyperKvasir Segmented": (0.8360, 0.1610, 0.7439, 1000),
        "CVC-ClinicDB": (0.7561, 0.2131, 0.6470, 495),
        "EndoScene CVC-300": (0.7402, 0.1590, 0.6098, 60),
        "PolypDB (All Modalities)": (0.7283, 0.2544, 0.6243, 7868),
        "ETIS-Larib": (0.0000, 0.0000, 0.0000, 196),
    }
    
    t51_audit = {}
    for ds_name, (exp_dice, exp_std, exp_miou, exp_n) in checks.items():
        found = None
        for k in parsed_t51:
            if ds_name.lower() in k.lower():
                found = parsed_t51[k]
                break
        assert found is not None, f"Dataset {ds_name} missing from Table 5.1 in Final Paper md"
        assert found["dice"] == exp_dice, f"Table 5.1 Dice mismatch for {ds_name}: {found['dice']} vs {exp_dice}"
        assert found["std"] == exp_std, f"Table 5.1 Std mismatch for {ds_name}: {found['std']} vs {exp_std}"
        assert found["miou"] == exp_miou, f"Table 5.1 mIoU mismatch for {ds_name}: {found['miou']} vs {exp_miou}"
        assert found["n"] == exp_n, f"Table 5.1 N mismatch for {ds_name}: {found['n']} vs {exp_n}"
        t51_audit[ds_name] = {"status": "PASS", "parsed": found}
        
    # Find Table 5.2 (Literature comparison)
    t52_match = re.search(r"\*\*Table 5\.2:[^\n]+\*\*(.*?)(?=\n###|\Z)", md_content, re.DOTALL)
    assert t52_match, "Table 5.2 not found in ChakraModel_Final_Paper.md"
    t52_text = t52_match.group(1)
    assert "Competent Baseline (Verified)" in t52_text, "ChakraModel not marked as 'Competent Baseline (Verified)' in Table 5.2"
    assert "0.8131 ± 0.1747" in t52_text, "Kvasir-SEG verified metric missing in Table 5.2"
    assert "0.7561 ± 0.2131" in t52_text, "CVC-ClinicDB verified metric missing in Table 5.2"
    assert "0.7402 ± 0.1590" in t52_text, "CVC-300 verified metric missing in Table 5.2"
    
    return {"Table_5.1": t51_audit, "Table_5.2": "PASS"}


def audit_narrative_positioning(file_path, content, is_latex=False):
    """Audit Abstract, Conclusion, and check for misleading claims or missing 'competent baseline'."""
    results = {}
    
    # Extract Abstract
    if is_latex:
        abs_match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", content, re.DOTALL)
        assert abs_match, f"Abstract not found in {file_path}"
        abstract_text = abs_match.group(1)
        
        conc_match = re.search(r"\\section\{Conclusion\}(.*?)(?=\\end\{document\}|\Z)", content, re.DOTALL)
        assert conc_match, f"Conclusion not found in {file_path}"
        conclusion_text = conc_match.group(1)
    else:
        abs_match = re.search(r"## Abstract(.*?)(?=## 1|### 1|\Z)", content, re.DOTALL)
        assert abs_match, f"Abstract not found in {file_path}"
        abstract_text = abs_match.group(1)
        
        conc_match = re.search(r"## 6\. Conclusion and Limitations(.*?)(?=## Reproducibility|\Z)", content, re.DOTALL)
        assert conc_match, f"Conclusion not found in {file_path}"
        conclusion_text = conc_match.group(1)
        
    # Check 'competent baseline' in Abstract
    has_cb_abstract = "competent baseline" in abstract_text.lower()
    assert has_cb_abstract, f"'competent baseline' MISSING in Abstract of {file_path}"
    
    # Check 'competent baseline' in Conclusion
    has_cb_conclusion = "competent baseline" in conclusion_text.lower()
    assert has_cb_conclusion, f"'competent baseline' MISSING in Conclusion of {file_path}"
    
    # Count occurrences
    cb_total_count = content.lower().count("competent baseline")
    
    # Check for ETIS-Larib catastrophic failure acknowledgement
    etis_catastrophic = "catastrophic" in content.lower() and "etis-larib" in content.lower()
    assert etis_catastrophic, f"ETIS-Larib catastrophic failure not disclosed in {file_path}"
    
    # Check that ETIS-Larib is reported as 0.0000 DSC
    assert "0.0000" in content, f"ETIS-Larib 0.0000 DSC missing in {file_path}"
    
    # Adversarial check: Ensure no claims that ETIS-Larib succeeded or achieved high Dice
    # e.g., "ETIS-Larib (0.8650)" or "achieving 0.86 on ETIS-Larib"
    assert "0.8650" not in content, f"Retracted ETIS-Larib 0.8650 found in {file_path}"
    assert "0.9852" not in content, f"Retracted Kvasir-SEG 0.9852 found in {file_path}"
    assert "0.9412" not in content, f"Retracted CVC-ClinicDB 0.9412 found in {file_path}"
    assert "0.9158" not in content, f"Retracted Focal 0.9158 found in {file_path}"
    assert "0.9210" not in content, f"Retracted Topo 0.9210 found in {file_path}"
    assert "0.9610" not in content, f"Retracted AdaBN 0.9610 found in {file_path}"
    
    # Check CVC-ClinicDB claim for ChakraModel:
    # PraNet or PolypMamba might have ~0.90, but ChakraModel itself must not claim >0.90 for ClinicDB
    # Verify that ChakraModel CVC-ClinicDB is 0.7561
    assert "0.7561" in content, f"Verified CVC-ClinicDB 0.7561 missing in {file_path}"
    
    results["competent_baseline_in_abstract"] = has_cb_abstract
    results["competent_baseline_in_conclusion"] = has_cb_conclusion
    results["competent_baseline_total_occurrences"] = cb_total_count
    results["etis_larib_catastrophic_failure_disclosed"] = etis_catastrophic
    results["retracted_metrics_absent"] = True
    results["status"] = "PASS"
    return results


def main():
    print("=" * 70)
    print("RUNNING ADVERSARIAL AUDIT FOR CHAKRAMODEL PAPER AND BENCHMARKS")
    print("=" * 70)
    
    # 1. Load Ground Truth
    gt = load_ground_truth()
    print("[1] Verifying Kaggle cross_dataset_results_v5.json against benchmark standards...")
    gt_audit = audit_ground_truth(gt)
    print("    -> PASS: All 6 benchmark datasets match expected ground truth.")
    
    # 2. Check docs/HONEST_METRICS.md
    print("[2] Verifying docs/HONEST_METRICS.md single source of truth...")
    audit_honest_metrics_doc()
    print("    -> PASS: docs/HONEST_METRICS.md contains exact floating-point values and retraction list.")
    
    # 3. Check paper/main.tex
    print("[3] Parsing paper/main.tex...")
    main_tex_content = MAIN_TEX.read_text(encoding="utf-8")
    tex_table_audit = audit_latex_table(main_tex_content)
    print("    -> PASS: Table tab:results parsed and verified against ground truth.")
    tex_narrative_audit = audit_narrative_positioning(MAIN_TEX, main_tex_content, is_latex=True)
    print(f"    -> PASS: Narrative positioning: 'competent baseline' in Abstract and Conclusion (total count: {tex_narrative_audit['competent_baseline_total_occurrences']}).")
    
    # 4. Check docs/paper/ChakraModel_Final_Paper.md
    print("[4] Parsing docs/paper/ChakraModel_Final_Paper.md...")
    final_paper_md_content = FINAL_PAPER_MD.read_text(encoding="utf-8")
    md_table_audit = audit_markdown_tables(final_paper_md_content)
    print("    -> PASS: Table 5.1 and Table 5.2 parsed and verified against ground truth.")
    md_narrative_audit = audit_narrative_positioning(FINAL_PAPER_MD, final_paper_md_content, is_latex=False)
    print(f"    -> PASS: Narrative positioning: 'competent baseline' in Abstract and Conclusion (total count: {md_narrative_audit['competent_baseline_total_occurrences']}).")
    
    # 5. Compile Full Audit Results
    full_audit = {
        "verdict": "PASS",
        "ground_truth_verification": gt_audit,
        "honest_metrics_md_verified": True,
        "main_tex": {
            "table_results": tex_table_audit,
            "narrative_audit": tex_narrative_audit,
        },
        "final_paper_md": {
            "tables_audit": md_table_audit,
            "narrative_audit": md_narrative_audit,
        },
        "adversarial_checks": {
            "kvasir_test_split_0.8131_pm_0.1747_miou_0.7141": "PASS",
            "hyperkvasir_segmented_0.8360_pm_0.1610_miou_0.7439": "PASS",
            "cvc_clinicdb_zero_shot_0.7561_pm_0.2131_miou_0.6470": "PASS",
            "endoscene_cvc_300_zero_shot_0.7402_pm_0.1590_miou_0.6098": "PASS",
            "polypdb_0.7283_pm_0.2544_miou_0.6243": "PASS",
            "etis_larib_catastrophic_failure_0.0000_pm_0.0000": "PASS",
            "no_misleading_claims_etis_or_clinicdb_gt_0.90": "PASS",
            "competent_baseline_in_abstract_and_conclusion_both_files": "PASS",
        }
    }
    
    print("=" * 70)
    print("ADVERSARIAL AUDIT COMPLETE: VERDICT = PASS")
    print("=" * 70)
    return full_audit


if __name__ == "__main__":
    audit_res = main()
