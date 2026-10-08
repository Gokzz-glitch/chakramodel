import os
import cv2
import numpy as np

def generate_shape_dataset():
    print("Generating a synthetic geometric shapes dataset for hackathon training...")
    target_classes = ['circle', 'rectangle', 'triangle', 'ellipse', 'line', 'polygon']
    num_per_class = 200
    img_size = 64
    
    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'raw'))
    os.makedirs(raw_dir, exist_ok=True)
    
    for c in target_classes:
        class_dir = os.path.join(raw_dir, c)
        os.makedirs(class_dir, exist_ok=True)
        
        for i in range(num_per_class):
            img = np.ones((img_size, img_size, 3), dtype=np.uint8) * 255 # White background
            color = (int(np.random.randint(0, 255)), int(np.random.randint(0, 255)), int(np.random.randint(0, 255)))
            
            if c == 'circle':
                center = (np.random.randint(15, 49), np.random.randint(15, 49))
                radius = np.random.randint(5, 15)
                cv2.circle(img, center, radius, color, -1)
            elif c == 'rectangle':
                pt1 = (np.random.randint(5, 20), np.random.randint(5, 20))
                pt2 = (np.random.randint(40, 60), np.random.randint(40, 60))
                cv2.rectangle(img, pt1, pt2, color, -1)
            elif c == 'triangle':
                pts = np.array([[np.random.randint(5, 60), np.random.randint(5, 60)] for _ in range(3)], np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.fillPoly(img, [pts], color)
            elif c == 'ellipse':
                center = (np.random.randint(20, 44), np.random.randint(20, 44))
                axes = (np.random.randint(10, 20), np.random.randint(5, 15))
                angle = np.random.randint(0, 180)
                cv2.ellipse(img, center, axes, angle, 0, 360, color, -1)
            elif c == 'line':
                pt1 = (np.random.randint(5, 60), np.random.randint(5, 60))
                pt2 = (np.random.randint(5, 60), np.random.randint(5, 60))
                thickness = np.random.randint(1, 5)
                cv2.line(img, pt1, pt2, color, thickness)
            elif c == 'polygon':
                num_points = np.random.randint(4, 7)
                pts = np.array([[np.random.randint(5, 60), np.random.randint(5, 60)] for _ in range(num_points)], np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.fillPoly(img, [pts], color)
                
            save_path = os.path.join(class_dir, f"{c}_{i}.png")
            cv2.imwrite(save_path, img)
            
    print(f"Generated {num_per_class} images for {len(target_classes)} classes.")

if __name__ == '__main__':
    generate_shape_dataset()
