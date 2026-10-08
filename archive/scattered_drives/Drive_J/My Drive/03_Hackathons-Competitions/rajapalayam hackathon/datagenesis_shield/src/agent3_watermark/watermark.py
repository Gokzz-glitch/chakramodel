import cv2
import numpy as np
import os
import hashlib

def get_payload_from_key(key: str) -> str:
    """Hashes the key and returns a 64-bit binary string payload."""
    h = hashlib.sha256(key.encode('utf-8')).hexdigest()
    # take first 16 hex chars = 64 bits, convert to binary string
    binary_payload = bin(int(h[:16], 16))[2:].zfill(64)
    return binary_payload

def embed_watermark(image_path: str, payload: str, alpha: float) -> np.ndarray:
    """Embeds a 64-bit payload into the Y channel DCT of an image."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read {image_path}")
    
    # Resize to exactly 64x64 for this prototype to fit exactly 64 (8x8) blocks
    img = cv2.resize(img, (64, 64))
    
    # Convert to YCrCb and get Y channel
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    Y = ycrcb[:, :, 0].astype(np.float32)
    
    # Positions to compare in each 8x8 DCT block (mid-frequency)
    pos1, pos2 = (4, 3), (3, 4)
    
    bit_index = 0
    # Process 8x8 blocks
    for i in range(0, Y.shape[0], 8):
        for j in range(0, Y.shape[1], 8):
            if bit_index >= 64:
                break
                
            block = Y[i:i+8, j:j+8]
            dct_block = cv2.dct(block)
            
            # Embed bit
            bit = int(payload[bit_index])
            val1 = dct_block[pos1]
            val2 = dct_block[pos2]
            
            # If bit is 1, val1 should be > val2 by alpha
            # If bit is 0, val1 should be < val2 by alpha
            if bit == 1:
                if val1 <= val2:
                    dct_block[pos1] = val2 + alpha
            else:
                if val1 >= val2:
                    dct_block[pos2] = val1 + alpha
                    
            # IDCT and replace block
            Y[i:i+8, j:j+8] = cv2.idct(dct_block)
            bit_index += 1
            
    # Reconstruct image
    Y = np.clip(Y, 0, 255).astype(np.uint8)
    ycrcb[:, :, 0] = Y
    watermarked_img = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
    return watermarked_img

def extract_watermark(image_path: str) -> str:
    """Extracts a 64-bit payload from the Y channel DCT of an image."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read {image_path}")
        
    img = cv2.resize(img, (64, 64))
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    Y = ycrcb[:, :, 0].astype(np.float32)
    
    pos1, pos2 = (4, 3), (3, 4)
    payload = ""
    
    bit_index = 0
    for i in range(0, Y.shape[0], 8):
        for j in range(0, Y.shape[1], 8):
            if bit_index >= 64:
                break
                
            block = Y[i:i+8, j:j+8]
            dct_block = cv2.dct(block)
            
            val1 = dct_block[pos1]
            val2 = dct_block[pos2]
            
            if val1 > val2:
                payload += "1"
            else:
                payload += "0"
                
            bit_index += 1
            
    return payload

def run_watermark_batch(config, source_dir, output_dir):
    print(f"[Agent 3 - Watermark] Watermarking images from {source_dir} to {output_dir}")
    payload = get_payload_from_key(config['watermark']['payload'])
    alpha = config['watermark']['alpha']
    
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(source_dir):
        print(f"[Agent 3 - Watermark] Source dir {source_dir} not found.")
        return

    files = [f for f in os.listdir(source_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
    for f in files:
        in_path = os.path.join(source_dir, f)
        out_path = os.path.join(output_dir, f)
        
        watermarked_img = embed_watermark(in_path, payload, alpha)
        cv2.imwrite(out_path, watermarked_img)
    
    print(f"[Agent 3 - Watermark] Processed {len(files)} files.")

# Overwrite dummy for verification script
extract_watermark_dummy = extract_watermark
