"""
PyTest Suite for Adversarial Paper Metrics and Narrative Alignment Audit
Challenger 2 (Milestone 3, Generation 9)
"""

import json
import re
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
KAGGLE_JSON = BASE_DIR / "kaggle_results" / "run_v5" / "cross_dataset_results_v5.json"
HONEST_METRICS_MD = BASE_DIR / "docs" / "HONEST_METRICS.md"
MAIN_TEX = BASE_DIR / "paper" / "main.tex"
FINAL_PAPER_MD = BASE_DIR / "docs" / "paper" / "ChakraModel_Final_Paper.md"


@pytest.fixture(scope="module")
def kaggle_data():
    with open(KAGGLE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def honest_metrics_text():
    return HONEST_METRICS_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def main_tex_text():
    return MAIN_TEX.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def final_paper_md_text():
    return FINAL_PAPER_MD.read_text(encoding="utf-8")


def test_kvasir_seg_metric_exactness(kaggle_data, main_tex_text, final_paper_md_text):
    kvasir = kaggle_data["Kvasir-SEG (test split)"]
    dice = round(kvasir["dice"], 4)
    std = round(kvasir["std"], 4)
    miou = round(kvasir["iou"], 4)
    n = kvasir["n"]
    
    assert dice == 0.8131
    assert std == 0.1747
    assert miou == 0.7141
    assert n == 150
    
    # Check paper/main.tex
    assert "0.8131" in main_tex_text
    assert "0.1747" in main_tex_text
    assert "0.7141" in main_tex_text
    assert "150" in main_tex_text
    
    # Check docs/paper/ChakraModel_Final_Paper.md
    assert "0.8131 ± 0.1747" in final_paper_md_text
    assert "0.7141" in final_paper_md_text


def test_hyperkvasir_segmented_exactness(kaggle_data, main_tex_text, final_paper_md_text):
    hk = kaggle_data["HyperKvasir Segmented"]
    dice = round(hk["dice"], 4)
    std = round(hk["std"], 4)
    miou = round(hk["iou"], 4)
    n = hk["n"]
    
    assert dice == 0.8360
    assert std == 0.1610
    assert miou == 0.7439
    assert n == 1000
    
    assert "0.8360" in main_tex_text
    assert "0.1610" in main_tex_text
    assert "0.7439" in main_tex_text
    assert "1000" in main_tex_text
    
    assert "0.8360 ± 0.1610" in final_paper_md_text
    assert "0.7439" in final_paper_md_text


def test_cvc_clinicdb_zero_shot_exactness(kaggle_data, main_tex_text, final_paper_md_text):
    clinic = kaggle_data["CVC-ClinicDB (zero-shot)"]
    dice = round(clinic["dice"], 4)
    std = round(clinic["std"], 4)
    miou = round(clinic["iou"], 4)
    n = clinic["n"]
    
    assert dice == 0.7561
    assert std == 0.2131
    assert miou == 0.6470
    assert n == 495
    
    assert "0.7561" in main_tex_text
    assert "0.2131" in main_tex_text
    assert "0.6470" in main_tex_text
    assert "495" in main_tex_text
    
    assert "0.7561 ± 0.2131" in final_paper_md_text
    assert "0.6470" in final_paper_md_text


def test_endoscene_cvc_300_zero_shot_exactness(kaggle_data, main_tex_text, final_paper_md_text):
    cvc300 = kaggle_data["EndoScene CVC-300 (zero-shot)"]
    dice = round(cvc300["dice"], 4)
    std = round(cvc300["std"], 4)
    miou = round(cvc300["iou"], 4)
    n = cvc300["n"]
    
    assert dice == 0.7402
    assert std == 0.1590
    assert miou == 0.6098
    assert n == 60
    
    assert "0.7402" in main_tex_text
    assert "0.1590" in main_tex_text
    assert "0.6098" in main_tex_text
    assert "60" in main_tex_text
    
    assert "0.7402 ± 0.1590" in final_paper_md_text
    assert "0.6098" in final_paper_md_text


def test_polypdb_exactness(kaggle_data, main_tex_text, final_paper_md_text):
    polypdb = kaggle_data["PolypDB (All Modalities)"]
    dice = round(polypdb["dice"], 4)
    std = round(polypdb["std"], 4)
    miou = round(polypdb["iou"], 4)
    n = polypdb["n"]
    
    assert dice == 0.7283
    assert std == 0.2544
    assert miou == 0.6243
    assert n == 7868
    
    assert "0.7283" in main_tex_text
    assert "0.2544" in main_tex_text
    assert "0.6243" in main_tex_text
    assert "7868" in main_tex_text
    
    assert "0.7283 ± 0.2544" in final_paper_md_text
    assert "0.6243" in final_paper_md_text


def test_etis_larib_catastrophic_failure(kaggle_data, main_tex_text, final_paper_md_text):
    etis = kaggle_data["ETIS-Larib (zero-shot)"]
    assert etis["dice"] == 0.0
    assert etis["std"] == 0.0
    assert etis["iou"] == 0.0
    assert etis["n"] == 196
    
    # Check paper/main.tex
    assert "0.0000" in main_tex_text
    assert "catastrophic" in main_tex_text.lower()
    
    # Check docs/paper/ChakraModel_Final_Paper.md
    assert "0.0000 ± 0.0000" in final_paper_md_text
    assert "catastrophic failure" in final_paper_md_text.lower()


def test_no_misleading_claims(main_tex_text, final_paper_md_text):
    retracted_vals = ["0.9852", "0.9412", "0.8650", "0.9158", "0.9210", "0.9610"]
    for val in retracted_vals:
        assert val not in main_tex_text, f"Retracted value {val} found in main.tex"
        assert val not in final_paper_md_text, f"Retracted value {val} found in final paper md"
        
    # Check that CVC-ClinicDB for ChakraModel is always reported as 0.7561 and never >0.90
    for doc_name, text in [("main.tex", main_tex_text), ("ChakraModel_Final_Paper.md", final_paper_md_text)]:
        for line in text.splitlines():
            if "CVC-ClinicDB" in line and ("ChakraModel" in line or "ChakraTransformer" in line or "Zero-Shot" in line):
                # If there's a dice value in this line, ensure it is not >0.90
                dices = re.findall(r"\b0\.\d{4}\b", line)
                for d in dices:
                    # In Table 5.2, ChakraModel has 0.7561, 0.8131, 0.7402; literature baselines have others
                    if "Chakra" in line or "Zero-Shot" in line:
                        assert float(d) < 0.90, f"Suspiciously high metric {d} for ChakraModel on CVC-ClinicDB in {doc_name}: {line}"


def test_competent_baseline_present(main_tex_text, final_paper_md_text):
    # LaTeX Abstract
    abs_tex = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", main_tex_text, re.DOTALL).group(1)
    assert "competent baseline" in abs_tex.lower()
    
    # LaTeX Conclusion
    conc_tex = re.search(r"\\section\{Conclusion\}(.*?)(?=\\end\{document\}|\Z)", main_tex_text, re.DOTALL).group(1)
    assert "competent baseline" in conc_tex.lower()
    
    # Markdown Abstract
    abs_md = re.search(r"## Abstract(.*?)(?=## 1|### 1|\Z)", final_paper_md_text, re.DOTALL).group(1)
    assert "competent baseline" in abs_md.lower()
    
    # Markdown Conclusion
    conc_md = re.search(r"## 6\. Conclusion and Limitations(.*?)(?=## Reproducibility|\Z)", final_paper_md_text, re.DOTALL).group(1)
    assert "competent baseline" in conc_md.lower()
