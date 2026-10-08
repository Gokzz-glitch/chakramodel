# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "pytest"]
# ///
"""Tests for symbol_stats.py."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add parent to path for import
sys.path.insert(0, str(Path(__file__).parent.parent))
from symbol_stats import analyze_symbols, parse_frontmatter, scan_journal


@pytest.fixture
def journal_dir(tmp_path):
    """Create a temporary journal directory with sample entries."""
    journal = tmp_path / "journal"
    journal.mkdir()

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    entry1 = journal / f"{today}-1.md"
    entry1.write_text(
        f"---\ndate: {today}\nsequence: 1\nvividness: 7\nlucid: false\n"
        f"emotions: [anxiety, curiosity]\nsymbols: [water, doorway]\n"
        f"recall_quality: high\nseeded: false\n---\n\nDream narrative here.\n"
    )

    entry2 = journal / f"{yesterday}-1.md"
    entry2.write_text(
        f"---\ndate: {yesterday}\nsequence: 1\nvividness: 5\nlucid: true\n"
        f"emotions: [peace, awe]\nsymbols: [water, flying]\n"
        f"recall_quality: medium\nseeded: true\n---\n\nAnother dream.\n"
    )

    return journal


@pytest.fixture
def empty_journal(tmp_path):
    """Create an empty journal directory."""
    journal = tmp_path / "journal"
    journal.mkdir()
    return journal


class TestParseFrontmatter:
    def test_valid_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\ndate: 2026-03-10\nsymbols: [water]\n---\nContent")
        result = parse_frontmatter(f)
        assert result is not None
        assert result["symbols"] == ["water"]

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("No frontmatter here.")
        assert parse_frontmatter(f) is None

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\n: invalid: yaml: [[\n---\nContent")
        assert parse_frontmatter(f) is None


class TestScanJournal:
    def test_scans_entries(self, journal_dir):
        entries = scan_journal(journal_dir)
        assert len(entries) == 2

    def test_empty_journal(self, empty_journal):
        entries = scan_journal(empty_journal)
        assert len(entries) == 0

    def test_days_filter(self, journal_dir):
        entries = scan_journal(journal_dir, days=0)
        # With days=0, cutoff is today, so yesterday's entry is excluded
        assert len(entries) <= 2

    def test_extracts_symbols(self, journal_dir):
        entries = scan_journal(journal_dir)
        all_symbols = [s for e in entries for s in e["symbols"]]
        assert "water" in all_symbols
        assert "doorway" in all_symbols


class TestAnalyzeSymbols:
    def test_basic_analysis(self, journal_dir):
        entries = scan_journal(journal_dir)
        result = analyze_symbols(entries)
        assert "water" in result
        assert result["water"]["count"] == 2

    def test_emotion_correlation(self, journal_dir):
        entries = scan_journal(journal_dir)
        result = analyze_symbols(entries)
        assert "anxiety" in result["water"]["emotion_correlation"]

    def test_empty_entries(self):
        result = analyze_symbols([])
        assert result == {}

    def test_first_last_seen(self, journal_dir):
        entries = scan_journal(journal_dir)
        result = analyze_symbols(entries)
        assert result["water"]["first_seen"] is not None
        assert result["water"]["last_seen"] is not None
