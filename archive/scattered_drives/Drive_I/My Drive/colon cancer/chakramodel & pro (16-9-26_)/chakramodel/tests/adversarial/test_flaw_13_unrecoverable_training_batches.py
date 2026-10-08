#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 13:
Training data composition for headline model is unrecoverable (num_batches_tracked = 2376 vs 330 expected).

Scientific & Provenance Impact:
  The headline checkpoint weights/checkpoints/chakra_transformer_best.pth records num_batches_tracked = 2376
  in its decoder BatchNorm layers. However, the committed notebook Combo6_ChakraTransformer.ipynb specifies
  15 epochs * 22 steps = 330 steps (700 images, batch 32).
  The checkpoint received 7.2x more optimizer steps (~5,069 images or ~108 epochs), came from a multi-GPU
  DDP run (evidenced by 'module.' prefixes), and was written on 2026-09-05 without training logs or manifests.
  Without an official provenance disclosure reconciling this discrepancy, the training composition
  is unrecoverable, invalidating zero-shot evaluation claims.

Exit Codes:
  1: Flaw detected (unreconciled 7.2x batch discrepancy; missing docs/TRAINING_PROVENANCE.md).
  0: Flaw resolved (training data provenance documented with batch audit and zero-shot caveats).
  2: Configuration or target file error.
"""

import argparse
import sys
import torch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CHECKPOINT = REPO_ROOT / "weights" / "checkpoints" / "chakra_transformer_best.pth"
DEFAULT_PROVENANCE_DOC = REPO_ROOT / "docs" / "TRAINING_PROVENANCE.md"


def check_flaw_13(checkpoint_path: Path, doc_path: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 13 - Training Data Provenance & Batch Tracking")
    print(f"Checkpoint:     {checkpoint_path}")
    print(f"Provenance Doc: {doc_path}")
    print("=" * 75)

    if not checkpoint_path.exists():
        print(f"[ERROR] Checkpoint file not found: {checkpoint_path}", file=sys.stderr)
        return 2

    try:
        # Load state dict on CPU
        state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except Exception as err:
        print(f"[ERROR] Failed to load checkpoint: {err}", file=sys.stderr)
        return 2

    tracked_batches = None
    for k, v in state_dict.items():
        if "num_batches_tracked" in k:
            tracked_batches = v.item() if hasattr(v, "item") else int(v)
            break

    if tracked_batches is None:
        print("[ERROR] No num_batches_tracked found in checkpoint state dict.", file=sys.stderr)
        return 2

    EXPECTED_NOTEBOOK_BATCHES = 330
    print(f"  - Checkpoint actual num_batches_tracked:   {tracked_batches}")
    print(f"  - Committed notebook expected batch steps: {EXPECTED_NOTEBOOK_BATCHES}")
    print(f"  - Discrepancy ratio:                       {tracked_batches / EXPECTED_NOTEBOOK_BATCHES:.1f}x")

    if tracked_batches > EXPECTED_NOTEBOOK_BATCHES * 2:
        if not doc_path.exists():
            print(f"\n[FAIL] FLAW 13 DETECTED: Missing training data provenance disclosure at {doc_path.name}.")
            print(f"       Checkpoint records 2376 optimizer steps ({tracked_batches / EXPECTED_NOTEBOOK_BATCHES:.1f}x more than notebook's 330).")
            print("       The shipped checkpoint was produced by an undocumented, multi-GPU DDP run on ~5,069 images,")
            print("       overwriting the 400-batch clean checkpoint. Training cohort composition is completely")
            print("       unrecoverable, which invalidates zero-shot cross-dataset generalization claims.")
            return 1

        doc_content = doc_path.read_text(encoding="utf-8")
        required_disclosures = ["2376", "zero-shot"]
        missing_disclosures = [d for d in required_disclosures if d.lower() not in doc_content.lower()]
        if missing_disclosures:
            print(f"\n[FAIL] FLAW 13 DETECTED: Provenance document {doc_path.name} exists but lacks required disclosures: {missing_disclosures}")
            return 1

    print("\n[PASS] Flaw 13 Resolved: Training data provenance and batch tracking discrepancy formally reconciled and documented.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 13 (Unrecoverable training batches).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=None,
        help="Path to checkpoint or documentation file."
    )
    parser.add_argument(
        "--checkpoint-file",
        type=Path,
        default=DEFAULT_CHECKPOINT,
        help=f"Path to checkpoint file (default: {DEFAULT_CHECKPOINT})"
    )
    parser.add_argument(
        "--doc-file",
        type=Path,
        default=DEFAULT_PROVENANCE_DOC,
        help=f"Path to TRAINING_PROVENANCE.md (default: {DEFAULT_PROVENANCE_DOC})"
    )
    args = parser.parse_args()

    checkpoint_path = args.checkpoint_file
    doc_path = args.doc_file

    if args.target_file is not None:
        if args.target_file.suffix in (".pth", ".pt"):
            checkpoint_path = args.target_file
        else:
            doc_path = args.target_file

    sys.exit(check_flaw_13(checkpoint_path, doc_path))


if __name__ == "__main__":
    main()
