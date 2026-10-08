import cv2
import numpy as np

def embed_watermark(image, bbox, watermark_bits, alpha=15.0):
    """
    Embeds a binary watermark string into the bounding box region using block-DCT.
    - image: RGB image as numpy array (H, W, 3)
    - bbox: list or tuple [x_min_rel, y_min_rel, x_max_rel, y_max_rel] (values 0.0 to 1.0)
    - watermark_bits: list of ints [0, 1, 0, ...]
    - alpha: robustness margin
    """
    img_yuv = cv2.cvtColor(image, cv2.COLOR_RGB2YCrCb)
    Y = img_yuv[:, :, 0].astype(np.float32)

    h, w = Y.shape
    x_min = int(bbox[0] * w)
    y_min = int(bbox[1] * h)
    x_max = int(bbox[2] * w)
    y_max = int(bbox[3] * h)
    
    # Ensure block size is multiple of 8
    width = x_max - x_min
    height = y_max - y_min
    
    # We need to embed len(watermark_bits) bits. Each 8x8 block can hold 1 bit.
    # Just to be safe, we tile the bits if we have more blocks, but for simplicity, we just embed sequentially.
    bit_idx = 0
    num_bits = len(watermark_bits)
    
    for row in range(y_min, y_max - 8, 8):
        for col in range(x_min, x_max - 8, 8):
            if bit_idx >= num_bits:
                break
                
            block = Y[row:row+8, col:col+8]
            dct_block = cv2.dct(block)
            
            # Select two mid-frequency coefficients, e.g., (4, 3) and (5, 2)
            c1_pos = (4, 3)
            c2_pos = (5, 2)
            
            c1 = dct_block[c1_pos]
            c2 = dct_block[c2_pos]
            
            bit = watermark_bits[bit_idx]
            
            # Embed logic
            if bit == 1:
                if c1 <= c2 + alpha:
                    diff = (c2 + alpha - c1) / 2.0
                    dct_block[c1_pos] += diff
                    dct_block[c2_pos] -= diff
            else: # bit == 0
                if c2 <= c1 + alpha:
                    diff = (c1 + alpha - c2) / 2.0
                    dct_block[c1_pos] -= diff
                    dct_block[c2_pos] += diff
            
            Y[row:row+8, col:col+8] = cv2.idct(dct_block)
            bit_idx += 1
            
    # Recombine
    img_yuv[:, :, 0] = np.clip(Y, 0, 255).astype(np.uint8)
    watermarked_img = cv2.cvtColor(img_yuv, cv2.COLOR_YCrCb2RGB)
    
    return watermarked_img
