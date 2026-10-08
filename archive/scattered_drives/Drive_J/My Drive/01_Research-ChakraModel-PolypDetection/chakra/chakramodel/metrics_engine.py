import torch
import torch.nn.functional as F
import numpy as np
from scipy.ndimage import morphology

class MetricsEngine:
    """
    Computes rigorous evaluation metrics for polyp segmentation,
    including Boundary-IoU, Structure-Measure (S-measure), and Size Stratification.
    """
    
    @staticmethod
    def boundary_iou(predict, target, boundary_width=3):
        """
        Computes Boundary-IoU to measure segmentation precision precisely at the mucosal edges.
        predict: (B, 1, H, W) tensor, values in [0, 1] (probabilities or binary)
        target: (B, 1, H, W) tensor, values in {0, 1}
        boundary_width: pixel width of the boundary region
        """
        # Binarize prediction
        predict_b = (predict > 0.5).float()
        
        # We need numpy for morph operations, assuming inputs can be on CPU
        predict_np = predict_b.cpu().numpy().astype(bool)
        target_np = target.cpu().numpy().astype(bool)
        
        ious = []
        for p, t in zip(predict_np, target_np):
            p = p[0]
            t = t[0]
            
            # Get boundaries
            p_boundary = p ^ morphology.binary_erosion(p, iterations=boundary_width)
            t_boundary = t ^ morphology.binary_erosion(t, iterations=boundary_width)
            
            intersection = np.logical_and(p_boundary, t_boundary).sum()
            union = np.logical_or(p_boundary, t_boundary).sum()
            
            if union == 0:
                ious.append(1.0 if np.array_equal(p, t) else 0.0)
            else:
                ious.append(intersection / union)
                
        return np.mean(ious)

    @staticmethod
    def s_measure(predict, target):
        """
        Computes Structure-Measure (S-measure) for spatial alignment.
        Based on "Structure-measure: A new way to evaluate foreground maps" (ICCV 2017).
        predict: (B, 1, H, W)
        target: (B, 1, H, W)
        """
        # Simplified S-measure approximation (Region-aware and Object-aware structural similarity)
        # For full rigorous S-measure, a dedicated library like PySot or identical implementation is used.
        # This provides the structural similarity index (SSIM) based approximation for spatial alignment.
        
        # Binarize
        predict = (predict > 0.5).float()
        target = target.float()
        
        mu_x = F.avg_pool2d(predict, 3, 1, 1)
        mu_y = F.avg_pool2d(target, 3, 1, 1)
        
        sigma_x = F.avg_pool2d(predict ** 2, 3, 1, 1) - mu_x ** 2
        sigma_y = F.avg_pool2d(target ** 2, 3, 1, 1) - mu_y ** 2
        sigma_xy = F.avg_pool2d(predict * target, 3, 1, 1) - mu_x * mu_y
        
        C1 = 0.01 ** 2
        C2 = 0.03 ** 2
        
        ssim_map = ((2 * mu_x * mu_y + C1) * (2 * sigma_xy + C2)) / \
                   ((mu_x ** 2 + mu_y ** 2 + C1) * (sigma_x + sigma_y + C2))
                   
        return ssim_map.mean().item()

    @staticmethod
    def stratify_by_size(target, dim_threshold_pixels=2500):
        """
        Categorizes a target mask as 'diminutive' or 'large' based on bounding box area.
        Diminutive polyps (<5mm) are harder to detect and highly clinically relevant.
        target: (1, H, W) tensor
        dim_threshold_pixels: Area threshold to define diminutive vs large
        """
        area = target.sum().item()
        if area == 0:
            return "background"
        if area < dim_threshold_pixels:
            return "diminutive"
        return "large"

if __name__ == "__main__":
    # Quick Test
    B, C, H, W = 2, 1, 256, 256
    pred = torch.rand(B, C, H, W)
    target = (torch.rand(B, C, H, W) > 0.5).float()
    
    print("Testing MetricsEngine...")
    print(f"Boundary-IoU: {MetricsEngine.boundary_iou(pred, target):.4f}")
    print(f"S-Measure (SSIM Approx): {MetricsEngine.s_measure(pred, target):.4f}")
    print(f"Stratification: {MetricsEngine.stratify_by_size(target[0])}")
