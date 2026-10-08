from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Union


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _image_info(path: Path, mime: str) -> dict[str, Any]:
    """Read dimensions and basic signature without importing image libraries."""
    with path.open("rb") as f:
        data = f.read(32)
    if mime == "image/png" and data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return {"width": struct.unpack(">I", data[16:20])[0], "height": struct.unpack(">I", data[20:24])[0], "format": "png"}
    if mime == "image/gif" and data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return {"width": struct.unpack("<H", data[6:8])[0], "height": struct.unpack("<H", data[8:10])[0], "format": "gif"}
    if mime == "image/bmp" and data[:2] == b"BM" and len(data) >= 26:
        return {"width": struct.unpack("<i", data[18:22])[0], "height": abs(struct.unpack("<i", data[22:26])[0]), "format": "bmp"}
    if mime == "image/jpeg" and data[:2] == b"\xff\xd8":
        # JPEG dimensions occur in a SOF marker; scan segments.
        with path.open("rb") as f:
            f.read(2)
            while True:
                marker = f.read(2)
                if len(marker) != 2 or marker[0] != 0xFF:
                    break
                while marker[1] == 0xFF:
                    marker = bytes((marker[0],)) + f.read(1)
                if marker[1] in (0xD8, 0xD9):
                    continue
                length_bytes = f.read(2)
                if len(length_bytes) != 2:
                    break
                length = struct.unpack(">H", length_bytes)[0]
                if marker[1] in range(0xC0, 0xC4) or marker[1] in range(0xC5, 0xC8) or marker[1] in range(0xC9, 0xCC) or marker[1] in range(0xCD, 0xD0):
                    body = f.read(length - 2)
                    if len(body) >= 5:
                        return {"width": struct.unpack(">H", body[3:5])[0], "height": struct.unpack(">H", body[1:3])[0], "format": "jpeg"}
                    break
                f.seek(length - 2, os.SEEK_CUR)
        return {"format": "jpeg"}
    return {}


def infer_modality(mime: str, suffix: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime in ("application/json", "text/csv", "text/tab-separated-values") or suffix in (".json", ".csv", ".tsv"):
        return "tabular" if suffix in (".csv", ".tsv") else "text"
    return "document" if mime.startswith(("text/", "application/")) else "binary"


@dataclass(frozen=True)
class Source:
    name: str
    root: str
    source_type: str = "filesystem"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FileRecord:
    path: str
    sha256: str
    size: int
    mtime_ns: int
    mime_type: str
    modality: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "size": self.size, "mtime_ns": self.mtime_ns,
                "mime_type": self.mime_type, "modality": self.modality, "metadata": dict(self.metadata),
                "errors": list(self.errors)}


@dataclass(frozen=True)
class Manifest:
    source: str
    created_at: str
    records: tuple[FileRecord, ...]
    manifest_sha256: str
    complete: bool = True
    run_id: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {"source": self.source, "created_at": self.created_at, "manifest_sha256": self.manifest_sha256,
                "complete": self.complete, "run_id": self.run_id, "records": [r.as_dict() for r in self.records]}


def inspect_file(path: Union[str, Path], root: Optional[Union[str, Path]] = None) -> FileRecord:
    p = Path(path)
    stat = p.stat()
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    metadata: dict[str, Any] = {"extension": p.suffix.lower()}
    errors: list[str] = []
    if stat.st_size == 0:
        errors.append("empty_file")
    if mime.startswith("image/"):
        info = _image_info(p, mime)
        metadata.update(info)
        if not info:
            errors.append("invalid_or_unsupported_image")
        elif info.get("width", 1) <= 0 or info.get("height", 1) <= 0:
            errors.append("invalid_image_dimensions")
    display = p.relative_to(root).as_posix() if root else str(p)
    return FileRecord(display, _sha256(p), stat.st_size, stat.st_mtime_ns, mime, infer_modality(mime, p.suffix.lower()), metadata, tuple(errors))


def validate_record(record: FileRecord) -> str:
    return "FAIL" if record.errors else "PASS"


def build_manifest(source: str, records: Iterable[FileRecord], created_at: str, complete: bool = True, run_id: Optional[str] = None) -> Manifest:
    ordered = tuple(sorted(records, key=lambda r: r.path))
    canonical = "\n".join(json.dumps(r.as_dict(), sort_keys=True, separators=(",", ":")) for r in ordered).encode()
    return Manifest(source, created_at, ordered, hashlib.sha256(canonical).hexdigest(), complete, run_id)


def duplicate_groups(records: Iterable[FileRecord]) -> list[list[str]]:
    groups: dict[str, list[str]] = {}
    for record in records:
        groups.setdefault(record.sha256, []).append(record.path)
    return [sorted(paths) for paths in groups.values() if len(paths) > 1]


def compare_manifests(current: Manifest, prior: Manifest) -> dict[str, Any]:
    old = {r.path: r for r in prior.records}
    new = {r.path: r for r in current.records}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(p for p in set(new) & set(old) if new[p].sha256 != old[p].sha256)
    unchanged = sorted(p for p in set(new) & set(old) if new[p].sha256 == old[p].sha256)
    return {"added": added, "removed": removed, "changed": changed, "unchanged": len(unchanged),
            "status": "FAIL" if added or removed or changed else ("WARN" if not current.complete else "PASS")}
