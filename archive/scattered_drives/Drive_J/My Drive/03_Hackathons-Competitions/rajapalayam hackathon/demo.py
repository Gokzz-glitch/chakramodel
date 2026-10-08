import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
from pipeline import CulturalPipeline

def run_demo():
    print("Starting Data Genesis 2026 - 4-Agent Pipeline Demo")
    
    ckpt_path = 'checkpoints/cnn_best.pth'
    if not os.path.exists(ckpt_path):
        print(f"Error: Could not find CNN checkpoint at {ckpt_path}. Did you run cnn_detector.py?")
        return
        
    pipeline = CulturalPipeline(ckpt_path)
    
    # Generate a dummy test image since we are using FakeData as fallback
    # In a real scenario, we would load an image from the test set
    test_img = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    # Add a pseudo object in the middle to be "detected"
    test_img[64:192, 64:192] = [200, 50, 50]
    
    # Define a secret watermark bit sequence (e.g., 64 bits)
    # 64 bits require 64 blocks of 8x8. Our bbox is max 256x256, so we have plenty of space.
    secret_watermark = np.random.randint(0, 2, 64).tolist()
    print(f"Secret Watermark (first 10 bits): {secret_watermark[:10]}...")
    
    # Run the forward pipeline
    print("Agent 2 & 3: Detecting Object and Embedding Watermark...")
    watermarked_bgr, bbox, class_label = pipeline.process_image(test_img, secret_watermark)
    
    print(f"Detection Complete. Predicted Class: {class_label}")
    print(f"Bounding Box: {bbox}")
    
    # Verify the watermark (Agent 4)
    print("Agent 4: Applying JPEG Compression (Q=75) and Verifying Watermark...")
    compressed_bgr, extracted_bits, ber = pipeline.verify_image(watermarked_bgr, bbox, secret_watermark)
    
    print(f"Extracted Watermark (first 10 bits): {extracted_bits[:10]}...")
    print(f"Bit Error Rate (BER): {ber:.4f}")
    
    if ber < 0.1:
        print("[SUCCESS] Watermark survived JPEG compression and verified ownership (BER < 0.1).")
    else:
        print("[FAILURE] Watermark was lost or corrupted (BER >= 0.1).")
        
    # Display Results
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    # Original
    axes[0].imshow(cv2.cvtColor(test_img, cv2.COLOR_BGR2RGB))
    axes[0].set_title("Original Image")
    axes[0].axis('off')
    
    # Watermarked + BBox
    wm_disp = watermarked_bgr.copy()
    h, w, _ = wm_disp.shape
    x1, y1 = int(bbox[0]*w), int(bbox[1]*h)
    x2, y2 = int(bbox[2]*w), int(bbox[3]*h)
    cv2.rectangle(wm_disp, (x1, y1), (x2, y2), (0, 255, 0), 2)
    axes[1].imshow(cv2.cvtColor(wm_disp, cv2.COLOR_BGR2RGB))
    axes[1].set_title(f"Watermarked & Detected\nClass: {class_label}")
    axes[1].axis('off')
    
    # Compressed
    axes[2].imshow(cv2.cvtColor(compressed_bgr, cv2.COLOR_BGR2RGB))
    axes[2].set_title(f"JPEG Compressed (Q=75)\nBER: {ber:.4f}")
    axes[2].axis('off')
    
    plt.tight_layout()
    plt.savefig('outputs/demo_result.png')
    print("Demo visualization saved to outputs/demo_result.png")
    
if __name__ == "__main__":
    run_demo()
