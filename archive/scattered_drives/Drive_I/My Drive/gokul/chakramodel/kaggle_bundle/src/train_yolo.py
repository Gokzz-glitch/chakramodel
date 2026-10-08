from ultralytics import YOLO
import multiprocessing

def main():
    # Load the pretrained X-Large model (maximum accuracy, hardware not a limit)
    model = YOLO("yolov8x.pt")
    
    # Path to our freshly generated dataset configuration
    data_yaml = r"M:\chakramodel\dataset_yolo\dataset.yaml"
    
    # ---------------------------------------------------------
    # MAXIMUM ACCURACY CONFIGURATION (Unlimited Hardware)
    # ---------------------------------------------------------
    
    print("Starting YOLOv8x Training on Colonoscopy Dataset...")
    results = model.train(
        data=data_yaml,
        epochs=100,        # Increased epochs for maximum accuracy
        imgsz=640,
        batch=32,          # High batch size for better gradients
        workers=8,         # Maximize dataloader throughput
        device=0,          # Target the NVIDIA GPU
        amp=True,          # Use fp16
        project=r"M:\chakramodel\outputs",
        name="polyp_yolov8x",
        patience=20,       # Increased patience
        save=True,
        exist_ok=True
    )
    
    print("Training finished! Models saved to M:\\chakramodel\\outputs\\polyp_yolov8x\\weights")

if __name__ == '__main__':
    # Required for Windows multiprocessing in DataLoader
    multiprocessing.freeze_support()
    main()
