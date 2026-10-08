#!/usr/bin/env python3
"""Generate a pass/fail audit report aligned with the Master Test Plan PDF.

This script consolidates available project evidence and evaluates key plan thresholds:
- Sensitivity >= 90%
- Specificity >= 90%
- Latency < 100 ms (if data available)
- Sampling rate >= 500 Hz
- Arrhythmia test-suite accuracy >= 90%
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_RESULTS = PROJECT_ROOT / "test_results"
GLOBAL_REPORT = TEST_RESULTS / "global_benchmark_report.json"
LATENCY_REPORT = TEST_RESULTS / "latency_benchmark_report.json"
AUDIT_JSON = TEST_RESULTS / "master_test_plan_audit.json"
AUDIT_MD = PROJECT_ROOT / "docs" / "master_test_plan_audit.md"


@dataclass
class Criterion:
    id: str
    name: str
    target: str
    status: str
    measured: str
    evidence: str
    remediation: str


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_latest_10case_json() -> Path | None:
    if not TEST_RESULTS.exists():
        return None
    files = sorted(TEST_RESULTS.glob("test_10cases_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _pct(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.1f}%"


def _parse_sampling_from_signal_processing() -> int | None:
    f = PROJECT_ROOT / "backend" / "signal_processing.py"
    if not f.exists():
        return None
    txt = f.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^FS\s*=\s*(\d+)", txt, flags=re.MULTILINE)
    if not m:
        return None
    return int(m.group(1))


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _build_criteria(
    global_report: dict[str, Any] | None,
    case10_report: dict[str, Any] | None,
    case10_path: Path | None,
    latency_report: dict[str, Any] | None,
) -> list[Criterion]:
    metrics = None
    if global_report:
        metrics = (((global_report.get("local_mitbih_evaluation") or {}).get("binary_metrics_vs_annotations")) or {})

    sensitivity = _to_float(metrics.get("recall")) if metrics else None
    specificity = _to_float(metrics.get("specificity")) if metrics else None

    arr_acc = None
    if case10_report and case10_report.get("accuracy") is not None:
        arr_acc = _to_float(case10_report.get("accuracy"))

    fs = _parse_sampling_from_signal_processing()
    lat_p95 = None
    lat_status = "N/A"
    lat_measured = "N/A"
    lat_evidence = "No latency artifact available in current reports"
    if latency_report:
        lat = (latency_report.get("latency_ms") or {}) if isinstance(latency_report, dict) else {}
        lat_p95 = _to_float(lat.get("p95")) if isinstance(lat, dict) else None
        if lat_p95 is not None:
            lat_status = "PASS" if lat_p95 < 100.0 else "FAIL"
            lat_measured = f"p95={lat_p95:.2f} ms"
            lat_evidence = str(LATENCY_REPORT.relative_to(PROJECT_ROOT))

    criteria: list[Criterion] = []

    criteria.append(
        Criterion(
            id="C1",
            name="Arrhythmia Sensitivity",
            target=">= 90%",
            status="PASS" if (sensitivity is not None and sensitivity >= 0.90) else "FAIL",
            measured=_pct(sensitivity),
            evidence=str(GLOBAL_REPORT.relative_to(PROJECT_ROOT)) if global_report else "missing report",
            remediation="Retrain on harder positives and tune operating threshold with false-negative penalty.",
        )
    )

    criteria.append(
        Criterion(
            id="C2",
            name="Arrhythmia Specificity",
            target=">= 90%",
            status="PASS" if (specificity is not None and specificity >= 0.90) else "FAIL",
            measured=_pct(specificity),
            evidence=str(GLOBAL_REPORT.relative_to(PROJECT_ROOT)) if global_report else "missing report",
            remediation="Add stronger non-arrhythmia hard negatives and post-filter to suppress noise-induced positives.",
        )
    )

    criteria.append(
        Criterion(
            id="C3",
            name="10-Case Real-Time Accuracy",
            target=">= 90%",
            status="PASS" if (arr_acc is not None and arr_acc >= 0.90) else "FAIL",
            measured=_pct(arr_acc),
            evidence=str(case10_path.relative_to(PROJECT_ROOT)) if case10_path else "missing report",
            remediation="Increase PVC/other-arrhythmia representation and retain safety-floor escalation for severe rhythms.",
        )
    )

    criteria.append(
        Criterion(
            id="C4",
            name="Sampling Frequency",
            target=">= 500 Hz",
            status="PASS" if (fs is not None and fs >= 500) else "FAIL",
            measured=f"{fs} Hz" if fs is not None else "N/A",
            evidence="backend/signal_processing.py",
            remediation="Increase ADC sampling task priority and verify effective sampling under network load.",
        )
    )

    criteria.append(
        Criterion(
            id="C5",
            name="Classification Latency",
            target="< 100 ms",
            status=lat_status,
            measured=lat_measured,
            evidence=lat_evidence,
            remediation="Instrument and log per-window inference latency in backend main loop and include p50/p95 metrics.",
        )
    )

    return criteria


def _write_markdown(criteria: list[Criterion], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Master Test Plan Audit",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Pass/Fail Matrix",
        "",
        "| ID | Criterion | Target | Measured | Status | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for c in criteria:
        lines.append(f"| {c.id} | {c.name} | {c.target} | {c.measured} | {c.status} | {c.evidence} |")

    lines.extend([
        "",
        "## Remediation",
        "",
    ])
    for c in criteria:
        if c.status in {"FAIL", "N/A"}:
            lines.append(f"- {c.id} {c.name}: {c.remediation}")

    lines.extend([
        "",
        "## Notes",
        "",
        "- Thresholds are sourced from the Master Test Plan PDF.",
        "- Missing metrics are marked N/A until instrumentation is added.",
    ])

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    global_report = _read_json(GLOBAL_REPORT)
    latency_report = _read_json(LATENCY_REPORT)
    case10_path = _find_latest_10case_json()
    case10_report = _read_json(case10_path) if case10_path else None

    criteria = _build_criteria(global_report, case10_report, case10_path, latency_report)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "criteria": [c.__dict__ for c in criteria],
        "sources": {
            "global_report": str(GLOBAL_REPORT.relative_to(PROJECT_ROOT)) if GLOBAL_REPORT.exists() else None,
            "latency_report": str(LATENCY_REPORT.relative_to(PROJECT_ROOT)) if LATENCY_REPORT.exists() else None,
            "latest_10case_report": str(case10_path.relative_to(PROJECT_ROOT)) if case10_path else None,
        },
    }

    AUDIT_JSON.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_markdown(criteria, AUDIT_MD)

    print(f"Audit JSON: {AUDIT_JSON}")
    print(f"Audit Markdown: {AUDIT_MD}")


if __name__ == "__main__":
    main()
