import torch
import cv2
import numpy as np
from data_loader import get_dataloaders
from cnn_detector import CNNDetector
from watermark_embed import embed_watermark
from watermark_verify import extract_watermark, calculate_ber

class CulturalPipeline:
    def __init__(self, cnn_ckpt_path):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.detector = CNNDetector(num_classes=5).to(self.device)
        self.detector.load_state_dict(torch.load(cnn_ckpt_path, map_location=self.device, weights_only=True))
        self.detector.eval()
        
    def process_image(self, image_bgr, watermark_bits):
        """
        Runs the full pipeline on a single image.
        """
        # 1. Detection
        # Resize to 64x64 for the CNN
        img_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (64, 64))
        
        # Normalize for CNN: [-1, 1] or [0, 1] - match data_loader
        img_tensor = torch.tensor(img_resized).permute(2, 0, 1).float() / 255.0
        img_tensor = (img_tensor - 0.5) / 0.5
        img_tensor = img_tensor.unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            class_logits, bbox_preds = self.detector(img_tensor)
            _, predicted_class = torch.max(class_logits, 1)
            bbox = bbox_preds[0].cpu().numpy() # [x_min, y_min, x_max, y_max] in [0, 1]
            
        # 2. Watermark Embedding
        watermarked_rgb = embed_watermark(img_rgb, bbox, watermark_bits, alpha=50.0)
        watermarked_bgr = cv2.cvtColor(watermarked_rgb, cv2.COLOR_RGB2BGR)
        
        return watermarked_bgr, bbox, predicted_class.item()
        
    def verify_image(self, watermarked_bgr, bbox, original_watermark_bits):
        """
        Simulates JPEG compression and verifies the watermark.
        """
        # Apply JPEG compression
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
        _, encimg = cv2.imencode('.jpg', watermarked_bgr, encode_param)
        compressed_bgr = cv2.imdecode(encimg, 1)
        compressed_rgb = cv2.cvtColor(compressed_bgr, cv2.COLOR_BGR2RGB)
        
        # Extract and verify
        extracted_bits = extract_watermark(compressed_rgb, bbox, len(original_watermark_bits))
        ber = calculate_ber(original_watermark_bits, extracted_bits)
        
        return compressed_bgr, extracted_bits, ber
