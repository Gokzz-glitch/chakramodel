#!/usr/bin/env python3
"""Evaluate backend model accuracy using demo2.html simulated ECG patterns.

This script reproduces the frontend signal generator from demo2.html,
feeds windows to backend preprocessing + inference, and reports:
1) Exact-string accuracy (strict UI expected text match)
2) Clinical-mapped accuracy (label-family match)
"""

from __future__ import annotations

import math
import random
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"

if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from ml_model import predict_arrhythmia  # type: ignore
from signal_processing import process_ecg, extract_beat_window  # type: ignore

FS = 500
WINDOW_LEN = 300
TRIALS_PER_MODE = 20

MODES = [
    {"id": 0, "title": "Normal Sinus Rhythm", "ecg_type": "normal", "hr": 72, "expected": "Healthy Individual (Normal)"},
    {"id": 1, "title": "Testing Phase Mode", "ecg_type": "normal", "hr": 70, "expected": "Healthy Individual (Normal)"},
    {"id": 2, "title": "Tachycardia (Fast)", "ecg_type": "tachy", "hr": 135, "expected": "Tachycardia"},
    {"id": 3, "title": "Bradycardia (Slow)", "ecg_type": "brady", "hr": 42, "expected": "Heart Block (Bradycardia)"},
    {"id": 4, "title": "Premature Contractions", "ecg_type": "pvc", "hr": 65, "expected": "Other Arrhythmia"},
    {"id": 5, "title": "AFib / Flutter (Irregular)", "ecg_type": "afib", "expected": "Atrial Fibrillation (AFib)"},
    {"id": 6, "title": "Ventricular Arrhythmias", "ecg_type": "vfib", "expected": "Ventricular Fibrillation (VF)"},
]


def _g(x: float, mu: float, sigma: float, amp: float) -> float:
    z = (x - mu) / max(sigma, 1e-6)
    return amp * math.exp(-0.5 * z * z)


def ecg_sample(ecg_type: str, ph: int, rng: random.Random, hr: int | None = None, mode_id: int | None = None) -> float:
    bpm = hr or 75
    rr = max(160, round(FS * 60 / bpm))
    c = ph % rr

    if ecg_type in ("normal", "brady", "tachy", "pvc"):
        p = _g(c, 0.18 * rr, 0.04 * rr, 0.10)
        q = _g(c, 0.40 * rr, 0.015 * rr, -0.16)
        r = _g(c, 0.43 * rr, 0.012 * rr, 1.45)
        s = _g(c, 0.46 * rr, 0.016 * rr, -0.28)
        t = _g(c, 0.68 * rr, 0.08 * rr, 0.22)
        v = p + q + r + s + t + 0.012 * (rng.random() - 0.5)

        if ecg_type == "tachy":
            v += 0.01 * math.sin(2 * math.pi * ph / (rr * 0.8))

        if ecg_type == "pvc":
            pvc_beat = ((ph // rr) + (mode_id or 0)) % 7 == 0
            if pvc_beat:
                pvc_qrs = _g(c, 0.36 * rr, 0.03 * rr, 2.1) + _g(c, 0.44 * rr, 0.03 * rr, -0.7)
                v = pvc_qrs + _g(c, 0.70 * rr, 0.10 * rr, 0.10) + 0.02 * (rng.random() - 0.5)
        return v

    if ecg_type == "afib":
        irr = rng.random() < 0.018
        if irr:
            return 1.3 + rng.random() * 0.5
        return 0.07 * math.sin(ph * 0.9 + rng.random()) + 0.03 * (rng.random() - 0.5)

    if ecg_type == "vfib":
        return (rng.random() - 0.5) * 1.8 + 0.4 * math.sin(ph * 0.3 + rng.random() * 2)

    return 0.0


def generate_window(mode: Dict[str, object], seed: int) -> List[float]:
    rng = random.Random(seed)
    ecg_type = str(mode["ecg_type"])
    hr = int(mode["hr"]) if mode.get("hr") is not None else None
    mode_id = int(mode["id"])
    return [ecg_sample(ecg_type, ph, rng, hr=hr, mode_id=mode_id) for ph in range(WINDOW_LEN)]


def canonical(label: str) -> str:
    l = (label or "").lower()
    if "normal" in l:
        return "normal"
    if "afib" in l or "atrial fibrillation" in l:
        return "afib"
    if "brady" in l:
        return "brady"
    if "vf" in l and "fibrillation" in l:
        return "vfib"
    if "ventricular tachycardia" in l or "tachycardia" in l:
        return "tachy"
    if "arrhythmia" in l or "flutter" in l or "pvc" in l:
        return "other"
    return "other"


def expected_canonical(mode: Dict[str, object]) -> str:
    e = mode["expected"].lower()
    if "normal" in e:
        return "normal"
    if "afib" in e:
        return "afib"
    if "brady" in e:
        return "brady"
    if "ventricular fibrillation" in e:
        return "vfib"
    if "tachy" in e:
        return "tachy"
    return "other"


def evaluate_mode(mode: Dict[str, object], trials: int) -> Tuple[int, int, int, float, Counter]:
    exact_hits = 0
    mapped_hits = 0
    confs: List[float] = []
    preds: Counter = Counter()

    for i in range(trials):
        raw = generate_window(mode, seed=int(mode["id"]) * 1000 + i)
        cleaned = process_ecg(raw)
        beat = extract_beat_window(cleaned)
        res = predict_arrhythmia(beat)

        pred = str(res.get("classification", "Unknown"))
        conf = float(res.get("confidence", 0.0) or 0.0)
        confs.append(conf)
        preds[pred] += 1

        if pred == str(mode["expected"]):
            exact_hits += 1
        if canonical(pred) == expected_canonical(mode):
            mapped_hits += 1

    avg_conf = statistics.mean(confs) if confs else 0.0
    return trials, exact_hits, mapped_hits, avg_conf, preds


def main() -> None:
    print("PulseAI demo2 simulated-data backend evaluation")
    print(f"Trials per mode: {TRIALS_PER_MODE}")
    print("=" * 96)

    total_trials = 0
    total_exact = 0
    total_mapped = 0

    for mode in MODES:
        trials, exact_hits, mapped_hits, avg_conf, preds = evaluate_mode(mode, TRIALS_PER_MODE)
        total_trials += trials
        total_exact += exact_hits
        total_mapped += mapped_hits

        top_pred, top_count = preds.most_common(1)[0]
        exact_pct = 100.0 * exact_hits / trials
        mapped_pct = 100.0 * mapped_hits / trials
        print(
            f"Mode {mode['id']} | {mode['title']:<28} | expected={mode['expected']:<30} "
            f"| top_pred={top_pred:<30} ({top_count:>2}/{trials}) | exact={exact_pct:5.1f}% | mapped={mapped_pct:5.1f}% | avg_conf={avg_conf:.3f}"
        )

    overall_exact = 100.0 * total_exact / total_trials if total_trials else 0.0
    overall_mapped = 100.0 * total_mapped / total_trials if total_trials else 0.0

    print("-" * 96)
    print(
        f"OVERALL: exact-label accuracy={overall_exact:.2f}% ({total_exact}/{total_trials}) | "
        f"clinical-mapped accuracy={overall_mapped:.2f}% ({total_mapped}/{total_trials})"
    )


if __name__ == "__main__":
    main()
