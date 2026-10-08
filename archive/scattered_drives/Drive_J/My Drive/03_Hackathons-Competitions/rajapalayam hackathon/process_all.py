import os
import glob
from PIL import Image
import cv2
import sys

def my_print(msg):
    print(msg, flush=True)

input_dir = r"J:\My Drive\rajapalayam hackathon\DATASET BY GOKUL"
output_dir = r"J:\My Drive\rajapalayam hackathon\processed_dataset"
os.makedirs(output_dir, exist_ok=True)

# 1. Process Images
image_files = glob.glob(os.path.join(input_dir, "*.jpg")) + glob.glob(os.path.join(input_dir, "*.jpeg")) + glob.glob(os.path.join(input_dir, "*.png"))
my_print(f"Found {len(image_files)} images to crop.")

for idx, img_path in enumerate(image_files):
    try:
        with Image.open(img_path) as img:
            width, height = img.size
            if height > 500:
                crop_height = height - 250
                cropped_img = img.crop((0, 0, width, crop_height))
                
                filename = os.path.basename(img_path)
                out_path = os.path.join(output_dir, f"cropped_{filename}")
                cropped_img.save(out_path)
        if idx % 10 == 0:
            my_print(f"Cropped {idx}/{len(image_files)} images...")
    except Exception as e:
        my_print(f"Failed to process image {img_path}: {e}")

my_print("Image cropping complete.")

# 2. Extract Frames from Videos
video_files = glob.glob(os.path.join(input_dir, "*.mp4"))
my_print(f"Found {len(video_files)} videos to extract frames from.")

frame_interval = 1 # extract 1 frame per second
for vid_idx, vid_path in enumerate(video_files):
    try:
        my_print(f"Opening video: {vid_path}")
        cap = cv2.VideoCapture(vid_path)
        if not cap.isOpened():
            my_print(f"Failed to open video: {vid_path}")
            continue
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0 or fps != fps:
            fps = 30
            
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        my_print(f"Processing video {vid_path} (FPS: {fps}, Total Frames: {frame_count})")
        
        frames_to_extract = int(fps * frame_interval)
        
        count = 0
        extracted_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if count % frames_to_extract == 0:
                filename = os.path.basename(vid_path)
                out_path = os.path.join(output_dir, f"frame_{vid_idx}_{extracted_count}_{filename}.jpg")
                cv2.imwrite(out_path, frame)
                extracted_count += 1
                
            count += 1
            
        cap.release()
        my_print(f"Extracted {extracted_count} frames from {vid_path}")
    except Exception as e:
        my_print(f"Failed to process video {vid_path}: {e}")

my_print("Video frame extraction complete.")
