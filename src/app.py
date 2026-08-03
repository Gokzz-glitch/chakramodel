import gradio as gr
import os
import tempfile
from infer_stream import process_video_stream

def analyze_video(input_video_path):
    if input_video_path is None:
        return None
    
    # Generate a temporary output path for the processed video
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, "polyp_output.mp4")
    
    # Path to our trained model
    weights_path = r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt"
    
    print(f"Starting analysis on {input_video_path}...")
    
    # Run the custom temporal inference script we built
    process_video_stream(input_video_path, output_path, weights_path)
    
    return output_path

# Inject custom CSS to make it look like a premium, dark-mode medical dashboard
custom_css = """
body {
    background-color: #0b0f19;
    color: #e2e8f0;
    font-family: 'Inter', sans-serif;
}
.gradio-container {
    max-width: 1300px !important;
}
h1 {
    text-align: center;
    color: #38bdf8;
    font-size: 3.5em;
    font-weight: 700;
    letter-spacing: -1px;
    margin-bottom: 0.1em;
}
h3 {
    text-align: center;
    color: #94a3b8;
    font-weight: 400;
}
.primary-btn {
    background: linear-gradient(135deg, #0ea5e9, #2563eb) !important;
    border: none !important;
    color: white !important;
    font-size: 1.2em !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4) !important;
    transition: all 0.2s ease-in-out !important;
}
.primary-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(14, 165, 233, 0.6) !important;
}
.block {
    border-radius: 12px !important;
    border: 1px solid #1e293b !important;
    background: #0f172a !important;
}
"""

with gr.Blocks(theme=gr.themes.Base(), css=custom_css) as demo:
    gr.Markdown("# 🩺 ChakraModel AI")
    gr.Markdown("### Real-time Polyp Detection with Artifact-Aware Temporal Smoothing")
    
    with gr.Row():
        with gr.Column(scale=1):
            input_video = gr.Video(label="Input Stream (Video / Webcam)", sources=["upload", "webcam"])
            analyze_btn = gr.Button("Initialize AI Analysis 🚀", elem_classes="primary-btn")
            
            gr.Markdown("""
            <div style="background: #1e293b; padding: 20px; border-radius: 8px; margin-top: 20px;">
                <h4 style="color: white; margin-top: 0;">UI State Guide</h4>
                <ul style="list-style-type: none; padding-left: 0;">
                    <li style="margin-bottom: 10px;">🟩 <b>DETECTING:</b> High confidence polyp lock.</li>
                    <li style="margin-bottom: 10px;">🟨 <b>HOLDING:</b> Camera obstructed/blurry, tracking algorithm holding last known position.</li>
                    <li>🟥 <b>ARTIFACT:</b> Poor camera quality detected (blur/feces). Warning flashed.</li>
                </ul>
            </div>
            """)
        
        with gr.Column(scale=2):
            output_video = gr.Video(label="Live AI Analysis")

    analyze_btn.click(fn=analyze_video, inputs=input_video, outputs=output_video)

if __name__ == "__main__":
    # Launching locally on port 7860
    demo.launch(server_name="0.0.0.0", server_port=7860)
