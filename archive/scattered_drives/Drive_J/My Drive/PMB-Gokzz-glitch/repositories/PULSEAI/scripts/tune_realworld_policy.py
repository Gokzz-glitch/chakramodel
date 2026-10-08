#!/usr/bin/env python3
"""Grid-search policy thresholds on real-world MIT-BIH benchmark.

This script runs the existing global benchmark multiple times with different
post-classification policy thresholds and selects the best configuration by
balanced score (F1 + specificity + recall).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCH_SCRIPT = PROJECT_ROOT / "scripts" / "global_realworld_benchmark.py"
REPORT_PATH = PROJECT_ROOT / "test_results" / "global_benchmark_report.json"
TUNE_REPORT_PATH = PROJECT_ROOT / "test_results" / "policy_tuning_report.json"


@dataclass
class TrialResult:
    min_conf: float
    max_normal_prob: float
    require_good_quality: bool
    f1: float
    recall: float
    specificity: float
    precision: float
    accuracy: float

    def is_feasible(self, min_specificity: float, min_precision: float, min_recall: float) -> bool:
        return (
            self.specificity >= min_specificity
            and self.precision >= min_precision
            and self.recall >= min_recall
        )

    @property
    def score(self) -> float:
        # Team-lead objective: reduce false alarms without losing dangerous events.
        if self.recall <= 0.01 or self.precision <= 0.01:
            return 0.0
        return (0.45 * self.f1) + (0.35 * self.specificity) + (0.20 * self.recall)


def run_trial(min_conf: float, max_normal_prob: float, require_good_quality: bool) -> TrialResult:
    env = os.environ.copy()
    env["PULSEAI_ARRHYTHMIA_MIN_CONF"] = f"{min_conf:.3f}"
    env["PULSEAI_MAX_NORMAL_PROB_FOR_ARR"] = f"{max_normal_prob:.3f}"
    env["PULSEAI_REQUIRE_GOOD_QUALITY"] = "1" if require_good_quality else "0"

    # Faster tuning pass on a representative subset.
    env["PULSEAI_BENCH_SCAN_WEB"] = "0"
    env["PULSEAI_BENCH_MAX_RECORDS"] = "16"
    env["PULSEAI_BENCH_WINDOWS_PER_RECORD"] = "8"
    env["PULSEAI_BENCH_SUBTLE_CASES"] = "80"

    proc = subprocess.run(
        [sys.executable, str(BENCH_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Benchmark failed for trial conf={min_conf}, normal={max_normal_prob}:\n{proc.stdout}")

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    m = report["local_mitbih_evaluation"]["binary_metrics_vs_annotations"]

    return TrialResult(
        min_conf=min_conf,
        max_normal_prob=max_normal_prob,
        require_good_quality=require_good_quality,
        f1=float(m.get("f1", 0.0)),
        recall=float(m.get("recall", 0.0)),
        specificity=float(m.get("specificity", 0.0)),
        precision=float(m.get("precision", 0.0)),
        accuracy=float(m.get("accuracy", 0.0)),
    )


def run_final(best: TrialResult) -> dict[str, Any]:
    env = os.environ.copy()
    env["PULSEAI_ARRHYTHMIA_MIN_CONF"] = f"{best.min_conf:.3f}"
    env["PULSEAI_MAX_NORMAL_PROB_FOR_ARR"] = f"{best.max_normal_prob:.3f}"
    env["PULSEAI_REQUIRE_GOOD_QUALITY"] = "1" if best.require_good_quality else "0"

    # Full benchmark.
    env["PULSEAI_BENCH_SCAN_WEB"] = "1"
    env["PULSEAI_BENCH_MAX_RECORDS"] = "28"
    env["PULSEAI_BENCH_WINDOWS_PER_RECORD"] = "8"
    env["PULSEAI_BENCH_SUBTLE_CASES"] = "140"

    proc = subprocess.run(
        [sys.executable, str(BENCH_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Final benchmark failed:\n{proc.stdout}")

    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def main() -> None:
    min_spec = float(os.getenv("PULSEAI_TUNE_MIN_SPEC", "0.45"))
    min_prec = float(os.getenv("PULSEAI_TUNE_MIN_PREC", "0.12"))
    min_rec = float(os.getenv("PULSEAI_TUNE_MIN_REC", "0.35"))

    # Include permissive baseline + moderate gating regimes.
    conf_grid = [0.00, 0.55, 0.70, 0.80, 0.90]
    normal_prob_grid = [1.00, 0.85, 0.70, 0.55, 0.40]
    quality_grid = [True, False]

    trials: list[TrialResult] = []
    print("Running real-world policy threshold tuning...")
    for c in conf_grid:
        for n in normal_prob_grid:
            for q in quality_grid:
                t = run_trial(c, n, q)
                trials.append(t)
                print(
                    f"trial conf={c:.2f} normal_prob={n:.2f} quality={q} | "
                    f"acc={t.accuracy:.4f} prec={t.precision:.4f} rec={t.recall:.4f} spec={t.specificity:.4f} f1={t.f1:.4f} score={t.score:.4f}"
                )

    feasible = [t for t in trials if t.is_feasible(min_spec, min_prec, min_rec)]
    if feasible:
        best = max(feasible, key=lambda x: x.score)
        selection_mode = "feasible"
    else:
        # Fall back to best score so tuning never fails hard.
        best = max(trials, key=lambda x: x.score)
        selection_mode = "fallback-best-score"

    print("\nBest trial selected:")
    print(
        f"conf={best.min_conf:.2f}, normal_prob={best.max_normal_prob:.2f}, "
        f"quality={best.require_good_quality}, score={best.score:.4f}, mode={selection_mode}"
    )

    final_report = run_final(best)
    out = {
        "constraints": {
            "min_specificity": min_spec,
            "min_precision": min_prec,
            "min_recall": min_rec,
        },
        "selection_mode": selection_mode,
        "best_trial": {
            "min_conf": best.min_conf,
            "max_normal_prob": best.max_normal_prob,
            "require_good_quality": best.require_good_quality,
            "score": round(best.score, 4),
            "accuracy": best.accuracy,
            "precision": best.precision,
            "recall": best.recall,
            "specificity": best.specificity,
            "f1": best.f1,
        },
        "recommended_env": {
            "PULSEAI_ARRHYTHMIA_MIN_CONF": f"{best.min_conf:.3f}",
            "PULSEAI_MAX_NORMAL_PROB_FOR_ARR": f"{best.max_normal_prob:.3f}",
            "PULSEAI_REQUIRE_GOOD_QUALITY": "1" if best.require_good_quality else "0",
        },
        "all_trials": [
            {
                "min_conf": t.min_conf,
                "max_normal_prob": t.max_normal_prob,
                "require_good_quality": t.require_good_quality,
                "score": round(t.score, 4),
                "accuracy": t.accuracy,
                "precision": t.precision,
                "recall": t.recall,
                "specificity": t.specificity,
                "f1": t.f1,
            }
            for t in trials
        ],
        "final_full_report": final_report,
    }

    TUNE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TUNE_REPORT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nPolicy tuning report written: {TUNE_REPORT_PATH}")


if __name__ == "__main__":
    main()
