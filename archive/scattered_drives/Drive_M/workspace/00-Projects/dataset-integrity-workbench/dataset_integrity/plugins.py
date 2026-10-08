"""Optional integration points.

These protocols describe integration boundaries only; no SDKs, network calls, or
credentials are required by this package.
"""
from __future__ import annotations
from typing import Any, Iterable, Mapping, Protocol
from .core import FileRecord, Source

class SourceAdapter(Protocol):
    def register(self) -> Source: ...
    def iter_files(self) -> Iterable[str]: ...

class MetadataProvider(Protocol):
    def metadata(self, path: str) -> dict: ...

class Validator(Protocol):
    def validate(self, record: FileRecord) -> list[str]: ...


class DatumaroAdapter(SourceAdapter, Protocol):
    """Adapter boundary for importing/exporting Datumaro datasets."""
    def export_records(self, records: Iterable[FileRecord]) -> Any: ...


class FiftyOneAdapter(SourceAdapter, Protocol):
    """Adapter boundary for interacting with a FiftyOne dataset."""
    def export_records(self, records: Iterable[FileRecord]) -> Any: ...


class CleanlabValidator(Validator, Protocol):
    """Optional Cleanlab-backed quality checks."""
    def validate_batch(self, records: Iterable[FileRecord]) -> Mapping[str, Any]: ...


class GeminiMetadataProvider(MetadataProvider, Protocol):
    """Optional Gemini metadata/annotation provider; implementations own transport."""
    def annotate(self, record: FileRecord, prompt: str) -> Mapping[str, Any]: ...


class OpenAIMetadataProvider(MetadataProvider, Protocol):
    """Optional OpenAI metadata/annotation provider; implementations own transport."""
    def annotate(self, record: FileRecord, prompt: str) -> Mapping[str, Any]: ...


# Explicit aliases make the integration roles discoverable to plugin authors.
DatumaroSourceAdapter = DatumaroAdapter
FiftyOneSourceAdapter = FiftyOneAdapter
GeminiAdapter = GeminiMetadataProvider
OpenAIAdapter = OpenAIMetadataProvider
