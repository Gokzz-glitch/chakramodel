from ultralytics import YOLO
import multiprocessing

def main():
    # Load the pretrained Nano model (optimized for real-time edge deployment)
    model = YOLO("yolov8n.pt")
    
    # Path to our freshly generated dataset configuration
    data_yaml = r"M:\chakramodel\dataset_yolo\dataset.yaml"
    
    # ---------------------------------------------------------
    # REAL-TIME EDGE CONFIGURATION
    # ---------------------------------------------------------
    
    print("Starting YOLOv8n Training on Colonoscopy Dataset...")
    results = model.train(
        data=data_yaml,
        epochs=30,        # Fast training
        imgsz=640,
        batch=32,          # High batch size for faster convergence
        workers=8,         # Maximize dataloader throughput
        device=0,          # Target the NVIDIA GPU
        amp=True,          # Use fp16
        project=r"M:\chakramodel\outputs",
        name="polyp_yolov8n",
        patience=20,       # Increased patience
        save=True,
        exist_ok=True
    )
    
    print("Training finished! Models saved to M:\\chakramodel\\outputs\\polyp_yolov8n\\weights")

if __name__ == '__main__':
    # Required for Windows multiprocessing in DataLoader
    multiprocessing.freeze_support()
    main()
