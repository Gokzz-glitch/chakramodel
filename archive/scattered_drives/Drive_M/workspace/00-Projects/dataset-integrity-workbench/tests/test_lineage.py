import json

from dataset_integrity.core import FileRecord, Source, build_manifest
from dataset_integrity.persistence import Store
from dataset_integrity.release import QualityContract, ReleaseCandidate


def test_lineage_is_deterministic_redacted_and_replayable(tmp_path):
    store = Store(str(tmp_path / "lineage.sqlite"))
    store.register(Source("images", str(tmp_path), metadata={"owner": "qa"}))
    store.record_credential_profile("registry", "windows", "https://registry.example")
    store.lineage.event("credential.test", {"token": "do-not-store", "ok": True})
    store.lineage.event("credential.test", {"token": "do-not-store", "ok": True})
    events = store.replay_lineage()
    assert len(events) == 3  # source registration + profile + one deduplicated event
    assert all("do-not-store" not in json.dumps(event) for event in events)
    node_ids = [row["node_id"] for row in store.lineage_for("images")["nodes"]]
    assert node_ids == [row["node_id"] for row in store.lineage_for("images")["nodes"]]
    store.close()


def test_release_lineage_connects_manifest_candidate_release(tmp_path):
    store = Store(str(tmp_path / "lineage.sqlite"))
    store.register(Source("images", str(tmp_path)))
    manifest = build_manifest(
        "images", [FileRecord("a.txt", "a" * 64, 1, 1, "text/plain", "text")],
        "2024-01-01T00:00:00Z", run_id="run-1",
    )
    store.save_manifest(manifest)
    candidate = ReleaseCandidate.create(manifest, QualityContract("production"), {})
    store.save_candidate(candidate)
    candidate = store.set_candidate_state(candidate.candidate_id, "promoted")
    store.save_release(candidate.candidate_id, candidate, "promoted")
    graph = store.lineage_for(candidate.candidate_id)
    kinds = {node["node_type"] for node in graph["nodes"]}
    assert {"source", "manifest", "release_candidate", "release", "approval"} <= kinds
    assert any(event["event_type"] == "release.created" for event in graph["events"])
    store.close()
