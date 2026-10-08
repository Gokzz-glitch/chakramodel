"""Read-only, deterministic inventory and validation of explicit filesystem roots."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any, Iterable

from .core import FileRecord, inspect_file, duplicate_groups
from .image_validation import capability as image_validator_capability, validate as validate_image

COMMON_EXCLUDED_DIRS = frozenset({
    ".git", ".venv", "__pycache__", "node_modules", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox",
    ".cache", "cache", "checkpoint", "checkpoints", ".checkpoint",
    ".checkpoints", ".ipynb_checkpoints", "htmlcov", "coverage",
})


def _annotation(record: FileRecord) -> bool:
    suffix = Path(record.path).suffix.lower()
    parts = {part.lower() for part in Path(record.path).parts}
    return suffix in {".json", ".xml", ".csv", ".tsv", ".txt", ".seg", ".mask", ".label"} and (
        bool(parts & {"annotation", "annotations", "label", "labels", "mask", "masks", "ground_truth", "gt"})
        or any(token in Path(record.path).stem.lower() for token in ("annot", "label", "mask", "ground_truth"))
    )


def _error_record(path: str, error: BaseException) -> FileRecord:
    return FileRecord(path, "", 0, 0, mimetypes.guess_type(path)[0] or "application/octet-stream",
                      "unknown", {"extension": Path(path).suffix.lower()},
                      (f"{type(error).__name__}: {error}",))


def _excluded_tree_counts(path: Path) -> tuple[int, int]:
    """Count an excluded directory and its contents without inspecting files."""
    directories = 1
    files = 0
    try:
        for _current, dirs, names in os.walk(path, followlinks=False):
            directories += len(dirs)
            files += len(names)
            dirs.sort()
            names.sort()
    except OSError:
        # Excluded content is intentionally never a validation error.
        pass
    return files, directories


def inventory_roots(
    roots: Iterable[str],
    progress: bool = False,
    exclude_dirs: Iterable[str] = (),
    image_validator: str = "stdlib",
) -> dict[str, Any]:
    """Inspect roots without writing to them or to the workbench database."""
    explicit = [Path(root).expanduser().resolve() for root in roots]
    excluded_names = frozenset(name.casefold() for name in exclude_dirs if name)
    records: list[FileRecord] = []
    errors: list[dict[str, str]] = []
    root_breakdown: list[dict[str, Any]] = []
    complete = True
    validator_info = (
        image_validator_capability() if image_validator == "pillow"
        else {"validator": "stdlib", "available": True, "mode": "header-check"}
    )
    count = 0
    # Root indexes make paths unambiguous while avoiding machine-specific absolute
    # paths in the deterministic manifest.
    for root_index, root in enumerate(explicit):
        prefix = f"root-{root_index}"
        if not root.exists():
            complete = False
            errors.append({"path": str(root), "error": "missing_root"})
            root_breakdown.append({
                "root": str(root), "files": 0, "excluded_files": 0,
                "excluded_directories": 0, "errors": 1,
            })
            continue
        if root.is_file():
            candidates = [root]
            excluded_files = 0
            excluded_directories = 0
        else:
            candidates = []
            excluded_files = 0
            excluded_directories = 0
            try:
                for current, dirs, files in os.walk(root, followlinks=False):
                    dirs.sort()
                    kept_dirs = []
                    for directory in dirs:
                        if directory.casefold() in excluded_names:
                            skipped_files, skipped_dirs = _excluded_tree_counts(Path(current) / directory)
                            excluded_files += skipped_files
                            excluded_directories += skipped_dirs
                        else:
                            kept_dirs.append(directory)
                    dirs[:] = kept_dirs
                    candidates.extend(Path(current) / name for name in sorted(files))
            except OSError as exc:
                complete = False
                errors.append({"path": str(root), "error": f"{type(exc).__name__}: {exc}"})
        for path in candidates:
            relative = path.name if root.is_file() else path.relative_to(root).as_posix()
            display = f"{prefix}/{relative}"
            try:
                record = inspect_file(path, root if root.is_dir() else None)
                if image_validator == "pillow" and record.modality == "image":
                    image_result = validate_image(path)
                    metadata = dict(record.metadata)
                    metadata["image_validation"] = image_result
                    record_errors = list(record.errors)
                    if image_result["status"] == "decode_error":
                        record_errors.append("image_decode_error")
                    record = FileRecord(record.path, record.sha256, record.size, record.mtime_ns,
                                        record.mime_type, record.modality, metadata, tuple(record_errors))
                record = FileRecord(display, record.sha256, record.size, record.mtime_ns,
                                    record.mime_type, record.modality, record.metadata, record.errors)
            except (OSError, ValueError) as exc:
                complete = False
                record = _error_record(display, exc)
                errors.append({"path": display, "error": str(exc)})
            records.append(record)
            count += 1
            if progress and count % 100 == 0:
                print(f"inventory: {count} files", end="\r", file=sys.stderr, flush=True)
        root_breakdown.append({
            "root": str(root),
            "files": len(candidates),
            "excluded_files": excluded_files,
            "excluded_directories": excluded_directories,
            "errors": sum(bool(record.errors) for record in records
                          if record.path.startswith(f"{prefix}/")),
        })
    if progress:
        print(f"inventory: {count} files", file=sys.stderr, flush=True)
    records.sort(key=lambda record: record.path)
    canonical_records = "\n".join(
        json.dumps(record.as_dict(), sort_keys=True, separators=(",", ":")) for record in records
    ).encode("utf-8")
    manifest_sha256 = hashlib.sha256(canonical_records).hexdigest()
    groups = duplicate_groups(record for record in records if record.sha256)
    modality: dict[str, int] = {}
    for record in records:
        modality[record.modality] = modality.get(record.modality, 0) + 1
    annotation_count = sum(_annotation(record) for record in records)
    error_paths = {item["path"] for item in errors}
    error_paths.update(record.path for record in records if record.errors)
    report: dict[str, Any] = {
        "operation": "inventory",
        "image_validator": validator_info,
        "roots": [str(root) for root in explicit],
        "complete": complete,
        "manifest": {"sha256": manifest_sha256, "record_count": len(records), "complete": complete}
        if complete else None,
        "records": [record.as_dict() for record in records],
        "summary": {
            "files": len(records),
            "modalities": dict(sorted(modality.items())),
            "annotations": annotation_count,
            "duplicate_groups": len(groups),
            "duplicate_files": sum(len(group) for group in groups),
            "errors": len(error_paths),
            "error_files": len(error_paths),
            "excluded_files": sum(item["excluded_files"] for item in root_breakdown),
            "excluded_directories": sum(item["excluded_directories"] for item in root_breakdown),
            "root_breakdown": root_breakdown,
        },
        "duplicates": groups,
        "errors": errors + [
            {"path": record.path, "error": error}
            for record in records for error in record.errors
        ],
    }
    evidence_payload = {
        "operation": "inventory", "roots": report["roots"], "manifest": report["manifest"],
        "complete": complete,
    }
    evidence_json = json.dumps(evidence_payload, sort_keys=True, separators=(",", ":")).encode()
    report["lineage"] = {
        "type": "read-only-inventory", "roots": report["roots"],
        "manifest_sha256": manifest_sha256, "complete": complete,
    }
    report["evidence"] = {"sha256": hashlib.sha256(evidence_json).hexdigest(),
                         "complete": complete}
    return report
