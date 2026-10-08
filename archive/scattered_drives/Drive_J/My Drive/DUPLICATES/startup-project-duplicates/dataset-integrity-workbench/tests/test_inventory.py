import json
from pathlib import Path

from dataset_integrity.inventory import inventory_roots
from dataset_integrity.image_validation import capability


def test_inventory_is_deterministic_and_summarizes_annotations(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.txt").write_text("same")
    (tmp_path / "annotations").mkdir()
    (tmp_path / "annotations" / "a.json").write_text("{}")
    first = inventory_roots([str(tmp_path)])
    second = inventory_roots([str(tmp_path)])
    assert first["manifest"] == second["manifest"]
    assert first["summary"]["annotations"] == 1
    assert first["summary"]["files"] == 2


def test_inventory_missing_root_is_incomplete_and_has_no_manifest(tmp_path):
    result = inventory_roots([str(tmp_path / "missing")])
    assert result["complete"] is False
    assert result["manifest"] is None
    assert result["errors"][0]["error"] == "missing_root"


def test_inventory_exclusions_are_opt_in_and_do_not_affect_validation(tmp_path):
    (tmp_path / "kept.txt").write_text("same")
    excluded = tmp_path / ".venv"
    excluded.mkdir()
    (excluded / "empty.txt").write_text("")
    (excluded / "bad.png").write_bytes(b"not an image")
    (excluded / "nested").mkdir()
    (excluded / "nested" / "duplicate.txt").write_text("same")

    default = inventory_roots([str(tmp_path)])
    filtered = inventory_roots([str(tmp_path)], exclude_dirs=[".venv"])

    assert default["summary"]["files"] == 4
    assert default["summary"]["excluded_files"] == 0
    assert filtered["summary"]["files"] == 1
    assert filtered["summary"]["excluded_files"] == 3
    assert filtered["summary"]["excluded_directories"] == 2
    assert filtered["summary"]["errors"] == 0
    assert filtered["summary"]["duplicate_groups"] == 0
    assert filtered["summary"]["modalities"] == {"document": 1}
    assert all(".venv" not in record["path"] for record in filtered["records"])


def test_common_exclusions_are_deterministic(tmp_path):
    (tmp_path / "kept.txt").write_text("kept")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "artifact.txt").write_text("artifact")

    first = inventory_roots([str(tmp_path)], exclude_dirs=["build", ".git"])
    second = inventory_roots([str(tmp_path)], exclude_dirs=[".git", "build"])

    assert first["manifest"] == second["manifest"]
    assert first["summary"]["excluded_files"] == 1
    assert first["summary"]["root_breakdown"][0]["excluded_directories"] == 1


def test_optional_pillow_validator_reports_decode_status_without_claiming_success(tmp_path):
    image = tmp_path / "sample.png"
    image.write_bytes(b"not a png")
    result = inventory_roots([str(tmp_path)], image_validator="pillow")
    assert result["image_validator"]["validator"] == "pillow"
    record = result["records"][0]
    validation = record["metadata"]["image_validation"]
    if capability()["available"]:
        assert validation["status"] == "decode_error"
        assert "image_decode_error" in record["errors"]
    else:
        assert validation["status"] == "unavailable"
