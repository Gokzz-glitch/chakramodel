"""Read-only source connector contracts and metadata-only adapters.

Connectors deliberately describe a target; they do not crawl directories,
download content, upload content, or resolve credentials.  Network access is
always an explicit opt-in.
"""
from __future__ import annotations

import mimetypes
import tarfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol
from urllib.parse import urlparse


@dataclass(frozen=True)
class DownloadBoundary:
    supported: bool = False
    resumable: bool = False
    method: str = "metadata-only"
    range_unit: Optional[str] = None
    notes: str = "No content transfer is performed by this connector."


@dataclass(frozen=True)
class ConnectorMetadata:
    connector: str
    target: str
    target_kind: str
    source_status: str  # "snapshot" or "mutable"
    read_only: bool = True
    exists: Optional[bool] = None
    size: Optional[int] = None
    modified_at_ns: Optional[int] = None
    content_type: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    license_terms: Mapping[str, Any] = field(default_factory=dict)
    credential_profile: Optional[str] = None
    download: DownloadBoundary = field(default_factory=DownloadBoundary)
    network_accessed: bool = False

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["metadata"] = dict(self.metadata)
        value["license_terms"] = dict(self.license_terms)
        value["download"] = asdict(self.download)
        return value


class SourceConnector(Protocol):
    name: str

    def inspect(self, target: str, *, network: bool = False) -> ConnectorMetadata: ...

    def test(self, target: str, *, network: bool = False) -> ConnectorMetadata: ...


def _license(metadata: Mapping[str, Any]) -> dict[str, Any]:
    value = metadata.get("license_terms", metadata.get("license"))
    if isinstance(value, Mapping):
        return dict(value)
    return {"declared": value} if value is not None else {}


class FilesystemConnector:
    name = "filesystem"

    def inspect(self, target: str, *, network: bool = False) -> ConnectorMetadata:
        if network:
            raise ValueError("filesystem connector does not support network access")
        path = Path(target).expanduser()
        if not path.exists():
            return ConnectorMetadata(self.name, str(path), "filesystem", "mutable",
                                     exists=False, metadata={"target_explicit": True})
        stat = path.stat()
        kind = "directory" if path.is_dir() else "file"
        return ConnectorMetadata(
            self.name, str(path.resolve()), kind, "mutable", exists=True,
            size=stat.st_size if path.is_file() else None,
            modified_at_ns=stat.st_mtime_ns,
            content_type=mimetypes.guess_type(path.name)[0],
            metadata={"target_explicit": True, "name": path.name},
            download=DownloadBoundary(False, False),
        )

    test = inspect


class ArchiveConnector:
    name = "archive"

    def inspect(self, target: str, *, network: bool = False) -> ConnectorMetadata:
        if network:
            raise ValueError("archive connector does not support network access")
        path = Path(target).expanduser()
        if not path.is_file():
            raise ValueError("archive target must be an existing file")
        stat = path.stat()
        archive_type = "zip" if zipfile.is_zipfile(path) else "tar" if tarfile.is_tarfile(path) else None
        if not archive_type:
            raise ValueError("target is not a supported ZIP or TAR archive")
        members = 0
        if archive_type == "zip":
            with zipfile.ZipFile(path) as archive:
                members = len(archive.infolist())
        else:
            with tarfile.open(path, "r:*") as archive:
                members = len(archive.getmembers())
        return ConnectorMetadata(
            self.name, str(path.resolve()), "archive", "snapshot", exists=True,
            size=stat.st_size, modified_at_ns=stat.st_mtime_ns,
            content_type="application/zip" if archive_type == "zip" else "application/x-tar",
            metadata={"archive_type": archive_type, "member_count": members,
                      "target_explicit": True, "extraction": False},
            download=DownloadBoundary(False, False),
        )

    test = inspect


class HTTPSConnector:
    name = "https"

    def inspect(self, target: str, *, network: bool = False) -> ConnectorMetadata:
        parsed = urlparse(target)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("HTTPS connector requires an explicit https URL")
        if not network:
            return ConnectorMetadata(
                self.name, target, "https-resource", "mutable", exists=None,
                metadata={"target_explicit": True, "network_opt_in_required": True},
                download=DownloadBoundary(True, True, "metadata-only", "bytes"),
            )
        request = urllib.request.Request(target, method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                headers = response.headers
                length = headers.get("Content-Length")
                return ConnectorMetadata(
                    self.name, target, "https-resource", "mutable", exists=200 <= response.status < 400,
                    size=int(length) if length and length.isdigit() else None,
                    content_type=headers.get_content_type(),
                    metadata={"status": response.status, "etag": headers.get("ETag"),
                              "last_modified": headers.get("Last-Modified"),
                              "accept_ranges": headers.get("Accept-Ranges", "").lower() == "bytes",
                              "target_explicit": True},
                    download=DownloadBoundary(True, headers.get("Accept-Ranges", "").lower() == "bytes",
                                              "metadata-only", "bytes"),
                    network_accessed=True,
                )
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            return ConnectorMetadata(self.name, target, "https-resource", "mutable",
                                     exists=False, metadata={"error": type(exc).__name__,
                                                             "target_explicit": True},
                                     download=DownloadBoundary(True, False, "metadata-only", "bytes"),
                                     network_accessed=True)

    test = inspect


def connector_for(kind: str) -> SourceConnector:
    normalized = kind.lower()
    if normalized in ("filesystem", "file"):
        return FilesystemConnector()
    if normalized in ("archive", "zip", "tar"):
        return ArchiveConnector()
    if normalized in ("https", "http"):
        if normalized == "http":
            raise ValueError("only HTTPS targets are supported")
        return HTTPSConnector()
    raise ValueError(f"unsupported connector: {kind}")


def inspect_target(kind: str, target: str, *, network: bool = False,
                   metadata: Optional[Mapping[str, Any]] = None) -> ConnectorMetadata:
    result = connector_for(kind).inspect(target, network=network)
    supplied = dict(metadata or {})
    if supplied:
        result = replace(result, metadata={**dict(result.metadata), **supplied},
                         license_terms=_license(supplied),
                         credential_profile=supplied.get("credential_profile"))
    return result
