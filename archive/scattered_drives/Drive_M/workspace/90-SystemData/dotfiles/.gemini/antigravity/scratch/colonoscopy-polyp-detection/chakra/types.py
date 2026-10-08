from dataclasses import dataclass
from typing import Optional, List

@dataclass(frozen=True)
class BBox:
    x: float
    y: float
    w: float
    h: float

@dataclass(frozen=True)
class Detection:
    frame_idx: int
    bbox: BBox
    confidence: float
    class_id: int

@dataclass(frozen=True)
class Track:
    track_id: int
    bbox: BBox
    confidence: float
    hits: int

@dataclass(frozen=True)
class PersistentTrack:
    track_id: int
    bbox: BBox
    stability_score: float
    conformal_in_set: bool = False
    box_margin: float = 0.0

@dataclass(frozen=True)
class FrameOutput:
    frame_idx: int
    persistent_tracks: List[PersistentTrack]
    latency_ms: float
