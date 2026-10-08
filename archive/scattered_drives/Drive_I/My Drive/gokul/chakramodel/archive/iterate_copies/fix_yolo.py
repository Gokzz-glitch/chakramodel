import os
import shutil
from pathlib import Path
import cv2
from ultralytics import YOLO

# Import mask_to_yolo from src.utils
import sys
sys.path.insert(0, r"M:\chakramodel\src\utils")
from mask_to_bbox import convert_mask_to_yolo

def prepare_and_train():
    root = Path(r"M:\chakramodel")
    images_dir = root / "data" / "kvasir-seg" / "images"
    masks_dir = root / "data" / "kvasir-seg" / "masks"
    
    # Get all images and masks
    image_paths = sorted([p for p in images_dir.glob("*") if p.suffix.lower() in {".jpg", ".png"}])
    n_total = len(image_paths)
    n_train = int(0.7 * n_total)
    n_val = int(0.1 * n_total)
    
    train_images = image_paths[:n_train]
    val_images = image_paths[n_train:n_train+n_val]
    
    # Create fixed dataset dir
    yolo_dir = root / "dataset_yolo_fixed"
    out_images = yolo_dir / "images" / "train"
    out_labels = yolo_dir / "labels" / "train"
    out_val_images = yolo_dir / "images" / "val"
    out_val_labels = yolo_dir / "labels" / "val"
    os.makedirs(out_images, exist_ok=True)
    os.makedirs(out_labels, exist_ok=True)
    os.makedirs(out_val_images, exist_ok=True)
    os.makedirs(out_val_labels, exist_ok=True)
    
    # Copy and convert
    count = 0
    for img_p in train_images:
        mask_p = masks_dir / f"{img_p.stem}{img_p.suffix}"
        if not mask_p.exists():
            continue
            
        label_p = out_labels / f"{img_p.stem}.txt"
        success = convert_mask_to_yolo(str(mask_p), str(label_p))
        if success:
            shutil.copy2(img_p, out_images / img_p.name)
            count += 1
            
    val_count = 0
    for img_p in val_images:
        mask_p = masks_dir / f"{img_p.stem}{img_p.suffix}"
        if not mask_p.exists():
            continue
            
        label_p = out_val_labels / f"{img_p.stem}.txt"
        success = convert_mask_to_yolo(str(mask_p), str(label_p))
        if success:
            shutil.copy2(img_p, out_val_images / img_p.name)
            val_count += 1
            
    print(f"Prepared {count} images for training and {val_count} for validation.")
    
    # Create dataset.yaml
    yaml_content = f"""
path: {yolo_dir}
train: images/train
val: images/val

names:
  0: polyp
"""
    yaml_path = yolo_dir / "dataset.yaml"
    with open(yaml_path, 'w') as f:
        f.write(yaml_content.strip())
        
    # Train YOLO
    print("Training YOLO...")
    model = YOLO("yolov8n.pt")
    model.train(
        data=str(yaml_path),
        epochs=3,
        imgsz=448,
        batch=16,
        project=str(root / "outputs"),
        name="polyp_yolo_fixed",
        exist_ok=True
    )
    
    # Copy best.pt to weights
    best_pt = root / "outputs" / "polyp_yolo_fixed" / "weights" / "best.pt"
    target_pt = root / "weights" / "best.pt"
    if best_pt.exists():
        shutil.copy2(best_pt, target_pt)
        print(f"Copied {best_pt} to {target_pt}")
    else:
        print("Training failed to produce best.pt")

if __name__ == "__main__":
    prepare_and_train()
