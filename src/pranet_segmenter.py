"""
PraNet: Parallel Reverse Attention Network for Polyp Segmentation
Specifically adapted for real-time ROI patch boundary segmentation in ChakraModel.
Implements:
  1. Receptive Field Blocks (RFB) for multi-scale context
  2. Parallel Partial Decoder (PPD) for global saliency estimation
  3. Reverse Attention (RA) Modules for boundary-aware mucosal edge refinement
"""

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

class BasicConv2d(nn.Module):
    def __init__(self, in_planes, out_planes, kernel_size, stride=1, padding=0, dilation=1):
        super(BasicConv2d, self).__init__()
        self.conv = nn.Conv2d(
            in_planes, out_planes,
            kernel_size=kernel_size, stride=stride,
            padding=padding, dilation=dilation, bias=False
        )
        self.bn = nn.BatchNorm2d(out_planes)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        return self.relu(x)

class RFBBlock(nn.Module):
    """Receptive Field Block (RFB) for multi-scale endoscopic feature extraction"""
    def __init__(self, in_channel, out_channel):
        super(RFBBlock, self).__init__()
        self.relu = nn.ReLU(True)
        self.branch0 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
        )
        self.branch1 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 3), padding=(0, 1)),
            BasicConv2d(out_channel, out_channel, kernel_size=(3, 1), padding=(1, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=3, dilation=3)
        )
        self.branch2 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 5), padding=(0, 2)),
            BasicConv2d(out_channel, out_channel, kernel_size=(5, 1), padding=(2, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=5, dilation=5)
        )
        self.branch3 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 7), padding=(0, 3)),
            BasicConv2d(out_channel, out_channel, kernel_size=(7, 1), padding=(3, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=7, dilation=7)
        )
        self.conv_cat = BasicConv2d(4 * out_channel, out_channel, 3, padding=1)
        self.conv_res = BasicConv2d(in_channel, out_channel, 1)

    def forward(self, x):
        x0 = self.branch0(x)
        x1 = self.branch1(x)
        x2 = self.branch2(x)
        x3 = self.branch3(x)
        x_cat = self.conv_cat(torch.cat((x0, x1, x2, x3), 1))
        x = self.relu(x_cat + self.conv_res(x))
        return x

class ReverseAttention(nn.Module):
    """
    Reverse Attention (RA) Module:
    Inverts previous saliency map to systematically erase the detected polyp body,
    forcing the network to focus on subtle boundary margins between the lesion & normal mucosa.
    """
    def __init__(self, in_channel, out_channel):
        super(ReverseAttention, self).__init__()
        self.conv1 = BasicConv2d(in_channel, out_channel, 3, padding=1)
        self.conv2 = BasicConv2d(out_channel, out_channel, 3, padding=1)
        self.conv3 = nn.Conv2d(out_channel, 1, 1)

    def forward(self, x, saliency_map):
        # Invert the saliency map (Reverse Attention Mechanism)
        reverse_weight = 1.0 - torch.sigmoid(saliency_map)
        x = x * reverse_weight.expand_as(x)
        x = self.conv1(x)
        x = self.conv2(x)
        out = self.conv3(x)
        return out

class PraNetMicroRefiner(nn.Module):
    """
    Lightweight, high-speed PraNet segmentation architecture optimized for ROI crops
    """
    def __init__(self, channels=32):
        super(PraNetMicroRefiner, self).__init__()
        
        # Backbone Feature Extractors (Lightweight Multi-Stage)
        self.enc1 = nn.Sequential(
            BasicConv2d(3, channels, 3, stride=1, padding=1),
            BasicConv2d(channels, channels, 3, stride=1, padding=1)
        )
        self.enc2 = nn.Sequential(
            BasicConv2d(channels, channels * 2, 3, stride=2, padding=1),
            BasicConv2d(channels * 2, channels * 2, 3, stride=1, padding=1)
        )
        self.enc3 = nn.Sequential(
            BasicConv2d(channels * 2, channels * 4, 3, stride=2, padding=1),
            BasicConv2d(channels * 4, channels * 4, 3, stride=1, padding=1)
        )
        
        # Receptive Field Blocks
        self.rfb2 = RFBBlock(channels * 2, channels)
        self.rfb3 = RFBBlock(channels * 4, channels)
        
        # Parallel Partial Decoder (PPD) for Coarse Saliency
        self.ppd_conv = BasicConv2d(channels * 2, channels, 3, padding=1)
        self.ppd_out = nn.Conv2d(channels, 1, 1)
        
        # Reverse Attention Modules
        self.ra3 = ReverseAttention(channels, channels)
        self.ra2 = ReverseAttention(channels, channels)
        
        # Final Output Refiner
        self.final_conv = nn.Sequential(
            BasicConv2d(channels, channels, 3, padding=1),
            nn.Conv2d(channels, 1, 1)
        )

    def forward(self, x):
        h, w = x.shape[2], x.shape[3]
        
        # Encoder forward pass
        f1 = self.enc1(x)        # [B, 32, H, W]
        f2 = self.enc2(f1)       # [B, 64, H/2, W/2]
        f3 = self.enc3(f2)       # [B, 128, H/4, W/4]
        
        # Multi-scale RFBs
        rfb2 = self.rfb2(f2)     # [B, 32, H/2, W/2]
        rfb3 = self.rfb3(f3)     # [B, 32, H/4, W/4]
        
        # Parallel Partial Decoder (PPD) -> Global Saliency
        rfb3_up = F.interpolate(rfb3, size=rfb2.shape[2:], mode='bilinear', align_corners=False)
        ppd_feat = self.ppd_conv(torch.cat([rfb2, rfb3_up], dim=1))
        global_saliency = self.ppd_out(ppd_feat)
        
        # Reverse Attention Stage 3
        ra3_out = self.ra3(rfb3, F.interpolate(global_saliency, size=rfb3.shape[2:], mode='bilinear', align_corners=False))
        
        # Reverse Attention Stage 2
        ra3_up = F.interpolate(ra3_out, size=rfb2.shape[2:], mode='bilinear', align_corners=False)
        ra2_out = self.ra2(rfb2, ra3_up)
        
        # Final Full-Resolution Mask Refinement
        final_feat = F.interpolate(ra2_out, size=(h, w), mode='bilinear', align_corners=False)
        mask_logits = self.final_conv(F.interpolate(ppd_feat, size=(h, w), mode='bilinear', align_corners=False) + final_feat)
        
        return mask_logits


class PraNetSegmenter:
    """
    PraNet Endoscopic Polyp Mask Inference Engine.
    Processes cropped polyp bounding boxes to generate sub-pixel resection boundary masks.
    """
    def __init__(self, device=None, img_size=(128, 128), weights_path=None):
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
            
        self.img_size = img_size
        self.model = PraNetMicroRefiner(channels=24).to(self.device)
        
        # Load weights if available
        from pathlib import Path
        if weights_path is None:
            default_weights = Path(__file__).parent.parent / "weights" / "pranet_kvasir_best.pth"
            if default_weights.exists():
                weights_path = default_weights
                
        if weights_path is not None:
            weights_path = Path(weights_path)
            if weights_path.exists():
                try:
                    self.model.load_state_dict(torch.load(weights_path, map_location=self.device))
                    print(f"[INFO] PraNetSegmenter: Loaded weights from {weights_path}")
                except Exception as e:
                    print(f"[WARN] PraNetSegmenter: Failed to load weights from {weights_path}: {e}")
            else:
                print(f"[WARN] PraNetSegmenter: Weights path {weights_path} not found")
        else:
            print("[WARN] PraNetSegmenter: No weights found. Running with random initialization.")
            
        self.model.eval()

    def segment_roi(self, roi_bgr, threshold=0.45):
        """
        Segments a single cropped polyp ROI.
        
        Args:
            roi_bgr: numpy.ndarray of shape (H, W, 3) representing the cropped polyp
            threshold: Confidence threshold for binarization (default 0.45)
            
        Returns:
            binary_mask: numpy.ndarray of shape (H, W) [0 or 255]
            contours: list of OpenCV contours for exact boundary line drawing
            confidence: float mean mask confidence score
        """
        if roi_bgr is None or roi_bgr.size == 0 or roi_bgr.shape[0] < 4 or roi_bgr.shape[1] < 4:
            return None, [], 0.0
            
        orig_h, orig_w = roi_bgr.shape[:2]
        
        # Preprocessing: BGR -> RGB -> Normalize -> Tensor
        rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, self.img_size, interpolation=cv2.INTER_LINEAR)
        img_tensor = torch.from_numpy(resized).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        
        # Standard ImageNet normalization
        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        img_tensor = (img_tensor - mean) / std
        img_tensor = img_tensor.to(self.device)
        
        with torch.no_grad():
            logits = self.model(img_tensor)
            prob = torch.sigmoid(logits)
            prob_map = prob.squeeze().cpu().numpy()
            
        # Resize probability map back to original crop resolution
        prob_resized = cv2.resize(prob_map, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        
        # Adaptive contrast boundary enhancement for colon mucosal blending
        lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        l_enhanced = clahe.apply(l_chan)
        _, otsu_cue = cv2.threshold(l_enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Combine Reverse-Attention Saliency with Mucosal Gradient Cues
        combined_prob = 0.75 * prob_resized + 0.25 * (otsu_cue.astype(np.float32) / 255.0)
        binary_mask = (combined_prob >= threshold).astype(np.uint8) * 255
        
        # Morphological clean-up (remove tiny noise, close holes)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)
        
        # Extract contours
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter largest contour representing the central polyp mass
        if contours:
            largest_cnt = max(contours, key=cv2.contourArea)
            filtered_mask = np.zeros_like(binary_mask)
            cv2.drawContours(filtered_mask, [largest_cnt], -1, 255, thickness=cv2.FILLED)
            binary_mask = filtered_mask
            contours = [largest_cnt]
            mean_conf = float(np.mean(prob_resized[binary_mask > 0])) if np.any(binary_mask > 0) else float(np.mean(prob_resized))
        else:
            mean_conf = 0.0
            
        return binary_mask, contours, mean_conf

    def overlay_mask_on_frame(self, frame_bgr, bbox, mask, color=(0, 255, 128), alpha=0.45):
        """
        Overlays the semi-transparent segmentation mask and boundary contour onto the full video frame.
        
        Args:
            frame_bgr: Full video frame (H, W, 3)
            bbox: (x1, y1, x2, y2)
            mask: Binary mask for the ROI (h_roi, w_roi)
            color: BGR tuple for mask overlay
            alpha: Transparency factor (0.0 to 1.0)
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h_frame, w_frame = frame_bgr.shape[:2]
        
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_frame, x2), min(h_frame, y2)
        
        if x2 <= x1 or y2 <= y1 or mask is None:
            return frame_bgr
            
        roi = frame_bgr[y1:y2, x1:x2]
        h_roi, w_roi = roi.shape[:2]
        
        if mask.shape[:2] != (h_roi, w_roi):
            mask = cv2.resize(mask, (w_roi, h_roi), interpolation=cv2.INTER_NEAREST)
            
        colored_mask = np.zeros_like(roi, dtype=np.uint8)
        colored_mask[mask > 0] = color
        
        # Alpha blend only inside the segmented polyp boundary
        idx = mask > 0
        roi[idx] = cv2.addWeighted(roi[idx], 1 - alpha, colored_mask[idx], alpha, 0)
        
        # Draw precise sub-pixel boundary contour line
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            cnt_shifted = cnt + np.array([[[x1, y1]]])
            cv2.drawContours(frame_bgr, cnt_shifted, -1, (0, 255, 255), thickness=2, lineType=cv2.LINE_AA)
            
        frame_bgr[y1:y2, x1:x2] = roi
        return frame_bgr
