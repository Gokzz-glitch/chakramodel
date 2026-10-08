import cv2
import numpy as np
import os
from app import process_video

# Create a dummy video
video_path = "dummy.mp4"
out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'mp4v'), 30, (640, 480))
for _ in range(30):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # add something for pranet to potentially detect
    cv2.rectangle(frame, (100, 100), (200, 200), (255, 255, 255), -1)
    out.write(frame)
out.release()

print("Running dynamic batching test...")
try:
    result_video, df = process_video(video_path, use_persistence=True, window_size=15, persistence_threshold=5, doubt_policy="Show Warning Banner", imgsz_val="640")
    print("Success!", result_video)
except Exception as e:
    import traceback
    traceback.print_exc()

os.remove(video_path)
