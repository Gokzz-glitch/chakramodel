import gradio as gr
import os
import tempfile
import time
from infer_stream import process_4way_video_streams

def analyze_4way_video(input_video_path, conf_slider):
    if input_video_path is None:
        return None, None, None, None, None, "⚠️ Please upload or select a video first."
    
    temp_dir = tempfile.gettempdir()
    timestamp = int(time.time())
    
    out_dict = {
        "raw": os.path.join(temp_dir, f"out_1_raw_{timestamp}.mp4"),
        "baseline": os.path.join(temp_dir, f"out_2_baseline_{timestamp}.mp4"),
        "kalman": os.path.join(temp_dir, f"out_3_kalman_{timestamp}.mp4"),
        "full": os.path.join(temp_dir, f"out_4_full_{timestamp}.mp4"),
        "grid": os.path.join(temp_dir, f"out_grid_{timestamp}.mp4"),
    }
    
    weights_path = r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt"
    
    print(f"Starting 4-way comparative analysis on {input_video_path} (Confidence: {conf_slider})...")
    
    process_4way_video_streams(
        input_source=input_video_path,
        output_dict=out_dict,
        model_path=weights_path,
        conf_thresh=float(conf_slider)
    )
    
    status_msg = (
        "✅ **Analysis Complete!** All 4 ablation streams and the 2x2 unified grid have been processed and synchronized."
    )
    
    return (
        out_dict["raw"],
        out_dict["baseline"],
        out_dict["kalman"],
        out_dict["full"],
        out_dict["grid"],
        status_msg
    )

# Premium Dark-Mode Medical Dashboard Styles
custom_css = """
body {
    background-color: #080c14;
    color: #f1f5f9;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.gradio-container {
    max-width: 1500px !important;
}
.main-header {
    text-align: center;
    padding: 18px 0 10px 0;
}
.main-title {
    color: #38bdf8;
    font-size: 2.8rem;
    font-weight: 800;
    letter-spacing: -1px;
    margin-bottom: 6px;
}
.subtitle {
    color: #94a3b8;
    font-size: 1.15rem;
    margin-top: 0;
}
.primary-btn {
    background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%) !important;
    border: none !important;
    color: white !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    padding: 12px 20px !important;
    box-shadow: 0 4px 18px rgba(14, 165, 233, 0.4) !important;
    transition: all 0.25s ease-in-out !important;
}
.primary-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 24px rgba(14, 165, 233, 0.65) !important;
}
.card-panel {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 16px;
}
.badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-right: 6px;
}
.badge-raw { background: #334155; color: #f8fafc; }
.badge-yolo { background: #7c2d12; color: #fdba74; }
.badge-kalman { background: #1e3a8a; color: #93c5fd; }
.badge-full { background: #064e3b; color: #6ee7b7; }
"""

with gr.Blocks(theme=gr.themes.Base(), css=custom_css, title="ChakraModel 4-Way Analysis") as demo:
    with gr.Column(elem_classes="main-header"):
        gr.Markdown("<h1 class='main-title'>🩺 ChakraModel AI</h1>", elem_classes="main-title")
        gr.Markdown("<p class='subtitle'>4-Way Comparative Ablation & Real-Time Polyp Tracking System</p>", elem_classes="subtitle")
    
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group():
                gr.Markdown("### 📥 Input Feed & Controls")
                input_video = gr.Video(label="Upload Colonoscopy Video", sources=["upload"])
                conf_slider = gr.Slider(
                    minimum=0.05, 
                    maximum=0.80, 
                    value=0.20, 
                    step=0.05, 
                    label="Detection Confidence Threshold",
                    info="Lower values detect faint/blurry polyps; higher values require strong visual features."
                )
                analyze_btn = gr.Button("Initialize 4-Way Comparative AI Analysis 🚀", elem_classes="primary-btn")
                status_box = gr.Markdown("Ready for video input.")
                
            gr.Markdown("""
            <div style="background: #0f172a; padding: 18px; border-radius: 10px; border: 1px solid #1e293b; margin-top: 14px;">
                <h4 style="color: #38bdf8; margin-top: 0; margin-bottom: 12px;">📊 4-Quadrant Architecture Guide</h4>
                <div style="font-size: 0.9rem; line-height: 1.5;">
                    <p style="margin-bottom: 8px;"><span class="badge badge-raw">Box 1</span> <b>Raw Video:</b> Original endoscopic stream with debris & blur.</p>
                    <p style="margin-bottom: 8px;"><span class="badge badge-yolo">Box 2</span> <b>Baseline YOLO:</b> Frame-by-frame detector without temporal memory (flicker demo).</p>
                    <p style="margin-bottom: 8px;"><span class="badge badge-kalman">Box 3</span> <b>YOLO + Kalman:</b> ByteTrack Kalman trajectory tracking & score smoothing.</p>
                    <p style="margin-bottom: 0;"><span class="badge badge-full">Box 4</span> <b>ChakraModel Full:</b> Kalman + BoxHolder state machine (DETECTING/HOLDING/LOST) + Artifact Red Warning.</p>
                </div>
            </div>
            """)
            
        with gr.Column(scale=3):
            with gr.Tabs():
                with gr.TabItem("🔲 4-Quadrant Split Comparison"):
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("#### 1️⃣ Raw Video Feed")
                            v_raw = gr.Video(label="1. Raw Video Feed", interactive=False)
                        with gr.Column():
                            gr.Markdown("#### 2️⃣ Baseline YOLOv8 (No Tracking)")
                            v_baseline = gr.Video(label="2. Baseline YOLO (Raw Detector Flicker)", interactive=False)
                            
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("#### 3️⃣ YOLOv8 + Kalman Tracking")
                            v_kalman = gr.Video(label="3. YOLO + Kalman Filter (ByteTrack)", interactive=False)
                        with gr.Column():
                            gr.Markdown("#### 4️⃣ ChakraModel Full Suite")
                            v_full = gr.Video(label="4. Full ChakraModel Suite (Temporal + Artifact Aware)", interactive=False)
                            
                with gr.TabItem("🎥 Unified 2x2 Grid View"):
                    gr.Markdown("#### Synchronized 4-in-1 Split-Screen Video")
                    v_grid = gr.Video(label="Combined 2x2 Grid Video", interactive=False)

    analyze_btn.click(
        fn=analyze_4way_video,
        inputs=[input_video, conf_slider],
        outputs=[v_raw, v_baseline, v_kalman, v_full, v_grid, status_box]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
