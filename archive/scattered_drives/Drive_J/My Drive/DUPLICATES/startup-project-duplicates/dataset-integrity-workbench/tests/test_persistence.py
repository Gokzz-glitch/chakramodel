import tempfile
from pathlib import Path

from dataset_integrity.core import FileRecord, Source, build_manifest
from dataset_integrity.persistence import Store


def record(path="a.txt", digest="a"):
    return FileRecord(path, digest, 1, 1, "text/plain", "document", {"extension": ".txt"})


def test_sqlite_source_run_and_manifest_round_trip():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "state.sqlite"
        store = Store(str(db))
        store.register(Source("demo", d, metadata={"owner": "test"}))
        assert store.source("demo").metadata["owner"] == "test"
        store.start_run("run-1", "demo", "1")
        store.save_record("run-1", record())
        assert store.run_records("run-1")[0].sha256 == "a"
        manifest = build_manifest("demo", store.run_records("run-1"), "2", run_id="run-1")
        store.save_manifest(manifest)
        assert store.latest_manifest("demo").manifest_sha256 == manifest.manifest_sha256
        store.close()


def test_incomplete_run_can_resume_idempotently():
    with tempfile.TemporaryDirectory() as d:
        store = Store(str(Path(d) / "state.sqlite"))
        store.start_run("run-1", "demo", "1")
        store.save_record("run-1", record("a.txt"))
        store.finish_run("run-1", "2", "incomplete")
        store.start_run("run-1", "demo", "3")  # INSERT OR IGNORE preserves existing run
        store.save_record("run-1", record("b.txt", "b"))
        records = store.run_records("run-1")
        assert [item.path for item in records] == ["a.txt", "b.txt"]
        assert len(records) == 2
        store.finish_run("run-1", "4", "complete")
        store.close()


def test_incomplete_manifest_is_explicit_and_warns_on_comparison():
    incomplete = build_manifest("demo", [record()], "1", complete=False, run_id="run-2")
    complete = build_manifest("demo", [record()], "2", complete=True, run_id="run-3")
    from dataset_integrity.core import compare_manifests
    assert incomplete.complete is False
    assert compare_manifests(incomplete, complete)["status"] == "WARN"
