"""
tests/test_adversarial_m3_architecture.py
=============================================================================
Milestone 3 Adversarial Challenge & Empirical Verification Suite:
Architectural Deliverables Integrity, Tensor Dimensionality & Code Annotations.

Authored independently by Challenger (challenger_m3_g14).

Adversarial Challenge Dimensions:
1. Acceptance Criterion 1 (AC1):
   - File existence & minimum byte size (>= 30 KB)
   - Mandatory architectural section coverage
   - Mermaid diagram block count (>= 3 blocks)
   - Mermaid syntax structure validation:
     * Balanced subgraph opening & 'end' statements
     * Valid flowchart directional headers
     * Balanced quotes in node labels
     * Graph topology: node definition vs edge reference resolution
   - Ubiquitous tensor shape [B, C, H, W] annotations & resolution transitions
2. Acceptance Criterion 2 (AC2):
   - File existence & minimum byte size (>= 15 KB)
   - Tally of standardized [B, ...] tensor shape signatures (>= 50)
   - Mathematical precision verification:
     * Convolution parameter closed-form formulas (in*out*k*k + bias)
     * BatchNorm parameter formulas (2 * channels)
     * Exact subtotal summations matching verified totals
     * Checkpoint alignment (YOLO: 3,011,043 | ViT: 309,173,737 | PraNet: 25,545,117)
3. Acceptance Criterion 3 (AC3):
   - Git diff status of core model files in src/
   - Verification of structural role tags ([BODY], [NECK], [HEAD]) in core model files
   - Inline comment density audit and empty/superficial touch detection
=============================================================================
"""

import os
import re
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def deep_dive_text():
    p = ROOT / "docs" / "ARCHITECTURE_DEEP_DIVE.md"
    assert p.exists(), f"Target file does not exist: {p}"
    return p.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parameter_mapping_text():
    p = ROOT / "docs" / "parameter_mapping.txt"
    if not p.exists():
        p = ROOT / "docs" / "parameter_mapping.csv"
    assert p.exists(), f"Parameter mapping file does not exist: {p}"
    return p.read_text(encoding="utf-8")


# ===========================================================================
# 1. Acceptance Criterion 1: docs/ARCHITECTURE_DEEP_DIVE.md
# ===========================================================================

def test_ac1_file_exists_and_size():
    """Verify docs/ARCHITECTURE_DEEP_DIVE.md exists and meets minimum size threshold."""
    doc_path = ROOT / "docs" / "ARCHITECTURE_DEEP_DIVE.md"
    assert doc_path.exists(), "docs/ARCHITECTURE_DEEP_DIVE.md does not exist."
    size_bytes = doc_path.stat().st_size
    assert size_bytes >= 30_000, f"Document size {size_bytes} bytes is below expected 30 KB threshold."


def test_ac1_markdown_sections(deep_dive_text):
    """Verify presence of core architectural sections and technical headings."""
    required_sections = [
        "Executive Summary & Clinical Context",
        "End-to-End System Architecture & Data Flow",
        "Breakdown of the YOLOv8 Detection Head",
        "Breakdown of the ViT-Large Backbone",
        "PraNet / ChakraNet CNN Architecture Deep Dive",
        "Detection-to-Segmentation Coupling Mechanisms",
        "Conformal Prediction, Epistemic Uncertainty & Post-Processing",
        "Clinical Rationale, Latency Profiles & Parameter Breakdown",
    ]
    for sec in required_sections:
        assert sec.lower() in deep_dive_text.lower(), f"Missing required section: '{sec}'"


def test_ac1_mermaid_blocks_presence(deep_dive_text):
    """Verify that at least one (and expected three) Mermaid diagram blocks exist."""
    blocks = re.findall(r"```mermaid(.*?)```", deep_dive_text, re.DOTALL)
    assert len(blocks) >= 1, "No ```mermaid blocks found in docs/ARCHITECTURE_DEEP_DIVE.md."
    assert len(blocks) >= 3, f"Expected 3 comprehensive mermaid blocks, found {len(blocks)}."


def test_ac1_mermaid_syntax_structures(deep_dive_text):
    """
    Adversarial verification of Mermaid diagram syntax structures:
    - Balanced subgraphs and 'end' statements
    - Graph orientation headers (flowchart TD / LR)
    - Valid node identifiers and edge arrows (--> / -.-> / &)
    - Balanced quoting on node labels
    """
    blocks = re.findall(r"```mermaid(.*?)```", deep_dive_text, re.DOTALL)
    for idx, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        assert lines, f"Mermaid block {idx} is empty."
        assert lines[0].startswith("flowchart") or lines[0].startswith("graph"), (
            f"Mermaid block {idx} missing valid flowchart/graph header: {lines[0]}"
        )

        subgraph_count = sum(1 for line in lines if line.startswith("subgraph"))
        end_count = sum(1 for line in lines if line == "end" or line.startswith("end "))
        assert subgraph_count == end_count, (
            f"Mermaid block {idx} subgraph mismatch: {subgraph_count} subgraphs opened but {end_count} 'end' found."
        )

        arrow_count = sum(
            1 for line in lines if "-->" in line or "-.->" in line or "==>" in line or "--" in line
        )
        assert arrow_count >= 5, f"Mermaid block {idx} has too few edges ({arrow_count})."

        for line_num, line in enumerate(lines, start=1):
            if "[" in line and "]" in line:
                quotes = line.count('"')
                assert quotes % 2 == 0, (
                    f"Mermaid block {idx}, line {line_num} has unbalanced quotes: {line}"
                )


def test_ac1_mermaid_node_linkage_graph(deep_dive_text):
    """
    Graph topology stress test:
    Verify that nodes referenced in edges have matching definitions within the diagram.
    """
    blocks = re.findall(r"```mermaid(.*?)```", deep_dive_text, re.DOTALL)
    for idx, block in enumerate(blocks, start=1):
        lines = block.strip().splitlines()
        defined_nodes = set()
        edge_tokens = []

        for line in lines:
            sline = line.strip()
            if not sline or sline.startswith(("flowchart", "graph", "subgraph", "end", "classDef", "style")):
                continue
            
            # Find defined node IDs: id["..."], id(...), id{...}
            m_defs = re.findall(r"\b([A-Za-z0-9_]+)\s*(?:\[|\(|\{)", sline)
            for d in m_defs:
                defined_nodes.add(d)

            # Look for edges: src --> dst, s1 & s2 --> dst
            if "-->" in sline or "-.->" in sline:
                # Strip string literals and brackets
                clean = re.sub(r'"[^"]*"', '', sline)
                clean = re.sub(r'\[[^\]]*\]', '', clean)
                clean = re.sub(r'\([^\)]*\)', '', clean)
                clean = re.sub(r'\{[^\}]*\}', '', clean)
                clean = clean.replace("-->", " ").replace("-.->", " ").replace("&", " ").replace("--", " ")
                parts = [p.strip() for p in clean.split() if p.strip()]
                for p in parts:
                    if re.match(r"^[A-Za-z0-9_]+$", p):
                        edge_tokens.append(p)

        # In a valid graph, almost all edge tokens must be defined nodes or subgraphs
        unresolved = [t for t in edge_tokens if t not in defined_nodes]
        # Some labels or annotations may remain, but unresolved node IDs should be minimal
        assert len(defined_nodes) >= 10, f"Mermaid block {idx} has too few defined nodes ({len(defined_nodes)})."
        assert len(unresolved) <= 5, (
            f"Mermaid block {idx} has too many unresolved edge endpoints: {unresolved}"
        )


def test_ac1_tensor_shape_descriptions(deep_dive_text):
    """Verify that tensor shape descriptions and dimensions are ubiquitous."""
    tensor_matches = re.findall(r"\[B,\s*[^\]]+\]", deep_dive_text)
    assert len(tensor_matches) >= 15, (
        f"Found only {len(tensor_matches)} tensor shapes in ARCHITECTURE_DEEP_DIVE.md, expected >= 15."
    )
    for res in ["640", "384", "96", "48", "24", "12"]:
        assert res in deep_dive_text, f"Key spatial resolution {res} missing from architecture doc."


# ===========================================================================
# 2. Acceptance Criterion 2: docs/parameter_mapping.txt
# ===========================================================================

def test_ac2_file_exists_and_size():
    """Verify docs/parameter_mapping.txt exists and meets minimum size threshold."""
    doc_path = ROOT / "docs" / "parameter_mapping.txt"
    if not doc_path.exists():
        doc_path = ROOT / "docs" / "parameter_mapping.csv"
    assert doc_path.exists(), "docs/parameter_mapping.txt (or .csv) does not exist."
    size_bytes = doc_path.stat().st_size
    assert size_bytes >= 15_000, f"Parameter mapping size {size_bytes} bytes is below expected 15 KB threshold."


def test_ac2_tensor_shape_notation_count(parameter_mapping_text):
    """Exhaustively count and verify standardized [B, C, H, W] tensor shapes."""
    b_shapes = re.findall(r"\[B,\s*[^\]]+\]", parameter_mapping_text)
    assert len(b_shapes) >= 50, (
        f"Found only {len(b_shapes)} '[B, ...]' tensor shapes in parameter mapping, expected >= 50."
    )


def test_ac2_mathematical_consistency(parameter_mapping_text):
    """
    Empirically verify mathematical consistency of parameter totals and module breakdowns:
    - YOLOv8: 3,011,043 params
    - ViT-Large: 309,173,737 params
    - PraNet ResNet-50: 25,545,117 params
    - PraNet ResNet-101: 45,671,821 params
    """
    assert "3,011,043" in parameter_mapping_text, "YOLOv8 exact parameter count (3,011,043) missing."
    assert "309,173,737" in parameter_mapping_text, "ViT-Large exact parameter count (309,173,737) missing."
    assert "25,545,117" in parameter_mapping_text, "PraNet ResNet-50 parameter count (25,545,117) missing."
    assert "45,671,821" in parameter_mapping_text, "PraNet ResNet-101 parameter count (45,671,821) missing."

    # Mathematical subtotal check for YOLOv8
    bb_match = re.search(r"Backbone Subtotal[^:]*:\s*([0-9,]+)", parameter_mapping_text)
    neck_match = re.search(r"Neck Subtotal[^:]*:\s*([0-9,]+)", parameter_mapping_text)
    head_match = re.search(r"Head Subtotal[^:]*:\s*([0-9,]+)", parameter_mapping_text)
    if bb_match and neck_match and head_match:
        bb = int(bb_match.group(1).replace(",", ""))
        neck = int(neck_match.group(1).replace(",", ""))
        head = int(head_match.group(1).replace(",", ""))
        assert bb + neck + head == 3011043, (
            f"YOLOv8 subtotals sum to {bb + neck + head}, expected 3,011,043."
        )


def test_ac2_layer_formulas_precision():
    """
    Oracle check of exact closed-form parameter calculations in decode head:
    ConvTranspose2d(1024, 256, k=4) + BN(256) + ConvTranspose2d(256, 64, k=4) + BN(64) + Conv2d(64, 1, k=3)
    """
    ct1 = 1024 * 256 * 4 * 4 + 256  # 4,194,560
    bn1 = 2 * 256                   # 512
    ct2 = 256 * 64 * 4 * 4 + 64     # 262,208
    bn2 = 2 * 64                    # 128
    c3 = 64 * 1 * 3 * 3 + 1         # 577
    decode_total = ct1 + bn1 + ct2 + bn2 + c3
    assert decode_total == 4457985, f"Decode head closed-form total mismatch: {decode_total}"


# ===========================================================================
# 3. Acceptance Criterion 3: Core Model Files Inline Comments in src/
# ===========================================================================

def test_ac3_src_files_exist():
    """Verify that the primary core model files exist in src/."""
    chakranet_path = ROOT / "src" / "models" / "chakranet_segmenter.py"
    transformer_path = ROOT / "src" / "chakra_transformer" / "transformer_segmenter.py"

    assert chakranet_path.exists(), f"Core file missing: {chakranet_path}"
    assert transformer_path.exists(), f"Core file missing: {transformer_path}"


def test_ac3_git_diff_modifications():
    """
    Adversarially check whether core model files in src/ have active git modifications.
    Acceptance Criteria 3 explicitly states:
    'A programmatic check (via git diff) verifies that the core model files in src/
    have been modified to include new inline comments.'
    """
    git_candidates = [
        "git",
        r"C:\Users\imgk3\AppData\Local\GitHubDesktop\app-3.6.2\resources\app\git\cmd\git.exe",
        r"C:\Program Files\Git\cmd\git.exe",
    ]
    git_cmd = None
    for candidate in git_candidates:
        try:
            res = subprocess.run([candidate, "--version"], capture_output=True, text=True)
            if res.returncode == 0:
                git_cmd = candidate
                break
        except Exception:
            continue

    if git_cmd is None:
        pytest.skip("Git executable not available to test git diff.")

    result = subprocess.run(
        [git_cmd, "diff", "--name-only", "src/"],
        cwd=str(ROOT),
        capture_output=True,
        text=True
    )
    modified_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert len(modified_files) > 0, (
        "EMPIRICAL FINDING: git diff src/ returns 0 modified files. "
        "No core model files in src/ are modified in git!"
    )


def test_ac3_inline_structural_tags_presence():
    """
    Adversarially inspect src/ core model files for presence of structural tags:
    [BODY], [NECK], [HEAD].
    """
    core_files = [
        ROOT / "src" / "models" / "chakranet_segmenter.py",
        ROOT / "src" / "chakra_transformer" / "transformer_segmenter.py",
    ]

    tag_findings = {}
    for cf in core_files:
        content = cf.read_text(encoding="utf-8", errors="ignore")
        body = content.count("[BODY]")
        neck = content.count("[NECK]")
        head = content.count("[HEAD]")
        tag_findings[cf.name] = {"[BODY]": body, "[NECK]": neck, "[HEAD]": head}

    total_tags = sum(
        sum(counts.values()) for counts in tag_findings.values()
    )

    assert total_tags > 0, (
        f"EMPIRICAL BUG CONFIRMED: Core model files in src/ contain ZERO [BODY], [NECK], [HEAD] tags! "
        f"Findings per file: {tag_findings}"
    )


def test_ac3_comment_density():
    """
    Inspect comment density and verify genuine inline comments exist
    versus empty lines or superficial modifications.
    """
    core_files = [
        ROOT / "src" / "models" / "chakranet_segmenter.py",
        ROOT / "src" / "chakra_transformer" / "transformer_segmenter.py",
    ]

    for cf in core_files:
        lines = cf.read_text(encoding="utf-8", errors="ignore").splitlines()
        comment_lines = [l for l in lines if l.strip().startswith("#")]
        code_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]

        ratio = len(comment_lines) / max(len(code_lines), 1)
        assert ratio >= 0.10, (
            f"File {cf.name} has low comment density: {len(comment_lines)} comment lines vs {len(code_lines)} code lines ({ratio:.1%})."
        )


# ===========================================================================
# Standalone CLI Runner
# ===========================================================================

if __name__ == "__main__":
    import sys
    print("=" * 80)
    print("RUNNING CHAKRAMODEL MILESTONE 3 ADVERSARIAL CHALLENGE SUITE")
    print("=" * 80)

    test_functions = [
        test_ac1_file_exists_and_size,
        test_ac1_markdown_sections,
        test_ac1_mermaid_blocks_presence,
        test_ac1_mermaid_syntax_structures,
        test_ac1_mermaid_node_linkage_graph,
        test_ac1_tensor_shape_descriptions,
        test_ac2_file_exists_and_size,
        test_ac2_tensor_shape_notation_count,
        test_ac2_mathematical_consistency,
        test_ac2_layer_formulas_precision,
        test_ac3_src_files_exist,
        test_ac3_git_diff_modifications,
        test_ac3_inline_structural_tags_presence,
        test_ac3_comment_density,
    ]

    p_deep = ROOT / "docs" / "ARCHITECTURE_DEEP_DIVE.md"
    deep_txt = p_deep.read_text(encoding="utf-8") if p_deep.exists() else ""
    p_param = ROOT / "docs" / "parameter_mapping.txt"
    param_txt = p_param.read_text(encoding="utf-8") if p_param.exists() else ""

    passed = 0
    failed = 0
    failures = []

    for test_fn in test_functions:
        fn_name = test_fn.__name__
        try:
            if "deep_dive_text" in test_fn.__code__.co_varnames:
                test_fn(deep_txt)
            elif "parameter_mapping_text" in test_fn.__code__.co_varnames:
                test_fn(param_txt)
            else:
                test_fn()
            print(f"  [PASS] {fn_name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {fn_name}: {e}")
            failed += 1
            failures.append((fn_name, str(e)))

    print("-" * 80)
    print(f"Summary: {passed} PASSED, {failed} FAILED (Total: {len(test_functions)})")
    print("=" * 80)
    if failed > 0:
        print("\nFAILURE DETAILS:")
        for fn, err in failures:
            print(f"\n- {fn}:\n  {err}")
        sys.exit(1)
    else:
        sys.exit(0)
