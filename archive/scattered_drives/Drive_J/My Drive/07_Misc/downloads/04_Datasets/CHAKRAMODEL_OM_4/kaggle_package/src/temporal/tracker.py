"""
ChakraTemporalTracker — Canonical Temporal Persistence Module
==============================================================
Unified replacement for the four legacy persistence implementations:
  - temporal_persistence.py (root, deque-based sliding window)
  - src/temporal/persistence_filter.py (life-counter)
  - src/temporal/persistence.py (single-object TTL)
  - BoxHolder in src/infer_stream.py (state machine + EMA)

Design principles:
  1. N-of-M confirmation gate prevents single-frame FP amplification
  2. Monotonic threshold decay eliminates oscillation bugs
  3. EMA confidence smoothing for stable overlays
  4. Mask + Paris classification metadata propagation
  5. Duplicate track ID deduplication per frame
  6. Configurable max_hold_frames with proper bypass at 0
  7. Grace-period cleanup prevents aggressive smoother resets
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Maximum number of doubt events recorded per track to prevent unbounded growth
_MAX_DOUBT_EVENTS = 200

import numpy as np


@dataclass
class TrackedObject:
    """State for a single tracked polyp across frames."""
    track_id: int
    box: Optional[np.ndarray] = None          # [x1, y1, x2, y2]
    confidence: float = 0.0
    smoothed_confidence: float = 0.0
    mask: Optional[np.ndarray] = None         # PraNet segmentation mask
    paris_class: Optional[str] = None         # Paris classification label
    state: str = "DETECTING"                  # DETECTING | HOLDING | LOST
    lost_frames: int = 0
    detection_history: deque = field(default_factory=lambda: deque(maxlen=10))
    _ema_initialized: bool = False
    
    # New fields for Detection Timeline and Doubt Tracking
    first_detected_frame: int = -1
    last_detected_frame: int = -1
    max_confidence: float = 0.0
    doubt_score: float = 0.0
    is_doubtful: bool = False
    doubt_events: List[int] = field(default_factory=list)
    last_box: Optional[np.ndarray] = None

    def reset_for_pool(self):
        """Reset state for object reuse (not currently used, reserved)."""
        self.box = None
        self.confidence = 0.0
        self.smoothed_confidence = 0.0
        self.mask = None
        self.paris_class = None
        self.state = "DETECTING"
        self.lost_frames = 0
        self.detection_history.clear()
        self._ema_initialized = False
        # Reset doubt/timeline fields
        self.first_detected_frame = -1
        self.last_detected_frame = -1
        self.max_confidence = 0.0
        self.doubt_score = 0.0
        self.is_doubtful = False
        self.doubt_events = []
        self.last_box = None


class ChakraTemporalTracker:
    """
    Unified temporal tracker for the ChakraModel pipeline.

    Replaces all legacy persistence implementations with a single,
    clinically-validated state machine.

    Parameters
    ----------
    confirm_n : int
        Number of detections required in the last `confirm_m` frames
        before a track is confirmed (transitions to HOLDING-eligible).
        Default: 3
    confirm_m : int
        Window size for the N-of-M confirmation gate.
        Default: 5
    max_hold_frames : int
        Maximum frames to hold a box after detection is lost.
        Set to 0 to disable holding entirely.
        Default: 8
    confidence_threshold : float
        Minimum confidence to consider a detection valid.
        Uses >= (inclusive) consistently.
        Default: 0.35
    ema_alpha : float
        Exponential moving average smoothing factor for confidence.
        Higher = more responsive. Lower = smoother.
        Default: 0.4
    decay_rate : float
        Multiplicative decay applied to smoothed confidence each lost frame.
        Default: 0.85
    cleanup_grace : int
        Number of frames after LOST before purging a track's state entirely.
        Prevents aggressive smoother resets on 1-frame drops.
        Default: 5
    window_size : int
        Maximum history length for the detection deque.
        Default: 10
    """

    def __init__(
        self,
        confirm_n: int = 3,
        confirm_m: int = 5,
        max_hold_frames: int = 8,
        confidence_threshold: float = 0.35,
        ema_alpha: float = 0.4,
        decay_rate: float = 0.85,
        cleanup_grace: int = 5,
        window_size: int = 10,
        doubt_drops_track: bool = False,
    ):
        self.confirm_n = confirm_n
        self.confirm_m = confirm_m
        self.max_hold_frames = max_hold_frames
        self.confidence_threshold = confidence_threshold
        self.ema_alpha = ema_alpha
        self.decay_rate = decay_rate
        self.cleanup_grace = cleanup_grace
        self.window_size = window_size
        self.doubt_drops_track = doubt_drops_track
        
        self.current_frame_idx = 0

        # Doubt hysteresis thresholds to prevent warning flicker
        self._doubt_enter_threshold = 0.5
        self._doubt_exit_threshold = 0.3

        # Track state: track_id -> TrackedObject
        self._tracks: Dict[int, TrackedObject] = {}
        # Frames since a track was last seen (for grace-period cleanup)
        self._gone_frames: Dict[int, int] = defaultdict(int)

    def _ema_update(self, track: TrackedObject, raw_conf: float) -> float:
        """Update EMA confidence smoother."""
        if not track._ema_initialized:
            track.smoothed_confidence = raw_conf
            track._ema_initialized = True
        else:
            track.smoothed_confidence = (
                self.ema_alpha * raw_conf
                + (1.0 - self.ema_alpha) * track.smoothed_confidence
            )
        return track.smoothed_confidence

    def _is_confirmed(self, track: TrackedObject) -> bool:
        """
        N-of-M confirmation gate (FR-2.2).
        Returns True if the track has been detected in at least N
        of the last M frames.
        """
        history = track.detection_history
        if len(history) < self.confirm_m:
            # Not enough history yet — check what we have
            recent = list(history)
        else:
            recent = list(history)[-self.confirm_m:]

        return sum(recent) >= self.confirm_n

    def _monotonic_threshold(self, track: TrackedObject) -> float:
        """
        Monotonic threshold degradation (FR-2.3).
        Returns the confidence threshold that monotonically increases
        (becomes stricter) as the track ages without detections,
        eliminating the oscillation bug from the legacy dual-branch logic.
        """
        if track.lost_frames == 0:
            return self.confidence_threshold

        # Exponential tightening: threshold rises toward 1.0 as lost_frames grows
        # This ensures display probability monotonically decreases after last detection
        base = self.confidence_threshold
        tightened = base + (1.0 - base) * (1.0 - self.decay_rate ** track.lost_frames)
        return min(tightened, 1.0)

    def _deduplicate_detections(
        self, detections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        FR-2.4: Deduplicate detections by track_id.
        If multiple detections share the same track_id in one frame,
        keep only the one with the highest confidence.
        """
        best: Dict[int, Dict[str, Any]] = {}
        for det in detections:
            tid = det.get("track_id")
            if tid is None:
                continue
            if tid not in best or det.get("conf", 0) > best[tid].get("conf", 0):
                best[tid] = det
        return list(best.values())

    @staticmethod
    def _compute_iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
        """
        Compute IoU between two boxes with guards for degenerate/inverted boxes.
        Returns -1.0 if either box is degenerate (signals "skip doubt update").
        """
        x1a, y1a, x2a, y2a = box_a
        x1b, y1b, x2b, y2b = box_b
        w_a, h_a = max(0.0, x2a - x1a), max(0.0, y2a - y1a)
        w_b, h_b = max(0.0, x2b - x1b), max(0.0, y2b - y1b)
        area_a = w_a * h_a
        area_b = w_b * h_b
        # Guard: degenerate box — don't let it spike doubt
        if area_a < 1.0 or area_b < 1.0:
            return -1.0
        inter_w = max(0.0, min(x2a, x2b) - max(x1a, x1b))
        inter_h = max(0.0, min(y2a, y2b) - max(y1a, y1b))
        inter_area = inter_w * inter_h
        union = area_a + area_b - inter_area
        return inter_area / (union + 1e-6)

    def _update_doubt(self, track: TrackedObject, iou: float, frame_idx: int) -> None:
        """
        Centralized doubt score update with hysteresis.
        Called from both valid-detection and low-confidence branches.

        Parameters
        ----------
        iou : float
            IoU between consecutive boxes. Use -1.0 to signal "no IoU available"
            (e.g., first detection, degenerate box). Use -2.0 for missing-track
            doubt (object not seen this frame).
        """
        if iou == -1.0:
            # Degenerate box or first detection — don't change doubt
            return

        if iou == -2.0:
            # Missing track: mild doubt increase
            track.doubt_score = min(1.0, track.doubt_score + 0.15)
        elif iou < 0.2:
            # High spatial volatility
            track.doubt_score = min(1.0, track.doubt_score + 0.3)
        else:
            # Stable — decay doubt
            track.doubt_score = max(0.0, track.doubt_score - 0.1)

        # Hysteresis: different thresholds for entering vs. exiting doubt
        was_doubtful = track.is_doubtful
        if not was_doubtful:
            track.is_doubtful = track.doubt_score >= self._doubt_enter_threshold
        else:
            track.is_doubtful = track.doubt_score > self._doubt_exit_threshold

        # Log doubt entry event (capped)
        if track.is_doubtful and not was_doubtful:
            if len(track.doubt_events) < _MAX_DOUBT_EVENTS:
                track.doubt_events.append(frame_idx)

    def update(
        self,
        detections: List[Dict[str, Any]],
    ) -> List[TrackedObject]:
        """
        Process one frame of detections and return the list of
        TrackedObjects that should be rendered.

        Parameters
        ----------
        detections : list of dict
            Each dict must have:
              - 'track_id': int
              - 'box': array-like [x1, y1, x2, y2]
              - 'conf': float
            Optional keys:
              - 'mask': np.ndarray (PraNet segmentation mask)
              - 'paris': str (Paris classification label)

        Returns
        -------
        list of TrackedObject
            Objects in DETECTING or HOLDING state that should be drawn.
        """
        # FR-2.4: Deduplicate
        detections = self._deduplicate_detections(detections)

        active_ids_this_frame = set()

        # --- Process current detections ---
        for det in detections:
            tid = det["track_id"]
            conf = det["conf"]
            box = np.asarray(det["box"], dtype=np.float32)
            mask = det.get("mask")
            paris = det.get("paris")

            active_ids_this_frame.add(tid)
            self._gone_frames[tid] = 0

            # Create or retrieve track
            if tid not in self._tracks:
                self._tracks[tid] = TrackedObject(
                    track_id=tid,
                    detection_history=deque(maxlen=self.window_size),
                )

            track = self._tracks[tid]

            # FR-2.5: Use >= consistently
            is_valid = conf >= self.confidence_threshold
            track.detection_history.append(1 if is_valid else 0)

            if is_valid:
                # Spatial doubt calculation via IoU
                if track.last_box is not None and track.box is not None:
                    iou = self._compute_iou(track.last_box, box)
                    self._update_doubt(track, iou, self.current_frame_idx)
                
                track.last_box = box
                track.box = box
                track.confidence = conf
                track.max_confidence = max(track.max_confidence, conf)
                track.last_detected_frame = self.current_frame_idx
                if track.first_detected_frame == -1:
                    track.first_detected_frame = self.current_frame_idx
                    
                track.lost_frames = 0
                self._ema_update(track, conf)

                # Update mask/paris if provided
                if mask is not None:
                    track.mask = mask
                if paris is not None:
                    track.paris_class = paris

                # Check confirmation gate before allowing DETECTING
                if self._is_confirmed(track):
                    track.state = "DETECTING"
                else:
                    # Not yet confirmed — don't display
                    track.state = "PENDING"
            else:
                # Low-confidence detection: still run doubt heuristics
                if track.last_box is not None and track.box is not None:
                    iou = self._compute_iou(track.last_box, box)
                    self._update_doubt(track, iou, self.current_frame_idx)
                track.last_box = box

                self._ema_update(track, conf)
                # Low confidence detection — enter HOLDING if confirmed, else stay PENDING
                if self._is_confirmed(track) and self.max_hold_frames > 0:
                    track.state = "HOLDING"
                    track.lost_frames = 0
                else:
                    track.state = "PENDING"

        # --- Update tracks NOT seen this frame ---
        for tid, track in list(self._tracks.items()):
            if tid in active_ids_this_frame:
                continue

            # Missing track: accumulate doubt AND update is_doubtful via hysteresis
            self._update_doubt(track, -2.0, self.current_frame_idx)
            track.detection_history.append(0)
            track.lost_frames += 1
            self._gone_frames[tid] += 1

            # Decay smoothed confidence
            self._ema_update(track, 0.0)

            # FR-3.4: If max_hold_frames=0, skip HOLDING entirely
            if self.max_hold_frames == 0:
                track.state = "LOST"
            elif track.lost_frames <= self.max_hold_frames:
                # Only hold if the track was previously confirmed
                if self._is_confirmed(track):
                    track.state = "HOLDING"
                else:
                    track.state = "LOST"
            else:
                track.state = "LOST"

        # --- Cleanup: purge tracks that have been LOST beyond grace period ---
        purge_ids = []
        for tid, gone_count in list(self._gone_frames.items()):
            if gone_count > self.max_hold_frames + self.cleanup_grace:
                purge_ids.append(tid)

        for tid in purge_ids:
            self._tracks.pop(tid, None)
            self._gone_frames.pop(tid, None)

        # --- Collect displayable tracks ---
        display = []
        for track in self._tracks.values():
            if track.state in ("DETECTING", "HOLDING") and track.box is not None:
                if self.doubt_drops_track and track.is_doubtful:
                    track.state = "LOST"
                    # Reset doubt so the track can recover if re-detected
                    track.doubt_score = 0.0
                    track.is_doubtful = False
                    continue
                
                # FR-2.3: Check monotonic threshold
                threshold = self._monotonic_threshold(track)
                if track.smoothed_confidence >= threshold:
                    display.append(track)
                    
        self.current_frame_idx += 1
        return display

    def get_track(self, track_id: int) -> Optional[TrackedObject]:
        """Retrieve a specific track's state."""
        return self._tracks.get(track_id)

    def get_all_tracks(self) -> Dict[int, TrackedObject]:
        """Return all tracked objects (including LOST/PENDING)."""
        return dict(self._tracks)

    @property
    def active_count(self) -> int:
        """Number of currently displayable tracks."""
        return sum(
            1 for t in self._tracks.values()
            if t.state in ("DETECTING", "HOLDING")
        )
