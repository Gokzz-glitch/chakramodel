"""Append-only, replayable evidence lineage.

Lineage metadata is deliberately boring: identifiers, hashes, timestamps and
redacted metadata.  In particular, this module must never persist credential
values or blobs.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

_SECRET = re.compile(r"(pass(word)?|secret|token|api[_-]?key|private[_-]?key|credential|blob)", re.I)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def node_id(kind: str, identity: Any) -> str:
    return f"{kind}:{hashlib.sha256(canonical(identity).encode()).hexdigest()}"


def redact(value: Any, key: str = "") -> Any:
    if _SECRET.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


class Lineage:
    """SQLite-backed append-only graph and event journal."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS lineage_nodes(
          node_id TEXT PRIMARY KEY, node_type TEXT NOT NULL, metadata TEXT NOT NULL,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lineage_edges(
          edge_id TEXT PRIMARY KEY, from_id TEXT NOT NULL, to_id TEXT NOT NULL,
          edge_type TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lineage_events(
          event_id TEXT PRIMARY KEY, sequence INTEGER UNIQUE NOT NULL, event_type TEXT NOT NULL,
          payload TEXT NOT NULL, created_at TEXT NOT NULL);
        """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def node(self, kind: str, identity: Any, metadata: Optional[Mapping[str, Any]] = None) -> str:
        nid = node_id(kind, identity)
        payload = redact(dict(metadata or {}))
        self.db.execute(
            "INSERT OR IGNORE INTO lineage_nodes VALUES(?,?,?,?)",
            (nid, kind, canonical(payload), self._now()),
        )
        return nid

    def edge(self, source: str, target: str, relation: str,
             metadata: Optional[Mapping[str, Any]] = None) -> str:
        eid = node_id("edge", {"from": source, "to": target, "relation": relation})
        self.db.execute(
            "INSERT OR IGNORE INTO lineage_edges VALUES(?,?,?,?,?,?)",
            (eid, source, target, relation, canonical(redact(dict(metadata or {}))), self._now()),
        )
        return eid

    def event(self, event_type: str, payload: Mapping[str, Any]) -> str:
        safe = redact(dict(payload))
        event_key = {"type": event_type, "payload": safe}
        eid = node_id("event", event_key)
        exists = self.db.execute("SELECT event_id FROM lineage_events WHERE event_id=?", (eid,)).fetchone()
        if not exists:
            seq = self.db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM lineage_events").fetchone()[0]
            self.db.execute("INSERT INTO lineage_events VALUES(?,?,?,?,?)",
                            (eid, seq, event_type, canonical(safe), self._now()))
        return eid

    def connect(self, source: str, target: str, relation: str,
                event_type: str, payload: Mapping[str, Any]) -> None:
        self.edge(source, target, relation)
        self.event(event_type, payload)

    def inspect(self, target: str) -> dict[str, Any]:
        rows = self.db.execute(
            "SELECT node_id,node_type,metadata,created_at FROM lineage_nodes WHERE node_id=?",
            (target,),
        ).fetchall()
        if not rows:
            rows = self.db.execute(
                "SELECT node_id,node_type,metadata,created_at FROM lineage_nodes "
                "WHERE node_id LIKE ? OR metadata LIKE ?",
                (f"%:{target}", f"%{target}%"),
            ).fetchall()
        ids = {r["node_id"] for r in rows}
        edges = self.db.execute(
            "SELECT edge_id,from_id,to_id,edge_type,metadata,created_at FROM lineage_edges "
            "WHERE from_id IN (SELECT node_id FROM lineage_nodes WHERE node_id LIKE ?) "
            "OR to_id IN (SELECT node_id FROM lineage_nodes WHERE node_id LIKE ?)",
            (f"%:{target}%", f"%:{target}%"),
        ).fetchall()
        # Walk the connected component so a release inspection includes its
        # candidate, manifest, source and evidence artifacts.
        changed = True
        while changed:
            changed = False
            for e in self.db.execute("SELECT from_id,to_id FROM lineage_edges").fetchall():
                if e[0] in ids or e[1] in ids:
                    before = len(ids); ids.update((e[0], e[1])); changed |= len(ids) != before
        nodes = self.db.execute(
            "SELECT node_id,node_type,metadata,created_at FROM lineage_nodes WHERE node_id IN (%s)"
            % ",".join("?" * len(ids)), tuple(ids)).fetchall() if ids else []
        edges = self.db.execute(
            "SELECT edge_id,from_id,to_id,edge_type,metadata,created_at FROM lineage_edges "
            "WHERE from_id IN (%s) AND to_id IN (%s)"
            % (",".join("?" * len(ids)), ",".join("?" * len(ids))), tuple(ids) * 2) if ids else []
        return {
            "target": target,
            "nodes": [self._row(r, "metadata") for r in nodes],
            "edges": [self._row(r, "metadata", "edge_type") for r in edges],
            "events": [self._row(r, "payload", "event_type", "sequence")
                       for r in self.db.execute("SELECT * FROM lineage_events ORDER BY sequence").fetchall()],
        }

    @staticmethod
    def _row(row: sqlite3.Row, json_key: str, *extra: str) -> dict[str, Any]:
        result = {k: row[k] for k in row.keys() if k != json_key}
        result[json_key] = json.loads(row[json_key])
        return result

    def replay(self) -> list[dict[str, Any]]:
        return [self._row(r, "payload", "event_type", "sequence")
                for r in self.db.execute("SELECT * FROM lineage_events ORDER BY sequence")]


# Public descriptive aliases for callers that refer to this as an evidence
# graph rather than lineage.
EvidenceGraph = Lineage
deterministic_node_id = node_id
