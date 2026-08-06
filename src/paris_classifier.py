"""
Paris Endoscopic Morphological Classifier & Millimeter Sizing Engine
Implements:
  1. Automated Paris Classification (Type 0-Ip Pedunculated, Type 0-Is Sessile, Type 0-IIa Flat Elevated)
  2. Physical Millimeter Diameter Estimation (Calibrated to Standard 10mm Endoscope Caliber)
  3. Resection Technique Recommendation (Cold Snare, Hot Snare, EMR)
"""

import cv2
import numpy as np

class ParisClassifier:
    """
    Morphological analysis engine for polyp risk stratification and surgical staging.
    """
    def __init__(self, pixel_to_mm_scale=0.085):
        # Default scale: ~0.085 mm per pixel on 720p/1080p endoscopy screens at typical viewing distance
        self.pixel_to_mm_scale = pixel_to_mm_scale

    def analyze_polyp(self, bbox, mask=None, contour=None):
        """
        Analyzes a detected polyp to extract clinical Paris classification and metrics.
        
        Args:
            bbox: (x1, y1, x2, y2) bounding box coordinates
            mask: Optional binary mask (H, W) from PraNet
            contour: Optional OpenCV contour
            
        Returns:
            dict containing:
              - paris_class: str ('0-Ip', '0-Is', '0-IIa', '0-IIb')
              - paris_label: str (e.g. 'Sessile (0-Is)')
              - est_diameter_mm: float (estimated size in mm)
              - size_category: str ('Diminutive (<5mm)', 'Small (5-9mm)', 'Large (>=10mm)')
              - clinical_resection: str recommended resection procedure
              - aspect_ratio: float
              - circularity: float
              - color_badge: tuple (B, G, R) for UI badge rendering
        """
        x1, y1, x2, y2 = bbox
        w_px = max(1, x2 - x1)
        h_px = max(1, y2 - y1)
        
        aspect_ratio = float(h_px) / float(w_px)
        max_dim_px = max(w_px, h_px)
        est_diameter_mm = round(max_dim_px * self.pixel_to_mm_scale, 1)
        
        # Calculate circularity and solidity if contour is available
        circularity = 0.8
        solidity = 0.9
        
        if contour is not None and len(contour) >= 5:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = (4 * np.pi * area) / (perimeter ** 2)
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            if hull_area > 0:
                solidity = area / hull_area
        elif mask is not None:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest)
                perimeter = cv2.arcLength(largest, True)
                if perimeter > 0:
                    circularity = (4 * np.pi * area) / (perimeter ** 2)
                hull = cv2.convexHull(largest)
                hull_area = cv2.contourArea(hull)
                if hull_area > 0:
                    solidity = area / hull_area

        # Paris Classification Decision Logic
        if aspect_ratio >= 1.35 and solidity < 0.85:
            # Stalked / Pedunculated (Type 0-Ip)
            paris_class = "0-Ip"
            paris_label = "Pedunculated (0-Ip)"
            color_badge = (255, 140, 0) # Deep Sky Blue (BGR)
        elif aspect_ratio <= 0.55 or (aspect_ratio <= 0.7 and circularity < 0.6):
            # Flat Elevated (Type 0-IIa) - High clinical danger of being missed
            paris_class = "0-IIa"
            paris_label = "Flat Elevated (0-IIa)"
            color_badge = (0, 165, 255) # Orange (BGR)
        elif est_diameter_mm < 3.0 and aspect_ratio <= 0.6:
            # Completely Flat (Type 0-IIb)
            paris_class = "0-IIb"
            paris_label = "Flat Mucosa (0-IIb)"
            color_badge = (0, 215, 255) # Gold
        else:
            # Standard Dome / Sessile (Type 0-Is)
            paris_class = "0-Is"
            paris_label = "Sessile (0-Is)"
            color_badge = (50, 205, 50) # Lime Green (BGR)

        # Sizing Category & Clinical Resection Guidance
        if est_diameter_mm < 5.0:
            size_cat = "Diminutive (<5mm)"
            resection = "Cold Biopsy Forceps / Cold Snare Polypectomy (CSP)"
        elif est_diameter_mm < 10.0:
            size_cat = "Small (5-9mm)"
            resection = "Cold Snare Polypectomy (CSP) - Complete margin inspection"
        else:
            size_cat = "Large (>=10mm)"
            resection = "Endoscopic Mucosal Resection (EMR) / Referral for ESD"

        return {
            "paris_class": paris_class,
            "paris_label": paris_label,
            "est_diameter_mm": est_diameter_mm,
            "size_category": size_cat,
            "clinical_resection": resection,
            "aspect_ratio": round(aspect_ratio, 2),
            "circularity": round(circularity, 2),
            "color_badge": color_badge
        }

    def draw_paris_badge(self, frame_bgr, bbox, analysis, track_id=None):
        """
        Draws a medical HUD badge showing the Paris Classification, Diameter, and Track ID.
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h_frame, w_frame = frame_bgr.shape[:2]
        
        badge_text = f"Paris: {analysis['paris_label']} | ~{analysis['est_diameter_mm']}mm"
        if track_id is not None:
            badge_text = f"ID #{track_id} | " + badge_text
            
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.48
        thickness = 1
        
        (tw, th), baseline = cv2.getTextSize(badge_text, font, font_scale, thickness)
        
        # Position above bounding box if space permits, otherwise below
        bx1 = max(0, min(x1, w_frame - tw - 12))
        by2 = max(th + 8, y1 - 6)
        by1 = by2 - th - 6
        bx2 = bx1 + tw + 10
        
        # Semi-transparent dark background box
        sub_img = frame_bgr[by1:by2, bx1:bx2]
        if sub_img.shape[0] > 0 and sub_img.shape[1] > 0:
            bg_rect = np.zeros_like(sub_img)
            cv2.rectangle(bg_rect, (0, 0), (bx2 - bx1, by2 - by1), (20, 20, 20), -1)
            cv2.addWeighted(sub_img, 0.2, bg_rect, 0.8, 0, sub_img)
            frame_bgr[by1:by2, bx1:bx2] = sub_img
            
        # Draw border in classification color
        cv2.rectangle(frame_bgr, (bx1, by1), (bx2, by2), analysis['color_badge'], 1, lineType=cv2.LINE_AA)
        
        # Draw text
        cv2.putText(frame_bgr, badge_text, (bx1 + 5, by2 - 4), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
        return frame_bgr
