#!/usr/bin/env python3
"""Global real-world ECG benchmark + anomaly sensitivity report.

What this script does:
1) Scans curated public ECG sources across regions (web scrape metadata/status).
2) Evaluates the local MIT-BIH corpus in this repo using backend inference.
3) Runs subtle-anomaly sensitivity challenge on perturbed normal rhythms.
4) Writes machine-readable report to test_results/global_benchmark_report.json.
"""

from __future__ import annotations

import json
import math
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np  # type: ignore
import requests  # type: ignore
from scipy.signal import resample  # type: ignore

try:
    import wfdb  # type: ignore
except Exception:
    wfdb = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"
MITBIH_PATH = PROJECT_ROOT / "mit-bih-arrhythmia-database-1.0.0"
REPORT_PATH = PROJECT_ROOT / "test_results" / "global_benchmark_report.json"

if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from ml_model import predict_arrhythmia, get_model_status  # type: ignore
from signal_processing import process_ecg, extract_beat_window, FS, SEGMENT_LEN  # type: ignore


GLOBAL_SOURCES: list[dict[str, str]] = [
    {
        "region": "North America",
        "country": "USA",
        "name": "MIT-BIH Arrhythmia Database",
        "url": "https://physionet.org/content/mitdb/1.0.0/",
    },
    {
        "region": "Europe",
        "country": "Germany",
        "name": "PTB-XL ECG Dataset",
        "url": "https://physionet.org/content/ptb-xl/1.0.3/",
    },
    {
        "region": "Asia",
        "country": "China",
        "name": "CPSC 2018 ECG Challenge Data",
        "url": "https://physionet.org/content/challenge-2020/1.0.2/",
    },
    {
        "region": "Asia",
        "country": "Israel",
        "name": "Long Term AF Database",
        "url": "https://physionet.org/content/ltafdb/1.0.0/",
    },
    {
        "region": "South America",
        "country": "Brazil",
        "name": "INCART 12-lead Arrhythmia",
        "url": "https://physionet.org/content/incartdb/1.0.0/",
    },
]


def scrape_global_sources(timeout: float = 7.0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    headers = {"User-Agent": "PulseAI-Global-Benchmark/1.0"}
    for src in GLOBAL_SOURCES:
        out: dict[str, Any] = dict(src)
        try:
            r = requests.get(src["url"], headers=headers, timeout=timeout)
            out["status_code"] = r.status_code
            out["reachable"] = r.status_code == 200
            html = r.text
            title = ""
            start = html.lower().find("<title>")
            end = html.lower().find("</title>")
            if start != -1 and end != -1 and end > start:
                title = html[start + 7 : end].strip().replace("\n", " ")
            out["page_title"] = title[:140]
        except Exception as exc:
            out["status_code"] = None
            out["reachable"] = False
            out["error"] = str(exc)
            out["page_title"] = ""
        rows.append(out)
    return rows


def _resample_to_fs(sig: np.ndarray, src_fs: float, dst_fs: int = FS) -> np.ndarray:
    if src_fs <= 1 or int(round(src_fs)) == dst_fs:
        return sig.astype(np.float32)
    n_out = int(len(sig) * (dst_fs / src_fs))
    if n_out <= 8:
        return sig.astype(np.float32)
    return resample(sig, n_out).astype(np.float32)


def _label_family(label: str) -> str:
    l = (label or "").lower()
    if "normal" in l:
        return "normal"
    if "afib" in l or "atrial fibrillation" in l:
        return "afib"
    if "brady" in l:
        return "brady"
    if "vf" in l and "fibrillation" in l:
        return "vfib"
    if "tachy" in l or "ventricular tachycardia" in l:
        return "tachy"
    if "subtle" in l:
        return "subtle"
    return "other"


def evaluate_mitbih_local(max_records: int = 30, windows_per_record: int = 8) -> dict[str, Any]:
    if wfdb is None:
        return {
            "ok": False,
            "error": "wfdb not installed. Install with: pip install wfdb",
        }

    records_file = MITBIH_PATH / "RECORDS"
    if not records_file.exists():
        return {
            "ok": False,
            "error": f"Missing RECORDS file at {records_file}",
        }

    all_records = [r.strip() for r in records_file.read_text(encoding="utf-8", errors="ignore").splitlines() if r.strip()]
    selected = all_records[:max_records]

    total_windows = 0
    subtle_flags = 0
    arrhythmia_flags = 0
    tp = 0
    tn = 0
    fp = 0
    fn = 0
    confidence_values: list[float] = []
    families: Counter[str] = Counter()
    per_record_summary: list[dict[str, Any]] = []

    normal_symbols = {"N", "L", "R", "e", "j", "/"}

    for rec in selected:
        rec_path = str(MITBIH_PATH / rec)
        try:
            sig, fields = wfdb.rdsamp(rec_path, channels=[0])
            ann = wfdb.rdann(rec_path, "atr")
        except Exception:
            # Some records can fail due to edge metadata; skip safely.
            continue

        if sig is None or len(sig) < SEGMENT_LEN + 8:
            continue

        raw = np.asarray(sig[:, 0], dtype=np.float32)
        src_fs = float(fields.get("fs", FS))
        raw = _resample_to_fs(raw, src_fs, FS)

        if len(raw) < SEGMENT_LEN + 8:
            continue

        step = max(1, (len(raw) - SEGMENT_LEN) // max(1, windows_per_record))
        starts = list(range(0, len(raw) - SEGMENT_LEN, step))[:windows_per_record]
        if not starts:
            starts = [0]

        ann_samples = np.asarray(getattr(ann, "sample", []), dtype=np.int64)
        ann_symbols = list(getattr(ann, "symbol", []))

        rec_counter: Counter[str] = Counter()
        for st in starts:
            win = raw[st : st + SEGMENT_LEN].tolist()
            cleaned = process_ecg(win)
            beat = extract_beat_window(cleaned)
            out = predict_arrhythmia(beat)
            if not isinstance(out, dict):
                out = {
                    "classification": "Unknown",
                    "confidence": 0.0,
                    "is_arrhythmia": False,
                    "subtle_anomaly_flag": False,
                }

            cls = str(out.get("classification", "Unknown"))
            fam = _label_family(cls)
            conf = float(out.get("confidence", 0.0) or 0.0)
            is_arr = bool(out.get("is_arrhythmia", False))
            subtle = bool(out.get("subtle_anomaly_flag", False))

            total_windows += 1
            arrhythmia_flags += int(is_arr)
            subtle_flags += int(subtle)
            confidence_values.append(conf)
            families[fam] += 1
            rec_counter[cls] += 1

            gt_arr = False
            if ann_samples.size > 0 and len(ann_symbols) == ann_samples.size:
                left = int(st)
                right = int(st + SEGMENT_LEN)
                idx = np.where((ann_samples >= left) & (ann_samples < right))[0]
                if idx.size > 0:
                    syms = [ann_symbols[int(i)] for i in idx]
                    gt_arr = any(sym not in normal_symbols for sym in syms)

            if is_arr and gt_arr:
                tp += 1
            elif (not is_arr) and (not gt_arr):
                tn += 1
            elif is_arr and (not gt_arr):
                fp += 1
            else:
                fn += 1

        if rec_counter:
            top_cls, top_n = rec_counter.most_common(1)[0]
            per_record_summary.append({"record": rec, "top_class": top_cls, "count": top_n})

    if total_windows == 0:
        return {"ok": False, "error": "No usable MIT-BIH windows found"}

    denom = max(1, tp + tn + fp + fn)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    f1 = (2 * precision * recall) / max(1e-9, precision + recall)

    return {
        "ok": True,
        "records_used": len(per_record_summary),
        "windows_tested": total_windows,
        "arrhythmia_flag_rate": round(arrhythmia_flags / total_windows, 4),
        "subtle_flag_rate": round(subtle_flags / total_windows, 4),
        "mean_confidence": round(statistics.mean(confidence_values), 4) if confidence_values else 0.0,
        "binary_metrics_vs_annotations": {
            "accuracy": round((tp + tn) / denom, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "specificity": round(specificity, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
        },
        "prediction_family_distribution": dict(families),
        "sample_record_outcomes": per_record_summary[:12],
    }


def synthetic_subtle_anomaly_challenge(num_cases: int = 120) -> dict[str, Any]:
    """Create subtle perturbed windows and measure detection sensitivity."""

    def normal_wave(i: int, rr: int) -> float:
        p = math.exp(-0.5 * ((i - 0.18 * rr) / (0.04 * rr)) ** 2) * 0.10
        q = math.exp(-0.5 * ((i - 0.40 * rr) / (0.015 * rr)) ** 2) * -0.16
        r = math.exp(-0.5 * ((i - 0.43 * rr) / (0.012 * rr)) ** 2) * 1.45
        s = math.exp(-0.5 * ((i - 0.46 * rr) / (0.016 * rr)) ** 2) * -0.28
        t = math.exp(-0.5 * ((i - 0.68 * rr) / (0.08 * rr)) ** 2) * 0.22
        return p + q + r + s + t

    rng = random.Random(1337)
    detected = 0
    detected_hard = 0
    confs: list[float] = []

    for _ in range(num_cases):
        bpm = rng.randint(62, 88)
        rr = max(160, round(FS * 60 / bpm))
        vals: list[float] = []
        for i in range(SEGMENT_LEN):
            c = i % rr
            v = normal_wave(c, rr) + 0.008 * (rng.random() - 0.5)
            # Inject a subtle micro-anomaly: tiny premature notch and low-energy spike.
            if 0.52 * rr <= c <= 0.56 * rr:
                v += 0.03 * math.sin((c - 0.52 * rr) * 0.7)
            if c == int(0.34 * rr):
                v += 0.05
            vals.append(v)

        out = predict_arrhythmia(extract_beat_window(process_ecg(vals)))
        if not isinstance(out, dict):
            out = {
                "classification": "Unknown",
                "confidence": 0.0,
                "is_arrhythmia": False,
                "subtle_anomaly_flag": False,
            }
        is_subtle = bool(out.get("subtle_anomaly_flag", False))
        is_arr = bool(out.get("is_arrhythmia", False))
        conf = float(out.get("confidence", 0.0) or 0.0)
        confs.append(conf)
        detected += int(is_subtle)
        detected_hard += int(is_arr)

    return {
        "cases": num_cases,
        "subtle_flag_detection_rate": round(detected / num_cases, 4),
        "overall_arrhythmia_detection_rate": round(detected_hard / num_cases, 4),
        "mean_confidence": round(statistics.mean(confs), 4) if confs else 0.0,
    }


def main() -> None:
    print("=" * 90)
    print("PulseAI Global Real-World Benchmark")
    print("=" * 90)

    model_status = get_model_status()
    print(f"Model status: {model_status}")

    scan_web = os.getenv("PULSEAI_BENCH_SCAN_WEB", "1").strip().lower() not in ("0", "false", "no")
    sources = scrape_global_sources() if scan_web else []
    reachable = sum(1 for s in sources if s.get("reachable"))
    if scan_web:
        print(f"Web source scan: {reachable}/{len(sources)} reachable")
    else:
        print("Web source scan: skipped (PULSEAI_BENCH_SCAN_WEB=0)")

    max_records = int(os.getenv("PULSEAI_BENCH_MAX_RECORDS", "28"))
    windows_per_record = int(os.getenv("PULSEAI_BENCH_WINDOWS_PER_RECORD", "8"))
    subtle_cases = int(os.getenv("PULSEAI_BENCH_SUBTLE_CASES", "140"))

    mitbih = evaluate_mitbih_local(max_records=max_records, windows_per_record=windows_per_record)
    if mitbih.get("ok"):
        print(
            "MIT-BIH local eval: "
            f"records={mitbih['records_used']} windows={mitbih['windows_tested']} "
            f"arrhythmia_rate={mitbih['arrhythmia_flag_rate']:.2%} subtle_rate={mitbih['subtle_flag_rate']:.2%}"
        )
    else:
        print(f"MIT-BIH local eval failed: {mitbih.get('error')}")

    subtle = synthetic_subtle_anomaly_challenge(num_cases=subtle_cases)
    print(
        "Subtle anomaly challenge: "
        f"subtle_detection={subtle['subtle_flag_detection_rate']:.2%} "
        f"overall_detection={subtle['overall_arrhythmia_detection_rate']:.2%}"
    )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_status": model_status,
        "global_sources": sources,
        "local_mitbih_evaluation": mitbih,
        "subtle_anomaly_challenge": subtle,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written: {REPORT_PATH}")


if __name__ == "__main__":
    main()
