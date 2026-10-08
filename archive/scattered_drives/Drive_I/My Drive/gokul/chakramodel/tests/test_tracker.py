import pytest
import numpy as np
from src.temporal.tracker import ChakraTemporalTracker, TrackedObject

def test_event_logging():
    tracker = ChakraTemporalTracker(confirm_n=1, confirm_m=1, confidence_threshold=0.5)
    
    # Frame 0: detection
    detections = [{"track_id": 1, "box": [0, 0, 10, 10], "conf": 0.6}]
    tracks = tracker.update(detections)
    
    assert len(tracks) == 1
    t = tracks[0]
    assert t.first_detected_frame == 0
    assert t.last_detected_frame == 0
    assert t.max_confidence == 0.6
    
    # Frame 1: detection
    detections = [{"track_id": 1, "box": [1, 1, 11, 11], "conf": 0.8}]
    tracks = tracker.update(detections)
    
    t = tracks[0]
    assert t.first_detected_frame == 0
    assert t.last_detected_frame == 1
    assert t.max_confidence == 0.8

def test_doubt_heuristics_spatial_volatility():
    tracker = ChakraTemporalTracker(confirm_n=1, confirm_m=1, confidence_threshold=0.5)
    
    # Frame 0: stable
    detections = [{"track_id": 2, "box": [0, 0, 10, 10], "conf": 0.9}]
    tracker.update(detections)
    
    t = tracker.get_track(2)
    assert not t.is_doubtful
    assert len(t.doubt_events) == 0
    
    # Frame 1: erratic jump (IoU = 0)
    # the jump will trigger doubt increase (+0.3)
    detections = [{"track_id": 2, "box": [100, 100, 110, 110], "conf": 0.9}]
    tracker.update(detections)
    
    # Frame 2: another erratic jump (+0.3)
    detections = [{"track_id": 2, "box": [200, 200, 210, 210], "conf": 0.9}]
    tracker.update(detections) 
    
    t = tracker.get_track(2)
    assert t.doubt_score > 0
    assert t.is_doubtful
    assert len(t.doubt_events) > 0

def test_doubt_drops_track_policy():
    tracker = ChakraTemporalTracker(confirm_n=1, confirm_m=1, confidence_threshold=0.5, doubt_drops_track=True)
    
    # Frame 0: stable
    detections = [{"track_id": 3, "box": [0, 0, 10, 10], "conf": 0.9}]
    tracks = tracker.update(detections)
    assert len(tracks) == 1
    
    # Frame 1: erratic jump
    detections = [{"track_id": 3, "box": [100, 100, 110, 110], "conf": 0.9}]
    # doubt score +0.3
    tracks = tracker.update(detections) 
    
    # Frame 2: erratic jump again
    detections = [{"track_id": 3, "box": [200, 200, 210, 210], "conf": 0.9}]
    # doubt score goes to +0.6, which >= 0.5, so is_doubtful becomes True.
    # Because doubt_drops_track is True, it should not be in display tracks.
    tracks = tracker.update(detections)
    
    assert len(tracks) == 0
    t = tracker.get_track(3)
    assert t.state == "LOST"
    # After drop, doubt should be reset so track can recover
    assert t.doubt_score == 0.0
    assert not t.is_doubtful


def test_degenerate_box_does_not_spike_doubt():
    """Zero-area boxes from detector artifacts should not trigger doubt."""
    tracker = ChakraTemporalTracker(confirm_n=1, confirm_m=1, confidence_threshold=0.5)
    
    # Frame 0: valid box
    tracker.update([{"track_id": 10, "box": [50, 50, 60, 60], "conf": 0.9}])
    
    # Frame 1: degenerate box (zero width)
    tracker.update([{"track_id": 10, "box": [50, 50, 50, 60], "conf": 0.9}])
    
    t = tracker.get_track(10)
    assert t.doubt_score == 0.0, "Degenerate box should not change doubt_score"


def test_hysteresis_prevents_flicker():
    """Doubt should not toggle rapidly when score oscillates near threshold."""
    tracker = ChakraTemporalTracker(confirm_n=1, confirm_m=1, confidence_threshold=0.5)
    
    # Build up doubt to 0.6 (above enter threshold 0.5)
    tracker.update([{"track_id": 20, "box": [0, 0, 10, 10], "conf": 0.9}])
    tracker.update([{"track_id": 20, "box": [100, 100, 110, 110], "conf": 0.9}])  # +0.3
    tracker.update([{"track_id": 20, "box": [200, 200, 210, 210], "conf": 0.9}])  # +0.3 = 0.6
    
    t = tracker.get_track(20)
    assert t.is_doubtful  # entered at >= 0.5
    
    # One stable frame: 0.6 - 0.1 = 0.5 -- still above exit threshold (0.3)
    tracker.update([{"track_id": 20, "box": [201, 201, 211, 211], "conf": 0.9}])
    t = tracker.get_track(20)
    assert t.is_doubtful, "Should stay doubtful due to hysteresis (score=0.5 > exit=0.3)"
    
    # Two more stable: 0.5 - 0.1 = 0.4, then 0.4 - 0.1 = 0.3 (float imprecision keeps it just above 0.3)
    tracker.update([{"track_id": 20, "box": [202, 202, 212, 212], "conf": 0.9}])
    tracker.update([{"track_id": 20, "box": [203, 203, 213, 213], "conf": 0.9}])
    t = tracker.get_track(20)
    assert t.is_doubtful, "Float imprecision: 0.30...04 > 0.3, still doubtful"
    
    # One more stable frame brings it to ~0.2, clearly below exit threshold
    tracker.update([{"track_id": 20, "box": [204, 204, 214, 214], "conf": 0.9}])
    t = tracker.get_track(20)
    assert not t.is_doubtful, "Should exit doubt when score drops well below exit threshold"


def test_low_confidence_detection_runs_doubt():
    """Low-confidence detections should still accumulate doubt from spatial volatility."""
    tracker = ChakraTemporalTracker(confirm_n=1, confirm_m=1, confidence_threshold=0.5)
    
    # Frame 0: valid detection sets last_box and box
    tracker.update([{"track_id": 30, "box": [0, 0, 10, 10], "conf": 0.9}])
    
    # Frame 1: low-confidence but spatially volatile (should still affect doubt)
    tracker.update([{"track_id": 30, "box": [200, 200, 210, 210], "conf": 0.3}])
    
    t = tracker.get_track(30)
    assert t.doubt_score > 0.0, "Low-confidence detections should still accumulate doubt"


def test_missing_track_updates_is_doubtful():
    """Tracks not seen for several frames should eventually become doubtful via hysteresis."""
    tracker = ChakraTemporalTracker(confirm_n=1, confirm_m=1, confidence_threshold=0.5, max_hold_frames=20)
    
    # Frame 0: valid detection
    tracker.update([{"track_id": 40, "box": [10, 10, 30, 30], "conf": 0.9}])
    
    # Next 5 frames: track disappears. Each adds +0.15 doubt.
    # After 4 frames: 0.6 >= 0.5 enter threshold → is_doubtful
    for _ in range(5):
        tracker.update([])
    
    t = tracker.get_track(40)
    assert t is not None
    assert t.is_doubtful, "Track missing for many frames should become doubtful"
    assert len(t.doubt_events) > 0, "Doubt entry should be logged"


def test_doubt_drops_track_allows_recovery():
    """After doubt_drops_track kills a track, re-detection should allow recovery."""
    tracker = ChakraTemporalTracker(confirm_n=1, confirm_m=1, confidence_threshold=0.5, doubt_drops_track=True)
    
    # Build doubt and drop
    tracker.update([{"track_id": 50, "box": [0, 0, 10, 10], "conf": 0.9}])
    tracker.update([{"track_id": 50, "box": [100, 100, 110, 110], "conf": 0.9}])
    tracker.update([{"track_id": 50, "box": [200, 200, 210, 210], "conf": 0.9}])
    
    t = tracker.get_track(50)
    assert t.state == "LOST"
    assert t.doubt_score == 0.0  # Reset after drop
    
    # Re-detect with stable position — should recover
    tracks = tracker.update([{"track_id": 50, "box": [200, 200, 210, 210], "conf": 0.9}])
    t = tracker.get_track(50)
    assert t.state != "LOST", "Track should recover after doubt reset"


def test_reset_for_pool_clears_doubt_fields():
    """reset_for_pool should clear all doubt and timeline state."""
    t = TrackedObject(track_id=99)
    t.doubt_score = 0.8
    t.is_doubtful = True
    t.doubt_events = [1, 2, 3]
    t.last_box = np.array([0, 0, 10, 10])
    t.first_detected_frame = 5
    t.last_detected_frame = 20
    t.max_confidence = 0.95
    
    t.reset_for_pool()
    
    assert t.doubt_score == 0.0
    assert not t.is_doubtful
    assert len(t.doubt_events) == 0
    assert t.last_box is None
    assert t.first_detected_frame == -1
    assert t.last_detected_frame == -1
    assert t.max_confidence == 0.0
