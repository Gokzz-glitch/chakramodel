import cv2
from ultralytics import YOLO

model = YOLO(r'M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt')
cap = cv2.VideoCapture(r'm:\chakramodel\video_testing\1_1.avi')

count = 0
found_predict = 0
found_track = 0

while cap.isOpened() and count < 300:
    ret, frame = cap.read()
    if not ret: break
    
    # Check predict
    res_pred = model.predict(frame, verbose=False, conf=0.1)[0]
    if len(res_pred.boxes) > 0:
        found_predict += 1
        
    # Check track
    res_track = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.1, verbose=False)[0]
    if res_track.boxes.id is not None:
        found_track += 1
        
    count += 1

print(f"Tested 300 frames.")
print(f"Found with PREDICT (no tracker): {found_predict} frames")
print(f"Found with TRACK (ByteTrack IDs assigned): {found_track} frames")
