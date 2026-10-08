#!/usr/bin/env python3
"""Harvest external ECG R&D intelligence into machine-readable local reports.

This script pulls a curated set of:
- Public datasets relevant to arrhythmia detection
- Research papers with transfer-learning or benchmark guidance
- Open-source repositories likely to provide implementation ideas
- Candidate pretrained-weight sources to evaluate

Outputs:
- test_results/research_intel_report.json
- docs/research_intel_report.md
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JSON_OUT = PROJECT_ROOT / "test_results" / "research_intel_report.json"
MD_OUT = PROJECT_ROOT / "docs" / "research_intel_report.md"


@dataclass
class SourceItem:
    kind: str
    name: str
    url: str
    why_it_matters: str


CURATED_ITEMS: list[SourceItem] = [
    SourceItem(
        kind="dataset",
        name="MIT-BIH Arrhythmia Database",
        url="https://physionet.org/content/mitdb/1.0.0/",
        why_it_matters="Gold-standard beat annotations for binary arrhythmia detection benchmarking.",
    ),
    SourceItem(
        kind="dataset",
        name="MIT-BIH Noise Stress Test Database",
        url="https://physionet.org/content/nstdb/1.0.0/",
        why_it_matters="Directly supports robustness testing under ambulatory noise.",
    ),
    SourceItem(
        kind="dataset",
        name="PTB-XL",
        url="https://physionet.org/content/ptb-xl/1.0.3/",
        why_it_matters="Large-scale ECG dataset with recommended train/val/test folds and rich metadata.",
    ),
    SourceItem(
        kind="dataset",
        name="INCART 12-lead Arrhythmia Database",
        url="https://physionet.org/content/incartdb/1.0.0/",
        why_it_matters="External-domain arrhythmia data for generalization checks.",
    ),
    SourceItem(
        kind="paper",
        name="Deep Learning for ECG Analysis: Benchmarks and Insights from PTB-XL",
        url="https://arxiv.org/abs/2004.13701",
        why_it_matters="Benchmarking blueprint and transfer-learning guidance for ECG models.",
    ),
    SourceItem(
        kind="paper",
        name="ECG Heartbeat Classification: A Deep Transferable Representation",
        url="https://arxiv.org/abs/1805.00794",
        why_it_matters="Transfer-learning strategy across arrhythmia and related ECG tasks.",
    ),
    SourceItem(
        kind="repo",
        name="resnet1d",
        url="https://github.com/hsd1503/resnet1d",
        why_it_matters="Strong 1D backbone family for signal tasks; useful for model refresh experiments.",
    ),
    SourceItem(
        kind="repo",
        name="automatic-ecg-diagnosis",
        url="https://github.com/antonior92/automatic-ecg-diagnosis",
        why_it_matters="Well-known ECG classification training pipeline with publication lineage.",
    ),
    SourceItem(
        kind="repo",
        name="py-ecg-detectors",
        url="https://github.com/berndporr/py-ecg-detectors",
        why_it_matters="Reference QRS detector implementations to harden preprocessing and HR estimates.",
    ),
    SourceItem(
        kind="pretrained_candidate",
        name="PTB-XL benchmark checkpoints ecosystem",
        url="https://arxiv.org/abs/2004.13701",
        why_it_matters="Candidate source for initialization and transfer to single-lead edge model.",
    ),
]


def _extract_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return title[:160]


def fetch_item(item: SourceItem, timeout: float = 10.0) -> dict[str, Any]:
    headers = {"User-Agent": "PulseAI-Research-Harvester/1.0"}
    row = asdict(item)
    try:
        r = requests.get(item.url, headers=headers, timeout=timeout)
        row["status_code"] = r.status_code
        row["reachable"] = r.status_code == 200
        row["page_title"] = _extract_title(r.text)
        row["content_size_bytes"] = len(r.text.encode("utf-8", errors="ignore"))
    except Exception as exc:
        row["status_code"] = None
        row["reachable"] = False
        row["page_title"] = ""
        row["content_size_bytes"] = 0
        row["error"] = str(exc)
    return row


def to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# PulseAI Research Intelligence Report")
    lines.append("")
    lines.append(f"Generated at: {report['generated_at_utc']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total sources scanned: {report['summary']['total_sources']}")
    lines.append(f"- Reachable sources: {report['summary']['reachable_sources']}")
    lines.append(f"- Datasets: {report['summary']['datasets']}")
    lines.append(f"- Papers: {report['summary']['papers']}")
    lines.append(f"- Repositories: {report['summary']['repos']}")
    lines.append(f"- Pretrained candidates: {report['summary']['pretrained_candidates']}")
    lines.append("")
    lines.append("## Source Details")
    lines.append("")
    for row in report["sources"]:
        status = "OK" if row.get("reachable") else "FAILED"
        lines.append(f"### {row['name']} ({row['kind']})")
        lines.append("")
        lines.append(f"- URL: {row['url']}")
        lines.append(f"- Status: {status} ({row.get('status_code')})")
        lines.append(f"- Title: {row.get('page_title', '')}")
        lines.append(f"- Why it matters: {row['why_it_matters']}")
        lines.append("")

    lines.append("## Execution Recommendations")
    lines.append("")
    for rec in report["recommendations"]:
        lines.append(f"- {rec}")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    rows = [fetch_item(item) for item in CURATED_ITEMS]

    summary = {
        "total_sources": len(rows),
        "reachable_sources": sum(1 for r in rows if r.get("reachable")),
        "datasets": sum(1 for r in rows if r.get("kind") == "dataset"),
        "papers": sum(1 for r in rows if r.get("kind") == "paper"),
        "repos": sum(1 for r in rows if r.get("kind") == "repo"),
        "pretrained_candidates": sum(1 for r in rows if r.get("kind") == "pretrained_candidate"),
    }

    recommendations = [
        "Prioritize PTB-XL transfer pretraining, then fine-tune on MIT-BIH rhythm targets.",
        "Add noise-stress evaluation (NSTDB) to quantify robustness before deployment.",
        "Benchmark at least one ResNet1D baseline against the current HCTG-Net model.",
        "Gate deployment by constrained metrics (specificity floor + recall floor), not accuracy alone.",
    ]

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "sources": rows,
        "recommendations": recommendations,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    MD_OUT.write_text(to_markdown(report), encoding="utf-8")

    print(f"Research JSON report written: {JSON_OUT}")
    print(f"Research markdown report written: {MD_OUT}")


if __name__ == "__main__":
    main()
