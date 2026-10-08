import os
import json
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

def test_10_percent_tail_truncation_artifact():
    """Verify that src/evaluate_all.py truncates to 10% and results in Table 5.1 artifact."""
    eval_script = ROOT / "src" / "evaluate_all.py"
    assert eval_script.exists(), "src/evaluate_all.py must exist"
    
    code = eval_script.read_text(encoding="utf-8")
    assert "n_test = max(1, int(0.1 * len(image_paths)))" in code, "Must contain 10% calculation"
    assert "image_paths = image_paths[-n_test:]" in code, "Must slice last 10% tail"

    # Verify final_5_datasets_eval.json
    results_path = ROOT / "results" / "final_5_datasets_eval.json"
    assert results_path.exists(), "results/final_5_datasets_eval.json must exist"
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert data["kvasir-seg"]["images"] == 100
    assert pytest.approx(data["kvasir-seg"]["dice"], rel=1e-3) == 0.9225
    
    assert data["cvc-clinicdb"]["images"] == 49
    assert pytest.approx(data["cvc-clinicdb"]["dice"], rel=1e-3) == 0.9081
    
    assert data["cvc-colondb"]["images"] == 38
    assert pytest.approx(data["cvc-colondb"]["dice"], rel=1e-3) == 0.8215
    
    assert data["cvc-300"]["images"] == 6
    assert pytest.approx(data["cvc-300"]["dice"], rel=1e-3) == 0.7949
    
    assert data["etis-larib"]["images"] == 1
    assert pytest.approx(data["etis-larib"]["dice"], rel=1e-3) == 0.9814

    # Verify Table 5.1 in paper
    paper_path = ROOT / "ChakraModel_Final_Paper.md"
    assert paper_path.exists()
    paper_text = paper_path.read_text(encoding="utf-8")
    assert "0.9225" in paper_text
    assert "0.9081" in paper_text
    assert "0.8215" in paper_text
    assert "0.7949" in paper_text
    assert "ETIS-Larib was excluded from this evaluation" in paper_text

    # Verify true_docs documentation
    doc_path = ROOT / "true_docs" / "verified_benchmarks_and_metrics.md"
    assert doc_path.exists()
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "38" in doc_text
    assert "6" in doc_text
    assert "1" in doc_text
    assert "10% Test Tail Truncation Artifact" in doc_text

def test_catastrophic_ood_collapse_on_full_cohorts():
    """Verify full-cohort evaluation collapse: ColonDB 0.0065, CVC-300 0.0048, ETIS 0.0000."""
    eval_dir = ROOT / "outputs" / "eval"
    assert eval_dir.exists(), "outputs/eval must exist"

    # Kvasir-SEG
    kvasir_json = eval_dir / "kvasir-seg_benchmark.json"
    assert kvasir_json.exists()
    with open(kvasir_json, "r", encoding="utf-8") as f:
        kv_data = json.load(f)
    assert kv_data["n_images"] == 1000
    assert pytest.approx(kv_data["dice"], abs=1e-4) == 0.9085
    assert pytest.approx(kv_data["dice_std"], abs=1e-4) == 0.1147
    assert pytest.approx(kv_data["iou"], abs=1e-4) == 0.8478
    # Ground truth iou_std in outputs/eval/kvasir-seg_benchmark.json is 0.1495,
    # whereas true_docs/verified_benchmarks_and_metrics.md copied an erroneous 0.1697 from an explorer report!
    assert pytest.approx(kv_data["iou_std"], abs=1e-4) == 0.1495
    assert pytest.approx(kv_data["sensitivity"], abs=1e-4) == 0.8965
    assert pytest.approx(kv_data["specificity"], abs=1e-4) == 0.9915
    # Ground truth w_fmeasure is 0.9095; 0.9240 reported in true_docs was f_beta_half from the markdown summary!
    assert pytest.approx(kv_data["w_fmeasure"], abs=1e-4) == 0.9095
    assert pytest.approx(kv_data["f_beta_half"], abs=1e-4) == 0.9240
    assert pytest.approx(kv_data["s_measure"], abs=1e-4) == 0.8556

    # CVC-ClinicDB
    clinicdb_json = eval_dir / "cvc-clinicdb_benchmark.json"
    assert clinicdb_json.exists()
    with open(clinicdb_json, "r", encoding="utf-8") as f:
        cl_data = json.load(f)
    assert cl_data["n_images"] == 495
    assert pytest.approx(cl_data["dice"], abs=1e-4) == 0.8066
    assert pytest.approx(cl_data["dice_std"], abs=1e-4) == 0.2482
    assert pytest.approx(cl_data["iou"], abs=1e-4) == 0.7286
    assert pytest.approx(cl_data["iou_std"], abs=1e-4) == 0.2584
    assert pytest.approx(cl_data["sensitivity"], abs=1e-4) == 0.8234
    assert pytest.approx(cl_data["specificity"], abs=1e-4) == 0.9905
    assert pytest.approx(cl_data["w_fmeasure"], abs=1e-4) == 0.8080
    assert pytest.approx(cl_data["s_measure"], abs=1e-4) == 0.7966

    # ColonDB
    colondb_json = eval_dir / "cvc-colondb_benchmark.json"
    assert colondb_json.exists()
    with open(colondb_json, "r", encoding="utf-8") as f:
        cdb_data = json.load(f)
    assert cdb_data["n_images"] == 380
    assert pytest.approx(cdb_data["dice"], abs=1e-4) == 0.0065
    assert pytest.approx(cdb_data["dice_std"], abs=1e-4) == 0.0732
    assert pytest.approx(cdb_data["iou"], abs=1e-4) == 0.0056
    assert pytest.approx(cdb_data["iou_std"], abs=1e-4) == 0.0638
    assert pytest.approx(cdb_data["sensitivity"], abs=1e-4) == 0.0063
    assert pytest.approx(cdb_data["specificity"], abs=1e-4) == 0.9999
    assert pytest.approx(cdb_data["w_fmeasure"], abs=1e-4) == 0.0065
    assert pytest.approx(cdb_data["s_measure"], abs=1e-4) == 0.2542

    # CVC-300
    cvc300_json = eval_dir / "cvc-300_benchmark.json"
    assert cvc300_json.exists()
    with open(cvc300_json, "r", encoding="utf-8") as f:
        c300_data = json.load(f)
    assert c300_data["n_images"] == 60
    assert pytest.approx(c300_data["dice"], abs=1e-4) == 0.0048
    assert pytest.approx(c300_data["dice_std"], abs=1e-4) == 0.0367
    assert pytest.approx(c300_data["iou"], abs=1e-4) == 0.0028
    assert pytest.approx(c300_data["iou_std"], abs=1e-4) == 0.0214
    assert pytest.approx(c300_data["sensitivity"], abs=1e-4) == 0.0028
    assert pytest.approx(c300_data["specificity"], abs=1e-4) == 1.0000
    assert pytest.approx(c300_data["w_fmeasure"], abs=1e-4) == 0.0048
    assert pytest.approx(c300_data["s_measure"], abs=1e-4) == 0.2532

    # ETIS local
    etis_json = eval_dir / "etis_benchmark.json"
    assert etis_json.exists()
    with open(etis_json, "r", encoding="utf-8") as f:
        etis_data = json.load(f)
    assert etis_data["n_images"] == 5
    assert pytest.approx(etis_data["dice"], abs=1e-4) == 0.0000
    assert pytest.approx(etis_data["dice_std"], abs=1e-4) == 0.0000
    assert pytest.approx(etis_data["iou"], abs=1e-4) == 0.0000
    assert pytest.approx(etis_data["sensitivity"], abs=1e-4) == 0.0000
    assert pytest.approx(etis_data["specificity"], abs=1e-4) == 1.0000
    assert pytest.approx(etis_data["w_fmeasure"], abs=1e-4) == 0.0000
    assert pytest.approx(etis_data["s_measure"], abs=1e-4) == 0.2500

    # Cross-dataset report (Kaggle run on full 196 ETIS images)
    cross_report = ROOT / "cross_dataset_report.md"
    assert cross_report.exists()
    cross_text = cross_report.read_text(encoding="utf-8")
    assert "ETIS-Larib (zero-shot)" in cross_text
    assert "196" in cross_text
    assert "0.0000" in cross_text

    # Verify true_docs accuracy
    doc_path = ROOT / "true_docs" / "verified_benchmarks_and_metrics.md"
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "0.0065" in doc_text
    assert "0.0048" in doc_text
    assert "0.0000" in doc_text
    assert "Catastrophic Out-of-Distribution Collapse" in doc_text

def test_latency_claims():
    """Verify latency claims: 94.7 FPS (standalone YOLOv8n) vs 3.7 FPS (integrated YOLOv8 + ViT-Large)."""
    latency_json = ROOT / "outputs" / "eval" / "fps_latency_report.json"
    assert latency_json.exists()
    with open(latency_json, "r", encoding="utf-8") as f:
        lat_data = json.load(f)
    
    stage1_fps = lat_data["stage1"]["fps"]
    assert pytest.approx(stage1_fps, rel=1e-2) == 94.7, f"Expected ~94.7 FPS, got {stage1_fps}"
    assert pytest.approx(lat_data["stage1"]["mean_ms"], rel=1e-2) == 10.56

    stage2_fps = lat_data["stage2"]["fps"]
    assert pytest.approx(stage2_fps, rel=1e-2) == 48.8, f"Expected ~48.8 FPS, got {stage2_fps}"

    # Ablation results for full hybrid pipeline
    ablation_md = ROOT / "ablation_results.md"
    assert ablation_md.exists()
    abl_text = ablation_md.read_text(encoding="utf-8")
    assert "3.7 FPS" in abl_text
    assert "0.4555" in abl_text

    # Paper latency statement
    paper_path = ROOT / "ChakraModel_Final_Paper.md"
    paper_text = paper_path.read_text(encoding="utf-8")
    assert "94.7 FPS" in paper_text
    assert "3.7 FPS" in paper_text

    # true_docs latency coverage
    doc_path = ROOT / "true_docs" / "verified_benchmarks_and_metrics.md"
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "94.67 FPS" in doc_text or "94.7" in doc_text
    assert "3.70 FPS" in doc_text or "3.7 FPS" in doc_text
    assert "48.8" in doc_text

def test_statistical_significance_invalidation():
    """Verify that statistical_significance.py invalidates p-values due to RealModel dummy."""
    stat_script = ROOT / "statistical_significance.py"
    assert stat_script.exists()
    lines = stat_script.read_text(encoding="utf-8").splitlines()
    
    # Check lines 14-23
    header_block = "\n".join(lines[13:32])
    assert "CRITICAL BUG" in header_block
    assert "RealModel" in header_block
    assert "RANDOM weights" in header_block
    assert "MEANINGLESS" in header_block

    # Check true_docs
    doc_path = ROOT / "true_docs" / "verified_benchmarks_and_metrics.md"
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "Invalidation of Statistical Significance Claims" in doc_text
    assert "RealModel" in doc_text

def test_paper_internal_contradiction():
    """Adversarial stress-test: uncover internal contradiction in ChakraModel_Final_Paper.md line 159."""
    paper_path = ROOT / "ChakraModel_Final_Paper.md"
    paper_text = paper_path.read_text(encoding="utf-8")
    
    # Check that paper paradoxically calls 0.8215 DSC 'near-zero'
    pattern = r"yielding near-zero scores on CVC-ColonDB \(\*\*0\.8215 DSC\*\*\) and CVC-300 \(\*\*0\.7949 DSC\*\*\)"
    match = re.search(pattern, paper_text)
    assert match is not None, "Paper contains verbatim contradiction: calling 0.8215 and 0.7949 'near-zero scores'"
