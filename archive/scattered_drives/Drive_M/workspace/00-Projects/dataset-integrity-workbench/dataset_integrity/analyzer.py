"""Portable, resumable filesystem analysis.

The analyzer is deliberately read-only with respect to the inspected root.
Only the SQLite state database and explicitly requested export files are
written.
"""
from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from .core import FileRecord, build_manifest, duplicate_groups, inspect_file


@dataclass(frozen=True)
class ScanResult:
    run_id: str
    root: str
    complete: bool
    records: tuple[FileRecord, ...]
    changes: tuple[dict[str, Any], ...]
    errors: tuple[dict[str, Any], ...]
    manifest_sha256: Optional[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation": "analyze",
            "run_id": self.run_id,
            "root": self.root,
            "complete": self.complete,
            "manifest_sha256": self.manifest_sha256,
            "records": [record.as_dict() for record in self.records],
            "duplicates": duplicate_groups(self.records),
            "changes": list(self.changes),
            "errors": list(self.errors),
            "summary": {
                "files": len(self.records),
                "duplicate_groups": len(duplicate_groups(self.records)),
                "duplicate_files": sum(len(group) for group in duplicate_groups(self.records)),
                "changes": len(self.changes),
                "errors": len(self.errors),
            },
        }


class InventoryDatabase:
    """SQLite state store used by :func:`scan_filesystem`."""

    def __init__(self, path: str):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS inventory_runs (
                run_id TEXT PRIMARY KEY, root TEXT NOT NULL,
                started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inventory_files (
                root TEXT NOT NULL, path TEXT NOT NULL, size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL, sha256 TEXT NOT NULL, payload TEXT NOT NULL,
                run_id TEXT NOT NULL, PRIMARY KEY(root, path)
            );
            CREATE TABLE IF NOT EXISTS inventory_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                path TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inventory_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                path TEXT NOT NULL, error TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def start_run(self, run_id: str, root: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO inventory_runs(run_id,root,started_at,status) "
            "VALUES(?,?,datetime('now'),'incomplete')",
            (run_id, root),
        )
        self.db.commit()

    def finish_run(self, run_id: str, complete: bool) -> None:
        self.db.execute(
            "UPDATE inventory_runs SET finished_at=datetime('now'),status=? WHERE run_id=?",
            ("complete" if complete else "incomplete", run_id),
        )
        self.db.commit()

    def prior(self, root: str, path: str) -> Optional[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM inventory_files WHERE root=? AND path=?", (root, path)
        ).fetchone()

    def save(self, root: str, path: str, record: FileRecord, run_id: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO inventory_files VALUES(?,?,?,?,?,?,?)",
            (root, path, record.size, record.mtime_ns, record.sha256,
             json.dumps(record.as_dict(), sort_keys=True), run_id),
        )
        self.db.commit()

    def log_change(self, run_id: str, path: str, kind: str, detail: str) -> None:
        self.db.execute(
            "INSERT INTO inventory_changes(run_id,path,kind,detail) VALUES(?,?,?,?)",
            (run_id, path, kind, detail),
        )
        self.db.commit()

    def log_error(self, run_id: str, path: str, error: str) -> None:
        self.db.execute(
            "INSERT INTO inventory_errors(run_id,path,error) VALUES(?,?,?)",
            (run_id, path, error),
        )
        self.db.commit()

    def records(self, root: str) -> list[FileRecord]:
        rows = self.db.execute(
            "SELECT payload FROM inventory_files WHERE root=? ORDER BY path", (root,)
        )
        return [_record(json.loads(row["payload"])) for row in rows]

    def prior_paths(self, root: str) -> set[str]:
        return {row["path"] for row in self.db.execute(
            "SELECT path FROM inventory_files WHERE root=?", (root,))}

    def remove(self, root: str, path: str) -> None:
        self.db.execute("DELETE FROM inventory_files WHERE root=? AND path=?", (root, path))
        self.db.commit()


def _record(payload: dict[str, Any]) -> FileRecord:
    return FileRecord(
        payload["path"], payload["sha256"], payload["size"], payload["mtime_ns"],
        payload["mime_type"], payload["modality"], payload.get("metadata", {}),
        tuple(payload.get("errors", [])),
    )


def _stable_record(path: Path, root: Path, prior: Optional[sqlite3.Row]) -> FileRecord:
    first = path.stat()
    if prior and first.st_size == prior["size"] and first.st_mtime_ns == prior["mtime_ns"]:
        return _record(json.loads(prior["payload"]))
    record = inspect_file(path, root)
    second = path.stat()
    if first.st_size != second.st_size or first.st_mtime_ns != second.st_mtime_ns:
        raise OSError("file changed while hashing")
    return record


def scan_filesystem(
    root: str,
    db_path: str = "dataset-integrity.sqlite",
    run_id: Optional[str] = None,
    workers: int = 4,
    exclude_dirs: Iterable[str] = (),
    stop_after: Optional[int] = None,
) -> ScanResult:
    """Scan ``root`` with bounded hashing and resumable safe hash reuse."""
    root_path = Path(root).expanduser().resolve()
    run_id = run_id or hashlib.sha256(str(root_path).encode()).hexdigest()[:16]
    store = InventoryDatabase(db_path)
    store.start_run(run_id, str(root_path))
    changes: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    records: list[FileRecord] = []
    complete = True
    try:
        if not root_path.exists() or not root_path.is_dir():
            raise FileNotFoundError(str(root_path))
        excluded = {name.casefold() for name in exclude_dirs}
        paths: list[Path] = []
        for current, dirs, names in os.walk(root_path, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d.casefold() not in excluded)
            paths.extend(Path(current) / name for name in sorted(names))
        truncated = stop_after is not None and stop_after < len(paths)
        if stop_after is not None:
            paths = paths[:stop_after]

        prior_by_path = {
            path.relative_to(root_path).as_posix(): store.prior(str(root_path), path.relative_to(root_path).as_posix())
            for path in paths
        }

        def inspect_one(path: Path, prior: Optional[sqlite3.Row]) -> tuple[Path, FileRecord, str]:
            relative = path.relative_to(root_path).as_posix()
            reused = bool(prior)
            record = _stable_record(path, root_path, prior)
            return path, record, "reused" if reused and record.sha256 == prior["sha256"] else "hashed"

        with ThreadPoolExecutor(max_workers=max(1, min(workers, 32))) as pool:
            futures = {pool.submit(inspect_one, path, prior_by_path[path.relative_to(root_path).as_posix()]): path
                       for path in paths}
            for future in as_completed(futures):
                try:
                    path, record, method = future.result()
                    relative = path.relative_to(root_path).as_posix()
                    prior = prior_by_path[relative]
                    if prior and prior["sha256"] != record.sha256:
                        change = {"path": relative, "kind": "changed",
                                  "detail": "sha256 changed"}
                        changes.append(change)
                        store.log_change(run_id, relative, "changed", change["detail"])
                    elif not prior:
                        change = {"path": relative, "kind": "added", "detail": "new file"}
                        changes.append(change)
                        store.log_change(run_id, relative, "added", change["detail"])
                    store.save(str(root_path), relative, record, run_id)
                    if method == "reused":
                        changes.append({"path": relative, "kind": "hash_reused",
                                        "detail": "size and mtime unchanged"})
                        store.log_change(run_id, relative, "hash_reused", "size and mtime unchanged")
                    records.append(record)
                except (OSError, ValueError) as exc:
                    complete = False
                    display = futures[future].relative_to(root_path).as_posix()
                    error = {"path": display, "error": f"{type(exc).__name__}: {exc}"}
                    errors.append(error)
                    store.log_error(run_id, display, error["error"])
        if not truncated:
            current_paths = {path.relative_to(root_path).as_posix() for path in paths}
            for removed in sorted(store.prior_paths(str(root_path)) - current_paths):
                changes.append({"path": removed, "kind": "removed", "detail": "file no longer exists"})
                store.log_change(run_id, removed, "removed", "file no longer exists")
                store.remove(str(root_path), removed)
        complete = complete and not truncated
    except (OSError, ValueError) as exc:
        complete = False
        error = {"path": str(root_path), "error": f"{type(exc).__name__}: {exc}"}
        errors.append(error)
        store.log_error(run_id, str(root_path), error["error"])
    finally:
        store.finish_run(run_id, complete)
    records.sort(key=lambda record: record.path)
    manifest = build_manifest(str(root_path), records, run_id, complete, run_id) if complete else None
    result = ScanResult(
        run_id, str(root_path), complete, tuple(records), tuple(sorted(changes, key=lambda x: x["path"])),
        tuple(errors), manifest.manifest_sha256 if manifest else None,
    )
    store.close()
    return result


def export_report(report: dict[str, Any], path: str, fmt: str = "json") -> None:
    """Export a report as JSON, CSV, or concise text."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        target.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    elif fmt == "csv":
        with target.open("w", newline="", encoding="utf-8") as stream:
            fields = ["path", "sha256", "size", "mtime_ns", "mime_type", "modality", "errors"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for record in report.get("records", []):
                writer.writerow({key: (json.dumps(record.get(key, []), sort_keys=True)
                                       if key == "errors" else record.get(key, ""))
                                 for key in fields})
    elif fmt == "text":
        summary = report.get("summary", {})
        target.write_text(
            "Dataset Integrity Analyzer\n"
            f"root: {report.get('root', '')}\n"
            f"complete: {report.get('complete', False)}\n"
            f"files: {summary.get('files', 0)}\n"
            f"duplicates: {summary.get('duplicate_groups', 0)}\n"
            f"errors: {summary.get('errors', 0)}\n",
            encoding="utf-8",
        )
    else:
        raise ValueError("format must be json, csv, or text")
