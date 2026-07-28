import gradio as gr
import cv2
import os
import tempfile
from ultralytics import YOLO
from temporal_persistence import TemporalPersistenceFilter

# Initialize YOLO
# Defaulting to yolov8n.pt for testing. 
# During the hackathon, change this to the path of your fine-tuned weights (e.g., 'runs/train/weights/best.pt')
MODEL_PATH = 'yolov8n.pt'  

def process_video(video_path, use_persistence, window_size, persistence_threshold):
    """Processes video frame-by-frame, applying YOLO tracking and optional persistence filtering."""
    if not video_path:
        return None
        
    model = YOLO(MODEL_PATH)
    
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    # Create temp output file
    temp_dir = tempfile.mkdtemp()
    out_path = os.path.join(temp_dir, 'output.mp4')
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
    
    persistence_filter = TemporalPersistenceFilter(
        window_size=int(window_size), 
        persistence_threshold=persistence_threshold
    )
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Run YOLO inference with built-in tracking (BoT-SORT handles camera motion)
        # persist=True keeps tracking IDs across frames
        results = model.track(frame, persist=True, tracker="botsort.yaml", verbose=False)
        
        display_frame = frame.copy()
        
        current_detections = []
        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            confidences = results[0].boxes.conf.cpu().numpy()
            
            for box, track_id, conf in zip(boxes, track_ids, confidences):
                current_detections.append({
                    'track_id': track_id,
                    'bbox': [int(b) for b in box],
                    'conf': float(conf)
                })
        
        if use_persistence:
            # Apply ChakraModel logic: Stable, persistent boxes
            filtered_detections = persistence_filter.update_and_filter(current_detections)
            for det in filtered_detections:
                x1, y1, x2, y2 = det['bbox']
                # Draw stable box (Green)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.putText(display_frame, f"Polyp ID:{det['track_id']} {det['conf']:.2f}", 
                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            # Draw Raw YOLO output: Will flicker on artifacts (Red)
            for det in current_detections:
                x1, y1, x2, y2 = det['bbox']
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(display_frame, f"Raw {det['track_id']} {det['conf']:.2f}", 
                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
        out.write(display_frame)
        
    cap.release()
    out.release()
    return out_path

# --- UI Setup ---
with gr.Blocks(title="ChakraModel Demo", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🏥 ChakraModel: Artifact-Robust Colonoscopy Polyp Detection")
    gr.Markdown("Upload a live colonoscopy video. Toggle the **Temporal Persistence Filter** to compare standard AI flickering vs. our stabilized clinical output.")
    
    with gr.Row():
        with gr.Column():
            video_input = gr.Video(label="Input Endoscopy Video")
            use_filter = gr.Checkbox(label="Enable Temporal Persistence Filter (ChakraModel)", value=True)
            
            with gr.Accordion("Advanced Settings", open=False):
                window_size = gr.Slider(minimum=3, maximum=30, value=10, step=1, label="Persistence Window (Frames)")
                persistence_threshold = gr.Slider(minimum=0.1, maximum=1.0, value=0.6, step=0.1, label="Persistence Threshold")
                
            submit_btn = gr.Button("Run Inference", variant="primary")
            
        with gr.Column():
            video_output = gr.Video(label="AI Detection Output")
            
    submit_btn.click(
        fn=process_video,
        inputs=[video_input, use_filter, window_size, persistence_threshold],
        outputs=video_output
    )

if __name__ == "__main__":
    print("Launching ChakraModel Demo Interface...")
    demo.launch(share=False)
