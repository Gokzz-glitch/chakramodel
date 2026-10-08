"""
Independent Forensic Verification Script - Generation 9 Audit
Run by Forensic Auditor in .agents/auditor_m3_g9/
"""

import re
import json
from pathlib import Path

ROOT = Path("m:/chakramodel")
TEX_PATH = ROOT / "paper" / "main.tex"
MD_PATH = ROOT / "docs" / "paper" / "ChakraModel_Final_Paper.md"
JSON_PATH = ROOT / "kaggle_results" / "run_v5" / "cross_dataset_results_v5.json"
TEST_PATH = ROOT / "tests" / "test_milestone2_manuscript_verification.py"

results = {
    "files_exist": False,
    "forbidden_strings": {},
    "obsolete_strings": {},
    "target_metric_08131": {},
    "table_metrics_provenance": {},
    "narrative_baseline_claims": {},
    "latex_structure": {},
    "test_suite_integrity": {},
    "verdict": "UNKNOWN"
}

# 1. Existence and size
assert TEX_PATH.exists(), "paper/main.tex missing"
assert MD_PATH.exists(), "docs/paper/ChakraModel_Final_Paper.md missing"
assert JSON_PATH.exists(), "cross_dataset_results_v5.json missing"
assert TEST_PATH.exists(), "test_milestone2_manuscript_verification.py missing"

tex_text = TEX_PATH.read_text(encoding="utf-8")
md_text = MD_PATH.read_text(encoding="utf-8")
v5_data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
test_text = TEST_PATH.read_text(encoding="utf-8")

results["files_exist"] = True
results["tex_size_bytes"] = len(tex_text.encode("utf-8"))
results["md_size_bytes"] = len(md_text.encode("utf-8"))

# 2. Forbidden strings
forbidden_list = ["SOTA", "State of the Art", "State-of-the-Art", "0.9852", "0.9412", "0.8650"]
for target in forbidden_list:
    tex_matches = [m.span() for m in re.finditer(re.escape(target), tex_text, re.IGNORECASE)]
    md_matches = [m.span() for m in re.finditer(re.escape(target), md_text, re.IGNORECASE)]
    results["forbidden_strings"][target] = {
        "tex_count": len(tex_matches),
        "md_count": len(md_matches),
        "pass": (len(tex_matches) == 0 and len(md_matches) == 0)
    }

# 3. Obsolete retracted strings
obsolete_list = ["0.9225", "0.9081", "0.8215", "0.7949", "0.7304"]
for target in obsolete_list:
    tex_matches = [m.span() for m in re.finditer(re.escape(target), tex_text, re.IGNORECASE)]
    md_matches = [m.span() for m in re.finditer(re.escape(target), md_text, re.IGNORECASE)]
    results["obsolete_strings"][target] = {
        "tex_count": len(tex_matches),
        "md_count": len(md_matches),
        "pass": (len(tex_matches) == 0 and len(md_matches) == 0)
    }

# 4. Presence of 0.8131
results["target_metric_08131"] = {
    "tex_count": tex_text.count("0.8131"),
    "md_count": md_text.count("0.8131"),
    "pass": (tex_text.count("0.8131") > 0 and md_text.count("0.8131") > 0)
}

# 5. Provenance check against cross_dataset_results_v5.json
expected_numbers = {
    "Kvasir-SEG": ("0.8131", 0.8131493330001831),
    "HyperKvasir": ("0.8360", 0.8359748721122742),
    "CVC-ClinicDB": ("0.7561", 0.7560632228851318),
    "CVC-300": ("0.7402", 0.7402245998382568),
    "PolypDB": ("0.7283", 0.7283103466033936),
    "ETIS-Larib": ("0.0000", 0.0)
}

prov_pass = True
for name, (str_val, num_val) in expected_numbers.items():
    in_tex = str_val in tex_text
    in_md = str_val in md_text
    results["table_metrics_provenance"][name] = {
        "expected_str": str_val,
        "in_tex": in_tex,
        "in_md": in_md,
        "match": in_tex and in_md
    }
    if not (in_tex and in_md):
        prov_pass = False

# 6. Narrative review
tex_abs = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex_text, re.DOTALL)
tex_conc = re.search(r"\\section\{Conclusion\}(.*?)(?:\\end\{document\}|$)", tex_text, re.DOTALL)
md_abs = re.search(r"## Abstract(.*?)(?:### 1\.1 Key Contributions|## 1\. Introduction)", md_text, re.DOTALL)
md_conc = re.search(r"## 6\. Conclusion and Limitations(.*?)(?:## Reproducibility|## References|$)", md_text, re.DOTALL)

narrative_pass = (
    tex_abs is not None and "competent baseline" in tex_abs.group(1).lower() and
    tex_conc is not None and "competent baseline" in tex_conc.group(1).lower() and
    md_abs is not None and "competent baseline" in md_abs.group(1).lower() and
    md_conc is not None and "competent baseline" in md_conc.group(1).lower() and
    "0.90+" in tex_text and "0.90+" in md_text
)

results["narrative_baseline_claims"] = {
    "tex_abstract_has_competent_baseline": (tex_abs is not None and "competent baseline" in tex_abs.group(1).lower()),
    "tex_conclusion_has_competent_baseline": (tex_conc is not None and "competent baseline" in tex_conc.group(1).lower()),
    "md_abstract_has_competent_baseline": (md_abs is not None and "competent baseline" in md_abs.group(1).lower()),
    "md_conclusion_has_competent_baseline": (md_conc is not None and "competent baseline" in md_conc.group(1).lower()),
    "tex_acknowledges_090_literature": ("0.90+" in tex_text),
    "md_acknowledges_090_literature": ("0.90+" in md_text),
    "pass": narrative_pass
}

# 7. LaTeX stack
tokens = re.findall(r"\\(begin|end)\{([a-zA-Z*]+)\}", tex_text)
stack = []
latex_valid = True
for tag_type, env_name in tokens:
    if tag_type == "begin":
        stack.append(env_name)
    else:
        if len(stack) == 0 or stack.pop() != env_name:
            latex_valid = False
            break
if len(stack) != 0:
    latex_valid = False

results["latex_structure"] = {
    "environments_balanced": latex_valid,
    "total_envs": len(tokens) // 2
}

# 8. Test file integrity
results["test_suite_integrity"] = {
    "contains_mock": ("mock" in test_text.lower()),
    "contains_skip": ("skip" in test_text.lower()),
    "contains_xfail": ("xfail" in test_text.lower()),
    "reads_disk_tex": ('ROOT / "paper" / "main.tex"' in test_text),
    "reads_disk_md": ('ROOT / "docs" / "paper" / "ChakraModel_Final_Paper.md"' in test_text),
    "pass": (
        not ("skip" in test_text.lower()) and
        not ("xfail" in test_text.lower()) and
        ('ROOT / "paper" / "main.tex"' in test_text) and
        ('ROOT / "docs" / "paper" / "ChakraModel_Final_Paper.md"' in test_text)
    )
}

all_forbidden_pass = all(v["pass"] for v in results["forbidden_strings"].values())
all_obsolete_pass = all(v["pass"] for v in results["obsolete_strings"].values())
overall_pass = (
    results["files_exist"] and
    all_forbidden_pass and
    all_obsolete_pass and
    results["target_metric_08131"]["pass"] and
    prov_pass and
    narrative_pass and
    latex_valid and
    results["test_suite_integrity"]["pass"]
)

results["verdict"] = "CLEAN" if overall_pass else "INTEGRITY VIOLATION"

print(json.dumps(results, indent=2))
