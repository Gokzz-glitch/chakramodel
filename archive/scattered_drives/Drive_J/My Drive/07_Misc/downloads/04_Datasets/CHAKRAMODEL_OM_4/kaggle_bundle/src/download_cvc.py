import os
from pathlib import Path
import cv2
import numpy as np

def download_cvc_clinicdb():
    print("Loading HuggingFace datasets library...")
    try:
        from datasets import load_dataset
    except ImportError:
        print("[ERROR] 'datasets' library not found. Please install it using 'pip install datasets'")
        return

    print("Downloading CVC-ClinicDB dataset from HuggingFace...")
    # There are multiple mirrors; we will use a common one containing images and masks
    
    try:
        dataset = load_dataset("Aeoo/CVC-ClinicDB", split='train')
    except Exception as e:
        print(f"Failed to load dataset from HF: {e}")
        return

    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "cvc-clinicdb"
    
    images_dir = data_dir / "images"
    masks_dir = data_dir / "masks"
    
    images_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Saving {len(dataset)} images to {data_dir} ...")
    
    # Try to find the image and mask keys dynamically
    keys = list(dataset[0].keys())
    img_key = next((k for k in keys if 'image' in k.lower() or 'img' in k.lower()), keys[0])
    mask_key = next((k for k in keys if 'mask' in k.lower() or 'label' in k.lower() or 'gt' in k.lower()), keys[1] if len(keys)>1 else keys[0])
    
    print(f"Using keys - Image: '{img_key}', Mask: '{mask_key}'")

    for i, item in enumerate(dataset):
        # HF datasets usually return PIL images
        image = item[img_key]
        mask = item[mask_key]
        
        # Convert PIL to cv2 BGR
        img_np = np.array(image)
        if len(img_np.shape) == 3 and img_np.shape[2] == 3:
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = img_np
            
        mask_np = np.array(mask)
        if len(mask_np.shape) == 3:
            mask_np = cv2.cvtColor(mask_np, cv2.COLOR_RGB2GRAY)
            
        # Ensure mask is binary (0 or 255)
        _, mask_bin = cv2.threshold(mask_np, 127, 255, cv2.THRESH_BINARY)
        
        # Save them
        cv2.imwrite(str(images_dir / f"{i:04d}.png"), img_bgr)
        cv2.imwrite(str(masks_dir / f"{i:04d}.png"), mask_bin)
        
    print("Download and extraction complete!")

if __name__ == "__main__":
    download_cvc_clinicdb()
