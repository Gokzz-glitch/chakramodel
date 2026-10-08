"""
╔══════════════════════════════════════════════════════════════╗
║               MANDIVISION AUTO-ANNOTATOR                    ║
║     GPU-Accelerated Bounding Box Generation                 ║
╚══════════════════════════════════════════════════════════════╝

This script uses a pre-trained YOLOv8 model to auto-generate
initial bounding boxes for the dataset. This saves hours of manual
drawing. The user only needs to verify/tweak the boxes.

NOTE: This is just for dataset PREPARATION (Round 1). 
The final model (Round 2) will be trained entirely from scratch.
"""

import os
import torch
from ultralytics import YOLO
import sys

# Paths
DATASET_DIR = r"J:\My Drive\rajapalayam hackathon\processed_dataset"
LABELS_DIR = r"J:\My Drive\rajapalayam hackathon\processed_dataset\labels"
IMAGES_DIR = r"J:\My Drive\rajapalayam hackathon\processed_dataset\images"

def setup_directories():
    os.makedirs(LABELS_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    print(f"Created label directory: {LABELS_DIR}")

def main():
    print("=" * 60)
    print("  🚀 MANDIVISION GPU AUTO-ANNOTATOR")
    print("=" * 60)
    
    # 1. Check GPU
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"\n💻 Hardware Acceleration: Using {device.upper()}")
    if device == 'cuda':
        print(f"   Detected GPU: {torch.cuda.get_device_name(0)}")
        print(f"   VRAM Allocated: {torch.cuda.memory_allocated(0) / 1024**2:.1f} MB")
    
    print("\n📦 Loading YOLOv8 nano model (fastest)...")
    try:
        # Load pre-trained model
        model = YOLO('yolov8n.pt')
        # Move model to GPU explicitly
        model.to(device)
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        sys.exit(1)

    setup_directories()

    # 2. Gather images
    images = [f for f in os.listdir(DATASET_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    print(f"\n🔍 Found {len(images)} images to process.")

    # We only care about fruits/veg COCO classes to filter out noise (like people, cars)
    # COCO classes: 46=banana, 47=apple, 49=orange, 50=broccoli, 51=carrot, 52=hot dog, 53=pizza, 54=donut, 55=cake
    # For Indian produce not in COCO, we'll just accept all detections and remap them later manually
    # or just keep classes 46-51
    
    target_classes = [46, 47, 49, 50, 51] 
    print(f"🎯 Target COCO classes (Fruits/Veg): {target_classes}")

    print(f"\n🔥 FIRING UP GPU FOR BATCH INFERENCE...")
    
    # Process in batches for maximum GPU utilization
    batch_size = 16
    total_processed = 0
    total_boxes = 0
    
    for i in range(0, len(images), batch_size):
        batch_files = images[i:i+batch_size]
        batch_paths = [os.path.join(DATASET_DIR, f) for f in batch_files]
        
        # Run inference (stream=False so we get all results)
        # conf=0.15 is low to catch unusual Indian fruits
        results = model.predict(source=batch_paths, conf=0.15, device=device, verbose=False)
        
        for idx, result in enumerate(results):
            img_file = batch_files[idx]
            base_name = os.path.splitext(img_file)[0]
            label_file = os.path.join(LABELS_DIR, f"{base_name}.txt")
            
            # Move the image into the images folder to organize YOLO style
            src_path = os.path.join(DATASET_DIR, img_file)
            dst_path = os.path.join(IMAGES_DIR, img_file)
            
            if os.path.exists(src_path):
                import shutil
                shutil.move(src_path, dst_path)
            
            boxes_written = 0
            with open(label_file, 'w') as f:
                # result.boxes has xywhn (normalized) which is what YOLO wants
                for box in result.boxes:
                    cls_id = int(box.cls.item())
                    # Write everything as class 0 ("produce") for our custom dataset
                    # We want the bounding box coordinates, the user will refine the exact class later
                    
                    x_center, y_center, width, height = box.xywhn[0].tolist()
                    f.write(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                    boxes_written += 1
                    total_boxes += 1
            
            total_processed += 1
            
        print(f"   Processed {total_processed}/{len(images)} images... (Generated {total_boxes} boxes)")
        
    print("\n" + "=" * 60)
    print(f"  ✅ AUTO-ANNOTATION COMPLETE")
    print(f"  Processed {total_processed} images.")
    print(f"  Generated {total_boxes} total bounding boxes.")
    print("=" * 60)

if __name__ == "__main__":
    main()
