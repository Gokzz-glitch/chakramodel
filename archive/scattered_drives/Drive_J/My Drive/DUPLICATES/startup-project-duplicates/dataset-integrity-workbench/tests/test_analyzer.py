import json
from pathlib import Path

from dataset_integrity.analyzer import export_report, scan_filesystem
from dataset_integrity.datasets import discover_dataset
from dataset_integrity.integrations import OptionalDependencyError, capability


def test_scan_resume_reuses_hash_and_reports_changes(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_text("same")
    db = tmp_path / "state.sqlite"
    first = scan_filesystem(str(root), str(db), run_id="run-1")
    assert first.complete and first.records[0].sha256
    resumed = scan_filesystem(str(root), str(db), run_id="run-2")
    assert resumed.complete
    assert any(item["kind"] == "hash_reused" for item in resumed.changes)
    (root / "a.txt").write_text("changed")
    changed = scan_filesystem(str(root), str(db), run_id="run-3")
    assert any(item["kind"] == "changed" for item in changed.changes)


def test_scan_duplicates_and_exports(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_text("same")
    (root / "b.txt").write_text("same")
    result = scan_filesystem(str(root), str(tmp_path / "state.sqlite")).as_dict()
    assert result["duplicates"] == [["a.txt", "b.txt"]]
    for fmt in ("json", "csv", "text"):
        output = tmp_path / ("report." + fmt)
        export_report(result, str(output), fmt)
        assert output.exists() and output.read_text(encoding="utf-8")


def test_dataset_discovery_reports_missing_pairs_and_malformed_yolo(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "labels").mkdir()
    (tmp_path / "images" / "one.jpg").write_bytes(b"not decoded here")
    (tmp_path / "labels" / "one.txt").write_text("bad line")
    report = discover_dataset(str(tmp_path))
    assert "yolo" in report["layouts"]
    assert report["yolo"]["malformed_annotations"]
    assert report["yolo"]["missing_labels"] == []


def test_dataset_discovery_reports_missing_label_pair(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "labels").mkdir()
    (tmp_path / "images" / "missing.jpg").write_bytes(b"image")
    report = discover_dataset(str(tmp_path))
    assert "yolo" in report["layouts"]
    assert report["yolo"]["missing_labels"] == ["missing"]


def test_optional_capability_is_explicit():
    info = capability("not-installed-name") if False else capability("datumaro")
    assert "available" in info
