"""One-command benchmark runner for published fetal-ultrasound models.

The model manifest is intentionally external: published checkpoints use
different architectures, licenses, and download locations. This runner never
pretends that an unavailable checkpoint is a valid model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, Iterable

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch import nn
from torch.utils.data import DataLoader
from torchvision import models

from data import CARDIUMDataset


def download(url: str, destination: Path, sha256: str = "") -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        urllib.request.urlretrieve(url, destination)
    if sha256:
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if digest.lower() != sha256.lower():
            raise ValueError(f"SHA-256 mismatch for {destination.name}")
    return destination


def load_model(row: Dict[str, str], cache_dir: Path, device: torch.device) -> nn.Module:
    name = row["name"].strip()
    loader = row["loader"].strip().lower()
    checkpoint = download(row["checkpoint_url"], cache_dir / row["filename"], row.get("sha256", ""))

    if loader == "torchscript":
        model = torch.jit.load(str(checkpoint), map_location=device)
    elif loader == "torchvision":
        constructor = getattr(models, row["architecture"])
        model = constructor(weights=None, num_classes=2)
        state = torch.load(checkpoint, map_location=device)
        state = state.get("state_dict", state)
        state = {key.removeprefix("module."): value for key, value in state.items()}
        model.load_state_dict(state, strict=False)
    else:
        raise ValueError(
            f"{name}: unsupported loader {loader!r}; use torchscript or torchvision"
        )
    return model.to(device).eval()


def positive_probability(output: torch.Tensor) -> torch.Tensor:
    if isinstance(output, (tuple, list)):
        output = output[0]
    if output.ndim == 1 or output.shape[-1] == 1:
        return torch.sigmoid(output.reshape(-1))
    return torch.softmax(output, dim=-1)[:, 1]


@torch.inference_mode()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> Dict[str, float]:
    probabilities, labels = [], []
    for images, batch_labels, _ in loader:
        probabilities.extend(positive_probability(model(images.to(device))).cpu().numpy())
        labels.extend(batch_labels.numpy())
    if not labels:
        raise ValueError("The evaluation split is empty")
    labels = np.asarray(labels)
    probabilities = np.asarray(probabilities)
    predictions = (probabilities >= 0.5).astype(np.int64)
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        "n": int(labels.size),
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall_sensitivity": float(recall_score(labels, predictions, zero_division=0)),
        "specificity": float(tn / (tn + fp)) if tn + fp else 0.0,
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities))
        if len(np.unique(labels)) == 2
        else float("nan"),
    }


def read_manifest(path: Path, expected: int) -> Iterable[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"name", "loader", "architecture", "checkpoint_url", "filename"}
    missing = required - set(rows[0]) if rows else required
    if missing:
        raise ValueError(f"Manifest is missing columns: {sorted(missing)}")
    if expected and len(rows) != expected:
        raise ValueError(f"Expected {expected} manifest rows, found {len(rows)}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, help="CARDIUM root directory")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", default="benchmark_results.csv", type=Path)
    parser.add_argument("--fold", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--expected-models", type=int, default=44)
    parser.add_argument("--cache", default="/kaggle/working/model_cache", type=Path)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    device = torch.device(args.device)
    dataset = CARDIUMDataset(args.data_root, split="test", fold=args.fold)
    if not len(dataset):
        raise ValueError(
            "No fold images found. Convert the CARDIUM data to "
            "cardium_images/cardium_images/fold_N/test/{CHD,Non_CHD}."
        )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=2)

    results = []
    for row in read_manifest(args.manifest, args.expected_models):
        try:
            metrics = evaluate(load_model(row, args.cache, device), loader, device)
            results.append({"model": row["name"], "status": "ok", **metrics})
        except Exception as error:
            results.append({"model": row["name"], "status": "failed", "error": str(error)})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        keys = sorted({key for row in results for key in row})
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps({"results": str(args.out), "models": len(results)}, indent=2))


if __name__ == "__main__":
    main()
