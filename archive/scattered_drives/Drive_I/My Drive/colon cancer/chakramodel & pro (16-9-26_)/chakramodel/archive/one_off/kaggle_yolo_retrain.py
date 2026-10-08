import os
import yaml
import multiprocessing
import subprocess
import sys

# 1. Install dependencies if missing BEFORE importing
try:
    import ultralytics
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "ultralytics"], check=True)
    import ultralytics

from ultralytics import YOLO
import torch

def main():
    # ==========================================
    # DATASET COMPOSITION WARNING
    # Do NOT train on a dataset containing only ETIS-Larib images!
    # ACTION: Make sure `chakramodel-yolo-combo-dataset` contains a COMBINED dataset.
    # ==========================================
    
    # Kaggle paths
    dataset_path = "/kaggle/input/datasets/gokulrocky/chakramodel-yolo-combo-dataset"
    working_dir = "/kaggle/working"
    
    if not os.path.exists(dataset_path):
        print(f"ERROR: Dataset not found at {dataset_path}")
        print("Please upload your COMBINED YOLO-formatted dataset to Kaggle and update the 'dataset_path' variable.")
        return

    data_yaml_path = os.path.join(working_dir, "dataset.yaml")
    
    yaml_content = {
        "path": dataset_path,
        "train": "images/train",
        "val": "images/val",
        "names": {
            0: "polyp"
        }
    }
    
    with open(data_yaml_path, 'w') as f:
        yaml.dump(yaml_content, f)

    weight_dir_options = [
        "/kaggle/input/chakramodel-weights",
        "/kaggle/input/datasets/gokulrocky/chakramodel-weights",
        "/kaggle/input/datasets/gokulraj324/chakramodel-weights",
        "/kaggle/working",
        "."
    ]
    
    yolo_weight = None
    for d in weight_dir_options:
        if os.path.exists(os.path.join(d, "best.pt")):
            yolo_weight = os.path.join(d, "best.pt")
            break
            
    if not yolo_weight:
        print("ERROR: Existing YOLO weight 'best.pt' not found in typical Kaggle paths!")
        return
        
    print(f"Loading existing fine-tuned weights from {yolo_weight}")
    model = YOLO(yolo_weight)
    
    print("Starting YOLOv8x Retraining for ETIS-Larib Domain Adaptation...")
    
    # 6. Fix: Gracefully handle CPU-only instances
    device = 0 if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("WARNING: No GPU found. Training on CPU will be extremely slow.")

    # ---------------------------------------------------------
    # PATH B: AGGRESSIVE AUGMENTATION CONFIGURATION
    # ---------------------------------------------------------
    results = model.train(
        data=data_yaml_path,
        epochs=30,
        imgsz=384, 
        batch=16,
        workers=4,
        device=device,
        amp=True,
        project=working_dir,
        name="polyp_yolov8x_etis_fix",
        patience=20,
        save=True,
        exist_ok=True,
        
        # 7. Fix: Explicit seed for reproducible benchmarking
        seed=42,
        
        # AGGRESSIVE AUGMENTATIONS FOR NBI/LCI/BLI (Path B Fix)
        hsv_h=0.1,    
        hsv_s=0.9,    
        hsv_v=0.9,    
        degrees=45.0, 
        translate=0.2,
        scale=0.5,    
        shear=0.1,    
        perspective=0.001, 
        flipud=0.5,   
        fliplr=0.5,   
        mosaic=1.0,   
        mixup=0.2     
    )
    
    print("Training finished! Models saved to /kaggle/working/polyp_yolov8x_etis_fix/weights/")

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
