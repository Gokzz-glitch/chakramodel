"""Governed, deterministic dataset releases."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .core import Manifest, duplicate_groups


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class QualityContract:
    name: str
    version: str = "1"
    require_complete: bool = True
    max_errors: int = 0
    max_duplicates: Optional[int] = None
    min_files: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version,
                "require_complete": self.require_complete, "max_errors": self.max_errors,
                "max_duplicates": self.max_duplicates, "min_files": self.min_files}


@dataclass(frozen=True)
class QualityResult:
    contract: str
    contract_version: str
    passed: bool
    checks: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {"contract": self.contract, "contract_version": self.contract_version,
                "passed": self.passed, "checks": [dict(c) for c in self.checks]}


def evaluate_contract(contract: QualityContract, manifest: Manifest) -> QualityResult:
    errors = sum(bool(r.errors) for r in manifest.records)
    duplicates = len(duplicate_groups(manifest.records))
    checks = [
        {"name": "complete", "passed": (manifest.complete or not contract.require_complete),
         "actual": manifest.complete, "required": contract.require_complete},
        {"name": "errors", "passed": errors <= contract.max_errors,
         "actual": errors, "maximum": contract.max_errors},
        {"name": "duplicates", "passed": (contract.max_duplicates is None or duplicates <= contract.max_duplicates),
         "actual": duplicates, "maximum": contract.max_duplicates},
        {"name": "file_count", "passed": len(manifest.records) >= contract.min_files,
         "actual": len(manifest.records), "minimum": contract.min_files},
    ]
    return QualityResult(contract.name, contract.version, all(c["passed"] for c in checks), tuple(checks))


@dataclass(frozen=True)
class ReleaseCandidate:
    candidate_id: str
    source: str
    manifest_sha256: str
    contract: QualityContract
    quality: QualityResult
    metadata: Mapping[str, Any]
    state: str = "candidate"

    def as_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "source": self.source,
                "manifest_sha256": self.manifest_sha256, "contract": self.contract.as_dict(),
                "quality": self.quality.as_dict(), "metadata": dict(self.metadata), "state": self.state}

    @classmethod
    def create(cls, manifest: Manifest, contract: QualityContract, metadata: Mapping[str, Any]) -> "ReleaseCandidate":
        quality = evaluate_contract(contract, manifest)
        body = {"source": manifest.source, "manifest_sha256": manifest.manifest_sha256,
                "contract": contract.as_dict(), "quality": quality.as_dict(), "metadata": dict(metadata)}
        return cls(_digest(body), manifest.source, manifest.manifest_sha256, contract, quality, dict(metadata))


@dataclass(frozen=True)
class Release:
    """A promoted or rejected immutable pointer to a candidate."""
    release_id: str
    candidate_id: str
    state: str
    metadata: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"release_id": self.release_id, "candidate_id": self.candidate_id,
                "state": self.state, "metadata": dict(self.metadata)}


def environment_info() -> dict[str, str]:
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "system": platform.system(), "machine": platform.machine()}


def default_metadata(seed: int = 0, code_version: str = "unknown",
                     config_version: str = "unknown", plugin_versions: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    return {"code_version": code_version, "config_version": config_version,
            "plugin_versions": dict(sorted((plugin_versions or {}).items())),
            "environment": environment_info(), "seed": seed}
