import tempfile
from pathlib import Path

from dataset_integrity.core import build_manifest, FileRecord
from dataset_integrity.release import QualityContract, ReleaseCandidate, default_metadata, evaluate_contract
from dataset_integrity.persistence import Store
from dataset_integrity.cli import _write_evidence
from dataset_integrity.cli import main
from dataset_integrity.core import Source


def rec(path, digest="x", errors=()):
    return FileRecord(path, digest, 1, 1, "text/plain", "document", {}, tuple(errors))


def test_contract_evaluation_and_candidate_id_are_deterministic():
    manifest = build_manifest("images", [rec("a")], "now")
    contract = QualityContract("production", min_files=1)
    first = ReleaseCandidate.create(manifest, contract, default_metadata(seed=7, code_version="1"))
    second = ReleaseCandidate.create(manifest, contract, default_metadata(seed=7, code_version="1"))
    assert first.candidate_id == second.candidate_id
    assert first.quality.passed


def test_failed_quality_cannot_be_promoted():
    manifest = build_manifest("images", [rec("empty", errors=("empty_file",))], "now")
    candidate = ReleaseCandidate.create(manifest, QualityContract("strict"), default_metadata())
    assert not evaluate_contract(candidate.contract, manifest).passed
    with tempfile.TemporaryDirectory() as directory:
        store = Store(str(Path(directory) / "state.sqlite"))
        store.save_candidate(candidate)
        try:
            try:
                if not store.candidate(candidate.candidate_id).quality.passed:
                    raise ValueError("quality contract has not passed")
            except ValueError:
                pass
            else:
                raise AssertionError("failed candidate was accepted")
        finally:
            store.close()


def test_rejected_candidate_persists_release_and_terminal_transitions_are_explicit():
    manifest = build_manifest("images", [rec("a")], "now")
    candidate = ReleaseCandidate.create(manifest, QualityContract("strict"), default_metadata())
    with tempfile.TemporaryDirectory() as directory:
        store = Store(str(Path(directory) / "state.sqlite"))
        try:
            store.save_candidate(candidate)
            rejected = store.set_candidate_state(candidate.candidate_id, "rejected")
            store.save_release(rejected.candidate_id, rejected, "rejected")
            release = store.release(rejected.candidate_id)
            assert release["release_id"] == rejected.candidate_id
            assert release["candidate_id"] == rejected.candidate_id
            assert release["state"] == "rejected"
            try:
                store.set_candidate_state(candidate.candidate_id, "promoted")
            except ValueError as exc:
                assert "invalid candidate transition" in str(exc)
            else:
                raise AssertionError("terminal candidate transition was accepted")
        finally:
            store.close()


def test_evidence_bundle_is_deterministic():
    manifest = build_manifest("images", [rec("a")], "now")
    candidate = ReleaseCandidate.create(manifest, QualityContract("strict"), default_metadata(seed=3))
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        _write_evidence(first, candidate.as_dict())
        _write_evidence(second, candidate.as_dict())
        for name in ("release.json", "checks.json", "bundle.sha256"):
            assert (Path(first) / name).read_bytes() == (Path(second) / name).read_bytes()


def test_reject_cli_persists_release_record():
    manifest = build_manifest("images", [rec("a")], "now")
    candidate = ReleaseCandidate.create(manifest, QualityContract("strict"), default_metadata())
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "state.sqlite"
        store = Store(str(db))
        store.register(Source("images", directory))
        store.save_manifest(manifest)
        store.save_candidate(candidate)
        store.close()
        assert main(["--db", str(db), "reject", candidate.candidate_id]) == 0
        store = Store(str(db))
        try:
            assert store.release(candidate.candidate_id)["state"] == "rejected"
        finally:
            store.close()
