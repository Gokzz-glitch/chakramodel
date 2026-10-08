import cv2
import numpy as np

def letterbox_pad(img, target_size=(352, 352), color=(0, 0, 0)):
    """
    Pads an image to a square aspect ratio and then resizes it to target_size.
    Returns the padded image and the padding metadata needed to reverse the operation.
    """
    if img is None or img.size == 0:
        return img, None
        
    h, w = img.shape[:2]
    
    # Calculate padding to make the image square
    if h > w:
        pad_top = 0
        pad_bottom = 0
        pad_left = (h - w) // 2
        pad_right = h - w - pad_left
        square_dim = h
    else:
        pad_top = (w - h) // 2
        pad_bottom = w - h - pad_top
        pad_left = 0
        pad_right = 0
        square_dim = w
        
    # Pad the image
    if len(img.shape) == 3:
        padded = cv2.copyMakeBorder(img, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_CONSTANT, value=color)
    else:
        val = color[0] if isinstance(color, tuple) else color
        padded = cv2.copyMakeBorder(img, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_CONSTANT, value=val)
        
    # Resize to target size
    if target_size is not None:
        interp = cv2.INTER_LINEAR if len(img.shape) == 3 else cv2.INTER_NEAREST
        resized = cv2.resize(padded, target_size, interpolation=interp)
    else:
        resized = padded
        
    meta = {
        'orig_h': h,
        'orig_w': w,
        'pad_top': pad_top,
        'pad_bottom': pad_bottom,
        'pad_left': pad_left,
        'pad_right': pad_right,
        'square_dim': square_dim
    }
    return resized, meta

def unletterbox(img, meta):
    """
    Reverses the letterbox padding operation.
    img: The image to unpad (typically a predicted mask)
    meta: The metadata dictionary returned by letterbox_pad
    """
    if meta is None or img is None or img.size == 0:
        return img
        
    # First, if the image was resized, we need to resize it back to the square_dim
    h, w = img.shape[:2]
    if meta['square_dim'] != h or meta['square_dim'] != w:
        interp = cv2.INTER_LINEAR if len(img.shape) == 3 else cv2.INTER_NEAREST
        img = cv2.resize(img, (meta['square_dim'], meta['square_dim']), interpolation=interp)
        
    # Crop the padding
    pad_top = meta['pad_top']
    pad_bottom = meta['pad_bottom']
    pad_left = meta['pad_left']
    pad_right = meta['pad_right']
    
    h_sq, w_sq = img.shape[:2]
    unpadded = img[pad_top : h_sq - pad_bottom, pad_left : w_sq - pad_right]
    
    return unpadded
