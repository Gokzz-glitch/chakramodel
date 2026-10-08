#!/usr/bin/env python3
"""Permutation+combination tuning across benchmark and 10-case tests.

Team-lead objective: maximize clinical usefulness by balancing
recall, specificity, precision, and scenario accuracy.
"""

from __future__ import annotations

import itertools
import json
import os
import random
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "scripts" / "global_realworld_benchmark.py"
TEN = ROOT / "test_10cases_age_variety.py"
BENCH_REPORT = ROOT / "test_results" / "global_benchmark_report.json"
TUNE_OUT = ROOT / "test_results" / "combined_policy_tuning_report.json"


@dataclass
class Trial:
    arrhythmia_min_conf: float
    max_normal_prob: float
    require_good_quality: bool
    strong_override_conf: float
    review_uncertainty: float
    high_uncertainty: float


@dataclass
class TrialScore:
    params: Trial
    recall: float
    specificity: float
    precision: float
    f1: float
    bench_accuracy: float
    ten_case_accuracy: float
    score: float


def run_cmd(cmd: list[str], env: dict[str, str]) -> None:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{proc.stdout}")


def latest_10case_file() -> Path:
    files = sorted((ROOT / "test_results").glob("test_10cases_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError("No 10-case report found.")
    return files[0]


def trial_env(t: Trial) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PULSEAI_ARRHYTHMIA_MIN_CONF"] = f"{t.arrhythmia_min_conf:.3f}"
    env["PULSEAI_MAX_NORMAL_PROB_FOR_ARR"] = f"{t.max_normal_prob:.3f}"
    env["PULSEAI_REQUIRE_GOOD_QUALITY"] = "1" if t.require_good_quality else "0"
    env["PULSEAI_STRONG_ML_OVERRIDE_CONF"] = f"{t.strong_override_conf:.3f}"
    env["PULSEAI_REVIEW_UNCERTAINTY_THRESHOLD"] = f"{t.review_uncertainty:.3f}"
    env["PULSEAI_HIGH_UNCERTAINTY_THRESHOLD"] = f"{t.high_uncertainty:.3f}"

    # Fast but representative pass for tuning.
    env["PULSEAI_BENCH_SCAN_WEB"] = "0"
    env["PULSEAI_BENCH_MAX_RECORDS"] = "24"
    env["PULSEAI_BENCH_WINDOWS_PER_RECORD"] = "12"
    env["PULSEAI_BENCH_SUBTLE_CASES"] = "120"
    return env


def evaluate_trial(t: Trial) -> TrialScore:
    env = trial_env(t)
    run_cmd([sys.executable, str(BENCH)], env)
    run_cmd([sys.executable, str(TEN)], env)

    bench = json.loads(BENCH_REPORT.read_text(encoding="utf-8"))
    ten = json.loads(latest_10case_file().read_text(encoding="utf-8"))

    m = bench["local_mitbih_evaluation"]["binary_metrics_vs_annotations"]
    recall = float(m.get("recall", 0.0))
    specificity = float(m.get("specificity", 0.0))
    precision = float(m.get("precision", 0.0))
    f1 = float(m.get("f1", 0.0))
    bench_acc = float(m.get("accuracy", 0.0))
    ten_acc = float(ten.get("accuracy", 0.0))

    # Weighted toward safety-critical sensitivity+specificity while preserving scenario accuracy.
    score = (
        0.32 * recall
        + 0.28 * specificity
        + 0.20 * ten_acc
        + 0.12 * precision
        + 0.08 * f1
    )

    return TrialScore(
        params=t,
        recall=recall,
        specificity=specificity,
        precision=precision,
        f1=f1,
        bench_accuracy=bench_acc,
        ten_case_accuracy=ten_acc,
        score=score,
    )


def main() -> None:
    random.seed(42)

    grid = {
        "arrhythmia_min_conf": [0.55, 0.60, 0.65, 0.70],
        "max_normal_prob": [0.55, 0.60, 0.65, 0.70],
        "require_good_quality": [False, True],
        "strong_override_conf": [0.72, 0.78, 0.84],
        "review_uncertainty": [0.50, 0.55, 0.60],
        "high_uncertainty": [0.72, 0.78],
    }

    all_trials: list[Trial] = []
    for combo in itertools.product(
        grid["arrhythmia_min_conf"],
        grid["max_normal_prob"],
        grid["require_good_quality"],
        grid["strong_override_conf"],
        grid["review_uncertainty"],
        grid["high_uncertainty"],
    ):
        t = Trial(*combo)
        if t.high_uncertainty <= t.review_uncertainty:
            continue
        all_trials.append(t)

    max_trials = int(os.getenv("PULSEAI_COMBINED_TUNE_TRIALS", "80"))
    if len(all_trials) > max_trials:
        selected = random.sample(all_trials, max_trials)
    else:
        selected = all_trials

    print(f"Running combined tuner with {len(selected)} trials (from {len(all_trials)} valid combos)...")

    results: list[TrialScore] = []
    failures: list[dict[str, Any]] = []

    for i, t in enumerate(selected, start=1):
        print(
            f"[{i}/{len(selected)}] conf={t.arrhythmia_min_conf:.2f} "
            f"norm={t.max_normal_prob:.2f} goodQ={t.require_good_quality} "
            f"strong={t.strong_override_conf:.2f} reviewU={t.review_uncertainty:.2f} highU={t.high_uncertainty:.2f}"
        )
        try:
            s = evaluate_trial(t)
            results.append(s)
            print(
                f"  -> score={s.score:.4f} rec={s.recall:.4f} spec={s.specificity:.4f} "
                f"prec={s.precision:.4f} ten={s.ten_case_accuracy:.4f}"
            )
        except Exception as exc:
            failures.append({"params": asdict(t), "error": str(exc)})
            print(f"  -> trial failed: {exc}")

    if not results:
        raise RuntimeError("No successful trials.")

    ranked = sorted(results, key=lambda x: x.score, reverse=True)
    best = ranked[0]

    out = {
        "trials_requested": len(selected),
        "trials_succeeded": len(results),
        "trials_failed": len(failures),
        "best": {
            "params": asdict(best.params),
            "metrics": {
                "recall": best.recall,
                "specificity": best.specificity,
                "precision": best.precision,
                "f1": best.f1,
                "benchmark_accuracy": best.bench_accuracy,
                "ten_case_accuracy": best.ten_case_accuracy,
                "score": best.score,
            },
        },
        "recommended_env": {
            "PULSEAI_ARRHYTHMIA_MIN_CONF": f"{best.params.arrhythmia_min_conf:.3f}",
            "PULSEAI_MAX_NORMAL_PROB_FOR_ARR": f"{best.params.max_normal_prob:.3f}",
            "PULSEAI_REQUIRE_GOOD_QUALITY": "1" if best.params.require_good_quality else "0",
            "PULSEAI_STRONG_ML_OVERRIDE_CONF": f"{best.params.strong_override_conf:.3f}",
            "PULSEAI_REVIEW_UNCERTAINTY_THRESHOLD": f"{best.params.review_uncertainty:.3f}",
            "PULSEAI_HIGH_UNCERTAINTY_THRESHOLD": f"{best.params.high_uncertainty:.3f}",
        },
        "top10": [
            {
                "params": asdict(s.params),
                "metrics": {
                    "recall": s.recall,
                    "specificity": s.specificity,
                    "precision": s.precision,
                    "f1": s.f1,
                    "benchmark_accuracy": s.bench_accuracy,
                    "ten_case_accuracy": s.ten_case_accuracy,
                    "score": s.score,
                },
            }
            for s in ranked[:10]
        ],
        "failures": failures[:20],
    }

    TUNE_OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Combined tuning report written: {TUNE_OUT}")


if __name__ == "__main__":
    main()
