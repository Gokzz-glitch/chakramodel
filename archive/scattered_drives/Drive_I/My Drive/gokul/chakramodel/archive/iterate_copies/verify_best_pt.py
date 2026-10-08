from ultralytics import YOLO

try:
    model = YOLO('M:/chakramodel/weights/best.pt')
    print("Model loaded successfully.")
    print(f"Task: {model.task}")
    print(f"Names: {model.names}")
except Exception as e:
    print(f"Error loading model: {e}")
