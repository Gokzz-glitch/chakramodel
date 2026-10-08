import os
import json
import shutil
import random
from pathlib import Path

def convert_bbox_to_yolo(bbox, img_w, img_h):
    x_center = (bbox['xmin'] + bbox['xmax']) / 2.0 / img_w
    y_center = (bbox['ymin'] + bbox['ymax']) / 2.0 / img_h
    w = (bbox['xmax'] - bbox['xmin']) / img_w
    h = (bbox['ymax'] - bbox['ymin']) / img_h
    
    x_center = max(0.0, min(1.0, x_center))
    y_center = max(0.0, min(1.0, y_center))
    w = max(0.0, min(1.0, w))
    h = max(0.0, min(1.0, h))
    return f"0 {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}"

def main():
    base_dir = Path(r"M:\chakramodel\data\colon_cancer_dataset")
    out_dir = Path(r"M:\chakramodel\dataset_yolo")
    
    # Create unified YOLO structure
    for split in ['train', 'val']:
        (out_dir / 'images' / split).mkdir(parents=True, exist_ok=True)
        (out_dir / 'labels' / split).mkdir(parents=True, exist_ok=True)
        
    json_path = base_dir / "segmented-images" / "bounding-boxes.json"
    
    with open(json_path, 'r') as f:
        bboxes = json.load(f)
        
    all_jpgs = list(base_dir.rglob("*.jpg"))
    exclude_folders = ["masks", "polyps", "dyed-lifted-polyps"]
    
    valid_images = []
    for img_path in all_jpgs:
        if any(ex in img_path.parts for ex in exclude_folders):
            continue
        valid_images.append(img_path)
        
    # 80/20 train/val split
    random.seed(42)
    random.shuffle(valid_images)
    split_idx = int(len(valid_images) * 0.8)
    
    splits = {
        'train': valid_images[:split_idx],
        'val': valid_images[split_idx:]
    }
    
    labeled_count = 0
    empty_count = 0
    
    for split_name, img_paths in splits.items():
        for img_path in img_paths:
            file_id = img_path.stem
            
            # Destination paths
            dest_img = out_dir / 'images' / split_name / img_path.name
            dest_label = out_dir / 'labels' / split_name / f"{file_id}.txt"
            
            # 1. Copy image (handle duplicates by adding unique prefix if needed, but uuid prevents this)
            # Actually, bubbles-occlusion and fecal might have duplicate names if they are e.g. "image_1.jpg"
            # Let's ensure unique names by prefixing the parent folder name
            parent_name = img_path.parent.name
            if parent_name == "images":
                parent_name = img_path.parent.parent.name # e.g. "negative" or "segmented-images"
                
            unique_name = f"{parent_name}_{img_path.name}"
            dest_img = out_dir / 'images' / split_name / unique_name
            dest_label = out_dir / 'labels' / split_name / f"{dest_img.stem}.txt"
            
            shutil.copy2(img_path, dest_img)
            
            # 2. Create label
            lines = []
            if file_id in bboxes:
                img_info = bboxes[file_id]
                img_w = img_info['width']
                img_h = img_info['height']
                for box in img_info['bbox']:
                    if box['label'] == 'polyp':
                        yolo_fmt = convert_bbox_to_yolo(box, img_w, img_h)
                        lines.append(yolo_fmt)
                        
            with open(dest_label, 'w') as f:
                if lines:
                    f.write("\n".join(lines) + "\n")
                    labeled_count += 1
                else:
                    f.write("")
                    empty_count += 1
                    
    print(f"Dataset rebuilt successfully in YOLO format at {out_dir}")
    print(f"Positive labels: {labeled_count}")
    print(f"Negative labels: {empty_count}")

    # Write new dataset.yaml
    yaml_content = f"""path: {out_dir.resolve().as_posix()}
train: images/train
val: images/val

names:
  0: polyp
"""
    with open(out_dir / "dataset.yaml", "w") as f:
        f.write(yaml_content)
    print("New dataset.yaml created.")

if __name__ == "__main__":
    main()
