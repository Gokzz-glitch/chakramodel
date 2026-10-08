# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "pytest"]
# ///
"""Tests for seed_tracker.py."""

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from seed_tracker import analyze_seeds, load_seed_log


@pytest.fixture
def seed_log(tmp_path):
    """Create a seed-log.yaml with mixed results."""
    log = tmp_path / "seed-log.yaml"
    data = {
        "seeds": [
            {
                "date": "2026-03-01",
                "intention": "Dream about the ocean",
                "technique": "visualization",
                "result": "full",
                "dream_ref": "2026-03-02-1",
                "notes": "Dreamed of swimming in deep water",
            },
            {
                "date": "2026-03-03",
                "intention": "Meet my grandmother",
                "technique": "mantra",
                "result": "none",
                "dream_ref": None,
                "notes": None,
            },
            {
                "date": "2026-03-05",
                "intention": "Fly over mountains",
                "technique": "visualization",
                "result": "partial",
                "dream_ref": "2026-03-06-1",
                "notes": "Floated but didn't fly",
            },
            {
                "date": "2026-03-08",
                "intention": "Open the locked door",
                "technique": "symbol-return",
                "result": "pending",
                "dream_ref": None,
                "notes": None,
            },
            {
                "date": "2026-03-10",
                "intention": "Explore underwater",
                "technique": "question",
                "result": "full",
                "dream_ref": "2026-03-11-1",
                "notes": "Breathed underwater",
            },
        ],
        "success_rate": 0.5,
    }
    log.write_text(yaml.dump(data))
    return log


@pytest.fixture
def empty_seed_log(tmp_path):
    log = tmp_path / "seed-log.yaml"
    log.write_text(yaml.dump({"seeds": []}))
    return log


class TestLoadSeedLog:
    def test_loads_seeds(self, seed_log):
        seeds = load_seed_log(seed_log)
        assert len(seeds) == 5

    def test_empty_log(self, empty_seed_log):
        seeds = load_seed_log(empty_seed_log)
        assert len(seeds) == 0

    def test_missing_file(self, tmp_path):
        seeds = load_seed_log(tmp_path / "nonexistent.yaml")
        assert len(seeds) == 0

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(": [invalid yaml {{")
        seeds = load_seed_log(f)
        assert len(seeds) == 0


class TestAnalyzeSeeds:
    def test_basic_analysis(self, seed_log):
        seeds = load_seed_log(seed_log)
        result = analyze_seeds(seeds)
        assert result["total_seeds"] == 5
        assert result["pending"] == 1
        assert result["resolved"] == 4

    def test_success_rate(self, seed_log):
        seeds = load_seed_log(seed_log)
        result = analyze_seeds(seeds)
        # 3 successes (full + partial) out of 4 resolved = 0.75
        assert result["success_rate"] == 0.75

    def test_technique_stats(self, seed_log):
        seeds = load_seed_log(seed_log)
        result = analyze_seeds(seeds)
        assert "visualization" in result["technique_stats"]
        assert result["technique_stats"]["visualization"]["total"] == 2

    def test_best_technique(self, seed_log):
        seeds = load_seed_log(seed_log)
        result = analyze_seeds(seeds)
        assert result["best_technique"] is not None

    def test_empty_seeds(self):
        result = analyze_seeds([])
        assert result["total_seeds"] == 0
        assert result["success_rate"] == 0

    def test_result_distribution(self, seed_log):
        seeds = load_seed_log(seed_log)
        result = analyze_seeds(seeds)
        dist = result["result_distribution"]
        assert dist["full"] == 2
        assert dist["partial"] == 1
        assert dist["none"] == 1
        assert dist["pending"] == 1

    def test_recent_trend(self, seed_log):
        seeds = load_seed_log(seed_log)
        result = analyze_seeds(seeds)
        assert 0 <= result["recent_trend_rate"] <= 1
