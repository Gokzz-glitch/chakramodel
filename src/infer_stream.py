import cv2
import numpy as np
import argparse
import os
from ultralytics import YOLO

class ConfidenceSmoother:
    """ Exponential Moving Average (EMA) to prevent sudden jumps in confidence """
    def __init__(self, alpha=0.4):
        self.alpha = alpha
        self.smoothed = 0.0

    def update(self, raw_conf):
        if self.smoothed == 0.0:
            self.smoothed = raw_conf
        else:
            self.smoothed = (self.alpha * raw_conf) + ((1 - self.alpha) * self.smoothed)
        return self.smoothed

class BoxHolder:
    """ Manages the temporal state (DETECTING, HOLDING, LOST) of a polyp across frames """
    def __init__(self, track_id, max_hold_frames=8):
        self.track_id = track_id
        self.max_hold_frames = max_hold_frames
        self.lost_frames = 0
        self.box = None
        self.smoother = ConfidenceSmoother(alpha=0.4)
        self.state = "DETECTING"

    def update_detection(self, box, conf):
        self.box = box
        self.lost_frames = 0
        smoothed_conf = self.smoother.update(conf)
        
        # If smoothed confidence is solid, we are actively DETECTING
        if smoothed_conf > 0.4:
            self.state = "DETECTING"
        else:
            self.state = "HOLDING"

    def update_lost(self):
        self.lost_frames += 1
        self.smoother.update(0.0) # Decay the confidence
        
        if self.lost_frames <= self.max_hold_frames:
            self.state = "HOLDING"
        else:
            self.state = "LOST"

def is_artifact_frame(frame):
    """
    OpenCV Heuristic to detect bad frames (blur, bubbles, feces).
    Triggers the ARTIFACT (Red Border) warning.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # 1. Laplacian variance detects severe motion blur or water distortion
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if lap_var < 80:  
        return True
        
    # 2. Average brightness detects heavy glare or dark occlusion (feces)
    avg_brightness = np.mean(gray)
    if avg_brightness < 30 or avg_brightness > 220:
        return True
        
    return False

def draw_ui(frame, active_holders, is_artifact):
    """ Renders the Green/Yellow/Red visual states onto the frame """
    h, w = frame.shape[:2]
    
    if is_artifact:
        # ARTIFACT STATE: Screen gets a red border flash
        cv2.rectangle(frame, (0, 0), (w, h), (0, 0, 255), 15)
        cv2.putText(frame, "ARTIFACT WARNING", (30, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    for track_id, holder in active_holders.items():
        if holder.state == "LOST" or holder.box is None:
            continue
            
        x1, y1, x2, y2 = map(int, holder.box)
        
        if holder.state == "DETECTING":
            color = (0, 255, 0) # Green Box
            label = f"Polyp (ID: {track_id}) [DETECTING]"
        elif holder.state == "HOLDING":
            color = (0, 255, 255) # Yellow Box
            label = f"Polyp (ID: {track_id}) [HOLDING]"
            
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        cv2.putText(frame, label, (x1, max(0, y1 - 10)), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
    return frame

def process_video_stream(input_source, output_path, model_path):
    print("Initializing YOLO, Kalman Tracker, and Temporal UI...")
    
    # Allow testing the UI with the base YOLOv8n model while training finishes
    if not os.path.exists(model_path):
        print(f"Trained weights not found at {model_path}. Using base yolov8n.pt for UI testing.")
        model = YOLO("yolov8n.pt")
    else:
        model = YOLO(model_path)

    source = int(input_source) if input_source.isdigit() else input_source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    width, height = int(cap.get(3)), int(cap.get(4))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'avc1'), int(fps), (width, height))
    
    active_holders = {} # Dictionary mapping track_id to BoxHolder
    
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            
            # 1. ByteTrack (Kalman Tracking)
            # tracker="bytetrack.yaml" applies Kalman filtering automatically in Ultralytics
            results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.2, iou=0.5, verbose=False)
            
            # 2. Check for Artifacts
            is_artifact = is_artifact_frame(frame)
            
            # 3. Update BoxHolders and Confidence Smoothing
            current_track_ids = []
            
            if results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                track_ids = results[0].boxes.id.int().cpu().numpy()
                confs = results[0].boxes.conf.cpu().numpy()
                
                for box, track_id, conf in zip(boxes, track_ids, confs):
                    current_track_ids.append(track_id)
                    if track_id not in active_holders:
                        active_holders[track_id] = BoxHolder(track_id, max_hold_frames=8)
                    
                    active_holders[track_id].update_detection(box, conf)
            
            # Update holders that were missing in this frame (triggering HOLDING state)
            for track_id, holder in active_holders.items():
                if track_id not in current_track_ids:
                    holder.update_lost()
            
            # Delete tracks that hit LOST state (exceeded 8 frames)
            active_holders = {tid: h for tid, h in active_holders.items() if h.state != "LOST"}
            
            # 4. Draw Custom UI and Save
            output_frame = draw_ui(frame, active_holders, is_artifact)
            out.write(output_frame)
            
    except KeyboardInterrupt:
        print("\nProcessing interrupted.")
    finally:
        cap.release()
        out.release()
        print(f"Demo saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="Video file or camera '0'")
    parser.add_argument("--output", type=str, default="ui_demo.mp4")
    parser.add_argument("--weights", type=str, default=r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt")
    args = parser.parse_args()
    process_video_stream(args.input, args.output, args.weights)
