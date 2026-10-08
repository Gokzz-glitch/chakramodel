import os
import json
from pathlib import Path
import random

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
    json_path = base_dir / "segmented-images" / "bounding-boxes.json"
    
    with open(json_path, 'r') as f:
        bboxes = json.load(f)
        
    all_jpgs = list(base_dir.rglob("*.jpg"))
    
    labeled_count = 0
    empty_count = 0
    valid_images = []
    
    # We must EXCLUDE the 'polyps' and 'dyed-lifted-polyps' folders from negative mining.
    # 'polyps' contains duplicates of 'segmented-images/images' + 28 unannotated polyps.
    # 'dyed-lifted-polyps' contains 1002 unannotated polyps. 
    # If we give them empty labels, the model will learn to ignore real polyps!
    exclude_folders = ["masks", "polyps", "dyed-lifted-polyps"]
    
    for img_path in all_jpgs:
        # Check if the file is in an excluded folder
        if any(ex in img_path.parts for ex in exclude_folders):
            continue
            
        valid_images.append(str(img_path))
        
        file_id = img_path.stem
        label_path = img_path.with_suffix('.txt')
        
        lines = []
        if file_id in bboxes:
            img_info = bboxes[file_id]
            img_w = img_info['width']
            img_h = img_info['height']
            for box in img_info['bbox']:
                if box['label'] == 'polyp':
                    yolo_fmt = convert_bbox_to_yolo(box, img_w, img_h)
                    lines.append(yolo_fmt)
                    
        with open(label_path, 'w') as f:
            if lines:
                f.write("\n".join(lines) + "\n")
                labeled_count += 1
            else:
                f.write("")
                empty_count += 1
                
    print(f"Generated {labeled_count} YOLO label files with bounding boxes.")
    print(f"Generated {empty_count} empty YOLO label files for negative images.")
    
    # 80/20 train/val split
    random.seed(42)
    random.shuffle(valid_images)
    split_idx = int(len(valid_images) * 0.8)
    
    train_imgs = valid_images[:split_idx]
    val_imgs = valid_images[split_idx:]
    
    with open(base_dir / "train.txt", 'w') as f:
        f.write("\n".join(train_imgs))
    with open(base_dir / "val.txt", 'w') as f:
        f.write("\n".join(val_imgs))
        
    print(f"Total valid images: {len(valid_images)}")

if __name__ == "__main__":
    main()
