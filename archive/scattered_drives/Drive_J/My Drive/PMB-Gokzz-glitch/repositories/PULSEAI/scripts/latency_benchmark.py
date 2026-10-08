#!/usr/bin/env python3
"""Measure end-to-end local inference latency on MIT-BIH windows.

Latency measured per window includes:
- ECG preprocessing
- Beat window extraction
- Local model inference

Output:
- test_results/latency_benchmark_report.json
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np  # type: ignore
from scipy.signal import resample  # type: ignore

try:
    import wfdb  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("wfdb is required. Install with: pip install wfdb") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"
MITBIH_PATH = PROJECT_ROOT / "mit-bih-arrhythmia-database-1.0.0"
REPORT_PATH = PROJECT_ROOT / "test_results" / "latency_benchmark_report.json"

if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from ml_model import predict_arrhythmia  # type: ignore
from signal_processing import FS, SEGMENT_LEN, process_ecg, extract_beat_window  # type: ignore


def _resample_to_fs(sig: np.ndarray, src_fs: float, dst_fs: int = FS) -> np.ndarray:
    if src_fs <= 1.0 or int(round(src_fs)) == dst_fs:
        return sig.astype(np.float32)
    n_out = int(len(sig) * (dst_fs / src_fs))
    if n_out <= 8:
        return sig.astype(np.float32)
    return resample(sig.astype(np.float32), n_out).astype(np.float32)


def _collect_windows(max_records: int, windows_per_record: int) -> list[list[float]]:
    records_file = MITBIH_PATH / "RECORDS"
    if not records_file.exists():
        raise FileNotFoundError(f"Missing RECORDS file: {records_file}")

    records = [r.strip() for r in records_file.read_text(encoding="utf-8", errors="ignore").splitlines() if r.strip()]
    selected = records[:max_records]

    windows: list[list[float]] = []
    for rec in selected:
        rec_path = str(MITBIH_PATH / rec)
        try:
            sig, fields = wfdb.rdsamp(rec_path, channels=[0])
        except Exception:
            continue

        raw = np.asarray(sig[:, 0], dtype=np.float32)
        src_fs = float(fields.get("fs", FS))
        raw = _resample_to_fs(raw, src_fs, FS)

        if len(raw) <= SEGMENT_LEN + 2:
            continue

        step = max(1, (len(raw) - SEGMENT_LEN) // max(1, windows_per_record))
        starts = list(range(0, len(raw) - SEGMENT_LEN, step))[:windows_per_record]
        if not starts:
            starts = [0]

        for st in starts:
            win = raw[st : st + SEGMENT_LEN]
            if len(win) == SEGMENT_LEN:
                windows.append(win.tolist())

    return windows


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    arr = np.asarray(values, dtype=np.float64)
    return float(np.percentile(arr, q))


def main() -> None:
    max_records = int(os.getenv("PULSEAI_LAT_MAX_RECORDS", "24"))
    windows_per_record = int(os.getenv("PULSEAI_LAT_WINDOWS_PER_RECORD", "20"))

    raw_windows = _collect_windows(max_records=max_records, windows_per_record=windows_per_record)
    if not raw_windows:
        raise RuntimeError("No windows collected for latency benchmark")

    latencies_ms: list[float] = []
    for raw in raw_windows:
        t0 = time.perf_counter()
        cleaned = process_ecg(raw)
        beat = extract_beat_window(cleaned)
        _ = predict_arrhythmia(beat)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(dt_ms)

    p50 = _percentile(latencies_ms, 50)
    p95 = _percentile(latencies_ms, 95)
    p99 = _percentile(latencies_ms, 99)
    max_v = max(latencies_ms)
    mean_v = statistics.mean(latencies_ms)

    target_ms = 100.0
    status = "PASS" if p95 < target_ms else "FAIL"

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "max_records": max_records,
            "windows_per_record": windows_per_record,
            "segment_len": SEGMENT_LEN,
            "fs": FS,
        },
        "samples_tested": len(latencies_ms),
        "latency_ms": {
            "mean": round(mean_v, 3),
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "p99": round(p99, 3),
            "max": round(max_v, 3),
        },
        "criterion": {
            "target": "p95 < 100 ms",
            "status": status,
        },
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Latency benchmark report: {REPORT_PATH}")
    print(json.dumps(report["latency_ms"], indent=2))


if __name__ == "__main__":
    main()
