import cv2
import numpy as np
import argparse
import os
import threading
import time
import io
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from ultralytics import YOLO

from src.pranet_segmenter import PraNetSegmenter
from src.paris_classifier import ParisClassifier
from src.clinical_report import ClinicalReportGenerator

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
        self.last_mask = None
        self.last_paris = None

    def update_detection(self, box, conf):
        self.box = box
        self.lost_frames = 0
        smoothed_conf = self.smoother.update(conf)
        
        if smoothed_conf > 0.35:
            self.state = "DETECTING"
        else:
            self.state = "HOLDING"

    def update_lost(self):
        self.lost_frames += 1
        self.smoother.update(0.0) # Decay confidence
        
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

def draw_header_banner(frame, title, subtitle=None, bg_color=(20, 24, 33), text_color=(240, 240, 240)):
    """ Draws a sleek professional header banner on top of the frame """
    h, w = frame.shape[:2]
    banner_h = 42
    
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, banner_h), bg_color, -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
    
    # Header Title
    cv2.putText(frame, title, (14, 28), cv2.FONT_HERSHEY_DUPLEX, 0.7, text_color, 2, cv2.LINE_AA)
    
    # Subtitle / Tag
    if subtitle:
        sub_size = cv2.getTextSize(subtitle, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        cv2.putText(frame, subtitle, (w - sub_size[0] - 14, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 175, 200), 1, cv2.LINE_AA)
        
    return frame

def render_panel1_raw(frame):
    """ Panel 1: Pure Raw Video Feed """
    p1 = frame.copy()
    return draw_header_banner(p1, "1. RAW VIDEO FEED", "Unprocessed Colonoscopy", bg_color=(30, 30, 40), text_color=(220, 220, 220))

def render_panel2_baseline_yolo(frame, model, conf_thresh=0.2):
    """ Panel 2: Baseline YOLOv8 Detection (No Tracking, No Memory, Demonstrates Flicker) """
    p2 = frame.copy()
    results = model.predict(p2, conf=conf_thresh, verbose=False)[0]
    
    boxes = results.boxes
    if len(boxes) > 0:
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            conf = float(box.conf[0].cpu().numpy())
            
            # Simple bounding box
            cv2.rectangle(p2, (x1, y1), (x2, y2), (0, 165, 255), 2)
            cv2.putText(p2, f"Polyp {conf:.2f}", (x1, max(45, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2, cv2.LINE_AA)
    
    return draw_header_banner(p2, "2. BASELINE YOLOv8", "No Tracking (Raw Flicker)", bg_color=(40, 25, 20), text_color=(0, 165, 255))

def render_panel3_kalman(frame, model, track_smoothers, conf_thresh=0.2):
    """ Panel 3: YOLOv8 + Kalman Tracking (ByteTrack) & EMA Score Smoothing """
    p3 = frame.copy()
    results = model.track(p3, persist=True, tracker="bytetrack.yaml", conf=conf_thresh, verbose=False)[0]
    
    if results.boxes.id is not None:
        boxes = results.boxes.xyxy.cpu().numpy()
        track_ids = results.boxes.id.int().cpu().numpy()
        confs = results.boxes.conf.cpu().numpy()
        
        for box, track_id, conf in zip(boxes, track_ids, confs):
            x1, y1, x2, y2 = map(int, box)
            if track_id not in track_smoothers:
                track_smoothers[track_id] = ConfidenceSmoother(alpha=0.35)
            
            smoothed_score = track_smoothers[track_id].update(conf)
            
            # Cyan Kalman tracked box
            cv2.rectangle(p3, (x1, y1), (x2, y2), (255, 200, 0), 2)
            label = f"ID #{track_id} [Kalman Active] {smoothed_score:.2f}"
            cv2.putText(p3, label, (x1, max(45, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 0), 2, cv2.LINE_AA)
                        
    return draw_header_banner(p3, "3. YOLO + KALMAN FILTER", "ByteTrack Trajectory Prediction", bg_color=(20, 35, 45), text_color=(255, 200, 0))

def render_panel4_full_chakramodel(frame, model, pranet_seg, paris_clf, active_holders, is_artifact, conf_thresh=0.2):
    """
    Panel 4: Full ChakraModel Clinical Suite
    - Stage 1: YOLOv8 + ByteTrack Kalman Tracking + BoxHolder State Machine
    - Stage 2: PraNet Sub-Pixel Reverse Attention Segmentation + Paris Classification Badges
    - Artifact Awareness: Real-time alert borders
    """
    p4 = frame.copy()
    h, w = p4.shape[:2]
    
    # 1. ByteTrack Forward Pass (Stage 1)
    results = model.track(p4, persist=True, tracker="bytetrack.yaml", conf=conf_thresh, verbose=False)[0]
    current_track_ids = []
    current_frame_dets = []
    
    if results.boxes.id is not None:
        boxes = results.boxes.xyxy.cpu().numpy()
        track_ids = results.boxes.id.int().cpu().numpy()
        confs = results.boxes.conf.cpu().numpy()
        
        for box, track_id, conf in zip(boxes, track_ids, confs):
            current_track_ids.append(track_id)
            if track_id not in active_holders:
                active_holders[track_id] = BoxHolder(track_id, max_hold_frames=8)
            active_holders[track_id].update_detection(box, conf)
            
    # Update lost tracks for HOLDING state
    for track_id, holder in active_holders.items():
        if track_id not in current_track_ids:
            holder.update_lost()
            
    # Purge LOST tracks
    active_holders_filtered = {tid: h for tid, h in active_holders.items() if h.state != "LOST"}
    active_holders.clear()
    active_holders.update(active_holders_filtered)
    
    # ARTIFACT Alert: Red border flash
    if is_artifact:
        cv2.rectangle(p4, (0, 0), (w, h), (0, 0, 255), 8)
        cv2.putText(p4, "ARTIFACT ALERT (Blur / Specularity)", (w - 360, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2, cv2.LINE_AA)
                    
    # Render Stage 2: PraNet Segmentation & Paris Staging
    for track_id, holder in active_holders.items():
        if holder.state == "LOST" or holder.box is None:
            continue
            
        x1, y1, x2, y2 = map(int, holder.box)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        if x2 <= x1 or y2 <= y1:
            continue
            
        # Crop ROI for PraNet Micro-Refiner
        roi_crop = frame[y1:y2, x1:x2]
        
        if holder.state == "DETECTING" and roi_crop.size > 0:
            mask, contours, seg_conf = pranet_seg.segment_roi(roi_crop)
            holder.last_mask = mask
            paris_info = paris_clf.analyze_polyp((x1, y1, x2, y2), mask=mask, contour=contours[0] if contours else None)
            holder.last_paris = paris_info
        else:
            mask = holder.last_mask
            paris_info = holder.last_paris or paris_clf.analyze_polyp((x1, y1, x2, y2))
            
        # 1. Overlay PraNet Sub-Pixel Segmentation Mask
        if mask is not None:
            mask_color = (0, 255, 128) if holder.state == "DETECTING" else (0, 200, 255)
            p4 = pranet_seg.overlay_mask_on_frame(p4, (x1, y1, x2, y2), mask, color=mask_color, alpha=0.40)
            
        # 2. Draw Bounding Box & State
        box_color = (0, 255, 0) if holder.state == "DETECTING" else (0, 230, 255)
        cv2.rectangle(p4, (x1, y1), (x2, y2), box_color, 2)
        
        # 3. Draw Paris Badge HUD
        p4 = paris_clf.draw_paris_badge(p4, (x1, y1, x2, y2), paris_info, track_id=track_id)
        
        current_frame_dets.append({
            "track_id": track_id,
            "bbox": (x1, y1, x2, y2),
            "conf": float(holder.smoother.smoothed),
            "paris": paris_info,
            "mask": mask
        })
                    
    p4 = draw_header_banner(p4, "4. CHAKRAMODEL CLINICAL SUITE", "PraNet Reverse Attention + Paris Class", bg_color=(15, 40, 25), text_color=(0, 255, 120))
    return p4, current_frame_dets

def process_4way_video_streams(input_source, output_dict, model_path=r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt", conf_thresh=0.2):
    """
    Simultaneously processes an input video stream into 4 distinct ablation outputs,
    an optional 2x2 combined comparative grid video, and an automated clinical diagnostic report.
    """
    print("Initializing 4-Way Comparative Processing Pipeline (with PraNet & Paris Classification)...")
    
    if not os.path.exists(model_path):
        print(f"Weights not found at {model_path}. Falling back to base yolov8n.pt.")
        model = YOLO("yolov8n.pt")
    else:
        model = YOLO(model_path)
        
    # Initialize Stage 2 Deep Learning Components
    pranet_seg = PraNetSegmenter()
    paris_clf = ParisClassifier()
    report_gen = ClinicalReportGenerator()
        
    source = int(input_source) if str(input_source).isdigit() else input_source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open input video stream: {input_source}")
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    # Initialize Writers
    writers = {}
    for key, path in output_dict.items():
        if key == "grid":
            writers[key] = cv2.VideoWriter(path, fourcc, int(fps), (width * 2, height * 2))
        else:
            writers[key] = cv2.VideoWriter(path, fourcc, int(fps), (width, height))
            
    # Track states across frames
    track_smoothers = {}
    active_holders = {}

    # Start MJPEG server to serve live preview
    try:
        start_mjpeg_server()
    except Exception:
        print("Warning: could not start MJPEG server for live preview")
    
    frame_idx = 0
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_idx += 1
            timestamp_sec = frame_idx / fps
            is_artifact = is_artifact_frame(frame)
            
            # 1. Panel 1 (Raw)
            p1 = render_panel1_raw(frame)
            
            # 2. Panel 2 (Baseline YOLO)
            p2 = render_panel2_baseline_yolo(frame, model, conf_thresh=conf_thresh)
            
            # 3. Panel 3 (YOLO + Kalman)
            p3 = render_panel3_kalman(frame, model, track_smoothers, conf_thresh=conf_thresh)
            
            # 4. Panel 4 (Full ChakraModel Suite with PraNet & Paris Badges)
            p4, frame_dets = render_panel4_full_chakramodel(
                frame, model, pranet_seg, paris_clf, active_holders, is_artifact, conf_thresh=conf_thresh
            )
            
            # Update Clinical Report Telemetry
            report_gen.update(frame_idx, timestamp_sec, frame_dets, is_artifact=is_artifact, current_frame_bgr=frame)
            
            # Write individual panels
            if "raw" in writers: writers["raw"].write(p1)
            if "baseline" in writers: writers["baseline"].write(p2)
            if "kalman" in writers: writers["kalman"].write(p3)
            if "full" in writers: writers["full"].write(p4)
            
            # Write 2x2 Grid
            if "grid" in writers:
                top_row = np.hstack((p1, p2))
                bottom_row = np.hstack((p3, p4))
                grid_frame = np.vstack((top_row, bottom_row))
                writers["grid"].write(grid_frame)
                # Update live MJPEG frame
                try:
                    ret, jpg = cv2.imencode('.jpg', grid_frame)
                    if ret:
                        set_latest_jpeg(jpg.tobytes())
                except Exception:
                    pass
                    
            if frame_idx % 250 == 0:
                print(f"Processed {frame_idx} frames across all 4 streams...")
                
        print(f"Processed {frame_idx} frames across all 4 streams successfully.")
        
        # Generate Clinical Procedure Report
        video_stem = Path(str(input_source)).stem if isinstance(input_source, (str, Path)) else "Live_Stream"
        report_text, report_file = report_gen.generate_report(video_name=video_stem)
        print(f"📋 Clinical Diagnostic Report generated at: {report_file}")
        
    finally:
        cap.release()
        for w in writers.values():
            w.release()
            
    return output_dict

def process_video_stream(input_source, output_path, model_path):
    """ Legacy single-stream compatibility wrapper """
    outputs = {"full": output_path}
    process_4way_video_streams(input_source, outputs, model_path=model_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="Video path or camera index")
    parser.add_argument("--output_dir", type=str, default="outputs")
    parser.add_argument("--weights", type=str, default=r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt")
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    out_dict = {
        "raw": os.path.join(args.output_dir, "1_raw.mp4"),
        "baseline": os.path.join(args.output_dir, "2_baseline.mp4"),
        "kalman": os.path.join(args.output_dir, "3_kalman.mp4"),
        "full": os.path.join(args.output_dir, "4_chakramodel.mp4"),
        "grid": os.path.join(args.output_dir, "combined_2x2_grid.mp4"),
    }
    process_4way_video_streams(args.input, out_dict, model_path=args.weights)


# --- MJPEG live preview server utilities ---
_MJPEG_PORT = 8081
_MJPEG_SERVER = None
_MJPEG_THREAD = None
_LATEST_JPEG = None
_SERVER_LOCK = threading.Lock()

def set_latest_jpeg(jpeg_bytes):
    global _LATEST_JPEG
    _LATEST_JPEG = jpeg_bytes

class _MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/', '/stream.mjpg', '/live'):
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.end_headers()

        try:
            while True:
                if _LATEST_JPEG is None:
                    time.sleep(0.05)
                    continue

                self.wfile.write(b'--FRAME\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(_LATEST_JPEG)))
                self.end_headers()
                self.wfile.write(_LATEST_JPEG)
                self.wfile.write(b'\r\n')
                time.sleep(0.04)
        except Exception:
            return

def start_mjpeg_server(port=_MJPEG_PORT):
    global _MJPEG_SERVER, _MJPEG_THREAD
    with _SERVER_LOCK:
        if _MJPEG_SERVER is not None:
            return

        def _run():
            server = HTTPServer(('0.0.0.0', port), _MJPEGHandler)
            try:
                server.serve_forever()
            except Exception:
                pass

        _MJPEG_THREAD = threading.Thread(target=_run, daemon=True)
        _MJPEG_THREAD.start()
        _MJPEG_SERVER = True
        print(f"Live MJPEG preview available at http://127.0.0.1:{port}/stream.mjpg")
