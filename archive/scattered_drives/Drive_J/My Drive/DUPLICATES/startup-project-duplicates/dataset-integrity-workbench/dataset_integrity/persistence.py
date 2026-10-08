from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Optional
from .core import FileRecord, Manifest, Source, build_manifest
from .release import QualityContract, QualityResult, Release, ReleaseCandidate
from .lineage import Lineage
from .connectors import ConnectorMetadata

class Store:
    def __init__(self, path: str = "dataset-integrity.sqlite"):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""CREATE TABLE IF NOT EXISTS sources(name TEXT PRIMARY KEY, root TEXT NOT NULL, source_type TEXT, metadata TEXT);
        CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, source TEXT, started_at TEXT, finished_at TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS records(run_id TEXT, path TEXT, payload TEXT, PRIMARY KEY(run_id,path));
        CREATE TABLE IF NOT EXISTS manifests(source TEXT, manifest_sha256 TEXT PRIMARY KEY, payload TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS release_candidates(candidate_id TEXT PRIMARY KEY, source TEXT, manifest_sha256 TEXT, payload TEXT, state TEXT);
        CREATE TABLE IF NOT EXISTS releases(release_id TEXT PRIMARY KEY, candidate_id TEXT, payload TEXT, state TEXT);""")
        self.lineage = Lineage(self.db)
        self.db.commit()

    def register(self, source: Source) -> None:
        self.db.execute("INSERT OR REPLACE INTO sources VALUES(?,?,?,?)", (source.name, source.root, source.source_type, json.dumps(dict(source.metadata), sort_keys=True)))
        source_id = self.lineage.node("source", source.name, {"name": source.name, "source_type": source.source_type,
                                                              "root": source.root, **dict(source.metadata)})
        self.lineage.event("source.registered", {"source_id": source_id, "name": source.name})
        self.db.commit()

    def source(self, name: str) -> Source:
        row = self.db.execute("SELECT * FROM sources WHERE name=?", (name,)).fetchone()
        if not row: raise KeyError(name)
        return Source(row["name"], row["root"], row["source_type"], json.loads(row["metadata"]))

    def start_run(self, run_id: str, source: str, started_at: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO runs VALUES(?,?,?,?,?)", (run_id, source, started_at, None, "incomplete"))
        sid = self.lineage.node("source", source, {"name": source})
        rid = self.lineage.node("run", run_id, {"run_id": run_id, "source": source, "status": "incomplete"})
        self.lineage.connect(sid, rid, "contains", "run.started", {"run_id": run_id, "source": source})
        self.db.commit()

    def save_record(self, run_id: str, record: FileRecord) -> None:
        self.db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)", (run_id, record.path, json.dumps(record.as_dict(), sort_keys=True)))
        self.db.commit()

    def run_records(self, run_id: str) -> list[FileRecord]:
        return [self._record(json.loads(r["payload"])) for r in self.db.execute("SELECT payload FROM records WHERE run_id=? ORDER BY path", (run_id,))]

    @staticmethod
    def _record(d: dict) -> FileRecord:
        return FileRecord(d["path"], d["sha256"], d["size"], d["mtime_ns"], d["mime_type"], d["modality"], d.get("metadata", {}), tuple(d.get("errors", [])))

    def finish_run(self, run_id: str, finished_at: str, status: str) -> None:
        self.db.execute("UPDATE runs SET finished_at=?,status=? WHERE run_id=?", (finished_at, status, run_id)); self.db.commit()
        rid = self.lineage.node("run", run_id, {"run_id": run_id, "status": status, "finished_at": finished_at})
        self.lineage.event("run.finished", {"run_id": run_id, "status": status, "node_id": rid})
        self.db.commit()

    def latest_manifest(self, source: str) -> Optional[Manifest]:
        row = self.db.execute("SELECT payload FROM manifests WHERE source=? ORDER BY created_at DESC LIMIT 1", (source,)).fetchone()
        return self._manifest(json.loads(row["payload"])) if row else None

    def previous_manifest(self, source: str, exclude: Optional[str] = None) -> Optional[Manifest]:
        if exclude:
            row = self.db.execute(
                "SELECT payload FROM manifests WHERE source=? AND manifest_sha256<>? ORDER BY created_at DESC LIMIT 1",
                (source, exclude),
            ).fetchone()
        else:
            row = self.db.execute("SELECT payload FROM manifests WHERE source=? ORDER BY created_at DESC LIMIT 1", (source,)).fetchone()
        return self._manifest(json.loads(row["payload"])) if row else None

    def save_manifest(self, manifest: Manifest) -> None:
        self.db.execute("INSERT OR REPLACE INTO manifests VALUES(?,?,?,?)", (manifest.source, manifest.manifest_sha256, json.dumps(manifest.as_dict(), sort_keys=True), manifest.created_at)); self.db.commit()
        sid = self.lineage.node("source", manifest.source, {"name": manifest.source})
        snap = self.lineage.node("snapshot", manifest.manifest_sha256,
                                 {"manifest_sha256": manifest.manifest_sha256, "source": manifest.source,
                                  "complete": manifest.complete, "run_id": manifest.run_id})
        mid = self.lineage.node("manifest", manifest.manifest_sha256,
                                {"manifest_sha256": manifest.manifest_sha256, "source": manifest.source,
                                 "complete": manifest.complete, "run_id": manifest.run_id})
        self.lineage.edge(sid, snap, "has_snapshot")
        self.lineage.edge(snap, mid, "produced_manifest")
        for record in manifest.records:
            for error in record.errors:
                fid = self.lineage.node("finding", {"manifest": manifest.manifest_sha256,
                                                     "path": record.path, "error": error},
                                        {"manifest_sha256": manifest.manifest_sha256,
                                         "path": record.path, "error": error, "severity": "error"})
                self.lineage.edge(mid, fid, "contains_finding")
        if manifest.run_id:
            self.lineage.edge(self.lineage.node("run", manifest.run_id, {"run_id": manifest.run_id}),
                              mid, "produced")
        self.lineage.event("manifest.saved", {"manifest_id": mid, "snapshot_id": snap,
                                               "complete": manifest.complete})
        self.db.commit()

    def manifest(self, digest: str) -> Manifest:
        row = self.db.execute("SELECT payload FROM manifests WHERE manifest_sha256=?", (digest,)).fetchone()
        if not row: raise KeyError(digest)
        return self._manifest(json.loads(row["payload"]))

    def save_candidate(self, candidate: ReleaseCandidate) -> None:
        self.db.execute("INSERT OR REPLACE INTO release_candidates VALUES(?,?,?,?,?)",
                        (candidate.candidate_id, candidate.source, candidate.manifest_sha256,
                         json.dumps(candidate.as_dict(), sort_keys=True), candidate.state))
        mid = self.lineage.node("manifest", candidate.manifest_sha256,
                                {"manifest_sha256": candidate.manifest_sha256, "source": candidate.source})
        cid = self.lineage.node("release_candidate", candidate.candidate_id,
                                {"candidate_id": candidate.candidate_id, "source": candidate.source,
                                 "manifest_sha256": candidate.manifest_sha256, "state": candidate.state,
                                 "contract": candidate.contract.as_dict()})
        self.lineage.connect(mid, cid, "candidate_for", "candidate.saved",
                             {"candidate_id": candidate.candidate_id, "manifest_sha256": candidate.manifest_sha256})
        self.db.commit()

    def candidate(self, candidate_id: str) -> ReleaseCandidate:
        row = self.db.execute("SELECT payload FROM release_candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
        if not row:
            raise KeyError(candidate_id)
        return self._candidate(json.loads(row["payload"]))

    @staticmethod
    def _candidate(d: dict) -> ReleaseCandidate:
        contract = QualityContract(**d["contract"])
        q = d["quality"]
        quality = QualityResult(q["contract"], q["contract_version"], q["passed"], tuple(q["checks"]))
        return ReleaseCandidate(d["candidate_id"], d["source"], d["manifest_sha256"], contract,
                                quality, d["metadata"], d.get("state", "candidate"))

    def set_candidate_state(self, candidate_id: str, state: str) -> ReleaseCandidate:
        candidate = self.candidate(candidate_id)
        if state not in ("candidate", "promoted", "rejected"):
            raise ValueError(f"invalid candidate state: {state}")
        if candidate.state != "candidate":
            raise ValueError(
                f"invalid candidate transition: {candidate.state} -> {state}"
            )
        updated = ReleaseCandidate(candidate.candidate_id, candidate.source, candidate.manifest_sha256,
                                   candidate.contract, candidate.quality, candidate.metadata, state)
        self.save_candidate(updated)
        return updated

    def save_release(self, release_id: str, candidate: ReleaseCandidate, state: str) -> None:
        if state not in ("promoted", "rejected"):
            raise ValueError(f"invalid release state: {state}")
        if candidate.state != state:
            raise ValueError(
                f"release state {state} does not match candidate state {candidate.state}"
            )
        payload = dict(candidate.as_dict())
        payload["release_id"] = release_id
        payload["state"] = state
        self.db.execute("INSERT OR REPLACE INTO releases VALUES(?,?,?,?)",
                        (release_id, candidate.candidate_id, json.dumps(payload, sort_keys=True), state))
        cid = self.lineage.node("release_candidate", candidate.candidate_id,
                                {"candidate_id": candidate.candidate_id, "state": state})
        rid = self.lineage.node("release", release_id,
                                {"release_id": release_id, "candidate_id": candidate.candidate_id, "state": state})
        self.lineage.connect(cid, rid, "released_as", "release.created",
                             {"release_id": release_id, "candidate_id": candidate.candidate_id, "state": state})
        aid = self.lineage.node("approval", {"release_id": release_id, "state": state},
                                {"release_id": release_id, "state": state})
        self.lineage.edge(aid, rid, "approves")
        self.lineage.event("approval.recorded", {"approval_id": aid, "release_id": release_id, "state": state})
        self.db.commit()

    def lineage_for(self, identifier: str) -> dict:
        return self.lineage.inspect(identifier)

    def replay_lineage(self) -> list[dict]:
        return self.lineage.replay()

    def record_credential_profile(self, name: str, provider: str, target: str) -> str:
        cid = self.lineage.node("credential_profile", name,
                                {"name": name, "provider": provider, "target": target})
        self.lineage.event("credential_profile.observed", {"profile_id": cid, "name": name,
                                                            "provider": provider, "target": target})
        self.db.commit()
        return cid

    def record_connector_metadata(self, source: str, metadata: ConnectorMetadata) -> str:
        """Persist a redacted connector observation and preserve its lineage."""
        source_id = self.lineage.node("source", source, {"name": source})
        observation_id = self.lineage.node(
            "connector_observation", {"source": source, "target": metadata.target,
                                      "connector": metadata.connector},
            metadata.as_dict(),
        )
        self.lineage.edge(source_id, observation_id, "inspected_by")
        self.lineage.event("source.connector_inspected", {
            "source": source, "observation_id": observation_id,
            "connector": metadata.connector, "target": metadata.target,
            "source_status": metadata.source_status,
            "network_accessed": metadata.network_accessed,
        })
        if metadata.credential_profile:
            credential_id = self.lineage.node("credential_profile", metadata.credential_profile,
                                              {"name": metadata.credential_profile})
            self.lineage.edge(credential_id, observation_id, "authorizes")
        self.db.commit()
        return observation_id

    def record_evidence_artifact(self, artifact_id: str, target_id: str, digest: str,
                                 path: str = "") -> str:
        aid = self.lineage.node("evidence_artifact", artifact_id,
                                {"artifact_id": artifact_id, "sha256": digest, "path": path})
        self.lineage.edge(target_id, aid, "supported_by")
        self.lineage.event("evidence_artifact.created", {"artifact_id": aid, "target_id": target_id,
                                                         "sha256": digest})
        self.db.commit()
        return aid

    def release(self, release_id: str) -> dict:
        row = self.db.execute("SELECT payload FROM releases WHERE release_id=?", (release_id,)).fetchone()
        if not row:
            raise KeyError(release_id)
        return json.loads(row["payload"])

    @classmethod
    def _manifest(cls, d: dict) -> Manifest:
        return Manifest(d["source"], d["created_at"], tuple(cls._record(x) for x in d["records"]), d["manifest_sha256"], d["complete"], d.get("run_id"))

    def release_model(self, release_id: str) -> Release:
        payload = self.release(release_id)
        return Release(payload["release_id"], payload["candidate_id"], payload["state"], payload)

    def close(self): self.db.close()
