import sys
import os

# Add src to python path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

import cv2
import time
import torch

# Hardcoded rule: Limit CPU usage (prevent pegging 100% across all cores)
torch.set_num_threads(2)

from ultralytics import YOLO
from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter

print("=== REAL-TIME LOCAL INFERENCE CHECK ===")

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Device: {device}")

# 1. Load YOLOv8
yolo_path = "M:/chakramodel/weights/best.pt"
if not os.path.exists(yolo_path):
    print("No YOLO weights found, downloading yolov8n.pt...")
    yolo_model = YOLO('yolov8n.pt')
else:
    print("Loading local YOLO weights...")
    yolo_model = YOLO(yolo_path)

# 2. Load ViT Segmenter
vit_path = "M:/chakramodel/weights/chakra_transformer_best.pth"
print("Loading ViT-Large segmenter...")
try:
    vit_model = ChakraTransformerSegmenter().to(device)
    if os.path.exists(vit_path):
        state_dict = torch.load(vit_path, map_location=device)
        vit_model.load_state_dict(state_dict, strict=False)
        print("ViT weights loaded!")
    else:
        print("No ViT weights found, running with initialized weights for latency testing.")
except Exception as e:
    print(f"Failed to load ViT: {e}")
    sys.exit(1)

vit_model.eval()

# 3. Process Video
video_path = "M:/chakramodel/video_testing/1_1.mp4"
if not os.path.exists(video_path):
    print(f"Video {video_path} not found!")
    sys.exit(1)

cap = cv2.VideoCapture(video_path)
frame_count = 0
total_time = 0

print(f"Starting real-time processing on {video_path}...")

while cap.isOpened() and frame_count < 100: # process 100 frames
    ret, frame = cap.read()
    if not ret:
        break
    
    start_time = time.time()
    
    # YOLO inference (simulating Stage 1)
    results = yolo_model(frame, verbose=False)
    
    # We force ViT inference on every frame to simulate worst-case real-time latency
    # In reality, it only triggers on bounding boxes, but we need the exact pipeline latency
    img_tensor = torch.randn(1, 3, 384, 384).to(device) 
    with torch.no_grad():
        out = vit_model(img_tensor)
        
    end_time = time.time()
    total_time += (end_time - start_time)
    frame_count += 1
    
    if frame_count % 10 == 0:
        fps = frame_count / total_time
        print(f"Processed {frame_count} frames | Current FPS: {fps:.2f}")

cap.release()

if frame_count > 0:
    final_fps = frame_count / total_time
    print(f"=== FINAL RESULTS ===")
    print(f"Total Frames Processed: {frame_count}")
    print(f"Average FPS: {final_fps:.2f}")
    if final_fps < 20.0:
        print(f"CONCLUSION: The {final_fps:.2f} FPS severely violates the <50ms real-time bound.")
        print("This perfectly matches our updated paper's limitation section!")
