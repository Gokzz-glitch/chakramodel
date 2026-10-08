import gradio as gr
import cv2
import os
import pandas as pd
import tempfile
from pathlib import Path
from ultralytics import YOLO
from src.temporal.tracker import ChakraTemporalTracker
from src.chakranet_segmenter import ChakraNet
from src.paris_classifier import ParisClassifier

# FR-4.4: Robust weight resolution with fallback chain
_WEIGHT_CANDIDATES = [
    Path("weights/best.pt"),
    Path("outputs/polyp_yolov8x/weights/best.pt"),
    Path("best.pt"),
]

def _resolve_weights() -> str:
    """Find model weights using a prioritized fallback chain."""
    for candidate in _WEIGHT_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        f"ChakraModel weights not found. Searched: {[str(p) for p in _WEIGHT_CANDIDATES]}"
    )

import torch

MODEL_PATH = _resolve_weights()
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# FR-4.5: Global model caching in VRAM to eliminate per-inference reload latency
print(f"[INFO] Initializing ChakraModel engines on target device: {DEVICE}...")
GLOBAL_MODEL = YOLO(MODEL_PATH)
if torch.cuda.is_available():
    GLOBAL_MODEL.to('cuda')

GLOBAL_PRANET = ChakraNet(device=DEVICE)
GLOBAL_PARIS = ParisClassifier()

def process_video(video_path, use_persistence, window_size, persistence_threshold, doubt_policy, imgsz_val, use_conformal):
    """Processes video frame-by-frame, applying YOLO tracking and optional persistence filtering."""
    if not video_path:
        return None, pd.DataFrame()
        
    model = GLOBAL_MODEL
    pranet_seg = GLOBAL_PRANET
    paris_clf = GLOBAL_PARIS
    
    imgsz = int(imgsz_val) if imgsz_val else 1024
    
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    # Create temp output file
    temp_dir = tempfile.mkdtemp()
    out_path = os.path.join(temp_dir, 'output.mp4')
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
    
    q_hat_pos, q_hat_neg = None, None
    if use_conformal:
        import json
        cal_path = Path("weights/conformal_calibration.json")
        if cal_path.exists():
            with open(cal_path) as f:
                cal = json.load(f)
            q_hat_pos = cal.get("q_hat_pos")
            q_hat_neg = cal.get("q_hat_neg", q_hat_pos)
        else:
            print("[WARN] Conformal requested but weights/conformal_calibration.json not found.")
    
    # FR-4.3: Use canonical ChakraTemporalTracker (replaces broken root temporal_persistence.py)
    tracker = ChakraTemporalTracker(
        confirm_n=3,
        confirm_m=5,
        max_hold_frames=8,
        confidence_threshold=0.35,
        ema_alpha=0.4,
        decay_rate=0.85,
        cleanup_grace=5,
        window_size=int(window_size),
        doubt_drops_track=(doubt_policy == "Drop Track"),
    )
    
    # 1. Dynamic VRAM Batch Size Calculation
    if torch.cuda.is_available():
        free_mem, _ = torch.cuda.mem_get_info()
        # Leave 800MB safety buffer
        usable_mem = max(0, free_mem - 800 * 1024 * 1024)
        # Approximate mem footprint per frame (YOLO + PraNet feature maps overhead)
        mem_per_frame = 250 * 1024 * 1024 
        dynamic_batch_size = max(1, usable_mem // mem_per_frame)
        # Cap batch size to avoid tracker lag or massive latency spikes
        dynamic_batch_size = min(int(dynamic_batch_size), 12)
        print(f"[INFO] Dynamic Batch Size: {dynamic_batch_size} (Free VRAM: {free_mem/1e9:.2f} GB)")
    else:
        dynamic_batch_size = 4
        
    batch_frames = []
    
    while cap.isOpened():
        ret, frame = cap.read()
        if ret:
            batch_frames.append(frame)
            
        if len(batch_frames) == dynamic_batch_size or (not ret and len(batch_frames) > 0):
            # Run YOLO batch inference with ByteTrack tracking on GPU
            batch_results = model.track(
                batch_frames,
                persist=True,
                tracker="bytetrack.yaml",
                verbose=False,
                device=0 if torch.cuda.is_available() else 'cpu',
                half=torch.cuda.is_available(),
                imgsz=imgsz,
            )
            
            all_display_frames = [f.copy() for f in batch_frames]
            all_display_tracks = []
            
            # Extract detections and apply temporal filter per frame sequentially
            for frame_idx, result in enumerate(batch_results):
                current_detections = []
                if result.boxes.id is not None:
                    boxes = result.boxes.xyxy.cpu().numpy()
                    track_ids = result.boxes.id.int().cpu().tolist()
                    confidences = result.boxes.conf.cpu().numpy()
                    
                    for box, track_id, conf in zip(boxes, track_ids, confidences):
                        current_detections.append({
                            'track_id': track_id,
                            'box': [int(b) for b in box],
                            'conf': float(conf)
                        })
                
                if use_persistence:
                    # FR-2.1: Apply unified temporal persistence filter
                    display_tracks = tracker.update(current_detections)
                    all_display_tracks.append(display_tracks)
                else:
                    # Draw raw detections directly
                    display_frame = all_display_frames[frame_idx]
                    for det in current_detections:
                        x1, y1, x2, y2 = det['box']
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(display_frame, f"Raw {det['track_id']} {det['conf']:.2f}", 
                                    (x1, max(45, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                                    
            if use_persistence:
                # 1. Collect ROIs across the ENTIRE batch
                roi_crops = []
                roi_refs = [] # (frame_idx, track)
                
                for frame_idx, display_tracks in enumerate(all_display_tracks):
                    for track in display_tracks:
                        if track.box is None: continue
                        x1, y1, x2, y2 = map(int, track.box)
                        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
                        
                        if x2 <= x1 or y2 <= y1: continue
                        
                        roi_crop = batch_frames[frame_idx][y1:y2, x1:x2]
                        if track.state == "DETECTING" and roi_crop.size > 0:
                            roi_crops.append(roi_crop)
                            roi_refs.append((frame_idx, track))
                            
                # 2. Execute PraNet batch inference (Massive speedup)
                if roi_crops:
                    pranet_results = pranet_seg.segment_batch_roi(
                        roi_crops, 
                        conformal=use_conformal, 
                        q_hat_pos=q_hat_pos, 
                        q_hat_neg=q_hat_neg
                    )
                    for (frame_idx, track), (mask, contours, seg_conf, extras) in zip(roi_refs, pranet_results):
                        track.mask = mask
                        if extras and "inner" in extras and "outer" in extras:
                            track.inner_mask = extras["inner"]
                            track.outer_mask = extras["outer"]
                        x1, y1, x2, y2 = map(int, track.box)
                        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
                        track.paris_info = paris_clf.analyze_polyp((x1, y1, x2, y2), mask=mask, contour=contours[0] if contours else None)
                        
                # 3. Render tracks onto display frames
                for frame_idx, display_tracks in enumerate(all_display_tracks):
                    display_frame = all_display_frames[frame_idx]
                    
                    for track in display_tracks:
                        if track.box is None: continue
                        x1, y1, x2, y2 = map(int, track.box)
                        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
                        
                        if x2 <= x1 or y2 <= y1: continue
                        
                        mask = getattr(track, "mask", None)
                        if track.state != "DETECTING":
                            paris_info = getattr(track, "paris_info", None)
                            if paris_info is None:
                                paris_info = paris_clf.analyze_polyp((x1, y1, x2, y2))
                        else:
                            paris_info = getattr(track, "paris_info", None)
                            
                        # Overlay mask
                        if mask is not None:
                            box_h, box_w = y2 - y1, x2 - x1
                            if getattr(track, "inner_mask", None) is not None and getattr(track, "outer_mask", None) is not None:
                                outer = cv2.resize(track.outer_mask, (box_w, box_h), interpolation=cv2.INTER_LINEAR)
                                inner = cv2.resize(track.inner_mask, (box_w, box_h), interpolation=cv2.INTER_LINEAR)
                                display_frame = pranet_seg.overlay_mask_on_frame(display_frame, (x1, y1, x2, y2), outer, color=(0, 165, 255), alpha=0.3)
                                display_frame = pranet_seg.overlay_mask_on_frame(display_frame, (x1, y1, x2, y2), inner, color=(0, 255, 0), alpha=0.6)
                            else:
                                if box_h > 0 and box_w > 0 and mask.shape[:2] != (box_h, box_w):
                                    mask = cv2.resize(mask, (box_w, box_h), interpolation=cv2.INTER_LINEAR)
                                mask_color = (0, 255, 128) if track.state == "DETECTING" else (0, 200, 255)
                                display_frame = pranet_seg.overlay_mask_on_frame(display_frame, (x1, y1, x2, y2), mask, color=mask_color, alpha=0.40)
                            
                        # Draw bounding box
                        if getattr(track, "is_doubtful", False):
                            color = (0, 191, 255) # Amber
                        else:
                            color = (0, 255, 0) if track.state == "DETECTING" else (0, 230, 255)
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 3)
                        
                        # Draw HUD
                        display_frame = paris_clf.draw_paris_badge(display_frame, (x1, y1, x2, y2), paris_info, track_id=track.track_id)
                        
                    # Draw Doubt Warning Banner
                    if any(getattr(t, "is_doubtful", False) for t in display_tracks):
                        overlay = display_frame.copy()
                        banner_half = min(250, width // 2)
                        x_start = max(0, width // 2 - banner_half)
                        x_end = min(width, width // 2 + banner_half)
                        cv2.rectangle(overlay, (x_start, 0), (x_end, 40), (0, 0, 0), -1)
                        cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
                        cv2.putText(display_frame, "WARNING - PAUSE OR REDO MOVEMENT", 
                                    (x_start + 20, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 191, 255), 2, cv2.LINE_AA)
                                    
            # 4. Write all rendered frames to output
            for display_frame in all_display_frames:
                out.write(display_frame)
                
            batch_frames = [] # clear buffer
            
        if not ret:
            break
        
    cap.release()
    out.release()
    
    # Generate Timeline Dataframe
    timeline_rows = []
    for tid, track in tracker.get_all_tracks().items():
        if track.max_confidence > 0:
            timeline_rows.append([
                f"Track {tid}",
                track.first_detected_frame,
                track.last_detected_frame,
                f"{track.max_confidence:.2f}",
                len(track.doubt_events)
            ])
            
    df_timeline = pd.DataFrame(timeline_rows, columns=["Track ID", "First Frame", "Last Frame", "Max Conf", "Doubt Events"])

    # Transcode to H264 so it is playable in browser HTML5 players
    h264_path = os.path.join(temp_dir, 'output_h264.mp4')
    import subprocess
    cmd = [
        'ffmpeg', '-y',
        '-i', out_path,
        '-vcodec', 'libx264',
        '-pix_fmt', 'yuv420p',
        h264_path
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return h264_path, df_timeline
    except Exception:
        return out_path, df_timeline

def handle_upload(file_path):
    if not file_path:
        return gr.update(visible=False)
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.avi':
        out_path = file_path.replace('.avi', '_converted.mp4')
        if not os.path.exists(out_path):
            cmd = ['ffmpeg', '-y', '-i', file_path, '-vcodec', 'libx264', '-pix_fmt', 'yuv420p', out_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return gr.update(value=out_path, visible=True)
    return gr.update(value=file_path, visible=True)

# --- UI Setup ---
with gr.Blocks(title="ChakraModel Demo") as demo:
    gr.Markdown("# 🏥 ChakraModel: Artifact-Robust Colonoscopy Polyp Detection")
    gr.Markdown("Upload a live colonoscopy video. Toggle the **Temporal Persistence Filter** to compare standard AI flickering vs. our stabilized clinical output.")
    
    with gr.Row():
        with gr.Column(scale=6):
            raw_video_upload = gr.File(label="Upload Video (Supports AVI/MP4)", file_types=["video"])
            video_input = gr.Video(label="Input Endoscopy Video", visible=False)
            use_filter = gr.Checkbox(label="Enable Temporal Persistence Filter (ChakraModel)", value=True)
            use_conformal = gr.Checkbox(label="Enable Conformal Prediction (Inner/Outer Bounds)", value=False)
            
            with gr.Accordion("Advanced Settings", open=False):
                window_size = gr.Slider(minimum=3, maximum=30, value=10, step=1, label="Persistence Window (Frames)")
                persistence_threshold = gr.Slider(minimum=0.1, maximum=1.0, value=0.6, step=0.1, label="Persistence Threshold")
                doubt_policy = gr.Radio(choices=["Warn Only", "Drop Track"], value="Warn Only", label="Doubt Policy")
                imgsz_input = gr.Radio(choices=["640", "1024", "1280"], value="1024", label="YOLO Resolution (imgsz - Higher uses 2.5GB+ VRAM)")
                
            submit_btn = gr.Button("Run Inference", variant="primary")
            
            video_output = gr.Video(label="AI Detection Output")
            
        with gr.Column(scale=4):
            gr.Markdown("### Detection Timeline")
            gr.Markdown("Summary of polyp detections and movement doubt events across the video.")
            timeline_output = gr.Dataframe(headers=["Track ID", "First Frame", "Last Frame", "Max Conf", "Doubt Events"], interactive=False)
            
    submit_btn.click(
        fn=process_video,
        inputs=[video_input, use_filter, window_size, persistence_threshold, doubt_policy, imgsz_input, use_conformal],
        outputs=[video_output, timeline_output]
    )
    
    raw_video_upload.upload(
        fn=handle_upload,
        inputs=raw_video_upload,
        outputs=video_input
    )

if __name__ == "__main__":
    print("Launching ChakraModel Demo Interface...")
    demo.launch(share=False, theme=gr.themes.Soft())

