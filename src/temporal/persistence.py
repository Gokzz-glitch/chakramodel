from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


@dataclass
class TrackState:
    bbox: list  # [x1, y1, x2, y2]
    score: float
    ttl: int


class PersistenceManager:
    def __init__(self, max_ttl=6, decay=0.92, min_score=0.15):
        self.max_ttl = max_ttl
        self.decay = decay
        self.min_score = min_score
        self.state = None

    def update(self, det_bbox, det_score):
        if det_bbox is not None:
            self.state = TrackState(det_bbox, float(det_score), self.max_ttl)
            return det_bbox, det_score, "detected"

        if self.state is not None and self.state.ttl > 0:
            self.state.ttl -= 1
            self.state.score *= self.decay
            if self.state.score >= self.min_score:
                return self.state.bbox, self.state.score, "persisted"

        self.state = None
        return None, 0.0, "dropped"


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    tags: list[str]
    kind: str = "artifact"
    metadata: dict[str, object] | None = None
    created_at: str = ""

    def to_dict(self) -> dict:
        payload = asdict(self)
        if not payload["created_at"]:
            payload["created_at"] = datetime.now(timezone.utc).isoformat()
        if payload["metadata"] is None:
            payload["metadata"] = {}
        return payload


class ArtifactTagger:
    def __init__(self, out_dir: str | Path, manifest_name: str = "artifact_manifest.json") -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.out_dir / manifest_name
        self._records: list[ArtifactRecord] = []

    def tag(self, path: str | Path, *tags: str, kind: str = "artifact", metadata: Mapping[str, object] | None = None) -> ArtifactRecord:
        record = ArtifactRecord(
            path=str(Path(path).as_posix()),
            tags=sorted(set(tags)),
            kind=kind,
            metadata=dict(metadata or {}),
        )
        self._records.append(record)
        return record

    def extend(self, records: Iterable[ArtifactRecord]) -> None:
        self._records.extend(records)

    def write_manifest(self) -> Path:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": [record.to_dict() for record in self._records],
        }
        self.manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return self.manifest_path
