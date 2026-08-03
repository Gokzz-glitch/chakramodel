from ultralytics import YOLO
import multiprocessing

def main():
    # Load the pretrained Nano model (fastest, lightest for laptop GPU)
    model = YOLO(r"M:\chakramodel\yolov8n.pt")
    
    # Path to our freshly generated dataset configuration
    data_yaml = r"M:\chakramodel\dataset_yolo\dataset.yaml"
    
    # ---------------------------------------------------------
    # HARDWARE OPTIMIZATIONS FOR RTX 3050 Laptop (4GB VRAM)
    # ---------------------------------------------------------
    # - imgsz: 640 is the YOLO standard. 
    # - batch: 8 is a safe conservative starting point to prevent CUDA OOM on 4GB VRAM.
    #          (If it OOMs, drop this to 4. If it runs easily, push to 16).
    # - workers: 4 is optimal for Windows laptops to prevent CPU bottlenecks.
    # - amp: True (Automatic Mixed Precision) saves VRAM and speeds up training.
    
    print("Starting YOLOv8n Training on Colonoscopy Dataset...")
    results = model.train(
        data=data_yaml,
        epochs=30,         # 30 epochs is a good start for a 36-hour hackathon prototype
        imgsz=640,
        batch=8,           # VRAM safeguard
        workers=0,         # Fixed windows multiprocessing bug
        device=0,          # Target the NVIDIA GPU
        amp=True,          # Use fp16 to save VRAM
        project=r"M:\chakramodel\outputs",
        name="polyp_yolov8n",
        patience=10,       # Early stopping
        save=True,
        exist_ok=True
    )
    
    print("Training finished! Models saved to M:\\chakramodel\\outputs\\polyp_yolov8n\\weights")

if __name__ == '__main__':
    # Required for Windows multiprocessing in DataLoader
    multiprocessing.freeze_support()
    main()
