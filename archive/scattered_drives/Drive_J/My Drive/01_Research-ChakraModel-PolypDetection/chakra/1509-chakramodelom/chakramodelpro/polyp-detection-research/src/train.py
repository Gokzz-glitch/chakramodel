"""
train.py — Training Entry Point

STRICT RULES:
  - All hyperparameters come from the YAML config file
  - NO hardcoded values in this file
  - All metrics are computed from real forward passes on real data
  - Training logs are written to results/ and wandb

Usage:
    python src/train.py --config configs/baseline_unet.yaml
    python src/train.py --config configs/pranet_repro.yaml --resume checkpoints/run001_epoch_50.pt
"""

import argparse
import os
import sys
import yaml
import logging
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# ─── Configure logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Polyp Segmentation Training")
    parser.add_argument(
        "--config", type=str, required=True,
        help="Path to YAML config file (e.g., configs/baseline_unet.yaml)"
    )
    parser.add_argument(
        "--resume", type=str, default=None,
        help="Path to checkpoint to resume from"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Debug mode: run 1 batch only, no wandb"
    )
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    """Load and validate YAML config file."""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Available configs: {list(Path('configs').glob('*.yaml'))}"
        )
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    logger.info(f"Loaded config from: {config_path}")
    return config


def validate_data_paths(config: dict) -> None:
    """
    STRICT: Verify all data paths exist before training starts.
    Raises FileNotFoundError if any path is missing.
    DO NOT fabricate data — fail explicitly.
    """
    data_root = Path(config["data"]["root"])
    if not data_root.exists():
        raise FileNotFoundError(
            f"Data root directory not found: {data_root}\n"
            f"Please download datasets following instructions in data/README.md"
        )
    
    train_list = Path(config["data"]["train_list"])
    if not train_list.exists():
        raise FileNotFoundError(
            f"Training file list not found: {train_list}\n"
            f"Run: python src/data_loaders/generate_splits.py first."
        )
    
    logger.info(f"✓ Data root verified: {data_root}")
    logger.info(f"✓ Train list verified: {train_list}")


def main():
    args = parse_args()
    config = load_config(args.config)
    
    # ─── Validate data paths FIRST (fail fast) ───────────────────────────────
    validate_data_paths(config)
    
    # ─── Set reproducibility seed ─────────────────────────────────────────────
    seed = config.get("seed", 42)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    import numpy as np
    np.random.seed(seed)
    logger.info(f"Random seed set to: {seed}")
    
    # ─── Device setup ─────────────────────────────────────────────────────────
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    if device.type == "cpu":
        logger.warning("CUDA not available. Training will be very slow.")
    
    # ─── Build model ─────────────────────────────────────────────────────────
    # TODO (Phase 1): Import and instantiate model from src/models/
    # model = build_model(config["model"])
    # model = model.to(device)
    raise NotImplementedError(
        "Phase 1 not yet implemented.\n"
        "This is a Phase 0 stub. Implement src/models/ first."
    )


if __name__ == "__main__":
    main()
