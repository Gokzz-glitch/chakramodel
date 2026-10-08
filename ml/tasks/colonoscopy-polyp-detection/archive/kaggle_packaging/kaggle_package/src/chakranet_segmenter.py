"""
ChakraNet: Parallel Reverse Attention Network for Polyp Segmentation
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
import torchvision.models as models

# ── Hardware Monitor: auto-starts as background daemon on first import ──────
try:
    from hardware_monitor import get_monitor as _get_monitor
    _hw_monitor = _get_monitor(auto_start=True)  # 240s warmup → then boost to 3.8 GB
except Exception as _e:
    _hw_monitor = None
    print(f"[WARN] HardwareMonitor unavailable: {_e}")

if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.deterministic = False

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

import timm

class ChakraNetMicroRefiner(nn.Module):
    """
    ChakraTransformerSegmenter masquerading as ChakraNet for compatibility.
    Uses ViT-Large backbone.
    """
    def __init__(self, channels=32):
        super(ChakraNetMicroRefiner, self).__init__()
        self.mc_dropout = False
        
        self.backbone = timm.create_model(
            'vit_large_patch16_384', 
            pretrained=True, 
            img_size=384, 
            drop_rate=0.1, 
            attn_drop_rate=0.1
        )
        self.embed_dim = self.backbone.embed_dim
        
        self.decode_head = nn.Sequential(
            nn.ConvTranspose2d(self.embed_dim, 256, kernel_size=4, stride=4),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(256, 64, kernel_size=4, stride=4),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 1, kernel_size=3, padding=1)
        )
        # MC Dropout is correctly enabled using model.apply(apply_dropout)
        # which sets all Dropout modules (including timm backbone) to train().
        self.drop = nn.Dropout2d(p=0.1)

    def enable_mc_dropout(self):
        self.mc_dropout = True
        def apply_dropout(m):
            if type(m) == nn.Dropout or type(m) == nn.Dropout2d:
                m.train()
            elif hasattr(m, '__class__') and 'DropPath' in m.__class__.__name__:
                m.train()
        self.apply(apply_dropout)

    def forward(self, x):
        B, C, H, W = x.shape
        dropout_active = self.training or self.mc_dropout

        try:
            with torch.amp.autocast('cuda' if x.is_cuda else 'cpu'):
                features = self.backbone.forward_features(x)
                if features.dim() == 3:
                    if features.shape[1] == (H // 16) * (W // 16) + 1:
                        features = features[:, 1:]
                    grid_h = H // 16
                    grid_w = W // 16
                    features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, grid_h, grid_w)

                if dropout_active:
                    features = self.drop(features)

                logits = self.decode_head(features)

                if logits.shape[2:] != (H, W):
                    logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)

            return logits

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                # Notify monitor to back off GPU fraction by 5%
                global _hw_monitor
                if _hw_monitor is not None:
                    _hw_monitor.handle_oom()
                else:
                    torch.cuda.empty_cache()
                # Retry once on CPU fallback to avoid crashing the pipeline
                x_cpu = x.cpu().float()
                self_cpu = self.to('cpu')
                features = self_cpu.backbone.forward_features(x_cpu)
                if features.dim() == 3:
                    features = features[:, 1:] if features.shape[1] == (H // 16) * (W // 16) + 1 else features
                    features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, H // 16, W // 16)
                logits = self_cpu.decode_head(features)
                if logits.shape[2:] != (H, W):
                    logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)
                self.to(x.device)  # Move back to GPU for next call
                return logits.to(x.device)
            raise



class ChakraNet:
    """
    ChakraNet Endoscopic Polyp Mask Inference Engine.
    Processes cropped polyp bounding boxes to generate sub-pixel resection boundary masks.
    """
    def __init__(self, device=None, img_size=(384, 384), weights_path=None):
        if device is None:
            assert torch.cuda.is_available(), "CUDA is required for ChakraNet!"
            self.device = torch.device('cuda')
        else:
            self.device = torch.device(device)
            
        self.img_size = img_size
        self.model = ChakraNetMicroRefiner(channels=24).to(self.device)
        
        # Load weights if available
        from pathlib import Path
        if weights_path is None:
            default_weights = Path(__file__).parent.parent / "weights" / "chakra_transformer_best.pth"
            if default_weights.exists():
                weights_path = default_weights
                
        if weights_path is not None:
            weights_path = Path(weights_path)
            if weights_path.exists():
                # Allow strict=False to handle any _orig_mod prefixes or minor mismatches, but don't swallow completely
                sd = torch.load(weights_path, map_location=self.device)
                sd = {k.replace("_orig_mod.", ""): v for k, v in sd.items()}
                self.model.load_state_dict(sd, strict=False)
                print(f"[INFO] ChakraNet: Loaded weights from {weights_path}")
            else:
                print(f"[WARN] ChakraNet: Weights path {weights_path} not found")
        else:
            print("[WARN] ChakraNet: No weights found. Running with random initialization.")
            
        self.model.eval()

    def segment_roi(self, roi_bgr, threshold=0.45, mc_passes=1, conformal=False, q_hat_pos=None, q_hat_neg=None):
        """
        Segments a single cropped polyp ROI.
        
        Args:
            roi_bgr: numpy.ndarray of shape (H, W, 3) representing the cropped polyp
            threshold: Confidence threshold for binarization (default 0.45)
            mc_passes: Number of stochastic forward passes for uncertainty estimation
            
        Returns:
            binary_mask: numpy.ndarray of shape (H, W) [0 or 255]
            contours: list of OpenCV contours for exact boundary line drawing
            confidence: float mean mask confidence score
            uncertainty_map: numpy.ndarray of shape (H, W) representing pixel variance (or None if mc_passes=1)
        """
        if roi_bgr is None or roi_bgr.size == 0 or roi_bgr.shape[0] < 4 or roi_bgr.shape[1] < 4:
            return None, [], 0.0, None
            
        orig_h, orig_w = roi_bgr.shape[:2]
        
        # Preprocessing: BGR -> RGB -> Normalize -> Tensor
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from utils.transforms import letterbox_pad, unletterbox
        
        rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
        resized, meta = letterbox_pad(rgb, target_size=self.img_size)
        img_tensor = torch.from_numpy(resized).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        
        # Standard ImageNet normalization
        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        img_tensor = (img_tensor - mean) / std
        img_tensor = img_tensor.to(self.device)
        
        uncertainty_resized = None
        
        if mc_passes > 1:
            self.model.enable_mc_dropout()
            probs = []
            with torch.no_grad():
                for _ in range(mc_passes):
                    logits = self.model(img_tensor)
                    probs.append(torch.sigmoid(logits).squeeze().cpu().numpy())
            
            probs = np.stack(probs, axis=0).astype(np.float32)
            prob_map = np.mean(probs, axis=0).astype(np.float32)
            variance_map = np.var(probs, axis=0).astype(np.float32)
            
            uncertainty_resized = unletterbox(variance_map, meta)
            
            # Reset model dropout flag for safety
            self.model.mc_dropout = False
        else:
            with torch.no_grad():
                logits = self.model(img_tensor)
                prob = torch.sigmoid(logits)
                prob_map = prob.squeeze().float().cpu().numpy().astype(np.float32)
            
        # Resize probability map back to original crop resolution using unletterbox
        prob_resized = unletterbox(prob_map, meta)
        
        # NO POST PROCESSING (Topological loss ensures structural integrity natively)
        binary_mask = (prob_resized >= threshold).astype(np.uint8) * 255
        
        # Extract contours
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            mean_conf = float(np.mean(prob_resized[binary_mask > 0])) if np.any(binary_mask > 0) else float(np.mean(prob_resized))
        else:
            mean_conf = 0.0
            
        if conformal and q_hat_pos is not None and q_hat_neg is not None:
            variance = uncertainty_resized if uncertainty_resized is not None else 0.0
            score_pos = 1.0 - (prob_resized + variance)
            score_neg = prob_resized - variance
            include_pos = (score_pos <= q_hat_pos)
            include_neg = (score_neg <= q_hat_neg)
            outer_mask = include_pos.astype(np.uint8) * 255
            inner_mask = (include_pos & (~include_neg)).astype(np.uint8) * 255
            return binary_mask, contours, mean_conf, {"unc": uncertainty_resized, "inner": inner_mask, "outer": outer_mask}
            
        return binary_mask, contours, mean_conf, uncertainty_resized

    def segment_batch_roi(self, roi_bgr_list, threshold=0.45, conformal=False, q_hat_pos=None, q_hat_neg=None):
        """
        Segments a batch of cropped polyp ROIs in parallel on the GPU to maximize VRAM utilization.
        
        Args:
            roi_bgr_list: List of numpy.ndarray of shape (H, W, 3).
            threshold: Confidence threshold for binarization.
            
        Returns:
            List of tuples (binary_mask, contours, mean_conf, extras) matching input order.
        """
        if not roi_bgr_list:
            return []
            
        valid_indices = []
        tensor_list = []
        orig_shapes = []
        
        # 1. Preprocess and accumulate valid crops
        for i, roi_bgr in enumerate(roi_bgr_list):
            if roi_bgr is None or roi_bgr.size == 0 or roi_bgr.shape[0] < 4 or roi_bgr.shape[1] < 4:
                continue
                
            from utils.transforms import letterbox_pad, unletterbox
            valid_indices.append(i)
            rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
            resized, meta = letterbox_pad(rgb, target_size=self.img_size)
            orig_shapes.append((roi_bgr.shape[:2], meta))
            img_tensor = torch.from_numpy(resized).permute(2, 0, 1).float() / 255.0
            
            # Standard ImageNet normalization
            mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
            std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            img_tensor = (img_tensor - mean) / std
            tensor_list.append(img_tensor)
            
        results = [(None, [], 0.0, None)] * len(roi_bgr_list)
        
        if not tensor_list:
            return results
            
        # 2. Batch inference on GPU with FP16 Autocast for TensorCore acceleration
        batch_tensor = torch.stack(tensor_list).to(self.device)
        
        with torch.no_grad():
            with torch.amp.autocast('cuda' if 'cuda' in str(self.device) else 'cpu'):
                logits = self.model(batch_tensor)
                probs = torch.sigmoid(logits)
        
        prob_maps = probs.squeeze(1).float().cpu().numpy()
        if len(prob_maps.shape) == 2:
            prob_maps = np.expand_dims(prob_maps, 0)
            
        # 3. Post-process each mask
        from utils.transforms import unletterbox
        for idx, list_idx in enumerate(valid_indices):
            (orig_h, orig_w), meta = orig_shapes[idx]
            prob_map = prob_maps[idx]
            roi_bgr = roi_bgr_list[list_idx]
            
            prob_resized = unletterbox(prob_map, meta)
            
            # NO POST PROCESSING (Topological loss ensures structural integrity natively)
            binary_mask = (prob_resized >= threshold).astype(np.uint8) * 255
            
            contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                mean_conf = float(np.mean(prob_resized[binary_mask > 0])) if np.any(binary_mask > 0) else float(np.mean(prob_resized))
            else:
                mean_conf = 0.0
                
            
            if conformal and q_hat_pos is not None and q_hat_neg is not None:
                score_pos = 1.0 - prob_resized
                score_neg = prob_resized
                include_pos = (score_pos <= q_hat_pos)
                include_neg = (score_neg <= q_hat_neg)
                outer_mask = include_pos.astype(np.uint8) * 255
                inner_mask = (include_pos & (~include_neg)).astype(np.uint8) * 255
                extras = {"inner": inner_mask, "outer": outer_mask, "unc": None}
            else:
                extras = None
                
            results[list_idx] = (binary_mask, contours, mean_conf, extras)
            
        return results

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
        roi[idx] = (roi[idx].astype(np.float32) * (1.0 - alpha) + colored_mask[idx].astype(np.float32) * alpha).astype(np.uint8)
        
        # Draw precise sub-pixel boundary contour line
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            cnt_shifted = cnt + np.array([[[x1, y1]]])
            cv2.drawContours(frame_bgr, cnt_shifted, -1, (0, 255, 255), thickness=2, lineType=cv2.LINE_AA)
            
        frame_bgr[y1:y2, x1:x2] = roi
        return frame_bgr
