import cv2
import numpy as np
import os
from pathlib import Path
import glob

def convert_mask_to_yolo(mask_path, output_txt_path, class_id=0):
    """
    Reads a binary segmentation mask and writes a YOLO format bounding box text file.
    YOLO format: class_id x_center y_center width height (normalized 0 to 1)
    """
    # Read mask in grayscale
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        print(f"Error reading {mask_path}")
        return False
        
    height, width = mask.shape
    
    # Find contours (Assuming polyps are white (255) on black (0) background)
    _, thresh = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    bboxes = []
    for cnt in contours:
        # Ignore very small pixel artifacts in the mask
        if cv2.contourArea(cnt) < 50:
            continue
            
        x, y, w, h = cv2.boundingRect(cnt)
        
        # Normalize coordinates to 0.0 - 1.0 (Required by YOLO)
        x_center = (x + w / 2) / width
        y_center = (y + h / 2) / height
        norm_w = w / width
        norm_h = h / height
        
        bboxes.append(f"{class_id} {x_center:.6f} {y_center:.6f} {norm_w:.6f} {norm_h:.6f}")
        
    # Only write a file if a bounding box was found
    if bboxes:
        with open(output_txt_path, 'w') as f:
            f.write('\n'.join(bboxes))
        return True
    return False

def process_dataset(masks_dir, output_labels_dir):
    """
    Iterates through a directory of masks and converts them all to YOLO .txt labels.
    """
    os.makedirs(output_labels_dir, exist_ok=True)
    mask_files = glob.glob(os.path.join(masks_dir, '*.*')) # Handles .png, .jpg, .tif
    
    success_count = 0
    for mask_path in mask_files:
        # Create output path with .txt extension
        base_name = Path(mask_path).stem
        txt_path = os.path.join(output_labels_dir, f"{base_name}.txt")
        
        if convert_mask_to_yolo(mask_path, txt_path):
            success_count += 1
            
    print(f"Processed {len(mask_files)} masks. Successfully generated {success_count} YOLO label files.")

if __name__ == "__main__":
    print("--- ChakraModel Data Prep: Mask to YOLO BBox Converter ---")
    print("Instructions: Update the paths below once datasets are downloaded.")
    
    # TODO: Uncomment and update these paths once you download the datasets
    # process_dataset(r"M:\GOKZZ_4\NIT HACKATHIN\datasets\Kvasir-SEG\masks", 
    #                 r"M:\GOKZZ_4\NIT HACKATHIN\datasets\Kvasir-SEG\labels")
    
    # process_dataset(r"M:\GOKZZ_4\NIT HACKATHIN\datasets\CVC-ClinicDB\Ground Truth", 
    #                 r"M:\GOKZZ_4\NIT HACKATHIN\datasets\CVC-ClinicDB\labels")
