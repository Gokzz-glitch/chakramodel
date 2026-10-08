import gradio as gr
import os
import sys
import tempfile
import time
from pathlib import Path

# Ensure local directories and submodules are resolvable in sys.path
_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent
for _p in [str(_current_dir), str(_project_root), str(_current_dir / "inference"), str(_current_dir / "models")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from infer_stream import process_4way_video_streams
except ModuleNotFoundError:
    try:
        from src.inference.infer_stream import process_4way_video_streams
    except ModuleNotFoundError:
        try:
            from src.infer_stream import process_4way_video_streams
        except Exception:
            raise

def get_available_models(project_root=None):
    """
    Dynamically discover all available CADe detection and CADx segmentation checkpoints
    across valid project locations, Google Drive, user downloads, and environment variables.
    Detects PyTorch (.pt, .pth), ONNX (.onnx), and TensorFlow/Keras SavedModel bundles.
    Assigns clinically informative descriptions to eliminate hardcoding.
    """
    if project_root is None:
        project_root = os.getcwd()
        
    search_dirs = [
        r"M:\chakramodelpro\valid_models",
        r"J:\My Drive\Girupa local pretrained weigths",
        os.path.expanduser(r"~\Downloads"),
        os.path.join(project_root, "weights"),
        os.path.join(project_root, "outputs"),
        r"M:\chakramodelpro",
    ]
    if "MODEL_DIR" in os.environ and os.path.exists(os.environ["MODEL_DIR"]):
        search_dirs.insert(0, os.environ["MODEL_DIR"])

    models = {}
    seen_paths = set()

    def categorize_model(path_str):
        p_lower = path_str.lower()
        fname = os.path.basename(path_str)
        if "yolo" in p_lower or fname == "best.pt" or "best_weights" in p_lower:
            return f"🎯 YOLOv8 Polyp Detector ({fname})"
        elif "res-v1" in p_lower or "pranet-v1" in p_lower:
            return f"🔬 PraNet Res2Net-50 Boundary Extractor ({fname})"
        elif "pvt-v1" in p_lower or "pvt_pranet" in p_lower or "pvtv2" in p_lower:
            return f"👁️ PVT-PraNet Vision Transformer ({fname})"
        elif "adabn" in p_lower:
            return f"⚡ ChakraNet AdaBN Domain-Adaptive ({fname})"
        elif "chakra_transformer" in p_lower:
            return f"🧬 ChakraTransformer ViT Segmenter ({fname})"
        elif "pranet_mobilenetv2" in p_lower or "mobilenet" in p_lower:
            return f"📱 PraNet MobileNetV2 Edge Model ({fname})"
        elif "pranet_resnet" in p_lower:
            return f"🏗️ PraNet ResNet-50 Deep CNN ({fname})"
        elif "colonsegnet" in p_lower or "compnet" in p_lower or fname == "checkpoint.pth":
            return f"🩺 ColonSegNet / CompNet ({fname})"
        elif "segformer" in p_lower:
            return f"🌐 SegFormer-B2 Segmentation ({fname})"
        elif "unet" in p_lower:
            return f"🔲 UNet-ResNet34 Baseline ({fname})"
        elif "xattn" in p_lower:
            return f"🔄 Cross-Attention Feature Fusion ({fname})"
        elif path_str.endswith(".onnx"):
            return f"⚡ ONNX Runtime Optimized Engine ({fname})"
        else:
            return f"📦 Model Checkpoint ({fname})"

    for d in search_dirs:
        if not os.path.exists(d):
            continue
        try:
            for root, dirs, files in os.walk(d):
                # Check for TensorFlow SavedModel directory
                if "saved_model.pb" in files:
                    dir_name = os.path.basename(root)
                    if root not in seen_paths:
                        seen_paths.add(root)
                        label = categorize_model(root)
                        models[label] = root

                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in [".pt", ".pth", ".onnx"]:
                        full_path = os.path.join(root, f)
                        if full_path in seen_paths:
                            continue
                        seen_paths.add(full_path)
                        label = categorize_model(full_path)
                        if label in models:
                            label = f"{label} [{os.path.basename(os.path.dirname(full_path))}]"
                        models[label] = full_path
        except Exception as e:
            print(f"[WARN] Error scanning directory {d}: {e}")

    # Prioritize key clinical suites in order if present
    priority_order = [
        "YOLOv8 Polyp Detector",
        "PraNet Res2Net-50 Boundary Extractor",
        "PVT-PraNet Vision Transformer",
        "ChakraNet AdaBN Domain-Adaptive",
        "ChakraTransformer ViT Segmenter",
        "PraNet MobileNetV2 Edge Model",
        "PraNet ResNet-50 Deep CNN",
        "ColonSegNet / CompNet",
    ]
    sorted_models = {}
    for prio in priority_order:
        for k, v in list(models.items()):
            if prio.lower() in k.lower() and k not in sorted_models:
                sorted_models[k] = v
    for k, v in models.items():
        if k not in sorted_models:
            sorted_models[k] = v

    return sorted_models

def analyze_4way_video(input_video_path, conf_slider, selected_model_name):
    if input_video_path is None:
        return None, None, None, None, None, "⚠️ Please upload or select a video first."
    
    if not selected_model_name or selected_model_name.startswith("⚠️"):
        return None, None, None, None, None, "⚠️ Please select a valid model first."

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

    available_models_map = get_available_models(project_root)
    weights_path = available_models_map.get(selected_model_name)
    if not weights_path:
        return None, None, None, None, None, f"⚠️ Model '{selected_model_name}' not found."

    print(f"Starting 4-way comparative analysis on {chosen_source} with model {selected_model_name} (Confidence: {conf_slider})...")

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
    color: #00dfa2;
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
    background: linear-gradient(135deg, #00dfa2 0%, #0284c7 100%) !important;
    border: none !important;
    color: white !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    padding: 12px 20px !important;
    box-shadow: 0 4px 18px rgba(0, 223, 162, 0.4) !important;
    transition: all 0.25s ease-in-out !important;
}
.primary-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 24px rgba(0, 223, 162, 0.65) !important;
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

available_models_map = get_available_models(os.getcwd())
model_choices = list(available_models_map.keys())
if not model_choices:
    model_choices = ["⚠️ No models found in weights/ directories"]

with gr.Blocks(theme=gr.themes.Base(), css=custom_css, title="ChakraModel AI Medical Suite") as demo:
    with gr.Column(elem_classes="main-header"):
        gr.Markdown("<h1 class='main-title'>🩺 ChakraModel AI</h1>", elem_classes="main-title")
        gr.Markdown("<p class='subtitle'>Real-Time Polyp Detection • Kalman Trajectory • PraNet Reverse-Attention • Paris Staging</p>", elem_classes="subtitle")
    
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group():
                gr.Markdown("### 📥 Input Feed & Controls")
                model_dropdown = gr.Dropdown(
                    choices=model_choices,
                    value=model_choices[0] if model_choices else None,
                    label="Select Detection Model (Weights)",
                    info="Choose the YOLOv8 weight file to use for analysis."
                )
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
        inputs=[input_video, conf_slider, model_dropdown],
        outputs=[v_raw, v_baseline, v_kalman, v_full, v_grid, report_viewer, status_box]
    )

if __name__ == "__main__":
    share_gradio = os.environ.get('GRADIO_SHARE', 'False').lower() == 'true'
    demo.launch(server_name="0.0.0.0", server_port=7860, share=share_gradio)
