import tempfile
from pathlib import Path
from dataset_integrity.core import build_manifest, compare_manifests, duplicate_groups, inspect_file, validate_record

def test_manifest_is_deterministic_and_duplicates_group():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); (root/"a.txt").write_text("same"); (root/"b.txt").write_text("same")
        records = [inspect_file(root/"b.txt", root), inspect_file(root/"a.txt", root)]
        first = build_manifest("x", records, "2020")
        second = build_manifest("x", reversed(records), "2020")
        assert first.manifest_sha256 == second.manifest_sha256
        assert duplicate_groups(records) == [["a.txt", "b.txt"]]

def test_png_dimensions_without_dependency():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)/"x.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00"*8 + (2).to_bytes(4,"big") + (3).to_bytes(4,"big"))
        record = inspect_file(p, d)
        assert record.metadata["width"] == 2 and record.metadata["height"] == 3


def test_validation_reports_empty_and_invalid_images():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        empty = root / "empty.txt"
        empty.write_bytes(b"")
        bad_image = root / "bad.png"
        bad_image.write_bytes(b"not a png")
        assert validate_record(inspect_file(empty, root)) == "FAIL"
        assert "empty_file" in inspect_file(empty, root).errors
        assert "invalid_or_unsupported_image" in inspect_file(bad_image, root).errors


def test_comparison_reports_added_removed_changed_and_unchanged():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "same.txt").write_text("same")
        (root / "changed.txt").write_text("old")
        prior = build_manifest("x", [inspect_file(root / "same.txt", root), inspect_file(root / "changed.txt", root)], "1")
        (root / "changed.txt").write_text("new")
        (root / "added.txt").write_text("added")
        current = build_manifest("x", [inspect_file(root / "same.txt", root), inspect_file(root / "changed.txt", root), inspect_file(root / "added.txt", root)], "2")
        result = compare_manifests(current, prior)
        assert result["added"] == ["added.txt"]
        assert result["changed"] == ["changed.txt"]
        assert result["unchanged"] == 1
        assert result["status"] == "FAIL"
