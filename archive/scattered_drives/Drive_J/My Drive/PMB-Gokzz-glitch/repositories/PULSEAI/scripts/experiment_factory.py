#!/usr/bin/env python3
"""Experiment factory for large, reproducible PulseAI trial campaigns.

This script expands beyond single-threshold tuning by composing experiment
metadata dimensions (dataset regime, backbone family, weight source,
policy profile) and executing ranked benchmark+10-case trials.

Current execution mode focuses on policy-level reproducible sweeps while
recording architecture/data-transfer candidates for subsequent retraining.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "test_results"
RUNS_DIR = RESULTS_DIR / "experiment_factory_runs"
REGISTRY_PATH = ROOT / "experiments" / "registry.json"

BENCH_SCRIPT = ROOT / "scripts" / "global_realworld_benchmark.py"
TEN_CASE_SCRIPT = ROOT / "test_10cases_age_variety.py"
BENCH_REPORT = RESULTS_DIR / "global_benchmark_report.json"


@dataclass
class PolicyProfile:
    name: str
    arrhythmia_min_conf: float
    max_normal_prob: float
    require_good_quality: bool
    strong_override_conf: float
    review_uncertainty: float
    high_uncertainty: float


@dataclass
class ExperimentSpec:
    experiment_id: str
    dataset_regime: str
    model_backbone: str
    weight_source: str
    paper_hint: str
    repo_hint: str
    policy_profile: str
    status: str = "planned"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_registry(seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)

    dataset_regimes = [
        "mitbih_core",
        "mitbih_plus_noise_stress",
        "ptbxl_transfer_then_mitbih",
        "incart_external_generalization",
    ]

    model_backbones = [
        "hctg_net",
        "resnet1d",
        "automatic_ecg_diagnosis_style",
    ]

    weight_sources = [
        "local_hctg_checkpoint",
        "ptbxl_pretrain_candidate",
        "self_supervised_1d_init_candidate",
    ]

    paper_hints = [
        "PTB-XL Benchmarks and Insights (arXiv:2004.13701)",
        "ECG Heartbeat Transferable Representation (arXiv:1805.00794)",
    ]

    repo_hints = [
        "github.com/hsd1503/resnet1d",
        "github.com/antonior92/automatic-ecg-diagnosis",
        "github.com/berndporr/py-ecg-detectors",
    ]

    policy_profiles = ["balanced_v1", "recall_guard_v1", "specificity_guard_v1", "high_review_safety_v1"]

    experiments: list[ExperimentSpec] = []
    counter = 1
    for dataset in dataset_regimes:
        for backbone in model_backbones:
            for weights in weight_sources:
                for profile in policy_profiles:
                    spec = ExperimentSpec(
                        experiment_id=f"EXP-{counter:04d}",
                        dataset_regime=dataset,
                        model_backbone=backbone,
                        weight_source=weights,
                        paper_hint=rng.choice(paper_hints),
                        repo_hint=rng.choice(repo_hints),
                        policy_profile=profile,
                    )
                    experiments.append(spec)
                    counter += 1

    return {
        "generated_at_utc": utc_now(),
        "execution_mode": "policy_only_with_metadata_for_transfer_learning",
        "notes": [
            "Dataset/backbone/weight dimensions are logged for experiment governance.",
            "Current runner executes benchmark + 10-case policy trials.",
            "Retraining/integration jobs can consume this registry in next phase.",
        ],
        "policy_profiles": [asdict(p) for p in get_policy_profiles()],
        "experiments": [asdict(e) for e in experiments],
    }


def get_policy_profiles() -> list[PolicyProfile]:
    return [
        PolicyProfile(
            name="balanced_v1",
            arrhythmia_min_conf=0.60,
            max_normal_prob=0.62,
            require_good_quality=False,
            strong_override_conf=0.78,
            review_uncertainty=0.55,
            high_uncertainty=0.78,
        ),
        PolicyProfile(
            name="recall_guard_v1",
            arrhythmia_min_conf=0.56,
            max_normal_prob=0.70,
            require_good_quality=False,
            strong_override_conf=0.74,
            review_uncertainty=0.52,
            high_uncertainty=0.75,
        ),
        PolicyProfile(
            name="specificity_guard_v1",
            arrhythmia_min_conf=0.68,
            max_normal_prob=0.56,
            require_good_quality=True,
            strong_override_conf=0.82,
            review_uncertainty=0.58,
            high_uncertainty=0.80,
        ),
        PolicyProfile(
            name="high_review_safety_v1",
            arrhythmia_min_conf=0.62,
            max_normal_prob=0.64,
            require_good_quality=True,
            strong_override_conf=0.80,
            review_uncertainty=0.50,
            high_uncertainty=0.72,
        ),
    ]


def get_profile_map() -> dict[str, PolicyProfile]:
    return {p.name: p for p in get_policy_profiles()}


def ensure_registry(path: Path, seed: int = 42) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    data = default_registry(seed=seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def run_cmd(cmd: list[str], env: dict[str, str], trial_dir: Path, log_name: str) -> None:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    (trial_dir / log_name).write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


def latest_10case_file(after_epoch: float) -> Path:
    files = sorted(
        RESULTS_DIR.glob("test_10cases_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in files:
        if p.stat().st_mtime >= after_epoch:
            return p
    if files:
        return files[0]
    raise RuntimeError("No test_10cases report found.")


def score_metrics(recall: float, specificity: float, precision: float, f1: float, ten_case_accuracy: float) -> float:
    score = (
        0.35 * recall
        + 0.30 * specificity
        + 0.20 * ten_case_accuracy
        + 0.10 * precision
        + 0.05 * f1
    )

    # Penalize clinically unsafe operating points.
    if recall < 0.50:
        score -= 0.08
    if specificity < 0.70:
        score -= 0.05
    if ten_case_accuracy < 0.90:
        score -= 0.05
    return score


def build_env(spec: dict[str, Any], profile: PolicyProfile, seed: int) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    env["PULSEAI_EXPERIMENT_ID"] = spec["experiment_id"]
    env["PULSEAI_EXPERIMENT_DATASET"] = spec["dataset_regime"]
    env["PULSEAI_EXPERIMENT_BACKBONE"] = spec["model_backbone"]
    env["PULSEAI_EXPERIMENT_WEIGHT_SOURCE"] = spec["weight_source"]
    env["PULSEAI_EXPERIMENT_PAPER_HINT"] = spec["paper_hint"]
    env["PULSEAI_EXPERIMENT_REPO_HINT"] = spec["repo_hint"]
    env["PULSEAI_RANDOM_SEED"] = str(seed)

    env["PULSEAI_ARRHYTHMIA_MIN_CONF"] = f"{profile.arrhythmia_min_conf:.3f}"
    env["PULSEAI_MAX_NORMAL_PROB_FOR_ARR"] = f"{profile.max_normal_prob:.3f}"
    env["PULSEAI_REQUIRE_GOOD_QUALITY"] = "1" if profile.require_good_quality else "0"
    env["PULSEAI_STRONG_ML_OVERRIDE_CONF"] = f"{profile.strong_override_conf:.3f}"
    env["PULSEAI_REVIEW_UNCERTAINTY_THRESHOLD"] = f"{profile.review_uncertainty:.3f}"
    env["PULSEAI_HIGH_UNCERTAINTY_THRESHOLD"] = f"{profile.high_uncertainty:.3f}"

    # Fast representative tuning mode; override externally for deeper sweeps.
    env.setdefault("PULSEAI_BENCH_SCAN_WEB", "0")
    env.setdefault("PULSEAI_BENCH_MAX_RECORDS", "20")
    env.setdefault("PULSEAI_BENCH_WINDOWS_PER_RECORD", "10")
    env.setdefault("PULSEAI_BENCH_SUBTLE_CASES", "100")
    return env


def select_experiments(registry: dict[str, Any], max_trials: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    experiments = [e for e in registry.get("experiments", []) if e.get("status", "planned") != "completed"]
    if len(experiments) <= max_trials:
        return experiments
    return rng.sample(experiments, max_trials)


def render_markdown(run_report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# PulseAI Experiment Factory Report")
    lines.append("")
    lines.append(f"Generated at: {run_report['generated_at_utc']}")
    lines.append(f"Run id: {run_report['run_id']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Trials requested: {run_report['summary']['trials_requested']}")
    lines.append(f"- Trials succeeded: {run_report['summary']['trials_succeeded']}")
    lines.append(f"- Trials failed: {run_report['summary']['trials_failed']}")
    lines.append("")
    lines.append("## Leaderboard")
    lines.append("")
    lines.append("| Rank | Experiment | Dataset | Backbone | Policy | Score | Recall | Specificity | Ten-case |")
    lines.append("|---|---|---|---|---|---:|---:|---:|---:|")
    for i, row in enumerate(run_report.get("leaderboard", [])[:15], start=1):
        lines.append(
            "| "
            f"{i} | {row['experiment_id']} | {row['dataset_regime']} | {row['model_backbone']} | "
            f"{row['policy_profile']} | {row['metrics']['score']:.4f} | {row['metrics']['recall']:.4f} | "
            f"{row['metrics']['specificity']:.4f} | {row['metrics']['ten_case_accuracy']:.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="PulseAI experiment factory runner")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH, help="Path to experiment registry JSON")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--max-trials", type=int, default=12, help="Maximum number of experiments to run")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute scripts; print selected experiments only")
    parser.add_argument("--write-registry-only", action="store_true", help="Create registry if missing, then exit")
    args = parser.parse_args()

    registry = ensure_registry(args.registry, seed=args.seed)
    if args.write_registry_only:
        print(f"Registry ready: {args.registry}")
        return

    selected = select_experiments(registry, max_trials=args.max_trials, seed=args.seed)
    print(f"Selected {len(selected)} experiments from registry: {args.registry}")
    if not selected:
        print("No pending experiments found.")
        return

    if args.dry_run:
        for spec in selected:
            print(
                f"- {spec['experiment_id']} | {spec['dataset_regime']} | {spec['model_backbone']} | "
                f"{spec['weight_source']} | {spec['policy_profile']}"
            )
        return

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    profile_map = get_profile_map()
    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for idx, spec in enumerate(selected, start=1):
        exp_id = spec["experiment_id"]
        policy_name = spec["policy_profile"]
        profile = profile_map.get(policy_name)
        if profile is None:
            failures.append({"experiment_id": exp_id, "error": f"Unknown policy profile: {policy_name}"})
            continue

        print(f"[{idx}/{len(selected)}] Running {exp_id} ({policy_name})")
        trial_dir = run_dir / exp_id
        trial_dir.mkdir(parents=True, exist_ok=True)

        env = build_env(spec, profile, seed=args.seed)
        trial_start_epoch = datetime.now().timestamp()

        try:
            run_cmd([sys.executable, str(BENCH_SCRIPT)], env, trial_dir, "benchmark.log")
            run_cmd([sys.executable, str(TEN_CASE_SCRIPT)], env, trial_dir, "ten_case.log")

            bench = json.loads(BENCH_REPORT.read_text(encoding="utf-8"))
            ten_case_file = latest_10case_file(after_epoch=trial_start_epoch)
            ten = json.loads(ten_case_file.read_text(encoding="utf-8"))

            m = bench["local_mitbih_evaluation"]["binary_metrics_vs_annotations"]
            recall = float(m.get("recall", 0.0))
            specificity = float(m.get("specificity", 0.0))
            precision = float(m.get("precision", 0.0))
            f1 = float(m.get("f1", 0.0))
            bench_acc = float(m.get("accuracy", 0.0))
            ten_acc = float(ten.get("accuracy", 0.0))
            score = score_metrics(recall, specificity, precision, f1, ten_acc)

            row = {
                "experiment_id": exp_id,
                "dataset_regime": spec["dataset_regime"],
                "model_backbone": spec["model_backbone"],
                "weight_source": spec["weight_source"],
                "paper_hint": spec["paper_hint"],
                "repo_hint": spec["repo_hint"],
                "policy_profile": policy_name,
                "policy_params": asdict(profile),
                "artifacts": {
                    "benchmark_report": str(BENCH_REPORT.relative_to(ROOT)).replace("\\", "/"),
                    "ten_case_report": str(ten_case_file.relative_to(ROOT)).replace("\\", "/"),
                    "trial_log_dir": str(trial_dir.relative_to(ROOT)).replace("\\", "/"),
                },
                "metrics": {
                    "recall": recall,
                    "specificity": specificity,
                    "precision": precision,
                    "f1": f1,
                    "benchmark_accuracy": bench_acc,
                    "ten_case_accuracy": ten_acc,
                    "score": score,
                },
            }
            successes.append(row)
            (trial_dir / "trial_result.json").write_text(json.dumps(row, indent=2), encoding="utf-8")

            print(
                f"  score={score:.4f} rec={recall:.4f} spec={specificity:.4f} "
                f"prec={precision:.4f} ten={ten_acc:.4f}"
            )
        except Exception as exc:
            failures.append({"experiment_id": exp_id, "error": str(exc)})
            print(f"  trial failed: {exc}")

    leaderboard = sorted(successes, key=lambda x: x["metrics"]["score"], reverse=True)
    run_report = {
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "registry_path": str(args.registry),
        "summary": {
            "trials_requested": len(selected),
            "trials_succeeded": len(successes),
            "trials_failed": len(failures),
        },
        "leaderboard": leaderboard,
        "failures": failures,
    }

    run_json = run_dir / "report.json"
    run_md = run_dir / "report.md"
    run_json.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
    run_md.write_text(render_markdown(run_report), encoding="utf-8")

    latest_json = RESULTS_DIR / "experiment_factory_latest.json"
    latest_md = ROOT / "docs" / "experiment_factory_latest.md"
    latest_json.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
    latest_md.write_text(render_markdown(run_report), encoding="utf-8")

    print(f"Run report written: {run_json}")
    print(f"Leaderboard written: {run_md}")
    if leaderboard:
        best = leaderboard[0]
        print(
            "Best trial: "
            f"{best['experiment_id']} score={best['metrics']['score']:.4f} "
            f"(rec={best['metrics']['recall']:.4f}, spec={best['metrics']['specificity']:.4f}, "
            f"ten={best['metrics']['ten_case_accuracy']:.4f})"
        )
    if failures:
        print(f"Failures: {len(failures)} (see {run_json})")


if __name__ == "__main__":
    main()
