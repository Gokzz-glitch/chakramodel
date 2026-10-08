"""
DEPRECATED: This module is superseded by src.temporal.tracker.ChakraTemporalTracker.
It is retained for backward compatibility only. All new code should import from
src.temporal.tracker instead. This module will be removed in a future release.
"""
import warnings
warnings.warn(
    "src.temporal.persistence_filter.TemporalPersistenceFilter is deprecated. "
    "Use src.temporal.tracker.ChakraTemporalTracker instead.",
    DeprecationWarning,
    stacklevel=2,
)

import numpy as np

class TemporalPersistenceFilter:
    """
    Suppresses 'alert fatigue' and flickering bounding boxes by persisting recent 
    track IDs across missed frames. Evaluated as highly critical in the 254-paper literature review.
    """
    def __init__(self, persistence_frames=15, confidence_threshold=0.35):
        self.persistence_frames = persistence_frames
        self.confidence_threshold = confidence_threshold
        self.active_tracks = {}

    def update(self, current_frame_boxes, current_frame_ids, current_frame_confs):
        """
        Takes the raw output from model.track() and applies persistence logic.
        """
        # Decay life of existing tracks
        for track_id in list(self.active_tracks.keys()):
            self.active_tracks[track_id]['life'] -= 1
            if self.active_tracks[track_id]['life'] <= 0:
                del self.active_tracks[track_id]

        # Update with new observations
        output_boxes = []
        output_ids = []
        
        for box, t_id, conf in zip(current_frame_boxes, current_frame_ids, current_frame_confs):
            if conf >= self.confidence_threshold:
                self.active_tracks[t_id] = {
                    'box': box,
                    'life': self.persistence_frames
                }
        
        # Return all currently active tracks
        for t_id, data in self.active_tracks.items():
            output_boxes.append(data['box'])
            output_ids.append(t_id)
            
        return output_boxes, output_ids
