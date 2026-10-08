import os
import sys
import time
import cv2
import pymupdf

sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH = "C:/Users/imgk3/Downloads/Opus1.pdf"
TEMP_DIR = "temp_ocr"

def extract_and_preprocess(pdf_path=PDF_PATH, out_dir=TEMP_DIR):
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    print(f"Opening {pdf_path}: {total_pages} pages")
    
    extracted_count = 0
    skipped_count = 0
    
    for page_idx in range(total_pages):
        out_file = os.path.join(out_dir, f"page_{page_idx:03d}.jpg")
        if os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
            skipped_count += 1
            continue
        
        page = doc[page_idx]
        img_list = page.get_images()
        if not img_list:
            print(f"Warning: Page {page_idx} has no images!")
            continue
        
        xref = img_list[0][0]
        base_img = doc.extract_image(xref)
        img_bytes = base_img["image"]
        
        # Decode image using OpenCV from memory
        import numpy as np
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        
        if img is None:
            print(f"Error decoding image on page {page_idx}")
            continue
        
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        resized = cv2.resize(blurred, (int(w * 0.5), int(h * 0.5)), interpolation=cv2.INTER_AREA)
        
        cv2.imwrite(out_file, resized, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        extracted_count += 1
        
        if extracted_count % 50 == 0:
            print(f"Extracted and preprocessed {extracted_count}/{total_pages} pages (elapsed: {time.time()-t0:.1f}s)")
            
    print(f"Complete: {extracted_count} extracted, {skipped_count} cached/skipped in {time.time()-t0:.1f}s")

if __name__ == "__main__":
    extract_and_preprocess()
