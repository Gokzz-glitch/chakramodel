from dataclasses import dataclass


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