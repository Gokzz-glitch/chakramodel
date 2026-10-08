#!/usr/bin/env python3
"""Train a window-level realtime arrhythmia model aligned to benchmark labels.

Label policy (same as benchmark):
- arrhythmia=1 if any non-normal MIT-BIH annotation occurs inside window
- arrhythmia=0 otherwise
"""

from __future__ import annotations

import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np  # type: ignore
from scipy.signal import resample  # type: ignore

try:
    import tensorflow as tf  # type: ignore
    from tensorflow import keras  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("TensorFlow is required. Install with: pip install tensorflow") from exc

try:
    import wfdb  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("wfdb is required. Install with: pip install wfdb") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"
MITBIH_PATH = PROJECT_ROOT / "mit-bih-arrhythmia-database-1.0.0"
OUTPUT_MODEL_PATH = PROJECT_ROOT / "hctg_net_model.h5"
THRESHOLDS_PATH = PROJECT_ROOT / "model_thresholds.json"
REPORT_PATH = PROJECT_ROOT / "test_results" / "training_mitbih_realtime_report.json"

if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from signal_processing import FS, SEGMENT_LEN, process_ecg  # type: ignore

NORMAL_SYMBOLS = {"N", "L", "R", "e", "j", "/"}


@dataclass
class SplitData:
    x_train: np.ndarray
    y_train: np.ndarray
    x_val: np.ndarray
    y_val: np.ndarray
    train_records: list[str]
    val_records: list[str]


def _resample_to_fs(sig: np.ndarray, src_fs: float, dst_fs: int = FS) -> np.ndarray:
    if src_fs <= 1.0 or int(round(src_fs)) == dst_fs:
        return sig.astype(np.float32)
    n_out = int(len(sig) * (dst_fs / src_fs))
    if n_out <= 8:
        return sig.astype(np.float32)
    return np.asarray(resample(sig.astype(np.float32), n_out), dtype=np.float32)


def _normalize_window(x: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(x.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    std = float(np.std(x))
    if std < 1e-6:
        return np.zeros_like(x, dtype=np.float32)
    return ((x - float(np.mean(x))) / std).astype(np.float32)


def _augment_window(x: np.ndarray, rng: random.Random) -> np.ndarray:
    y = x.copy()
    y *= rng.uniform(0.90, 1.10)
    y += np.random.normal(0.0, rng.uniform(0.002, 0.02), size=y.shape).astype(np.float32)
    if rng.random() < 0.35:
        t = np.linspace(0.0, 1.0, y.size, dtype=np.float32)
        y += (rng.uniform(0.003, 0.03) * np.sin(2 * np.pi * rng.uniform(0.1, 0.6) * t + rng.uniform(0, np.pi))).astype(np.float32)
    return _normalize_window(y)


def load_window_dataset(max_records: int = 48, windows_per_record: int = 1400) -> tuple[np.ndarray, np.ndarray, list[str]]:
    records_file = MITBIH_PATH / "RECORDS"
    if not records_file.exists():
        raise FileNotFoundError(f"Missing RECORDS file: {records_file}")

    records = [r.strip() for r in records_file.read_text(encoding="utf-8", errors="ignore").splitlines() if r.strip()]
    selected = records[:max_records]

    all_x: list[np.ndarray] = []
    all_y: list[int] = []
    rec_ids: list[str] = []

    for rec in selected:
        rec_path = str(MITBIH_PATH / rec)
        try:
            sig, fields = wfdb.rdsamp(rec_path, channels=[0])
            ann = wfdb.rdann(rec_path, "atr")
        except Exception:
            continue

        raw = np.asarray(sig[:, 0], dtype=np.float32)
        src_fs = float(fields.get("fs", FS))
        raw = _resample_to_fs(raw, src_fs, FS)

        if len(raw) <= SEGMENT_LEN + 2:
            continue

        ann_samples = np.asarray(getattr(ann, "sample", []), dtype=np.int64)
        ann_symbols = list(getattr(ann, "symbol", []))
        if ann_samples.size != len(ann_symbols):
            continue

        ratio = float(FS / src_fs) if src_fs > 1 else 1.0
        ann_scaled = np.asarray(np.round(ann_samples * ratio), dtype=np.int64)

        step = max(50, SEGMENT_LEN // 5)
        starts = list(range(0, len(raw) - SEGMENT_LEN, step))
        if len(starts) > windows_per_record:
            starts = starts[:windows_per_record]

        for st in starts:
            end = st + SEGMENT_LEN
            win = raw[st:end]
            clean = np.asarray(process_ecg(win.tolist()), dtype=np.float32)
            if clean.size != SEGMENT_LEN:
                continue

            idx = np.where((ann_scaled >= st) & (ann_scaled < end))[0]
            gt_arr = False
            if idx.size > 0:
                syms = [ann_symbols[int(i)] for i in idx]
                gt_arr = any(sym not in NORMAL_SYMBOLS for sym in syms)

            all_x.append(_normalize_window(clean))
            all_y.append(1 if gt_arr else 0)
            rec_ids.append(rec)

    if not all_x:
        raise RuntimeError("No window-level samples could be extracted from MIT-BIH")

    x = np.asarray(all_x, dtype=np.float32)
    y = np.asarray(all_y, dtype=np.int32)
    return x, y, rec_ids


def split_by_record(x: np.ndarray, y: np.ndarray, rec_ids: list[str], val_ratio: float = 0.2) -> SplitData:
    records_sorted = sorted(set(rec_ids))
    val_count = max(1, int(round(len(records_sorted) * val_ratio)))
    val_records = set(records_sorted[:val_count])
    train_records = [r for r in records_sorted if r not in val_records]

    mask_val = np.asarray([r in val_records for r in rec_ids], dtype=bool)
    mask_train = ~mask_val

    return SplitData(
        x_train=x[mask_train],
        y_train=y[mask_train],
        x_val=x[mask_val],
        y_val=y[mask_val],
        train_records=train_records,
        val_records=sorted(val_records),
    )


def balance_with_augmentation(x: np.ndarray, y: np.ndarray, seed: int = 1337) -> tuple[np.ndarray, np.ndarray]:
    rng = random.Random(seed)
    idx0 = np.where(y == 0)[0]
    idx1 = np.where(y == 1)[0]
    if idx0.size == 0 or idx1.size == 0:
        return x, y

    if idx0.size > idx1.size:
        major, minor, minor_label = idx0, idx1, 1
    else:
        major, minor, minor_label = idx1, idx0, 0

    need = int(major.size - minor.size)
    if need <= 0:
        return x, y

    picks = np.random.choice(minor, size=need, replace=True)
    aug = np.zeros((need, x.shape[1]), dtype=np.float32)
    for i, p in enumerate(picks):
        aug[i] = _augment_window(x[int(p)], rng)

    out_x = np.concatenate([x, aug], axis=0)
    out_y = np.concatenate([y, np.full((need,), minor_label, dtype=np.int32)], axis=0)
    order = np.random.permutation(out_x.shape[0])
    return out_x[order], out_y[order]


def build_model() -> keras.Model:
    inp = keras.Input(shape=(SEGMENT_LEN, 1), name="ecg_window")

    x = keras.layers.Conv1D(24, 11, padding="same", use_bias=False)(inp)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Activation("relu")(x)
    x = keras.layers.MaxPooling1D(pool_size=2)(x)

    x = keras.layers.SeparableConv1D(48, 7, padding="same", use_bias=False)(x)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Activation("relu")(x)
    x = keras.layers.MaxPooling1D(pool_size=2)(x)

    x = keras.layers.SeparableConv1D(96, 5, padding="same", use_bias=False)(x)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Activation("relu")(x)
    x = keras.layers.MaxPooling1D(pool_size=2)(x)

    x = keras.layers.SeparableConv1D(128, 3, padding="same", use_bias=False)(x)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Activation("relu")(x)
    x = keras.layers.GlobalAveragePooling1D()(x)

    x = keras.layers.Dense(96, activation="relu")(x)
    x = keras.layers.Dropout(0.25)(x)
    x = keras.layers.Dense(32, activation="relu")(x)
    out = keras.layers.Dense(1, activation="sigmoid", name="arrhythmia_prob")(x)

    model = keras.Model(inputs=inp, outputs=out, name="pulseai_realtime_window_binary")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=8e-4),
        loss=keras.losses.BinaryCrossentropy(),
        metrics=[
            keras.metrics.BinaryAccuracy(name="accuracy"),
            keras.metrics.AUC(name="auc"),
            keras.metrics.Precision(name="precision"),
            keras.metrics.Recall(name="recall"),
        ],
    )
    return model


def metric_stats(y_true: np.ndarray, y_prob: np.ndarray, thr: float) -> dict[str, float]:
    y_hat = (y_prob >= thr).astype(np.int32)
    tp = int(np.sum((y_hat == 1) & (y_true == 1)))
    tn = int(np.sum((y_hat == 0) & (y_true == 0)))
    fp = int(np.sum((y_hat == 1) & (y_true == 0)))
    fn = int(np.sum((y_hat == 0) & (y_true == 1)))

    acc = (tp + tn) / max(1, tp + tn + fp + fn)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    f1 = (2 * precision * recall) / max(1e-9, precision + recall)
    bal = 0.5 * (recall + specificity)

    return {
        "threshold": float(round(thr, 4)),
        "accuracy": float(round(acc, 4)),
        "precision": float(round(precision, 4)),
        "recall": float(round(recall, 4)),
        "specificity": float(round(specificity, 4)),
        "f1": float(round(f1, 4)),
        "balanced_accuracy": float(round(bal, 4)),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def pick_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    best: dict[str, float] | None = None
    for thr in np.linspace(0.1, 0.95, 86):
        s = metric_stats(y_true, y_prob, float(thr))
        score = float(s["accuracy"]) + 0.12 * float(s["balanced_accuracy"])
        if float(s["recall"]) < 0.20:
            score -= 0.15

        if best is None or score > float(best.get("_score", -1e9)):
            best = dict(s)
            best["_score"] = score

    assert best is not None
    best.pop("_score", None)
    return best


def main() -> None:
    seed = int(os.getenv("PULSEAI_TRAIN_SEED", "1337"))
    np.random.seed(seed)
    random.seed(seed)
    tf.random.set_seed(seed)

    max_records = int(os.getenv("PULSEAI_TRAIN_MAX_RECORDS", "48"))
    windows_per_record = int(os.getenv("PULSEAI_TRAIN_WINDOWS_PER_RECORD", "1400"))
    epochs = int(os.getenv("PULSEAI_TRAIN_EPOCHS", "12"))
    batch_size = int(os.getenv("PULSEAI_TRAIN_BATCH", "128"))

    x, y, rec_ids = load_window_dataset(max_records=max_records, windows_per_record=windows_per_record)
    split = split_by_record(x, y, rec_ids, val_ratio=0.2)

    x_train, y_train = balance_with_augmentation(split.x_train, split.y_train, seed=seed)
    x_val, y_val = split.x_val, split.y_val

    x_train = x_train[..., None]
    x_val = x_val[..., None]

    model = build_model()
    callbacks: list[keras.callbacks.Callback] = [
        keras.callbacks.EarlyStopping(monitor="val_auc", mode="max", patience=3, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor="val_auc", mode="max", patience=2, factor=0.5, min_lr=1e-5),
    ]

    hist = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        verbose=2,
        callbacks=callbacks,
    )

    y_prob = model.predict(x_val, verbose=0).reshape(-1).astype(np.float32)
    best = pick_threshold(y_val.astype(np.int32), y_prob)

    model.save(OUTPUT_MODEL_PATH)
    THRESHOLDS_PATH.write_text(
        json.dumps(
            {
                "binary_decision_threshold": best["threshold"],
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "model": OUTPUT_MODEL_PATH.name,
                "segment_len": SEGMENT_LEN,
                "fs": FS,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "window_definition": {"segment_len": SEGMENT_LEN, "fs": FS},
        "dataset": {
            "total_windows": int(x.shape[0]),
            "train_windows_before_balance": int(split.x_train.shape[0]),
            "train_windows_after_balance": int(x_train.shape[0]),
            "val_windows": int(x_val.shape[0]),
            "train_positive_rate_before_balance": float(round(float(np.mean(split.y_train)), 4)),
            "train_positive_rate_after_balance": float(round(float(np.mean(y_train)), 4)),
            "val_positive_rate": float(round(float(np.mean(y_val)), 4)),
            "train_records": split.train_records,
            "val_records": split.val_records,
        },
        "training": {
            "epochs_requested": epochs,
            "epochs_ran": len(hist.history.get("loss", [])),
            "final_history": {k: float(v[-1]) for k, v in hist.history.items() if v},
        },
        "validation_best_threshold_metrics": best,
        "artifacts": {
            "model_path": str(OUTPUT_MODEL_PATH),
            "thresholds_path": str(THRESHOLDS_PATH),
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 80)
    print("PulseAI realtime window-level model training complete")
    print("=" * 80)
    print(json.dumps(best, indent=2))
    print(f"Saved model: {OUTPUT_MODEL_PATH}")
    print(f"Saved thresholds: {THRESHOLDS_PATH}")
    print(f"Saved report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
