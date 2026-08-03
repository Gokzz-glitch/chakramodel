import cv2
from ultralytics import YOLO

model = YOLO(r'M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt')
cap = cv2.VideoCapture(r'm:\chakramodel\video_testing\1_1.avi')

fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
count = 0
polyps_found = 0

print(f"Scanning entire video: {total_frames} frames at {fps} FPS")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    
    # We use a very low confidence threshold just to see if the model has ANY activation
    res = model.predict(frame, verbose=False, conf=0.15)[0]
    
    if len(res.boxes) > 0:
        if polyps_found == 0:
            print(f"First polyp detected at frame {count} (Timestamp: {count/fps:.2f} seconds)")
        polyps_found += 1
        
    count += 1

print(f"\nScan complete.")
print(f"Total frames with polyps detected: {polyps_found} out of {total_frames}")
