# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "pytest"]
# ///
"""Tests for recall_metrics.py."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from recall_metrics import calculate_metrics, parse_frontmatter, scan_journal


@pytest.fixture
def journal_dir(tmp_path):
    """Create a journal directory with entries spanning multiple days."""
    journal = tmp_path / "journal"
    journal.mkdir()

    today = datetime.now().date()
    for i in range(7):
        day = today - timedelta(days=i)
        entry = journal / f"{day}-1.md"
        vividness = 5 + (i % 4)
        lucid = "true" if i == 2 else "false"
        quality = "high" if i < 3 else "medium"
        entry.write_text(
            f"---\ndate: {day}\nsequence: 1\nvividness: {vividness}\n"
            f"lucid: {lucid}\nrecall_quality: {quality}\n"
            f"emotions: [curiosity]\nsymbols: [water]\nseeded: false\n---\n\nDream.\n"
        )

    return journal


@pytest.fixture
def empty_journal(tmp_path):
    journal = tmp_path / "journal"
    journal.mkdir()
    return journal


class TestParseFrontmatter:
    def test_valid(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\ndate: 2026-03-10\nvividness: 7\n---\nContent")
        result = parse_frontmatter(f)
        assert result["vividness"] == 7

    def test_missing(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("No frontmatter")
        assert parse_frontmatter(f) is None


class TestScanJournal:
    def test_scans_all(self, journal_dir):
        entries = scan_journal(journal_dir)
        assert len(entries) == 7

    def test_empty(self, empty_journal):
        entries = scan_journal(empty_journal)
        assert len(entries) == 0

    def test_extracts_vividness(self, journal_dir):
        entries = scan_journal(journal_dir)
        assert all(e["vividness"] is not None for e in entries)


class TestCalculateMetrics:
    def test_basic_metrics(self, journal_dir):
        entries = scan_journal(journal_dir)
        metrics = calculate_metrics(entries)
        assert metrics["total_dreams"] == 7
        assert metrics["dreams_per_week"] > 0
        assert metrics["current_streak"] > 0
        assert metrics["avg_vividness"] > 0

    def test_empty_entries(self):
        metrics = calculate_metrics([])
        assert metrics["total_dreams"] == 0
        assert metrics["dreams_per_week"] == 0
        assert metrics["current_streak"] == 0

    def test_quality_distribution(self, journal_dir):
        entries = scan_journal(journal_dir)
        metrics = calculate_metrics(entries)
        assert "high" in metrics["quality_distribution"]
        assert "medium" in metrics["quality_distribution"]

    def test_lucid_count(self, journal_dir):
        entries = scan_journal(journal_dir)
        metrics = calculate_metrics(entries)
        assert metrics["lucid_count"] == 1

    def test_weekly_counts(self, journal_dir):
        entries = scan_journal(journal_dir)
        metrics = calculate_metrics(entries)
        assert len(metrics["weekly_counts"]) == 8

    def test_vividness_trend_with_data(self, journal_dir):
        entries = scan_journal(journal_dir)
        metrics = calculate_metrics(entries)
        assert metrics["vividness_trend"] in (
            "improving", "declining", "stable", "insufficient_data"
        )

    def test_streak_calculation(self, journal_dir):
        entries = scan_journal(journal_dir)
        metrics = calculate_metrics(entries)
        assert metrics["longest_streak"] >= metrics["current_streak"]
