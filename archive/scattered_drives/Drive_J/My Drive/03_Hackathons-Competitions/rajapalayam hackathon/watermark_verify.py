import cv2
import numpy as np

def extract_watermark(image, bbox, num_bits):
    """
    Extracts the watermark from the bounding box region using block-DCT.
    - image: RGB image as numpy array (H, W, 3) (potentially JPEG compressed)
    - bbox: list or tuple [x_min_rel, y_min_rel, x_max_rel, y_max_rel]
    - num_bits: expected length of the watermark
    Returns: list of extracted bits
    """
    img_yuv = cv2.cvtColor(image, cv2.COLOR_RGB2YCrCb)
    Y = img_yuv[:, :, 0].astype(np.float32)

    h, w = Y.shape
    x_min = int(bbox[0] * w)
    y_min = int(bbox[1] * h)
    x_max = int(bbox[2] * w)
    y_max = int(bbox[3] * h)
    
    extracted_bits = []
    bit_idx = 0
    
    for row in range(y_min, y_max - 8, 8):
        for col in range(x_min, x_max - 8, 8):
            if bit_idx >= num_bits:
                break
                
            block = Y[row:row+8, col:col+8]
            dct_block = cv2.dct(block)
            
            c1_pos = (4, 3)
            c2_pos = (5, 2)
            
            c1 = dct_block[c1_pos]
            c2 = dct_block[c2_pos]
            
            if c1 > c2:
                extracted_bits.append(1)
            else:
                extracted_bits.append(0)
                
            bit_idx += 1
            
    return extracted_bits

def calculate_ber(original_bits, extracted_bits):
    if len(original_bits) != len(extracted_bits) or len(original_bits) == 0:
        return 1.0 # 100% error if mismatched
        
    errors = sum([1 for o, e in zip(original_bits, extracted_bits) if o != e])
    ber = errors / len(original_bits)
    return ber
