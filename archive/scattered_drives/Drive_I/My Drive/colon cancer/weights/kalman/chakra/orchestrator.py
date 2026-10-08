from typing import Any
# No direct implementation imports allowed according to AD-14

class Pipeline:
    def __init__(self, detector: Any, tracker: Any, persistence_filter: Any, conformal_calibrator: Any, renderer: Any):
        self.detector = detector
        self.tracker = tracker
        self.persistence_filter = persistence_filter
        self.conformal_calibrator = conformal_calibrator
        self.renderer = renderer
        self.state = "UNINITIALIZED"
        
    def start(self):
        self.state = "READY"
        
    def process_frame(self, frame: Any) -> Any:
        if self.state not in ["READY", "RUNNING"]:
            raise RuntimeError("Pipeline must be started before processing frames")
        self.state = "RUNNING"
        # Mock logic
        return None
        
    def end_procedure(self):
        self.tracker.reset()
        self.persistence_filter.reset()
        self.state = "READY"
        
    def stop(self):
        self.state = "STOPPED"
