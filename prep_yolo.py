import json
import os
import shutil

json_path = r'M:\GOKZZ_4\NIT HACKATHIN\datasets\colon_cancer_dataset\segmented-images\bounding-boxes.json'
images_dir = r'M:\GOKZZ_4\NIT HACKATHIN\datasets\colon_cancer_dataset\segmented-images\images'
yolo_base_dir = r'M:\GOKZZ_4\NIT HACKATHIN\datasets\yolo'

os.makedirs(os.path.join(yolo_base_dir, 'images', 'train'), exist_ok=True)
os.makedirs(os.path.join(yolo_base_dir, 'labels', 'train'), exist_ok=True)

with open(json_path, 'r') as f:
    data = json.load(f)

count = 0
for img_id, info in data.items():
    img_name = f"{img_id}.jpg"
    src_img = os.path.join(images_dir, img_name)
    
    if not os.path.exists(src_img):
        continue
        
    width = info['height'] # wait, let's look at the dictionary: {'height': 529, 'width': 622}
    w = info['width']
    h = info['height']
    
    yolo_bboxes = []
    for bbox in info['bbox']:
        xmin = bbox['xmin']
        ymin = bbox['ymin']
        xmax = bbox['xmax']
        ymax = bbox['ymax']
        
        # Convert to YOLO (normalized center x, center y, w, h)
        box_w = xmax - xmin
        box_h = ymax - ymin
        x_center = xmin + box_w / 2.0
        y_center = ymin + box_h / 2.0
        
        yolo_bboxes.append(f"0 {x_center/w:.6f} {y_center/h:.6f} {box_w/w:.6f} {box_h/h:.6f}")
        
    if yolo_bboxes:
        # Copy image
        shutil.copy(src_img, os.path.join(yolo_base_dir, 'images', 'train', img_name))
        
        # Write label
        label_path = os.path.join(yolo_base_dir, 'labels', 'train', f"{img_id}.txt")
        with open(label_path, 'w') as f:
            f.write("\n".join(yolo_bboxes))
            
        count += 1

print(f"Dataset preparation complete! Converted {count} images and labels.")

# Create dataset.yaml
yaml_content = f"""
path: {yolo_base_dir}
train: images/train
val: images/train  # Using train as val for hackathon rapid prototyping if no val set exists

names:
  0: polyp
"""

with open(os.path.join(yolo_base_dir, 'dataset.yaml'), 'w') as f:
    f.write(yaml_content.strip())
