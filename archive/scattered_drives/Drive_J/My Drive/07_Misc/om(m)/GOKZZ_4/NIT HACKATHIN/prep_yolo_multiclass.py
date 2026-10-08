import json
import os
import shutil
from pathlib import Path

# Setup paths
base_dir = r'M:\GOKZZ_4\NIT HACKATHIN\datasets\colon_cancer_dataset'
json_path = os.path.join(base_dir, 'segmented-images', 'bounding-boxes.json')
polyps_images_dir = os.path.join(base_dir, 'segmented-images', 'images')

yolo_base_dir = r'M:\GOKZZ_4\NIT HACKATHIN\datasets\yolo_multiclass'
os.makedirs(os.path.join(yolo_base_dir, 'images', 'train'), exist_ok=True)
os.makedirs(os.path.join(yolo_base_dir, 'labels', 'train'), exist_ok=True)

# Class IDs mapping
class_map = {
    'polyp': 0,
    'fecal': 1,
    'impacted-stool': 2,
    'bubbles-occlusion': 3,
    'dyed-lifted-polyps': 4
}

count_per_class = {k: 0 for k in class_map.keys()}

# 1. Process Polyps (From JSON)
print("Processing polyps with actual bounding boxes...")
if os.path.exists(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    for img_id, info in data.items():
        img_name = f"{img_id}.jpg"
        src_img = os.path.join(polyps_images_dir, img_name)
        
        if not os.path.exists(src_img):
            continue
            
        w = info['width']
        h = info['height']
        
        yolo_bboxes = []
        for bbox in info.get('bbox', []):
            xmin = bbox['xmin']
            ymin = bbox['ymin']
            xmax = bbox['xmax']
            ymax = bbox['ymax']
            
            box_w = xmax - xmin
            box_h = ymax - ymin
            x_center = xmin + box_w / 2.0
            y_center = ymin + box_h / 2.0
            
            yolo_bboxes.append(f"{class_map['polyp']} {x_center/w:.6f} {y_center/h:.6f} {box_w/w:.6f} {box_h/h:.6f}")
            
        if yolo_bboxes:
            # Save
            shutil.copy(src_img, os.path.join(yolo_base_dir, 'images', 'train', img_name))
            with open(os.path.join(yolo_base_dir, 'labels', 'train', f"{img_id}.txt"), 'w') as f:
                f.write("\n".join(yolo_bboxes))
            count_per_class['polyp'] += 1

# 2. Process Artifact Classes (Full-Frame bounding boxes)
artifact_classes = ['fecal', 'impacted-stool', 'bubbles-occlusion', 'dyed-lifted-polyps']

print("Processing artifact classes (Synthesizing full-frame bounding boxes)...")
for cls_name in artifact_classes:
    cls_dir = os.path.join(base_dir, cls_name)
    if not os.path.exists(cls_dir):
        continue
        
    cls_id = class_map[cls_name]
    full_frame_bbox = f"{cls_id} 0.500000 0.500000 1.000000 1.000000"
    
    # Check if we need to oversample (for impacted-stool)
    multiplier = 8 if cls_name == 'impacted-stool' else 1
    
    for img_name in os.listdir(cls_dir):
        if not img_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
            
        src_img = os.path.join(cls_dir, img_name)
        base_name = Path(img_name).stem
        
        for i in range(multiplier):
            suffix = f"_dup{i}" if i > 0 else ""
            out_img_name = f"{base_name}{suffix}.jpg"
            out_txt_name = f"{base_name}{suffix}.txt"
            
            shutil.copy(src_img, os.path.join(yolo_base_dir, 'images', 'train', out_img_name))
            with open(os.path.join(yolo_base_dir, 'labels', 'train', out_txt_name), 'w') as f:
                f.write(full_frame_bbox)
                
            count_per_class[cls_name] += 1

print("\n--- Final Dataset Balance ---")
for cls_name, count in count_per_class.items():
    print(f"{cls_name}: {count} images")

# 3. Create dataset_multiclass.yaml
yaml_content = f"""
path: {yolo_base_dir}
train: images/train
val: images/train  

names:
  0: polyp
  1: fecal
  2: impacted-stool
  3: bubbles-occlusion
  4: dyed-lifted-polyps
"""

with open(os.path.join(yolo_base_dir, 'dataset_multiclass.yaml'), 'w') as f:
    f.write(yaml_content.strip())
