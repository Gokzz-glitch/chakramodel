"""
test_target_baselines_adversarial.py
====================================
Adversarial & empirical verification test suite for ChakraModel target baseline claims:
1. SUN-SEG is 100% absent across the repository.
2. CVC-VideoClinicDB (18 sequences) is absent and conflated with static CVC-ClinicDB.
3. LDPolypVideo is absent as a continuous video benchmark (<2% static slice, failed to mount, paper claims fabricated).
4. PolypGen is 100% absent and replaced by PolypDB.
"""

import json
import os
import re
import struct
import zipfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_sun_seg_complete_absence_and_citations():
    """Verify Claim 1: SUN-SEG is 100% absent across codebase and citations match verbatim."""
    # 1. Verify build_master_eval_notebook.py line 13
    build_nb = ROOT / "build_master_eval_notebook.py"
    assert build_nb.exists(), "build_master_eval_notebook.py must exist"
    lines = build_nb.read_text(encoding="utf-8").splitlines()
    # Check lines around 13
    line_13 = lines[12]  # 0-indexed line 12 is line 13
    assert "SUN-SEG" in line_13, f"Expected SUN-SEG on line 13, got: {line_13}"
    assert "not uploaded yet, 12.5 GB" in line_13, f"Expected upload status, got: {line_13}"

    # 2. Verify REPORT.txt citations
    report_txt = ROOT / "REPORT.txt"
    assert report_txt.exists(), "REPORT.txt must exist"
    rep_lines = report_txt.read_text(encoding="utf-8").splitlines()

    # Lines 159-160
    assert "### 2.5 SUN-SEG Access Problem" in rep_lines[158]
    assert "SUN-SEG, 158,690 frames" in rep_lines[159]
    assert "emailing the original database maintainer" in rep_lines[159]

    # Line 240
    assert any("Do NOT wait for LDPolypVideo or SUN-SEG" in l for l in rep_lines[235:245]), (
        "Expected instruction not to wait for SUN-SEG around L240"
    )

    # Line 445
    assert any("LDPolypVideo / SUN-SEG not accessible in time" in l and "Already excluded from plan" in l
               for l in rep_lines[440:450]), "Expected risk table entry around L445"

    # 3. Empirically verify 0 image/mask/video files belonging to SUN-SEG exist in data/ or Kaggle_Datasets_Upload/
    for search_dir in [ROOT / "data", ROOT / "Kaggle_Datasets_Upload"]:
        if search_dir.exists():
            sun_files = [f for f in search_dir.rglob("*") if "sun" in f.name.lower()]
            assert len(sun_files) == 0, f"Found unexpected SUN-SEG files in {search_dir}: {sun_files}"


def test_cvc_videoclinicdb_absence_and_conflation():
    """Verify Claim 2: CVC-VideoClinicDB (18 sequences) is absent and conflated with static CVC-ClinicDB."""
    # 1. Verify REPORT.txt line 502
    report_txt = ROOT / "REPORT.txt"
    rep_lines = report_txt.read_text(encoding="utf-8").splitlines()
    line_502 = rep_lines[501]  # 0-indexed 501 is line 502
    assert "CVC-ClinicVideoDB (the actual name" in line_502
    assert "\"CVC-VideoClinicDB\" is a common misspelling" in line_502
    assert "balraj98/cvcclinicdb" in line_502
    assert "612-image dataset" in line_502
    assert "conflate these two" in line_502

    # 2. Verify build_crossval_v5.py L14 and L28 (conflation with 495 static images)
    crossval_v5 = ROOT / "build_crossval_v5.py"
    assert crossval_v5.exists()
    v5_lines = crossval_v5.read_text(encoding="utf-8").splitlines()
    assert any("cvc-clinicdb/images  [495 images]" in l for l in v5_lines[:25])
    assert any("CVC-ClinicDB: 495 images" in l for l in v5_lines[:35])

    # 3. Verify cross_dataset_report.md evaluated static CVC-ClinicDB (495 frames), not 18 video sequences
    cross_report = ROOT / "cross_dataset_report.md"
    assert cross_report.exists()
    cross_text = cross_report.read_text(encoding="utf-8")
    assert "CVC-ClinicDB (zero-shot)" in cross_text
    assert "495" in cross_text
    assert "0.7561" in cross_text
    assert "CVC-VideoClinicDB" not in cross_text
    assert "ClinicVideoDB" not in cross_text

    # 4. Verify CVC_ClinicVideoDB_Kaggle.zip has 0 ground truth annotations and fails standard zip parsing
    zip_path = ROOT / "CVC_ClinicVideoDB_Kaggle.zip"
    assert zip_path.exists()
    with pytest.raises(zipfile.BadZipFile):
        zipfile.ZipFile(zip_path, "r")

    # Byte-level check: confirm it contains 42 pairs of unannotated clips, NOT 18 annotated sequences
    with open(zip_path, "rb") as f:
        file_count = 0
        has_gt = False
        while True:
            sig = f.read(4)
            if sig != b"PK\x03\x04":
                break
            f.seek(14, 1)
            comp_size, uncomp_size, name_len, extra_len = struct.unpack("<IIHH", f.read(12))
            fn = f.read(name_len).decode("utf-8", errors="ignore")
            f.seek(extra_len + comp_size, 1)
            file_count += 1
            if "mask" in fn.lower() or "ground" in fn.lower() or "gt" in fn.lower():
                has_gt = True
            if comp_size == 0xFFFFFFFF:
                break
    assert file_count == 88, f"Expected 88 entries in local headers, found {file_count}"
    assert not has_gt, "CVC_ClinicVideoDB_Kaggle.zip must contain 0 ground-truth annotations"


def test_ldpolypvideo_absence_and_fabrication():
    """Verify Claim 3: LDPolypVideo is absent as video benchmark (<2% static slice, unmounted, fabricated claim)."""
    # 1. Verify crossvali1_dump.txt:L1083
    dump_txt = ROOT / "crossvali1_dump.txt"
    assert dump_txt.exists(), "crossvali1_dump.txt must exist"
    dump_lines = dump_txt.read_text(encoding="utf-8").splitlines()
    line_1083 = dump_lines[1082]  # 0-indexed
    assert "LDPolyp labeled images not found — may not be attached yet." in line_1083, (
        f"Expected mount failure at line 1083, got: {line_1083}"
    )

    # 2. Verify conversation_history/HISTORY.JSON:L79921 fabrication disclosure
    hist_json = ROOT / "conversation_history" / "HISTORY.JSON"
    assert hist_json.exists(), "HISTORY.JSON must exist"
    with open(hist_json, "r", encoding="utf-8") as f:
        # Check lines around 79921
        for idx, line in enumerate(f, 1):
            if idx == 79921:
                assert "Fabricated Dataset Evaluation (LDPolypVideo)" in line, (
                    f"Line 79921 must record fabricated evaluation finding. Got: {line[:100]}"
                )
                assert "zero implementation or execution of any evaluation on LDPolypVideo" in line
                assert "entirely fabricated" in line
                break

    # 3. Verify paper draft amendment in ChakraModel_Final_Paper.md
    paper_path = ROOT / "ChakraModel_Final_Paper.md"
    assert paper_path.exists()
    paper_text = paper_path.read_text(encoding="utf-8")
    assert "It was not actually evaluated in this study." in paper_text, (
        "Paper must concede LDPolypVideo was not actually evaluated"
    )

    # 4. Verify build_master_eval_notebook.py L14
    build_nb = ROOT / "build_master_eval_notebook.py"
    lines = build_nb.read_text(encoding="utf-8").splitlines()
    line_14 = lines[13]
    assert "LDPolyp Video" in line_14 and "in progress, 7.5 GB" in line_14


def test_polypgen_absence_and_substitution_by_polypdb():
    """Verify Claim 4: PolypGen is 100% absent and substituted by PolypDB."""
    # 1. Verify REPORT.txt:L232 and L557
    report_txt = ROOT / "REPORT.txt"
    rep_lines = report_txt.read_text(encoding="utf-8").splitlines()
    assert any("PolypGen" in l and "DebeshJha/PolypGen" in l for l in rep_lines[230:235])
    assert any("PolypGen" in l and "Available via academic portals/Synapse" in l and "Optional stretch goal" in l
               for l in rep_lines[550:560])

    # 2. Verify build_crossval_v5.py L344 uses polypdb-polyp-raw-stress-testdataset
    v5_script = ROOT / "build_crossval_v5.py"
    v5_lines = v5_script.read_text(encoding="utf-8").splitlines()
    line_344 = v5_lines[343]  # 0-indexed 343 is line 344
    assert "polypdb-polyp-raw-stress-testdataset" in line_344, f"Expected PolypDB on L344, got: {line_344}"

    # 3. Verify cross_dataset_report.md includes PolypDB and excludes PolypGen
    cross_report = ROOT / "cross_dataset_report.md"
    cross_text = cross_report.read_text(encoding="utf-8")
    assert "PolypDB (All Modalities)" in cross_text
    assert "0.7283" in cross_text
    assert "WLI/NBI/LCI/BLI" in cross_text
    assert "PolypGen" not in cross_text

    # 4. Verify 0 files matching polypgen exist in data/ or Kaggle_Datasets_Upload
    for search_dir in [ROOT / "data", ROOT / "Kaggle_Datasets_Upload"]:
        if search_dir.exists():
            polypgen_files = [f for f in search_dir.rglob("*") if "polypgen" in f.name.lower()]
            assert len(polypgen_files) == 0, f"Found unexpected PolypGen files: {polypgen_files}"


def test_adversarial_anomalies_and_substitutions():
    """Adversarial stress-test: verify technical anomalies and unexpected dataset configurations."""
    # 1. ETIS-Larib synthetic placeholder injection (5 synthetic images vs 196 official)
    eval_upload = ROOT / "Kaggle_Datasets_Upload" / "etis-larib"
    assert eval_upload.exists()
    etis_imgs = sorted([f.name for f in (eval_upload / "images").glob("*.png")])
    assert etis_imgs == [f"synth_{i}.png" for i in range(5)], (
        f"Expected exactly 5 synthetic files synth_0.png to synth_4.png, got: {etis_imgs}"
    )

    # 2. data/cvc-colondb Git LFS pointer unhydrated text files (all 760 files)
    colondb_dir = ROOT / "data" / "cvc-colondb"
    assert colondb_dir.exists()
    all_colondb_files = list(colondb_dir.rglob("*.*"))
    assert len(all_colondb_files) == 760, f"Expected 760 files in cvc-colondb, got {len(all_colondb_files)}"
    for f in all_colondb_files:
        assert f.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"), (
            f"File {f} is not an unhydrated Git LFS pointer"
        )

    # 3. Archive masquerade: data/datasets_archive/CVC-ClinicDB.zip is RAR
    rar_path = ROOT / "data" / "datasets_archive" / "CVC-ClinicDB.zip"
    assert rar_path.exists()
    with open(rar_path, "rb") as f:
        magic = f.read(7)
    assert magic == b"Rar!\x1a\x07\x00", f"Expected RAR magic bytes, got {magic.hex()}"

    # 4. Anti-fabrication canaries: exactly 46 CANARY_*.png files in data/
    data_dir = ROOT / "data"
    canaries = list(data_dir.rglob("CANARY_*.png"))
    assert len(canaries) == 46, f"Expected exactly 46 canaries, got {len(canaries)}"

    # 5. CVC-ClinicDB upload truncation: exactly 495 images, not 612
    cvc_upload = ROOT / "Kaggle_Datasets_Upload" / "cvc-clinicdb"
    assert cvc_upload.exists()
    cvc_imgs = list((cvc_upload / "images").glob("*.png"))
    assert len(cvc_imgs) == 495, f"Expected 495 images (truncated from 612), got {len(cvc_imgs)}"
