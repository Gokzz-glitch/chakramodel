import cv2
from ultralytics import YOLO

def test_inference():
    # Load model
    model_path = r"M:\chakramodel\outputs\polyp_yolov8n\weights\best.pt"
    model = YOLO(model_path)
    
    # Let's test on one of the validation images we know has a polyp
    # We reformatted the dataset to M:\chakramodel\dataset_yolo\images\val
    import glob
    val_images = glob.glob(r"M:\chakramodel\dataset_yolo\images\val\*.jpg")
    
    if not val_images:
        print("No validation images found!")
        return
        
    print(f"Testing on 5 validation images out of {len(val_images)}")
    for i, img_path in enumerate(val_images[:5]):
        print(f"\n--- Image {i+1}: {img_path} ---")
        
        # 1. Raw predict
        res_predict = model.predict(img_path, conf=0.1, verbose=False)
        boxes_pred = res_predict[0].boxes
        print(f"PREDICT (No tracking): Found {len(boxes_pred)} boxes.")
        if len(boxes_pred) > 0:
            print("Confs:", boxes_pred.conf.cpu().numpy())
            
        # 2. Track
        res_track = model.track(img_path, persist=True, tracker="bytetrack.yaml", conf=0.1, verbose=False)
        boxes_track = res_track[0].boxes
        print(f"TRACK (ByteTrack): Found {len(boxes_track)} boxes.")
        if len(boxes_track) > 0:
            print("Confs:", boxes_track.conf.cpu().numpy())
            print("IDs:", boxes_track.id)

if __name__ == "__main__":
    test_inference()
