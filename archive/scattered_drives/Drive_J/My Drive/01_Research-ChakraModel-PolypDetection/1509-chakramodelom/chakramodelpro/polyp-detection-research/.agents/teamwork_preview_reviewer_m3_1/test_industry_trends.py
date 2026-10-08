#!/usr/bin/env python3
"""
Independent Quality, Completeness & Adversarial Stress-Test Script
Target: docs/industry_trends.md
Author: Reviewer 1 (Milestone M3)
"""

import os
import re
import sys
from pathlib import Path

def test_industry_trends():
    doc_path = Path(r"m:\chakramodelpro\polyp-detection-research\docs\industry_trends.md")
    lit_path = Path(r"m:\chakramodelpro\polyp-detection-research\docs\literature_review.md")
    
    assert doc_path.exists(), f"Target file does not exist: {doc_path}"
    content = doc_path.read_text(encoding="utf-8")
    
    print(f"Loaded {doc_path} ({len(content)} characters, {len(content.splitlines())} lines).")
    
    # 1. Check for placeholders or unfinished tags
    placeholders = re.findall(r'\b(TODO|TBD|FIXME|LOREM IPSUM|PLACEHOLDER|INSERT HERE)\b', content, re.IGNORECASE)
    print(f"Placeholder count: {len(placeholders)}")
    assert len(placeholders) == 0, f"Found unfinished placeholders: {placeholders}"
    
    # 2. Check 7 top companies presence
    companies = [
        ("Medtronic / Cosmo Pharmaceuticals", ["GI Genius", "DEN200055", "Repici", "Hassan", "Wallace"]),
        ("Iterative Health", ["SKOUT", "K213123", "Shaukat", "APC", "hysteresis"]),
        ("Olympus", ["EndoBRAIN", "EndoBRAIN-EYE", "30000BZX00088000", "30200BZX00021000", "Mori", "Kudo", "Misawa"]),
        ("NEC Corporation", ["WISE VISION", "30200BZX00371000", "Yamada", "NCC"]),
        ("Fujifilm", ["CAD EYE", "EW10-EC01", "LCI", "BLI", "Neumann", "Weigt"]),
        ("Wision AI", ["EndoScreener", "K203382", "Liu", "Wang"]),
        ("Pentax Medical", ["Discovery", "Magentiq", "MAG-1", "i-scan"])
    ]
    
    for comp_name, keywords in companies:
        assert comp_name.lower() in content.lower() or any(k.lower() in content.lower() for k in keywords[:2]), f"Missing company: {comp_name}"
        missing_keys = [k for k in keywords if k not in content]
        print(f"Company '{comp_name}': Verified all keywords: {keywords}. Missing: {missing_keys}")
        assert len(missing_keys) == 0, f"Company {comp_name} missing key terms: {missing_keys}"

    # 3. Check ASCII diagrams
    ascii_diagrams = re.findall(r'```(?:\n|\r\n)(?:\+|\[)[^`]+```', content)
    print(f"Found {len(ascii_diagrams)} ASCII architecture/dataflow diagrams.")
    assert len(ascii_diagrams) >= 8, f"Expected at least 8 ASCII diagrams, found {len(ascii_diagrams)}"
    
    # 4. Check Comparison Table
    table_pattern = re.compile(r'\|(?:\s*\*\*?[a-zA-Z0-9_\-\[\]\s\./\(\)\+]+?\*\*?\s*\|){8,}')
    table_rows = [line for line in content.splitlines() if line.strip().startswith("|") and not line.strip().startswith("| :---")]
    print(f"Total markdown table lines: {len(table_rows)}")
    
    # Check that both commercial and academic models appear in table
    expected_models = [
        "GI Genius", "SKOUT", "EndoBRAIN-EYE", "EndoBRAIN", "WISE VISION", "CAD EYE", "EndoScreener", "Discovery",
        "PraNet", "Polyp-PVT", "ColonSegNet", "DoubleU-Net", "MSNet", "ESFPNet", "BGNet", "ST-PolypNet", "Mamba-VPS"
    ]
    for model in expected_models:
        found = any(model.lower() in line.lower() for line in table_rows)
        print(f"Model '{model}' in comparison matrix: {found}")
        assert found, f"Model {model} missing from comparison matrix!"

    # 5. Check Regulatory Submissions & Approvals
    regulatory_tokens = [
        "DEN200055", "21 CFR 876.1510", "QVD", "QNX", "K203382", "K213123",
        "30000BZX00088000", "30200BZX00021000", "30200BZX00371000", "EU MDR"
    ]
    for reg in regulatory_tokens:
        assert reg in content, f"Missing regulatory identifier: {reg}"
    print("All regulatory submission IDs verified.")

    # 6. Check Mathematical Formulas & Equations
    equations = [
        r"\mathbf{x}_t = [x_c, y_c, w, h, \dot{x}_c, \dot{y}_c, \dot{w}, \dot{h}]^T",
        r"\tau_{\text{init}}",
        r"\tau_{\text{maintain}}",
        r"\mathbf{F}",
        r"\mathbf{H}",
        r"\mathbf{C}_{ij}",
        r"\mathcal{L}_{\text{hard\_neg}}"
    ]
    for eq in equations:
        assert eq in content, f"Missing mathematical equation token: {eq}"
    print("All mathematical formalisms verified.")

    # 7. Check Cross-Reference with literature_review.md
    lit_content = lit_path.read_text(encoding="utf-8")
    for academic_model in ["PraNet [P03]", "Polyp-PVT [P07]", "ColonSegNet [P04]", "DoubleU-Net [P46]", "MSNet [P48]", "ESFPNet [P51]", "BGNet [P52]", "ST-PolypNet [P54]", "Mamba-VPS [P45]"]:
        pid = academic_model.split()[-1]
        assert pid in lit_content, f"Paper ID {pid} not found in literature_review.md!"
        assert pid in content, f"Paper ID {pid} not cross-referenced in industry_trends.md!"
    print("Cross-referencing with literature_review.md fully verified.")

    print("\nALL AUTOMATED VERIFICATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_industry_trends()
