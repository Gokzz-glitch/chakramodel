import gradio as gr
import os
import tempfile
import time
try:
    from infer_stream import process_4way_video_streams
except ModuleNotFoundError:
    try:
        from src.infer_stream import process_4way_video_streams
    except Exception:
        raise

def analyze_4way_video(input_video_path, conf_slider):
    if input_video_path is None:
        return None, None, None, None, None, "⚠️ Please upload or select a video first."

    # Resolve if user passed a directory — pick the first video file inside
    project_root = os.getcwd()
    chosen_source = input_video_path
    if os.path.isdir(input_video_path):
        video_exts = ('.mp4', '.mov', '.mkv', '.avi', '.webm')
        files = [f for f in sorted(os.listdir(input_video_path)) if f.lower().endswith(video_exts)]
        if not files:
            return None, None, None, None, None, "⚠️ No video files found in the selected directory."
        chosen_source = os.path.join(input_video_path, files[0])

    # Ensure outputs directory (match requested format)
    out_dir = os.path.join(project_root, 'outputs', 'test_results', '1_1')
    os.makedirs(out_dir, exist_ok=True)

    out_dict = {
        "raw": os.path.join(out_dir, "raw_1.mp4"),
        "baseline": os.path.join(out_dir, "baseline_2.mp4"),
        "kalman": os.path.join(out_dir, "kalman_3.mp4"),
        "full": os.path.join(out_dir, "full_4.mp4"),
        "grid": os.path.join(out_dir, "combined_2x2_grid.mp4"),
    }

    # Prefer project-local weights when available
    weights_path = r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt"

    print(f"Starting 4-way comparative analysis on {chosen_source} (Confidence: {conf_slider})...")

    process_4way_video_streams(
        input_source=chosen_source,
        output_dict=out_dict,
        model_path=weights_path,
        conf_thresh=float(conf_slider)
    )

    # Look for newly generated clinical reports
    report_md_content = "### 📋 No report generated yet."
    reports_dir = os.path.join(project_root, 'outputs', 'clinical_reports')
    if os.path.exists(reports_dir):
        report_files = sorted([os.path.join(reports_dir, f) for f in os.listdir(reports_dir) if f.endswith('_report.md')], reverse=True)
        if report_files:
            with open(report_files[0], 'r', encoding='utf-8') as f:
                report_md_content = f.read()

    status_msg = (
        f"✅ **Analysis Complete!**\n\n"
        f"• **Stage 1:** YOLOv8 + ByteTrack Kalman Trajectory Tracking\n"
        f"• **Stage 2:** PraNet Reverse-Attention Boundary Mask & Paris Morphological Staging\n"
        f"• **Clinical Telemetry:** Standardized Diagnostic Report & Keyframes saved to `outputs/clinical_reports/`"
    )

    return (
        out_dict["raw"],
        out_dict["baseline"],
        out_dict["kalman"],
        out_dict["full"],
        out_dict["grid"],
        report_md_content,
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

with gr.Blocks(theme=gr.themes.Base(), css=custom_css, title="ChakraModel AI Medical Suite") as demo:
    with gr.Column(elem_classes="main-header"):
        gr.Markdown("<h1 class='main-title'>🩺 ChakraModel AI</h1>", elem_classes="main-title")
        gr.Markdown("<p class='subtitle'>Real-Time Polyp Detection • Kalman Trajectory • PraNet Reverse-Attention • Paris Staging</p>", elem_classes="subtitle")
    
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
                    info="Lower values detect faint/flat polyps; higher values require high confidence."
                )
                analyze_btn = gr.Button("Initialize 4-Way Cascade AI Analysis 🚀", elem_classes="primary-btn")
                status_box = gr.Markdown("Ready for video input.")
                
            gr.Markdown("""
            <div style="background: #0f172a; padding: 18px; border-radius: 10px; border: 1px solid #1e293b; margin-top: 14px;">
                <h4 style="color: #38bdf8; margin-top: 0; margin-bottom: 12px;">📊 4-Quadrant Architecture Guide</h4>
                <div style="font-size: 0.9rem; line-height: 1.5;">
                    <p style="margin-bottom: 8px;"><span class="badge badge-raw">Box 1</span> <b>Raw Video:</b> Original endoscopic stream with debris & blur.</p>
                    <p style="margin-bottom: 8px;"><span class="badge badge-yolo">Box 2</span> <b>Baseline YOLO:</b> Frame-by-frame detector without temporal memory (flicker demo).</p>
                    <p style="margin-bottom: 8px;"><span class="badge badge-kalman">Box 3</span> <b>YOLO + Kalman:</b> ByteTrack Kalman trajectory tracking & score smoothing.</p>
                    <p style="margin-bottom: 0;"><span class="badge badge-full">Box 4</span> <b>ChakraModel Clinical Suite:</b> Kalman + PraNet Reverse Attention Masks + Paris Morphological Staging + Artifact Red Alert.</p>
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
                            gr.Markdown("#### 4️⃣ ChakraModel Clinical Suite")
                            v_full = gr.Video(label="4. Full Suite (PraNet Reverse Attention + Paris Badges)", interactive=False)
                            
                with gr.TabItem("🎥 Unified 2x2 Grid View"):
                    gr.Markdown("#### Synchronized 4-in-1 Split-Screen Video")
                    v_grid = gr.Video(label="Combined 2x2 Grid Video", interactive=False)

                with gr.TabItem("📋 Automated Diagnostic Report"):
                    gr.Markdown("#### Multimodal Clinical Procedure Record & Keyframes")
                    report_viewer = gr.Markdown("### Click 'Initialize Analysis' to generate clinical diagnostic record.")

    analyze_btn.click(
        fn=analyze_4way_video,
        inputs=[input_video, conf_slider],
        outputs=[v_raw, v_baseline, v_kalman, v_full, v_grid, report_viewer, status_box]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
