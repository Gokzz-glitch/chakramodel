from collections import defaultdict, deque

class TemporalPersistenceFilter:
    def __init__(self, window_size=10, confidence_threshold=0.4, persistence_threshold=0.6):
        """
        window_size: Number of frames to keep in history
        confidence_threshold: Minimum YOLO confidence to consider a detection valid
        persistence_threshold: Fraction of frames in window that must have a detection to display it
        """
        self.window_size = window_size
        self.confidence_threshold = confidence_threshold
        self.persistence_threshold = persistence_threshold
        
        # Maps track_id -> deque of recent detection statuses (1 or 0)
        self.history = defaultdict(lambda: deque(maxlen=window_size))
        # Maps track_id -> last known bounding box [x1, y1, x2, y2]
        self.last_known_bbox = {}
        # Maps track_id -> last known confidence
        self.last_known_conf = {}
        # Maps track_id -> missed frames count
        self.missed_frames = defaultdict(int)

    def update_and_filter(self, current_frame_detections):
        """
        current_frame_detections: List of dicts [{'track_id': id, 'bbox': [x1,y1,x2,y2], 'conf': conf}, ...]
        Returns: List of bounding boxes to actually draw
        """
        active_ids_this_frame = set()
        
        for det in current_frame_detections:
            track_id = det['track_id']
            conf = det['conf']
            bbox = det['bbox']
            
            if track_id is None:
                continue # Ignore un-tracked objects
                
            active_ids_this_frame.add(track_id)
            
            # Record detection
            if conf >= self.confidence_threshold:
                self.history[track_id].append(1)
                self.last_known_bbox[track_id] = bbox
                self.last_known_conf[track_id] = conf
                self.missed_frames[track_id] = 0
            else:
                self.history[track_id].append(0)

        # Update history for tracks NOT seen in this frame
        for track_id in list(self.history.keys()):
            if track_id not in active_ids_this_frame:
                self.history[track_id].append(0)
                self.missed_frames[track_id] += 1
                
                # Cleanup old tracks that have been gone longer than the window size
                if self.missed_frames[track_id] > self.window_size:
                    del self.history[track_id]
                    if track_id in self.last_known_bbox:
                        del self.last_known_bbox[track_id]
                        del self.last_known_conf[track_id]
                    del self.missed_frames[track_id]

        # Determine which boxes to actually display based on persistence logic
        display_boxes = []
        for track_id, h in self.history.items():
            # If we don't have enough history yet, be conservative and require high confidence
            if len(h) < self.window_size // 2:
                persistence_score = sum(h) / len(h) if len(h) > 0 else 0
                if persistence_score >= 0.8: # Stricter when track is brand new
                    if track_id in self.last_known_bbox:
                        display_boxes.append({
                            'track_id': track_id,
                            'bbox': self.last_known_bbox[track_id],
                            'conf': self.last_known_conf[track_id]
                        })
            else:
                # Normal persistence check
                persistence_score = sum(h) / len(h)
                if persistence_score >= self.persistence_threshold:
                    if track_id in self.last_known_bbox:
                        display_boxes.append({
                            'track_id': track_id,
                            'bbox': self.last_known_bbox[track_id],
                            'conf': self.last_known_conf[track_id]
                        })
                        
        return display_boxes
