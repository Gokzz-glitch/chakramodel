#!/usr/bin/env python3
"""Generate SDG impact coverage report for PulseAI.

This script maps current project artifacts and metrics to UN SDGs,
then emits machine-readable and markdown reports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_RESULTS = PROJECT_ROOT / "test_results"
DOCS = PROJECT_ROOT / "docs"

GLOBAL_BENCH = TEST_RESULTS / "global_benchmark_report.json"
POLICY_TUNE = TEST_RESULTS / "policy_tuning_report.json"
RESEARCH_INTEL = TEST_RESULTS / "research_intel_report.json"
SAFETY_STANDARD = DOCS / "safety_operating_standard.md"
EXEC_PLAN = DOCS / "clinical_grade_execution_plan.md"

OUT_JSON = TEST_RESULTS / "sdg_impact_report.json"
OUT_MD = DOCS / "sdg_impact_report.md"


@dataclass
class SDGItem:
    id: str
    title: str
    rationale: str
    evidence: list[str]
    status: str
    score: int
    gaps: list[str]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def exists_str(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.exists() else "missing"


def build_report() -> dict[str, Any]:
    bench = load_json(GLOBAL_BENCH)
    tune = load_json(POLICY_TUNE)

    metrics = (((bench.get("local_mitbih_evaluation") or {}).get("binary_metrics_vs_annotations") or {}))
    specificity = float(metrics.get("specificity", 0.0) or 0.0)
    recall = float(metrics.get("recall", 0.0) or 0.0)
    precision = float(metrics.get("precision", 0.0) or 0.0)

    has_safety = SAFETY_STANDARD.exists() and EXEC_PLAN.exists()
    has_research = RESEARCH_INTEL.exists()
    has_tuning = POLICY_TUNE.exists()

    sdgs: list[SDGItem] = [
        SDGItem(
            id="SDG-3",
            title="Good Health and Well-Being",
            rationale="Core objective is safer arrhythmia triage and early risk detection.",
            evidence=[exists_str(GLOBAL_BENCH), exists_str(SAFETY_STANDARD)],
            status="in-progress" if specificity < 0.70 else "strong",
            score=45 if specificity < 0.30 else 65,
            gaps=[
                "Specificity remains below clinical-grade threshold.",
                "Need prospective validation on diverse real-world cohorts.",
            ],
        ),
        SDGItem(
            id="SDG-9",
            title="Industry, Innovation and Infrastructure",
            rationale="Digital health infrastructure using streaming, edge inference, and interoperable outputs.",
            evidence=[exists_str(EXEC_PLAN), exists_str(RESEARCH_INTEL)],
            status="strong" if has_research else "in-progress",
            score=72 if has_research else 58,
            gaps=["Need full DICOM waveform export implementation for hospital systems."],
        ),
        SDGItem(
            id="SDG-10",
            title="Reduced Inequalities",
            rationale="Potentially expands screening access via low-cost sensing pathways.",
            evidence=[exists_str(EXEC_PLAN)],
            status="in-progress",
            score=55,
            gaps=["Need explicit bias/fairness audits across age/sex/comorbidity cohorts."],
        ),
        SDGItem(
            id="SDG-12",
            title="Responsible Consumption and Production",
            rationale="Safety gates and strict deployment checks reduce unsafe releases.",
            evidence=[exists_str(SAFETY_STANDARD), exists_str(POLICY_TUNE)],
            status="in-progress" if has_tuning else "planned",
            score=68 if has_tuning else 45,
            gaps=["Need mandatory CI release blocking on safety and benchmark thresholds."],
        ),
        SDGItem(
            id="SDG-16",
            title="Peace, Justice and Strong Institutions",
            rationale="Medical trust requires privacy, security, and accountable decision support.",
            evidence=[exists_str(SAFETY_STANDARD), exists_str(EXEC_PLAN)],
            status="in-progress" if has_safety else "planned",
            score=62 if has_safety else 40,
            gaps=[
                "Need formal audit logging and immutable access trails.",
                "Need external compliance assessment process.",
            ],
        ),
        SDGItem(
            id="SDG-17",
            title="Partnerships for the Goals",
            rationale="Open datasets and research integration accelerate responsible clinical innovation.",
            evidence=[exists_str(RESEARCH_INTEL)],
            status="strong" if has_research else "planned",
            score=75 if has_research else 50,
            gaps=["Need active clinical/hospital partner validation programs."],
        ),
    ]

    overall = round(sum(item.score for item in sdgs) / max(1, len(sdgs)), 1)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_metrics": {
            "specificity": specificity,
            "recall": recall,
            "precision": precision,
            "has_safety_docs": has_safety,
            "has_research_intel": has_research,
            "has_policy_tuning": has_tuning,
        },
        "overall_sdg_alignment_score": overall,
        "sdg_coverage": [item.__dict__ for item in sdgs],
        "priority_actions": [
            "Raise specificity to clinically acceptable threshold before deployment claims.",
            "Add fairness and subgroup performance reporting into benchmark pipeline.",
            "Add CI gate to block release when safety benchmark floors are unmet.",
            "Establish pilot clinical partnerships for prospective validation.",
        ],
    }


def to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# PulseAI SDG Impact Report")
    lines.append("")
    lines.append(f"Generated at: {report['generated_at_utc']}")
    lines.append("")
    lines.append(f"Overall SDG Alignment Score: {report['overall_sdg_alignment_score']}/100")
    lines.append("")
    lines.append("## SDG Coverage")
    lines.append("")

    for row in report["sdg_coverage"]:
        lines.append(f"### {row['id']} - {row['title']}")
        lines.append(f"- Status: {row['status']}")
        lines.append(f"- Score: {row['score']}/100")
        lines.append(f"- Rationale: {row['rationale']}")
        lines.append(f"- Evidence: {', '.join(row['evidence'])}")
        for gap in row["gaps"]:
            lines.append(f"- Gap: {gap}")
        lines.append("")

    lines.append("## Priority Actions")
    lines.append("")
    for action in report["priority_actions"]:
        lines.append(f"- {action}")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    report = build_report()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(to_markdown(report), encoding="utf-8")

    print(f"SDG JSON report written: {OUT_JSON}")
    print(f"SDG markdown report written: {OUT_MD}")


if __name__ == "__main__":
    main()
