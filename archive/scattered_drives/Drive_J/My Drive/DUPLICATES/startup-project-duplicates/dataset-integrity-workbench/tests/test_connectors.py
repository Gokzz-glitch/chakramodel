import json
import zipfile

from dataset_integrity.connectors import ArchiveConnector, FilesystemConnector, HTTPSConnector
from dataset_integrity.core import Source
from dataset_integrity.persistence import Store


def test_filesystem_is_single_target_mutable_metadata(tmp_path):
    target = tmp_path / "one.txt"
    target.write_text("fixture")
    result = FilesystemConnector().inspect(str(target))
    assert result.source_status == "mutable"
    assert result.read_only and result.metadata["target_explicit"]


def test_archive_is_snapshot_without_extraction(tmp_path):
    target = tmp_path / "fixture.zip"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("one.txt", "fixture")
    result = ArchiveConnector().inspect(str(target))
    assert result.source_status == "snapshot"
    assert result.metadata["member_count"] == 1
    assert result.metadata["extraction"] is False


def test_https_requires_opt_in_and_records_resume_boundary():
    result = HTTPSConnector().inspect("https://example.invalid/dataset")
    assert result.network_accessed is False
    assert result.download.resumable is True


def test_connector_observation_is_in_lineage_and_secrets_redacted(tmp_path):
    db = tmp_path / "store.sqlite"
    target = tmp_path / "one.txt"
    target.write_text("fixture")
    store = Store(str(db))
    store.register(Source("fixture", str(target), metadata={
        "credential_profile": "private-profile",
        "license_terms": {"reference": "fixture-license"},
    }))
    result = FilesystemConnector().inspect(str(target))
    from dataclasses import replace
    result = replace(result, credential_profile="private-profile",
                     license_terms={"reference": "fixture-license"})
    store.record_connector_metadata("fixture", result)
    events = store.replay_lineage()
    assert any(event["event_type"] == "source.connector_inspected" for event in events)
    assert "secret" not in json.dumps(store.lineage_for("fixture")).lower()
    store.close()
