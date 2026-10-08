"""
Automated Verification Script for Milestone 3 Performance Analysis
Challenger 1 (teamwork_preview_challenger)
Target: docs/PERFORMANCE_ANALYSIS.md
Reference: outputs/eval/pipeline_profiling_report.json
"""

import os
import sys
import json
import re

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def main():
    print("=" * 80)
    print("STARTING EMPIRICAL VERIFICATION OF docs/PERFORMANCE_ANALYSIS.md")
    print("=" * 80)

    doc_path = r"M:\chakramodel\docs\PERFORMANCE_ANALYSIS.md"
    json_path = r"M:\chakramodel\outputs\eval\pipeline_profiling_report.json"

    checks_passed = 0
    checks_failed = 0
    findings = []

    # -------------------------------------------------------------------------
    # Check 1: File existence and non-zero size
    # -------------------------------------------------------------------------
    print("\n[CHECK 1] Verifying file existence and non-zero size...")
    if not os.path.exists(doc_path):
        print(f"FAIL: {doc_path} does not exist!")
        checks_failed += 1
        return
    doc_size = os.path.getsize(doc_path)
    if doc_size == 0:
        print(f"FAIL: {doc_path} is empty (0 bytes)!")
        checks_failed += 1
        return
    print(f"PASS: {doc_path} exists ({doc_size:,} bytes, {doc_size/1024:.2f} KB).")
    checks_passed += 1

    with open(doc_path, "r", encoding="utf-8") as f:
        doc_text = f.read()

    # -------------------------------------------------------------------------
    # Check 2: Load pipeline profiling JSON and verify metrics extraction
    # -------------------------------------------------------------------------
    print("\n[CHECK 2] Loading outputs/eval/pipeline_profiling_report.json and matching metrics...")
    if not os.path.exists(json_path):
        print(f"FAIL: {json_path} does not exist!")
        checks_failed += 1
        return

    with open(json_path, "r", encoding="utf-8") as f:
        prof_data = json.load(f)

    # Key profiling metrics to verify in document:
    yolo_mean = prof_data["components"]["yolo_detection"]["mean_ms"]
    yolo_fps = prof_data["components"]["yolo_detection"]["standalone_fps"]
    vit_fp32_mean = prof_data["components"]["vit_large_fp32_single_pass"]["mean_ms"]
    vit_fp32_fps = prof_data["components"]["vit_large_fp32_single_pass"]["fps"]
    vit_amp_mean = prof_data["components"]["vit_large_amp_fp16_single_pass"]["mean_ms"]
    vit_amp_fps = prof_data["components"]["vit_large_amp_fp16_single_pass"]["fps"]
    vit_tta_mean = prof_data["components"]["vit_large_3pass_tta"]["mean_ms"]
    vit_tta_fps = prof_data["components"]["vit_large_3pass_tta"]["fps"]

    print(f"JSON YOLO Detection: mean={yolo_mean:.2f} ms, fps={yolo_fps:.2f}")
    print(f"JSON ViT FP32: mean={vit_fp32_mean:.2f} ms, fps={vit_fp32_fps:.2f}")
    print(f"JSON ViT AMP FP16: mean={vit_amp_mean:.2f} ms, fps={vit_amp_fps:.2f}")
    print(f"JSON ViT 3-Pass TTA: mean={vit_tta_mean:.2f} ms, fps={vit_tta_fps:.2f}")

    # Search for patterns in document
    metric_patterns = [
        ("YOLO Latency (19.67 ms / 19.7 ms)", r"19\.67|19\.7\s*ms"),
        ("YOLO FPS (50.8 FPS / 50.84 FPS)", r"50\.8(?:4)?\s*FPS"),
        ("ViT FP32 Latency (167.26 ms / 167.3 ms)", r"167\.26|167\.3\s*ms"),
        ("ViT FP32 FPS (5.98 FPS)", r"5\.98\s*FPS"),
        ("ViT AMP Latency (87.27 ms / 87.3 ms)", r"87\.27|87\.3\s*ms"),
        ("ViT AMP FPS (11.46 FPS / 11.5 FPS)", r"11\.46|11\.5\s*FPS"),
        ("ViT 3-Pass TTA Latency (175.15 ms / 175.2 ms)", r"175\.15|175\.2\s*ms"),
        ("ViT 3-Pass TTA FPS (5.71 FPS)", r"5\.71\s*FPS"),
    ]

    for name, pattern in metric_patterns:
        matches = re.findall(pattern, doc_text, re.IGNORECASE)
        if matches:
            print(f"  PASS: Found {name}: {matches[:3]}")
            checks_passed += 1
        else:
            print(f"  FAIL: Could not find pattern for {name} ({pattern})")
            checks_failed += 1
            findings.append(f"Missing expected metric pattern: {name}")

    # Also check scenarios from JSON:
    scenario_patterns = [
        ("Zero Polyps (19.67 ms, 50.8 FPS)", r"19\.67\s*ms.*?50\.8\s*FPS"),
        ("One Polyp Single Pass AMP (109.94 ms, 9.1 FPS)", r"109\.94\s*ms.*?9\.1\s*FPS"),
        ("One Polyp Default TTA (197.82 ms, 5.1 FPS / 5.06 FPS)", r"197\.82\s*ms.*?(?:5\.1|5\.06)\s*FPS"),
        ("Two Polyps Default TTA (375.97 ms, 2.7 FPS / 2.66 FPS)", r"375\.97\s*ms.*?(?:2\.7|2\.66)\s*FPS"),
    ]
    for name, pattern in scenario_patterns:
        match = re.search(pattern, doc_text, re.IGNORECASE | re.DOTALL)
        if match:
            print(f"  PASS: Scenario matched: {name}")
            checks_passed += 1
        else:
            print(f"  FAIL: Scenario missing or mismatch: {name}")
            checks_failed += 1
            findings.append(f"Scenario metric mismatch: {name}")

    # Check VRAM metrics from JSON
    vram_patterns = [
        ("ViT-Large weights VRAM (1180.4 MB / 1.15 GB)", r"1,?180\.4\s*MB|1\.15\s*GB"),
        ("Peak allocated VRAM (1868.8 MB / 1.82 GB)", r"1,?868\.8\s*MB|1\.82\s*GB"),
        ("Peak reserved VRAM (1972.0 MB / 1.93 GB)", r"1,?972(?:\.0)?\s*MB|1\.93\s*GB"),
    ]
    for name, pattern in vram_patterns:
        matches = re.findall(pattern, doc_text, re.IGNORECASE)
        if matches:
            print(f"  PASS: Found VRAM metric {name}: {matches[:2]}")
            checks_passed += 1
        else:
            print(f"  FAIL: Could not find VRAM metric {name}")
            checks_failed += 1
            findings.append(f"Missing VRAM metric: {name}")

    # -------------------------------------------------------------------------
    # Check 3: Search and count open-source video polyp datasets
    # -------------------------------------------------------------------------
    print("\n[CHECK 3] Verifying open-source video datasets (Target: count >= 2)...")
    datasets = {
        "SUN-SEG": len(re.findall(r"\bSUN-SEG\b", doc_text)),
        "CVC-VideoClinicDB": len(re.findall(r"\bCVC-(?:VideoClinicDB|ClinicVideoDB)\b", doc_text)),
        "LDPolypVideo": len(re.findall(r"\bLDPolypVideo\b", doc_text)),
        "PolypGen (Video)": len(re.findall(r"\bPolypGen\b", doc_text)),
        "HyperKvasir (Video)": len(re.findall(r"\bHyperKvasir\b", doc_text)),
        "EndoScene": len(re.findall(r"\bEndoScene\b", doc_text)),
    }

    found_datasets = [k for k, v in datasets.items() if v > 0]
    print(f"Datasets found ({len(found_datasets)} distinct benchmarks):")
    for ds, count in datasets.items():
        print(f"  - {ds}: {count} occurrences")

    if len(found_datasets) >= 2:
        print(f"PASS: Found {len(found_datasets)} video datasets (>= 2 required).")
        checks_passed += 1
    else:
        print(f"FAIL: Found only {len(found_datasets)} video datasets (< 2 required).")
        checks_failed += 1
        findings.append(f"Insufficient video datasets: found {len(found_datasets)}, required >= 2.")

    # -------------------------------------------------------------------------
    # Check 4: Search and count literature citations
    # -------------------------------------------------------------------------
    print("\n[CHECK 4] Verifying literature citations (Target: count >= 2)...")
    citations = {
        "PNS-Net (Ji et al. MICCAI 2021 / MedIA 2023)": len(re.findall(r"\bPNS-Net\b", doc_text)),
        "ST-PUNet": len(re.findall(r"\bST-PUNet\b", doc_text)),
        "FSNet": len(re.findall(r"\bFSNet\b", doc_text)),
        "PolyMamba-Net": len(re.findall(r"\bPolyMamba-Net\b", doc_text)),
        "MAPSeg": len(re.findall(r"\bMAPSeg\b", doc_text)),
        "SegFormer (Xie et al. NeurIPS 2021)": len(re.findall(r"\bSegFormer\b", doc_text)),
        "LDPolypVideo paper (Ma et al. MICCAI 2021)": len(re.findall(r"\bMa et al\b", doc_text)),
        "PolypGen paper (Ali et al. Sci Data 2023)": len(re.findall(r"\bAli et al\b", doc_text)),
    }

    found_citations = [k for k, v in citations.items() if v > 0]
    print(f"Literature citations found ({len(found_citations)} distinct references):")
    for cit, count in citations.items():
        print(f"  - {cit}: {count} occurrences")

    if len(found_citations) >= 2:
        print(f"PASS: Found {len(found_citations)} literature references (>= 2 required).")
        checks_passed += 1
    else:
        print(f"FAIL: Found only {len(found_citations)} literature references (< 2 required).")
        checks_failed += 1
        findings.append(f"Insufficient literature citations: found {len(found_citations)}, required >= 2.")

    # -------------------------------------------------------------------------
    # Check 5: Search and count failure modes in video polyp segmentation
    # -------------------------------------------------------------------------
    print("\n[CHECK 5] Verifying failure modes in video polyp segmentation (Target: count >= 2)...")
    failure_modes = {
        "Motion Blur & Rapid Camera Dynamics": len(re.findall(r"motion blur", doc_text, re.IGNORECASE)),
        "Temporal Inconsistency / Mask Flickering": len(re.findall(r"(?:temporal inconsistency|mask flickering|flickering)", doc_text, re.IGNORECASE)),
        "Specular Glare / Mucosal Reflection": len(re.findall(r"(?:specular glare|specular reflection|mucosal reflections)", doc_text, re.IGNORECASE)),
        "Occlusions / Fluids / Debris / Feces / Bubbles": len(re.findall(r"(?:occlusion|debris|feces|bubbles|biopsy snares)", doc_text, re.IGNORECASE)),
        "Tissue Deformation / Peristalsis": len(re.findall(r"(?:peristaltic|peristalsis|tissue deformation)", doc_text, re.IGNORECASE)),
    }

    found_modes = [k for k, v in failure_modes.items() if v > 0]
    print(f"Failure modes found ({len(found_modes)} distinct categories):")
    for fm, count in failure_modes.items():
        print(f"  - {fm}: {count} mentions")

    if len(found_modes) >= 2:
        print(f"PASS: Found {len(found_modes)} failure modes (>= 2 required).")
        checks_passed += 1
    else:
        print(f"FAIL: Found only {len(found_modes)} failure modes (< 2 required).")
        checks_failed += 1
        findings.append(f"Insufficient failure modes: found {len(found_modes)}, required >= 2.")

    # -------------------------------------------------------------------------
    # Check 6: Adversarial Consistency Analysis
    # -------------------------------------------------------------------------
    print("\n[CHECK 6] Running Adversarial Consistency Checks...")

    # A: Check for undefined or vague claims
    vague_phrases = [
        r"it is obvious that",
        r"roughly speaking",
        r"some milliseconds",
        r"very fast",
        r"blazing fast",
        r"infinitely",
    ]
    found_vague = []
    for vp in vague_phrases:
        m = re.findall(vp, doc_text, re.IGNORECASE)
        if m:
            found_vague.append((vp, len(m)))

    if found_vague:
        print(f"  WARNING: Detected vague phrases: {found_vague}")
        findings.append(f"Vague phrases detected: {found_vague}")
    else:
        print("  PASS: No informal/vague qualitative phrases detected.")
        checks_passed += 1

    # B: Check unit consistency on numbers (e.g. latency numbers accompanied by ms or FPS)
    # Check if any standalone latency numbers lack ms/FPS
    table_lines = [line for line in doc_text.splitlines() if "|" in line]
    print(f"  Analyzed {len(table_lines)} markdown table rows for unit specifications.")

    # C: Check Table 7.5 vs Section 1.3 / Section 3.3 consistency:
    # Notice: In Table 7.5 line 916: "ChakraModel Baseline (YOLOv8x + ViT-Large + 5 Writers) | FP32 PyTorch | 372.6M | 258 + 191 | 42.0 ms | 172.0 ms | 270.3 ms | 3.7 FPS"
    # Versus Section 1.3: Stage 1 YOLOv8n Detection: 19.67 ms.
    # Why does Table 7.5 baseline say "YOLOv8x" (42.0 ms) while Section 1.3 and Section 3.3 profile "YOLOv8n" (19.67 ms)?
    # Let's inspect this!
    print("  Checking YOLO variant naming across sections...")
    yolo_variants_v8n = len(re.findall(r"YOLOv8n", doc_text))
    yolo_variants_v8x = len(re.findall(r"YOLOv8x", doc_text))
    yolo_variants_v8s = len(re.findall(r"YOLOv8s", doc_text))
    print(f"  Occurrences of YOLOv8n: {yolo_variants_v8n}")
    print(f"  Occurrences of YOLOv8x: {yolo_variants_v8x}")
    print(f"  Occurrences of YOLOv8s: {yolo_variants_v8s}")

    # Let's check where YOLOv8x is mentioned
    v8x_lines = [(i+1, l) for i, l in enumerate(doc_text.splitlines()) if "YOLOv8x" in l]
    for lnum, lcontent in v8x_lines:
        print(f"    Line {lnum}: {lcontent.strip()}")

    # D: Check FLOPs / GMACs distinction in Section 3.5:
    # Line 367: FLOPs_backbone = 24 * 15.884 GFLOPs ≈ 381.2 GFLOPs (FP32 MAC ops) ≈ 190.6 GMACs
    # Line 371: Compute_TTA = 3 * 190.6 GMACs = 571.8 GFLOPs.
    # Note: 1 MAC = 2 FLOPs. If 190.6 is GMACs, then 3 * 190.6 GMACs = 571.8 GMACs = 1143.6 GFLOPs!
    # OR if 190.6 is GFLOPs, then 3 * 190.6 = 571.8 GFLOPs.
    # Let's flag this mathematical nuance in the challenge!
    print("  Checking mathematical consistency in Section 3.5 (FLOPs vs GMACs)...")
    if "381.2 GFLOPs (FP32 MAC ops)" in doc_text or "571.8 GFLOPs" in doc_text:
        print("  NOTICE: Found FLOPs / MAC calculation in Section 3.5 to challenge.")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f"VERIFICATION SUMMARY: {checks_passed} PASSED, {checks_failed} FAILED")
    print("=" * 80)
    if checks_failed == 0:
        print("FINAL VERDICT: ALL ACCEPTANCE CRITERIA MET (PASS)")
    else:
        print(f"FINAL VERDICT: CRITERIA FAILED (FAIL - {checks_failed} issues)")

    return checks_passed, checks_failed, findings

if __name__ == "__main__":
    main()
