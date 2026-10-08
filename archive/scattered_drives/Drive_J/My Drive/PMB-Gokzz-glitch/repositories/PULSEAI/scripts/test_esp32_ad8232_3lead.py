#!/usr/bin/env python3
"""Simulated 3-lead ESP32 + AD8232 test against PulseAI backend logic.

Generates realistic Lead I/II/III signals with hardware-like artifacts,
runs backend preprocessing + model inference per lead and fused lead,
and reports accuracy against expected rhythm families.
"""

from __future__ import annotations

import math
import random
import statistics
import sys
import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from signal_processing import process_ecg, extract_beat_window, FS, SEGMENT_LEN  # type: ignore
from ml_model import predict_arrhythmia  # type: ignore

TRIALS_PER_CASE = 20
MOTION_SCALE = 0.06

FILTER_CONFIG = {
    "mains_hz": 50,
    "notch_enabled": True,
    "hp_enabled": True,
    "lp_enabled": True,
    "ma_enabled": False,
    "median_enabled": True,
    "hampel_enabled": True,
    "clip_enabled": False,
}

REPORT_PATH = PROJECT_ROOT / "test_results" / "esp32_ad8232_3lead_sim_report.json"

CASES = [
    {"name": "Normal", "rhythm": "normal", "bpm": 76, "expected": "normal"},
    {"name": "AFib-like", "rhythm": "afib", "bpm": 95, "expected": "afib"},
    {"name": "PVC-like", "rhythm": "pvc", "bpm": 74, "expected": "other"},
    {"name": "Tachy-like", "rhythm": "tachy", "bpm": 142, "expected": "tachy"},
]


def gauss(x: float, mu: float, sigma: float, amp: float) -> float:
    z = (x - mu) / max(sigma, 1e-6)
    return amp * math.exp(-0.5 * z * z)


def ecg_base_sample(i: int, bpm: int, rhythm: str, rng: random.Random) -> float:
    rr = max(160, round(FS * 60 / max(35, bpm)))
    c = i % rr

    p = gauss(c, 0.18 * rr, 0.04 * rr, 0.10)
    q = gauss(c, 0.40 * rr, 0.015 * rr, -0.16)
    r = gauss(c, 0.43 * rr, 0.012 * rr, 1.45)
    s = gauss(c, 0.46 * rr, 0.016 * rr, -0.28)
    t = gauss(c, 0.68 * rr, 0.08 * rr, 0.22)
    v = p + q + r + s + t

    if rhythm == "afib":
        v += 0.07 * math.sin(i * 0.9 + rng.random()) + 0.03 * (rng.random() - 0.5)
        if rng.random() < 0.018:
            v += 0.5 + 0.5 * rng.random()
    elif rhythm == "pvc":
        if ((i // rr) % 7) == 0:
            v = gauss(c, 0.36 * rr, 0.03 * rr, 2.0) + gauss(c, 0.44 * rr, 0.03 * rr, -0.7)
    elif rhythm == "tachy":
        v += 0.01 * math.sin(2 * math.pi * i / (rr * 0.8))

    return v


def generate_three_leads(bpm: int, rhythm: str, seed: int) -> tuple[list[float], list[float], list[float]]:
    rng = random.Random(seed)
    lead_i: list[float] = []
    lead_ii: list[float] = []
    lead_iii: list[float] = []

    n = SEGMENT_LEN
    for i in range(n):
        base = ecg_base_sample(i, bpm, rhythm, rng)

        # Hardware-like artifacts for AD8232 + ESP32 acquisition
        baseline = 0.08 * math.sin(2 * math.pi * 0.33 * i / FS)
        mains = 0.06 * math.sin(2 * math.pi * 50 * i / FS)
        emg = 0.03 * math.sin(2 * math.pi * 27 * i / FS)
        motion = MOTION_SCALE * (rng.random() - 0.5)

        # 3 leads with slight gain/phase variability
        li = 0.92 * base + 0.020 * math.sin(2 * math.pi * i / 180) + baseline + mains + emg + motion
        liii = 0.88 * base + 0.018 * math.sin(2 * math.pi * i / 205 + 0.2) + baseline + mains + emg + motion
        lii = li + liii + 0.01 * (rng.random() - 0.5)  # Einthoven relation approx: II = I + III

        # occasional contact spike
        if rng.random() < 0.008:
            li += (rng.random() - 0.5) * 0.9
            lii += (rng.random() - 0.5) * 1.0
            liii += (rng.random() - 0.5) * 0.8

        lead_i.append(li)
        lead_ii.append(lii)
        lead_iii.append(liii)

    return lead_i, lead_ii, lead_iii


def canonical_family(label: str) -> str:
    l = (label or "").lower()
    if "normal" in l:
        return "normal"
    if "afib" in l or "atrial fibrillation" in l:
        return "afib"
    if "brady" in l:
        return "brady"
    if ("vf" in l and "fibrillation" in l) or "ventricular fibrillation" in l:
        return "vfib"
    if "tachy" in l or "ventricular tachycardia" in l:
        return "tachy"
    if "subtle" in l:
        return "subtle"
    return "other"


def infer_one(sig: list[float]) -> dict:
    cleaned = process_ecg(sig, filter_config=FILTER_CONFIG)
    window = extract_beat_window(cleaned)
    return predict_arrhythmia(window)


def run() -> None:
    print("=" * 92)
    print("PulseAI 3-Lead ESP32+AD8232 Simulation Test")
    print("=" * 92)
    print(f"Trials per case: {TRIALS_PER_CASE}")

    total = 0
    correct_fused = 0
    all_preds = Counter()
    case_reports = []

    for ci, case in enumerate(CASES):
        expected = case["expected"]
        fused_match = 0
        lead_family_counts = Counter()
        fused_conf = []

        for t in range(TRIALS_PER_CASE):
            l1, l2, l3 = generate_three_leads(case["bpm"], case["rhythm"], seed=1000 * (ci + 1) + t)

            r1 = infer_one(l1)
            r2 = infer_one(l2)
            r3 = infer_one(l3)

            # Fused signal prioritizes Lead II while retaining I/III information
            fused = [(0.2 * a) + (0.6 * b) + (0.2 * c) for a, b, c in zip(l1, l2, l3)]
            rf = infer_one(fused)

            fam1 = canonical_family(str(r1.get("classification", "Unknown")))
            fam2 = canonical_family(str(r2.get("classification", "Unknown")))
            fam3 = canonical_family(str(r3.get("classification", "Unknown")))
            famf = canonical_family(str(rf.get("classification", "Unknown")))

            lead_family_counts.update([fam1, fam2, fam3])
            all_preds[famf] += 1
            fused_conf.append(float(rf.get("confidence", 0.0) or 0.0))

            total += 1
            if famf == expected:
                fused_match += 1
                correct_fused += 1

        acc = 100.0 * fused_match / TRIALS_PER_CASE
        case_reports.append(
            {
                "case": case["name"],
                "expected_family": expected,
                "fused_accuracy": round(acc, 4),
                "mean_fused_confidence": round(statistics.mean(fused_conf), 4),
                "lead_family_counts": dict(lead_family_counts),
            }
        )
        print(
            f"Case: {case['name']:<12} expected={expected:<6} | fused_acc={acc:5.1f}% | "
            f"mean_fused_conf={statistics.mean(fused_conf):.3f} | lead_families={dict(lead_family_counts)}"
        )

    overall = 100.0 * correct_fused / max(1, total)
    print("-" * 92)
    print(f"OVERALL fused family accuracy: {overall:.2f}% ({correct_fused}/{total})")
    print(f"Fused prediction family distribution: {dict(all_preds)}")

    report = {
        "trials_per_case": TRIALS_PER_CASE,
        "filter_config": FILTER_CONFIG,
        "overall_fused_family_accuracy": round(overall, 4),
        "correct": correct_fused,
        "total": total,
        "fused_prediction_family_distribution": dict(all_preds),
        "cases": case_reports,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written: {REPORT_PATH}")


if __name__ == "__main__":
    run()
