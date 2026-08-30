"""
Verification and Test Suite for Worker 3: Combos 5 & 6
"""
import json
import ast
import os
import sys
from pathlib import Path
import nbformat

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

def test_notebooks():
    combo5_path = Path("m:/chakramodel/notebooks/Combo5_Federated_ChakraNet.ipynb")
    combo6_path = Path("m:/chakramodel/notebooks/Combo6_ChakraTransformer.ipynb")

    assert combo5_path.exists(), f"Missing {combo5_path}"
    assert combo6_path.exists(), f"Missing {combo6_path}"

    print(f"=== Testing Combo 5 Notebook: {combo5_path.name} ===")
    with open(combo5_path, "r", encoding="utf-8") as f:
        c5_data = json.load(f)
    with open(combo5_path, "r", encoding="utf-8") as f:
        c5_nb = nbformat.read(f, as_version=4)

    assert c5_nb.nbformat == 4, f"Expected nbformat 4, got {c5_nb.nbformat}"
    assert len(c5_nb.cells) >= 8, f"Expected at least 8 cells, got {len(c5_nb.cells)}"

    # Check Combo 5 key components
    all_c5_code = "\n".join(["\n".join(c.source.splitlines()) for c in c5_nb.cells if c.cell_type == "code"])
    assert "PraNetResNet101" in all_c5_code, "PraNetResNet101 missing from Combo 5"
    assert "FederatedClient" in all_c5_code, "FederatedClient missing from Combo 5"
    assert "FederatedServer" in all_c5_code, "FederatedServer missing from Combo 5"
    assert "aggregate_fedavg" in all_c5_code, "aggregate_fedavg missing from Combo 5"
    assert "batch_size=32" in all_c5_code or "batch_size = 32" in all_c5_code, "batch_size=32 missing from Combo 5"
    assert "num_workers=4" in all_c5_code or "num_workers = 4" in all_c5_code, "num_workers=4 missing from Combo 5"
    assert "autocast" in all_c5_code, "autocast missing from Combo 5"
    assert "setup_kvasir_seg_dataset" in all_c5_code, "setup_kvasir_seg_dataset missing from Combo 5"

    for idx, cell in enumerate(c5_nb.cells):
        if cell.cell_type == "code":
            clean_lines = [l if not (l.strip().startswith("!") or l.strip().startswith("%")) else f"# {l}" for l in cell.source.splitlines()]
            ast.parse("\n".join(clean_lines))
    print(f"✅ Combo 5 Notebook verified: {len(c5_nb.cells)} cells, valid JSON, valid AST.")

    print(f"\n=== Testing Combo 6 Notebook: {combo6_path.name} ===")
    with open(combo6_path, "r", encoding="utf-8") as f:
        c6_data = json.load(f)
    with open(combo6_path, "r", encoding="utf-8") as f:
        c6_nb = nbformat.read(f, as_version=4)

    assert c6_nb.nbformat == 4, f"Expected nbformat 4, got {c6_nb.nbformat}"
    assert len(c6_nb.cells) >= 8, f"Expected at least 8 cells, got {len(c6_nb.cells)}"

    # Check Combo 6 key components
    all_c6_code = "\n".join(["\n".join(c.source.splitlines()) for c in c6_nb.cells if c.cell_type == "code"])
    assert "ChakraTransformerSegmenter" in all_c6_code, "ChakraTransformerSegmenter missing from Combo 6"
    assert "vit_large_patch16_384" in all_c6_code, "vit_large_patch16_384 missing from Combo 6"
    assert "ProgressiveDecoderBlock" in all_c6_code, "ProgressiveDecoderBlock missing from Combo 6"
    assert "ConformalCalibrator" in all_c6_code, "ConformalCalibrator missing from Combo 6"
    assert "predict_conformal_bands" in all_c6_code, "predict_conformal_bands missing from Combo 6"
    assert "batch_size=32" in all_c6_code or "batch_size = 32" in all_c6_code, "batch_size=32 missing from Combo 6"
    assert "num_workers=4" in all_c6_code or "num_workers = 4" in all_c6_code, "num_workers=4 missing from Combo 6"
    assert "autocast" in all_c6_code, "autocast missing from Combo 6"
    assert "setup_kvasir_seg_dataset" in all_c6_code, "setup_kvasir_seg_dataset missing from Combo 6"

    for idx, cell in enumerate(c6_nb.cells):
        if cell.cell_type == "code":
            clean_lines = [l if not (l.strip().startswith("!") or l.strip().startswith("%")) else f"# {l}" for l in cell.source.splitlines()]
            ast.parse("\n".join(clean_lines))
    print(f"✅ Combo 6 Notebook verified: {len(c6_nb.cells)} cells, valid JSON, valid AST.")

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! Forensic audit verification complete.")

if __name__ == "__main__":
    test_notebooks()
