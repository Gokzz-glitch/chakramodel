import os
import json
import shutil
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
    
    if out_dir.exists():
        print(f"Removing old {out_dir}")
        shutil.rmtree(out_dir)
    
    for split in ['train', 'val', 'test']:
        (out_dir / 'images' / split).mkdir(parents=True, exist_ok=True)
        (out_dir / 'labels' / split).mkdir(parents=True, exist_ok=True)
        
    json_path = base_dir / "segmented-images" / "bounding-boxes.json"
    with open(json_path, 'r') as f: bboxes = json.load(f)
        
    all_jpgs = list(base_dir.rglob("*.jpg"))
    exclude_folders = ["masks", "polyps", "dyed-lifted-polyps"]
    
    valid_images = []
    for img_path in all_jpgs:
        if any(ex in img_path.parts for ex in exclude_folders):
            continue
        valid_images.append(img_path)
        
    positive_images = [p for p in valid_images if p.parent.name == "images" and p.parent.parent.name == "segmented-images"]
    negative_images = [p for p in valid_images if not (p.parent.name == "images" and p.parent.parent.name == "segmented-images")]
    
    # Sort strictly by filename. This mimics KvasirSEGDataset sorting in segmenter.
    positive_images = sorted(positive_images, key=lambda p: p.name)
    negative_images = sorted(negative_images, key=lambda p: p.name)
    
    def get_splits(img_list):
        n_total = len(img_list)
        n_train = int(0.7 * n_total)
        n_val = int(0.1 * n_total)
        return {
            'train': img_list[:n_train],
            'val': img_list[n_train:n_train+n_val],
            'test': img_list[n_train+n_val:]
        }
        
    pos_splits = get_splits(positive_images)
    neg_splits = get_splits(negative_images)
    
    labeled_count = 0
    empty_count = 0
    
    for split_name in ['train', 'val', 'test']:
        img_paths = pos_splits[split_name] + neg_splits[split_name]
        for img_path in img_paths:
            file_id = img_path.stem
            parent_name = img_path.parent.name
            if parent_name == "images":
                parent_name = img_path.parent.parent.name
                
            unique_name = f"{parent_name}_{img_path.name}"
            dest_img = out_dir / 'images' / split_name / unique_name
            dest_label = out_dir / 'labels' / split_name / f"{dest_img.stem}.txt"
            
            shutil.copy2(img_path, dest_img)
            
            lines = []
            if file_id in bboxes:
                img_info = bboxes[file_id]
                for box in img_info['bbox']:
                    if box['label'] == 'polyp':
                        yolo_fmt = convert_bbox_to_yolo(box, img_info['width'], img_info['height'])
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
    print(f"Empty labels (background): {empty_count}")
    print(f"Train size: {len(pos_splits['train']) + len(neg_splits['train'])} ({len(pos_splits['train'])} polyps)")
    print(f"Val size: {len(pos_splits['val']) + len(neg_splits['val'])} ({len(pos_splits['val'])} polyps)")
    print(f"Test size: {len(pos_splits['test']) + len(neg_splits['test'])} ({len(pos_splits['test'])} polyps)")

if __name__ == "__main__":
    main()
