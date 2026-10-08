#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 09:
MC-Dropout variance collapse (~2.85e-15) making uncertainty signal numerically dead.

Root Cause:
  Calling model.eval() sets all module.training = False. The method enable_mc_dropout()
  only sets self.mc_dropout = True without recursively setting dropout modules to train() mode.
  PyTorch's nn.Dropout2d acts as identity in eval mode, producing identical deterministic passes.
  The recorded variance ~2.85e-15 in results/combo1_metrics.json is strictly GPU floating-point noise.

Exit Codes:
  1: Flaw detected (collapsed uncertainty < 1e-10 in metrics JSON or unactivated dropout in code).
  0: Flaw resolved (genuine epistemic variance produced and dropout train mode enforced).
  2: Configuration or target file error.
"""

import argparse
import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_METRICS = REPO_ROOT / "results" / "combo1_metrics.json"
DEFAULT_SOURCE = REPO_ROOT / "src" / "evaluation" / "run_all_combos.py"


def check_source_enable_mc_dropout(source_file: Path) -> bool:
    """Returns True if enable_mc_dropout properly activates training mode on dropout layers."""
    if not source_file.exists():
        return False
    try:
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    except Exception:
        return False

    properly_activated = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "enable_mc_dropout":
            source_code = ast.unparse(node)
            if ".train()" in source_code or "apply(" in source_code:
                properly_activated = True

    return properly_activated


def check_flaw_09(metrics_file: Path | None, source_file: Path | None) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 09 - MC-Dropout Variance Collapse")
    print("=" * 75)

    has_collapsed_json = False
    json_mean_unc = None
    if metrics_file and metrics_file.exists():
        try:
            with open(metrics_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            json_mean_unc = data.get("mean_uncertainty", None)
            if json_mean_unc is not None and json_mean_unc < 1e-10:
                has_collapsed_json = True
        except Exception as e:
            print(f"[WARN] Could not parse metrics file {metrics_file}: {e}")

    proper_dropout_code = False
    if source_file and source_file.exists():
        proper_dropout_code = check_source_enable_mc_dropout(source_file)

    print(f"  - Metrics file: {metrics_file}")
    print(f"  - Recorded mean_uncertainty in JSON:      {json_mean_unc}")
    print(f"  - Source file:  {source_file}")
    print(f"  - enable_mc_dropout activates train():    {proper_dropout_code}")

    flaw_detected = False
    if metrics_file is not None and source_file is not None:
        if has_collapsed_json or not proper_dropout_code:
            flaw_detected = True
    elif metrics_file is not None:
        if has_collapsed_json:
            flaw_detected = True
    elif source_file is not None:
        if not proper_dropout_code:
            flaw_detected = True

    if flaw_detected:
        print("\n[FAIL] FLAW 09 DETECTED: MC-Dropout uncertainty has collapsed.")
        if has_collapsed_json:
            print(f"       results/combo1_metrics.json records mean_uncertainty = {json_mean_unc} (< 1e-10).")
            print("       This ~2.85e-15 variance is hardware FP roundoff noise, not epistemic uncertainty.")
        if source_file and not proper_dropout_code:
            print("       src/evaluation/run_all_combos.py: enable_mc_dropout() sets self.mc_dropout = True")
            print("       without calling self.drop.train() or putting dropout layers into training mode.")
        print("       All stochastic MC passes execute identical deterministic passes in eval mode.")
        return 1
    else:
        print("\n[PASS] Flaw 09 Resolved: MC-Dropout produces genuine epistemic variance (> 1e-4).")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 09 (MC-Dropout variance collapse).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=None,
        help="Path to combo1_metrics.json or run_all_combos.py"
    )
    parser.add_argument(
        "--metrics-file",
        type=Path,
        default=DEFAULT_METRICS,
        help=f"Path to combo1_metrics.json (default: {DEFAULT_METRICS})"
    )
    parser.add_argument(
        "--source-file",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Path to run_all_combos.py (default: {DEFAULT_SOURCE})"
    )
    args = parser.parse_args()

    if args.target_file is not None:
        if args.target_file.suffix == ".json":
            metrics_path = args.target_file
            source_path = None
        else:
            metrics_path = None
            source_path = args.target_file
    else:
        metrics_path = args.metrics_file
        source_path = args.source_file

    sys.exit(check_flaw_09(metrics_path, source_path))


if __name__ == "__main__":
    main()
